"""Liste noire de l'AMF : métadonnées, téléchargement, filtrage, instantané et écart avec la veille.

Source : jeu « Listes noires des entités non autorisées à proposer des produits ou services
financiers en France » sur data.gouv.fr, Licence Ouverte 2.0. La liste n'est jamais republiée
dans le dépôt public : l'instantané filtré est gardé dans le dépôt privé de la collecte.

Le filtre écarte les noms en texte libre (ils peuvent désigner une personne physique) et ne
garde jamais la partie avant le @ d'une adresse de courriel.

Règle d'usage des instantanés : une entrée retirée par l'AMF reste dans les anciens instantanés,
qui servent à l'évaluation (« la liste de la veille »). La fiche de constats, elle, ne s'appuie
que sur la liste du jour : une entrée retirée n'y est plus jamais citée.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from typing import Any

from investment_offer_check.noms import NomInvalideError, liste_des_suffixes
from investment_offer_check.plateformes import Genre, identifier, plateformes
from investment_offer_check.reseau import Client

JEU = "641d5dab1d84b530f7720b08"
RESSOURCE = "d2d9df6d-1cd2-41a8-96f5-684cb3057ecb"
URL_JEU = f"https://www.data.gouv.fr/api/1/datasets/{JEU}/"
# Lien permanent de data.gouv.fr, qui redirige vers le dernier fichier publié par l'AMF.
URL_FICHIER = f"https://www.data.gouv.fr/api/1/datasets/r/{RESSOURCE}"
SOURCE = "datagouv"
COLONNES = ("nom", "categorie", "date_inscription")
# Version du filtre : à changer dès que la lecture ou le filtrage changent.
VERSION_FILTRE = "1"
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ListeAmfError(RuntimeError):
    """Réponse ou fichier inattendu : la collecte s'arrête et le signale."""


@dataclass(frozen=True)
class Metadonnees:
    """Ce que data.gouv.fr publie sur la ressource, pour savoir si le fichier a changé."""

    last_modified: str
    analysis_checksum: str | None
    analysis_taille: int | None

    def identiques(self, autre: Metadonnees | None) -> bool:
        return autre is not None and (self.last_modified, self.analysis_checksum) == (
            autre.last_modified,
            autre.analysis_checksum,
        )


@dataclass(frozen=True)
class Entree:
    genre: str
    nom: str
    chemin: str | None
    chemin_retire: bool
    mention: str | None
    origine: str  # « site » ou « courriel »
    categorie: str
    date_inscription: str

    def cle(self) -> tuple[str, str, str, str, str]:
        """Identité, origine et date d'inscription.

        Un domaine présent comme site et comme courriel donne deux entrées distinctes, et un
        changement de catégorie seul ne fait ni une entrée nouvelle ni une entrée retirée.
        """
        return (self.genre, self.nom, self.chemin or "", self.origine, self.date_inscription)


@dataclass(frozen=True)
class Rejet:
    motif: str
    texte: str  # pour un courriel, seulement la partie après le @
    origine: str
    date_inscription: str


@dataclass
class Lecture:
    entrees: list[Entree] = field(default_factory=list)
    rejets: list[Rejet] = field(default_factory=list)
    lignes: int = 0
    texte_libre: int = 0
    doublons: int = 0

    def bilan(self) -> dict[str, Any]:
        genres = Counter(e.genre for e in self.entrees)
        return {
            "lignes": self.lignes,
            "entrees": len(self.entrees),
            "texte_libre_ecarte": self.texte_libre,
            "doublons": self.doublons,
            "rejets": dict(sorted(Counter(r.motif for r in self.rejets).items())),
            "par_genre": {g.value: genres.get(g.value, 0) for g in Genre},
            "chemins_retires": sum(e.chemin_retire for e in self.entrees),
            "liens_raccourcis": sum(e.mention is not None for e in self.entrees),
        }


def lire_metadonnees(client: Client) -> Metadonnees:
    reponse = client.get(SOURCE, URL_JEU)
    if reponse.statut != 200:
        raise ListeAmfError(f"métadonnées : statut {reponse.statut}")
    jeu = json.loads(reponse.corps)
    ressource = next((r for r in jeu.get("resources", []) if r.get("id") == RESSOURCE), None)
    if ressource is None:
        raise ListeAmfError("ressource de la liste noire absente du jeu de données")
    extras = ressource.get("extras") or {}
    taille = extras.get("analysis:content-length")
    return Metadonnees(
        last_modified=str(ressource["last_modified"]),
        analysis_checksum=extras.get("analysis:checksum"),
        analysis_taille=int(taille) if taille is not None else None,
    )


def telecharger(client: Client) -> bytes:
    reponse = client.get(SOURCE, URL_FICHIER)
    if reponse.statut != 200:
        raise ListeAmfError(f"fichier : statut {reponse.statut}")
    return reponse.corps


def empreintes(contenu: bytes) -> dict[str, str]:
    return {
        # SHA-1 seulement pour comparer avec analysis:checksum de data.gouv.fr.
        "sha1": hashlib.sha1(contenu, usedforsecurity=False).hexdigest(),
        "sha256": hashlib.sha256(contenu).hexdigest(),
    }


def lire_csv(contenu: bytes) -> Lecture:
    """Lit et filtre le fichier ; échoue clairement si les colonnes changent."""
    lecteur = csv.DictReader(io.StringIO(contenu.decode("utf-8-sig")), delimiter=";")
    if tuple(lecteur.fieldnames or ()) != COLONNES:
        raise ListeAmfError(f"colonnes inattendues : {lecteur.fieldnames}")
    lecture = Lecture()
    vues: dict[tuple[str, str, str, str, str], Entree] = {}
    for ligne in lecteur:
        lecture.lignes += 1
        nom = (ligne["nom"] or "").strip()
        date = (ligne["date_inscription"] or "").strip()
        categorie = (ligne["categorie"] or "").strip()
        courriel = "@" in nom
        origine = "courriel" if courriel else "site"
        texte = nom.rsplit("@", 1)[1] if courriel else nom
        if not _DATE.match(date):
            lecture.rejets.append(Rejet("date invalide", texte, origine, date))
            continue
        if not courriel and (" " in nom or "." not in nom):
            lecture.texte_libre += 1  # nom en texte libre : jamais gardé
            continue
        try:
            identite = identifier(texte, courriel=courriel)
        except NomInvalideError as erreur:
            lecture.rejets.append(Rejet(erreur.motif, texte, origine, date))
            continue
        entree = Entree(
            genre=identite.genre.value,
            nom=identite.nom,
            chemin=identite.chemin,
            chemin_retire=identite.chemin_retire,
            mention=identite.mention,
            origine=origine,
            categorie=categorie,
            date_inscription=date,
        )
        if entree.cle() in vues:
            lecture.doublons += 1
            continue
        vues[entree.cle()] = entree
    lecture.entrees = sorted(vues.values(), key=Entree.cle)
    return lecture


def versions() -> dict[str, str]:
    return {
        "filtre": VERSION_FILTRE,
        "liste_des_suffixes": liste_des_suffixes().version,
        "plateformes": plateformes().version,
    }


def ecart(veille: Iterable[Entree], jour: Iterable[Entree]) -> tuple[list[Entree], list[Entree]]:
    """Entrées nouvelles et entrées retirées, comparées sur leur clé."""
    avant = {e.cle(): e for e in veille}
    apres = {e.cle(): e for e in jour}
    nouvelles = [apres[c] for c in sorted(apres.keys() - avant.keys())]
    retirees = [avant[c] for c in sorted(avant.keys() - apres.keys())]
    return nouvelles, retirees


def instantane_json(lecture: Lecture, meta: dict[str, Any]) -> str:
    contenu = {
        "meta": meta,
        "entrees": [asdict(e) for e in lecture.entrees],
        "rejets": [asdict(r) for r in lecture.rejets],
    }
    return json.dumps(contenu, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def lire_instantane(texte: str) -> tuple[dict[str, Any], list[Entree]]:
    contenu = json.loads(texte)
    return contenu["meta"], [Entree(**e) for e in contenu["entrees"]]
