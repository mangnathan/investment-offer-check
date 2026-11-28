"""Client réseau de la collecte : https seulement, plafonds, pauses et arrêt au premier refus.

Le client ne garde aucune réponse sur disque : une réponse RDAP peut contenir les coordonnées
d'une personne physique. Les modules appelants n'en extraient que les champs utiles.
"""

from __future__ import annotations

import http.client
import ssl
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlsplit

# Nom de client générique : ni nom de personne ni adresse de contact.
USER_AGENT = "investment-offer-check/0.0 (collecte de donnees publiques)"
DELAI_SECONDES = 30.0
TAILLE_MAX_OCTETS = 20_000_000
REDIRECTIONS_MAX = 5


class AdresseRefuseeError(ValueError):
    """Adresse qui n'est pas en https, ou sans nom d'hôte."""


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


Transport = Callable[[str, Mapping[str, str], float], Reponse]


def verifier_https(url: str) -> None:
    """Refuse toute adresse qui n'est pas en https avec un nom d'hôte."""
    parties = urlsplit(url)
    if parties.scheme != "https" or not parties.hostname:
        raise AdresseRefuseeError(f"adresse refusée, https obligatoire : {url!r}")


def transport_https(url: str, entetes: Mapping[str, str], delai: float) -> Reponse:
    """GET en https avec vérification du certificat et du nom d'hôte, redirections en https."""
    contexte = ssl.create_default_context()
    for _ in range(REDIRECTIONS_MAX + 1):
        verifier_https(url)
        parties = urlsplit(url)
        chemin = parties.path or "/"
        if parties.query:
            chemin += "?" + parties.query
        connexion = http.client.HTTPSConnection(
            parties.hostname or "", parties.port, timeout=delai, context=contexte
        )
        try:
            connexion.request("GET", chemin, headers=dict(entetes))
            reponse = connexion.getresponse()
            if reponse.status in (301, 302, 303, 307, 308):
                cible = reponse.getheader("Location")
                if not cible:
                    return Reponse(reponse.status, b"")
                url = urljoin(url, cible)
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
    appels: dict[str, int] = field(default_factory=dict)
    arrete: bool = False
    _dernier: dict[str, float] = field(default_factory=dict)

    def get(self, source: str, url: str) -> Reponse:
        verifier_https(url)
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
            reponse = self.transport(url, {"User-Agent": USER_AGENT}, self.delai)
        finally:
            self._dernier[source] = self.horloge()
        if reponse.statut == 429:
            self.arrete = True
            raise RefusDeQuotaError(f"{source} : 429 sur {url}")
        return reponse
