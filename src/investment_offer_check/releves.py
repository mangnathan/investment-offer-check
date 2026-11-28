"""Relevés RDAP et crt.sh d'un domaine : quatre champs seulement.

Une réponse RDAP peut contenir les coordonnées d'une personne physique (titulaire, contact).
Seuls sont extraits la date de création et le nom du bureau d'enregistrement ; de crt.sh, la date
et l'émetteur du premier certificat. La réponse brute n'est jamais écrite, ni sur disque ni dans
un journal, ni dans un message d'erreur.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlsplit

from investment_offer_check.reseau import Client

URL_AMORCAGE = "https://data.iana.org/rdap/dns.json"
URL_CRT = "https://crt.sh/"


@dataclass(frozen=True)
class ReleveRdap:
    statut: str  # « trouvé », « absent », « pas de serveur », « échec <code> », « illisible »
    creation: str | None = None
    bureau: str | None = None


@dataclass(frozen=True)
class ReleveCrt:
    statut: str  # « trouvé », « aucun certificat », « échec <code> », « illisible »
    premier: str | None = None
    emetteur: str | None = None


def lire_amorcage(client: Client) -> dict[str, str]:
    """Extension de domaine → adresse du serveur RDAP (https), d'après le fichier de l'IANA."""
    reponse = client.get("iana", URL_AMORCAGE)
    if reponse.statut != 200:
        raise RuntimeError(f"fichier d'amorçage RDAP : statut {reponse.statut}")
    serveurs: dict[str, str] = {}
    for extensions, adresses in json.loads(reponse.corps)["services"]:
        https = [a for a in adresses if urlsplit(a).scheme == "https"]
        if https:
            for extension in extensions:
                serveurs[extension.lower()] = https[0]
    client.declarer_serveurs_rdap(serveurs.values())
    return serveurs


def _champs_rdap(document: dict[str, Any]) -> tuple[str | None, str | None]:
    creation = next(
        (
            str(e.get("eventDate", ""))[:10] or None
            for e in document.get("events", [])
            if e.get("eventAction") == "registration"
        ),
        None,
    )
    bureau = None
    for entite in document.get("entities", []):
        # Seul le bureau d'enregistrement est lu : jamais le titulaire ni les contacts.
        if "registrar" in entite.get("roles", []):
            for propriete in (entite.get("vcardArray") or [None, []])[1]:
                if propriete and propriete[0] == "fn":
                    bureau = str(propriete[3])
            break
    return creation, bureau


def relever_rdap(client: Client, serveurs: dict[str, str], domaine: str) -> ReleveRdap:
    base = serveurs.get(domaine.rsplit(".", 1)[-1])
    if base is None:
        return ReleveRdap("pas de serveur")
    url = base.rstrip("/") + "/domain/" + quote(domaine)
    reponse = client.get("rdap", url, domaine_recherche=domaine)
    if reponse.statut == 404:
        return ReleveRdap("absent")
    if reponse.statut != 200:
        return ReleveRdap(f"échec {reponse.statut}")
    try:
        creation, bureau = _champs_rdap(json.loads(reponse.corps))
    except (ValueError, TypeError, AttributeError, IndexError):
        return ReleveRdap("illisible")
    return ReleveRdap("trouvé", creation, bureau)


def relever_crt(client: Client, domaine: str) -> ReleveCrt:
    url = URL_CRT + "?q=" + quote(domaine) + "&output=json"
    reponse = client.get("crt", url, domaine_recherche=domaine)
    if reponse.statut != 200:
        return ReleveCrt(f"échec {reponse.statut}")
    try:
        certificats = json.loads(reponse.corps) if reponse.corps.strip() else []
        datees = sorted(
            (str(c["not_before"]), str(c.get("issuer_name") or ""))
            for c in certificats
            if c.get("not_before")
        )
    except (ValueError, TypeError, AttributeError, KeyError):
        return ReleveCrt("illisible")
    if not datees:
        return ReleveCrt("aucun certificat")
    premier, emetteur = datees[0]
    return ReleveCrt("trouvé", premier[:10], emetteur or None)
