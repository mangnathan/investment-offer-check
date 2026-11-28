"""Client réseau de la collecte : https seulement, hôtes fermés, plafonds, pauses, arrêt au 429.

Règle de sécurité : l'outil ne visite jamais un lien, ni le site d'une entité ni un lien
raccourci. Les appels portent sur un domaine (RDAP, crt.sh), jamais vers lui. Seuls les hôtes
de HOTES_FIXES et les serveurs RDAP publiés dans le fichier d'amorçage de l'IANA sont
joignables, et jamais le domaine recherché ni l'un de ses sous-domaines.

Le client ne garde aucune réponse sur disque : une réponse RDAP peut contenir les coordonnées
d'une personne physique. Les modules appelants n'en extraient que les champs utiles.
"""

from __future__ import annotations

import http.client
import ssl
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlsplit

# Nom de client générique : ni nom de personne ni adresse de contact.
USER_AGENT = "investment-offer-check/0.0 (collecte de donnees publiques)"
DELAI_SECONDES = 30.0
TAILLE_MAX_OCTETS = 20_000_000
REDIRECTIONS_MAX = 5

# Liste fermée. Ajouter un hôte demande un commit et la mise à jour du test qui la fige.
HOTES_FIXES = frozenset(
    {
        "www.data.gouv.fr",  # métadonnées et lien permanent de la liste de l'AMF
        "amf.s3.sbg.io.cloud.ovh.net",  # stockage du fichier de l'AMF, cible du lien permanent
        "data.iana.org",  # fichier d'amorçage RDAP
        "crt.sh",  # journal public des certificats
    }
)


class AdresseRefuseeError(ValueError):
    """Adresse qui n'est pas en https, ou sans nom d'hôte."""


class HoteRefuseError(AdresseRefuseeError):
    """Hôte absent de la liste fermée, ou domaine recherché lui-même."""


class RedirectionRefuseeError(HoteRefuseError):
    """Redirection vers un hôte non autorisé : refusée, comptée, jamais suivie."""


class RefusDeQuotaError(RuntimeError):
    """Le serveur a répondu 429 : la collecte s'arrête pour toutes les sources."""


class PlafondAtteintError(RuntimeError):
    """Le plafond d'appels de la source est atteint pour cette exécution."""


class ReponseTropGrosseError(RuntimeError):
    """Le corps de la réponse dépasse la taille maximale acceptée."""


class SourceNonDeclareeError(ValueError):
    """Source appelée sans plafond ou sans pause déclarés."""


@dataclass(frozen=True)
class Reponse:
    statut: int
    corps: bytes


Autorisation = Callable[[str], bool]
Transport = Callable[[str, Mapping[str, str], float, Autorisation], Reponse]


def verifier_https(url: str) -> None:
    """Refuse toute adresse qui n'est pas en https avec un nom d'hôte."""
    parties = urlsplit(url)
    if parties.scheme != "https" or not parties.hostname:
        raise AdresseRefuseeError(f"adresse refusée, https obligatoire : {url!r}")


def hote(url: str) -> str:
    verifier_https(url)
    return urlsplit(url).hostname or ""


def transport_https(
    url: str, entetes: Mapping[str, str], delai: float, autorise: Autorisation
) -> Reponse:
    """GET en https, certificat et nom d'hôte vérifiés ; chaque redirection est contrôlée."""
    contexte = ssl.create_default_context()
    for etape in range(REDIRECTIONS_MAX + 1):
        cible = hote(url)
        if not autorise(cible):
            erreur = RedirectionRefuseeError if etape else HoteRefuseError
            raise erreur(f"hôte non autorisé : {cible}")
        parties = urlsplit(url)
        chemin = parties.path or "/"
        if parties.query:
            chemin += "?" + parties.query
        connexion = http.client.HTTPSConnection(
            cible, parties.port, timeout=delai, context=contexte
        )
        try:
            connexion.request("GET", chemin, headers=dict(entetes))
            reponse = connexion.getresponse()
            if reponse.status in (301, 302, 303, 307, 308):
                location = reponse.getheader("Location")
                if not location:
                    return Reponse(reponse.status, b"")
                url = urljoin(url, location)
                continue
            corps = reponse.read(TAILLE_MAX_OCTETS + 1)
            if len(corps) > TAILLE_MAX_OCTETS:
                raise ReponseTropGrosseError(url)
            return Reponse(reponse.status, corps)
        finally:
            connexion.close()
    raise AdresseRefuseeError(f"trop de redirections : {url!r}")


@dataclass
class Client:
    """Appels comptés par source, avec plafond, pause minimale et arrêt au premier 429."""

    plafonds: Mapping[str, int]
    pauses: Mapping[str, float]
    transport: Transport = transport_https
    delai: float = DELAI_SECONDES
    attendre: Callable[[float], None] = time.sleep
    horloge: Callable[[], float] = time.monotonic
    hotes_fixes: frozenset[str] = HOTES_FIXES
    serveurs_rdap: set[str] = field(default_factory=set)
    appels: dict[str, int] = field(default_factory=dict)
    redirections_refusees: dict[str, int] = field(default_factory=dict)
    arrete: bool = False
    _dernier: dict[str, float] = field(default_factory=dict)

    def declarer_serveurs_rdap(self, urls: Iterable[str]) -> None:
        """Serveurs RDAP publiés par le fichier d'amorçage de l'IANA : seuls ajouts permis."""
        for url in urls:
            self.serveurs_rdap.add(hote(url))

    def _autorisation(self, domaine_recherche: str | None) -> Autorisation:
        def autorise(cible: str) -> bool:
            if domaine_recherche and (
                cible == domaine_recherche or cible.endswith("." + domaine_recherche)
            ):
                return False
            return cible in self.hotes_fixes or cible in self.serveurs_rdap

        return autorise

    def get(self, source: str, url: str, domaine_recherche: str | None = None) -> Reponse:
        """GET compté ; domaine_recherche est le domaine sur lequel porte l'appel."""
        autorise = self._autorisation(domaine_recherche)
        cible = hote(url)
        if not autorise(cible):
            raise HoteRefuseError(f"hôte non autorisé : {cible}")
        if self.arrete:
            raise RefusDeQuotaError("collecte arrêtée après un refus de quota")
        # Une pause de 0 est permise, mais elle doit être écrite : un oubli ne passe pas.
        if source not in self.plafonds or source not in self.pauses:
            raise SourceNonDeclareeError(f"source sans plafond ou sans pause déclarés : {source}")
        if self.appels.get(source, 0) >= self.plafonds[source]:
            raise PlafondAtteintError(source)
        dernier = self._dernier.get(source)
        if dernier is not None:
            reste = self.pauses[source] - (self.horloge() - dernier)
            if reste > 0:
                self.attendre(reste)
        self.appels[source] = self.appels.get(source, 0) + 1
        try:
            reponse = self.transport(url, {"User-Agent": USER_AGENT}, self.delai, autorise)
        except RedirectionRefuseeError:
            self.redirections_refusees[source] = self.redirections_refusees.get(source, 0) + 1
            raise
        finally:
            self._dernier[source] = self.horloge()
        if reponse.statut == 429:
            self.arrete = True
            raise RefusDeQuotaError(f"{source} : 429 sur {url}")
        return reponse
