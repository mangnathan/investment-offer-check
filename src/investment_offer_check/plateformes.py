"""Identité d'un nom : domaine de l'entité, ou plateforme partagée qui ne la désigne pas.

Les listes sont dans plateformes.toml. Un nom sur une plateforme partagée n'est jamais envoyé
à RDAP ni à crt.sh : interroger gmail.com ou facebook.com n'apprend rien sur l'entité.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from enum import StrEnum
from functools import cache
from importlib.resources import files

from investment_offer_check.noms import NomInvalideError, liste_des_suffixes, normaliser_hote

LIEN_RACCOURCI = "lien raccourci, cible non vérifiée"
_SCHEMA = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")


class Genre(StrEnum):
    DOMAINE = "domaine"  # domaine propre à l'entité : RDAP et crt.sh possibles
    MESSAGERIE = "messagerie"  # adresse chez un fournisseur public de courriel
    PLATEFORME = "plateforme"  # page sur un réseau social, un agenda, un formulaire...
    HEBERGEUR = "hebergeur"  # sous-domaine d'un hébergeur absent de la liste des suffixes


@dataclass(frozen=True)
class Identite:
    genre: Genre
    nom: str  # domaine enregistrable, fournisseur, plateforme ou hôte complet
    chemin: str | None = None
    chemin_retire: bool = False
    mention: str | None = None

    @property
    def interrogeable(self) -> bool:
        """Seul un domaine propre à l'entité est envoyé à RDAP et à crt.sh."""
        return self.genre is Genre.DOMAINE


@dataclass(frozen=True)
class Plateformes:
    version: str
    messageries: frozenset[str]
    plateformes_a_chemin: frozenset[str]
    chemin_garde: frozenset[str]
    raccourcisseurs: frozenset[str]
    hebergeurs: frozenset[str]


@cache
def plateformes() -> Plateformes:
    fichier = files("investment_offer_check") / "plateformes.toml"
    d = tomllib.loads(fichier.read_text(encoding="utf-8"))
    return Plateformes(
        version=d["version"],
        messageries=frozenset(d["messageries"]),
        plateformes_a_chemin=frozenset(d["plateformes_a_chemin"]),
        chemin_garde=frozenset(d["chemin_garde"]),
        raccourcisseurs=frozenset(d["raccourcisseurs"]),
        hebergeurs=frozenset(d["hebergeurs"]),
    )


def _chemin(texte: str) -> str | None:
    """Chemin d'une adresse web, sans requête ni fragment ; None s'il est vide."""
    reste = _SCHEMA.sub("", texte.strip())
    _, barre, chemin = reste.partition("/")
    chemin = re.split(r"[?#]", chemin, maxsplit=1)[0].strip("/")
    return chemin if barre and chemin else None


def _sur(hote: str, liste: frozenset[str]) -> str | None:
    """Élément de la liste égal à l'hôte ou dont l'hôte est un sous-domaine."""
    morceaux = hote.split(".")
    for i in range(len(morceaux) - 1):
        candidat = ".".join(morceaux[i:])
        if candidat in liste:
            return candidat
    return None


def identifier(texte: str, courriel: bool = False) -> Identite:
    """Identité d'un site ou d'une adresse de courriel ; NomInvalideError si impossible."""
    p = plateformes()
    hote = normaliser_hote(texte)
    if courriel and (fournisseur := _sur(hote, p.messageries)) is not None:
        return Identite(Genre.MESSAGERIE, fournisseur)
    if courriel:
        texte = hote  # une adresse de courriel n'a pas de chemin
    if (plateforme := _sur(hote, p.plateformes_a_chemin)) is not None:
        chemin = _chemin(texte)
        garde = plateforme in p.chemin_garde
        return Identite(
            Genre.PLATEFORME,
            plateforme,
            chemin=chemin if garde else None,
            chemin_retire=bool(chemin) and not garde,
            mention=LIEN_RACCOURCI if plateforme in p.raccourcisseurs else None,
        )
    if _sur(hote, p.hebergeurs) is not None:
        return Identite(Genre.HEBERGEUR, hote, chemin_retire=_chemin(texte) is not None)
    domaine = liste_des_suffixes().domaine_enregistrable(hote)
    if domaine is None:
        raise NomInvalideError("suffixe public seul", texte)
    return Identite(Genre.DOMAINE, domaine)
