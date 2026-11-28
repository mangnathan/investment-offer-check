"""Normalisation des noms d'hôte et domaine enregistrable.

Un nom est mis en minuscules, débarrassé du schéma, du chemin, du port, de « www. » et du point
final, puis converti en punycode. Le codec idna de la bibliothèque standard suit la norme
IDNA 2003 : il transforme par exemple « ß » en « ss », là où IDNA 2008 le garde. L'écart ne
touche que quelques caractères rares dans les noms visés ; il est accepté et testé.

Le domaine enregistrable est le suffixe public plus un morceau, d'après la liste publique des
suffixes (dossier suffixes/, voir PROVENANCE.md), parties ICANN et privée comprises.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cache
from importlib.resources import files

_SCHEMA = re.compile(r"^[a-z][a-z0-9+.-]*://")
_MORCEAU = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")


class NomInvalideError(ValueError):
    """Nom impossible à normaliser ; le motif est gardé pour le bilan."""

    def __init__(self, motif: str, nom: str) -> None:
        super().__init__(f"{motif} : {nom!r}")
        self.motif = motif
        self.nom = nom


def _en_punycode(morceau: str, nom: str) -> str:
    if morceau.isascii():
        return morceau
    try:
        return morceau.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise NomInvalideError("codage impossible", nom) from exc


def normaliser_hote(texte: str) -> str:
    """Hôte normalisé (minuscules, punycode), ou NomInvalideError avec son motif."""
    nom = texte.strip().lower()
    nom = _SCHEMA.sub("", nom)
    nom = re.split(r"[/?#]", nom, maxsplit=1)[0]
    nom = nom.rsplit("@", 1)[-1]  # identifiants avant @ dans une adresse web, ou courriel
    nom = nom.split(":", 1)[0]  # port
    nom = nom.rstrip(".")
    nom = nom.removeprefix("www.")
    if not nom:
        raise NomInvalideError("nom vide", texte)
    morceaux = nom.split(".")
    if len(morceaux) < 2:
        raise NomInvalideError("un seul morceau", texte)
    if any(not m for m in morceaux):
        raise NomInvalideError("morceau vide", texte)
    morceaux = [_en_punycode(m, texte) for m in morceaux]
    for m in morceaux:
        if len(m) > 63:
            raise NomInvalideError("morceau trop long", texte)
        if not _MORCEAU.match(m):
            raise NomInvalideError("caractère interdit", texte)
    resultat = ".".join(morceaux)
    if len(resultat) > 253:
        raise NomInvalideError("nom trop long", texte)
    return resultat


@dataclass(frozen=True)
class ListeDesSuffixes:
    version: str
    regles: frozenset[str]
    exceptions: frozenset[str]
    jokers: frozenset[str]

    def suffixe_public(self, hote: str) -> str:
        """Suffixe public d'un hôte déjà normalisé, selon l'algorithme officiel."""
        morceaux = hote.split(".")
        meilleur = morceaux[-1:]  # règle par défaut « * »
        for i in range(len(morceaux)):
            candidat = ".".join(morceaux[i:])
            if candidat in self.exceptions:
                # Une exception l'emporte : le suffixe est la règle moins son premier morceau.
                return ".".join(morceaux[i + 1 :])
            parent = ".".join(morceaux[i + 1 :])
            if (candidat in self.regles or (i + 1 < len(morceaux) and parent in self.jokers)) and (
                len(morceaux) - i > len(meilleur)
            ):
                meilleur = morceaux[i:]
        return ".".join(meilleur)

    def domaine_enregistrable(self, hote: str) -> str | None:
        """Suffixe public plus un morceau ; None si l'hôte est lui-même un suffixe public."""
        suffixe = self.suffixe_public(hote)
        if hote == suffixe:
            return None
        reste = hote[: -len(suffixe) - 1].split(".")
        return f"{reste[-1]}.{suffixe}"


def lire_liste(texte: str) -> ListeDesSuffixes:
    """Lit la liste ; les règles en Unicode sont converties en punycode au chargement."""
    version = ""
    regles: set[str] = set()
    exceptions: set[str] = set()
    jokers: set[str] = set()
    for ligne in texte.splitlines():
        ligne = ligne.strip()
        if ligne.startswith("// VERSION:"):
            version = ligne.removeprefix("// VERSION:").strip()
        if not ligne or ligne.startswith("//"):
            continue
        regle = ligne.split()[0].lower()
        exception = regle.startswith("!")
        regle = regle.removeprefix("!")
        joker = regle.startswith("*.")
        regle = regle.removeprefix("*.")
        regle = ".".join(_en_punycode(m, regle) for m in regle.split("."))
        if exception:
            exceptions.add(regle)
        elif joker:
            jokers.add(regle)
        else:
            regles.add(regle)
    if not version:
        raise ValueError("liste des suffixes sans ligne VERSION")
    return ListeDesSuffixes(version, frozenset(regles), frozenset(exceptions), frozenset(jokers))


@cache
def liste_des_suffixes() -> ListeDesSuffixes:
    """Liste copiée dans le paquet, chargée une seule fois par exécution."""
    fichier = files("investment_offer_check") / "suffixes" / "public_suffix_list.dat"
    return lire_liste(fichier.read_text(encoding="utf-8"))
