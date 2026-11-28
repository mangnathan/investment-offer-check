"""Normalisation des noms et domaine enregistrable.

Les cas officiels de la liste des suffixes sont rejoués tels quels, y compris les noms
internationalisés, sous forme Unicode et punycode. Les autres tests n'utilisent que des noms
fictifs.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from investment_offer_check.noms import (
    NomInvalideError,
    lire_liste,
    liste_des_suffixes,
    normaliser_hote,
)

CAS_OFFICIELS = Path(__file__).parent / "donnees" / "test_psl.txt"
_CAS = re.compile(r"^checkPublicSuffix\((null|'[^']*'), (null|'[^']*')\);")


def _cas_officiels() -> list[tuple[str, str | None]]:
    cas: list[tuple[str, str | None]] = []
    for ligne in CAS_OFFICIELS.read_text(encoding="utf-8").splitlines():
        m = _CAS.match(ligne.strip())
        if not m or m.group(1) == "null":  # l'entrée nulle n'a pas d'équivalent typé ici
            continue
        attendu = None if m.group(2) == "null" else m.group(2).strip("'")
        cas.append((m.group(1).strip("'"), attendu))
    return cas


def _en_punycode(nom: str) -> str:
    return ".".join(m if m.isascii() else m.encode("idna").decode("ascii") for m in nom.split("."))


def test_tous_les_cas_officiels_sont_lus() -> None:
    # 78 cas actifs (4 autres sont mis en commentaire dans le fichier officiel), moins l'entrée
    # nulle.
    assert len(_cas_officiels()) == 77


@pytest.mark.parametrize(("entree", "attendu"), _cas_officiels())
def test_cas_officiels_de_la_liste_des_suffixes(entree: str, attendu: str | None) -> None:
    liste = liste_des_suffixes()
    nom = entree.lower()
    # Un point initial rend le nom invalide.
    obtenu = None if nom.startswith(".") else liste.domaine_enregistrable(_en_punycode(nom))
    assert obtenu == (None if attendu is None else _en_punycode(attendu))


def test_version_de_la_liste_lue_dans_l_en_tete() -> None:
    assert liste_des_suffixes().version == "2026-11-27_12-48-40_UTC"


def test_regles_unicode_converties_au_chargement() -> None:
    liste = lire_liste("// VERSION: essai\nélysée-exemple\n*.joker-exemple\n!ici.joker-exemple\n")
    assert "xn--lyse-exemple-9dbd" in liste.regles
    assert liste.domaine_enregistrable("banque.xn--lyse-exemple-9dbd") == (
        "banque.xn--lyse-exemple-9dbd"
    )
    assert liste.domaine_enregistrable("a.b.joker-exemple") == "a.b.joker-exemple"
    assert liste.domaine_enregistrable("a.ici.joker-exemple") == "ici.joker-exemple"


def test_suffixes_prives_des_hebergeurs() -> None:
    liste = liste_des_suffixes()
    assert liste.domaine_enregistrable("conseil-fictif.wixsite.com") == (
        "conseil-fictif.wixsite.com"
    )
    assert liste.domaine_enregistrable("page.conseil-fictif.github.io") == (
        "conseil-fictif.github.io"
    )
    assert liste.domaine_enregistrable("espace.patrimoine-fictif.co.uk") == (
        "patrimoine-fictif.co.uk"
    )
    assert liste.domaine_enregistrable("wixsite.com") is None


@pytest.mark.parametrize(
    ("entree", "attendu"),
    [
        ("HTTPS://WWW.Banque-Elysee-Fictive.FR/offre?x=1", "banque-elysee-fictive.fr"),
        ("banque-élysée.fr", "xn--banque-lyse-hbbd.fr"),
        ("www.banque-élysée.fr.", "xn--banque-lyse-hbbd.fr"),
        ("contact@conseil-patrimoine-exemple.test", "conseil-patrimoine-exemple.test"),
        ("http://conseil-fictif.test:8443/chemin", "conseil-fictif.test"),
        ("  Placement-Fictif.example  ", "placement-fictif.example"),
        ("xn--banque-lyse-hbbd.fr", "xn--banque-lyse-hbbd.fr"),
        # IDNA 2003 (bibliothèque standard) : « ß » devient « ss ».
        ("straße-fictive.de", "strasse-fictive.de"),
    ],
)
def test_normalisation(entree: str, attendu: str) -> None:
    assert normaliser_hote(entree) == attendu


@pytest.mark.parametrize(
    ("entree", "motif"),
    [
        ("", "nom vide"),
        ("www.", "un seul morceau"),
        ("localhost", "un seul morceau"),
        ("conseil..fictif.fr", "morceau vide"),
        ("conseil_fictif.fr", "caractère interdit"),
        ("-conseil-fictif.fr", "caractère interdit"),
        ("a" * 64 + ".fr", "morceau trop long"),
        (".".join(["a" * 60] * 5) + ".fr", "nom trop long"),
    ],
)
def test_nom_impossible_a_normaliser_garde_son_motif(entree: str, motif: str) -> None:
    with pytest.raises(NomInvalideError) as erreur:
        normaliser_hote(entree)
    assert erreur.value.motif == motif
    assert erreur.value.nom == entree
