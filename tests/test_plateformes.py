"""Plateformes partagées : noms fictifs seulement, aucune variante de vraie banque."""

from __future__ import annotations

import pytest

from investment_offer_check.noms import NomInvalideError
from investment_offer_check.plateformes import (
    LIEN_RACCOURCI,
    Genre,
    Identite,
    identifier,
    plateformes,
)


def test_version_des_listes() -> None:
    assert plateformes().version == "2"


@pytest.mark.parametrize(
    ("texte", "attendu"),
    [
        (
            "https://pages.orange.fr/conseil-fictif",
            Identite(Genre.HEBERGEUR, "pages.orange.fr", chemin_retire=True),
        ),
        ("conseil-fictif.free.fr", Identite(Genre.HEBERGEUR, "conseil-fictif.free.fr")),
        (
            "http://perso.wanadoo.fr/conseil-fictif/",
            Identite(Genre.HEBERGEUR, "perso.wanadoo.fr", chemin_retire=True),
        ),
    ],
)
def test_pages_personnelles_des_fournisseurs_d_acces(texte: str, attendu: Identite) -> None:
    identite = identifier(texte)
    assert identite == attendu
    assert not identite.interrogeable


def test_courriel_free_reste_une_messagerie() -> None:
    assert identifier("conseil.fictif@free.fr", courriel=True) == Identite(
        Genre.MESSAGERIE, "free.fr"
    )


def test_listes_coherentes() -> None:
    p = plateformes()
    assert p.chemin_garde <= p.plateformes_a_chemin
    assert p.raccourcisseurs <= p.chemin_garde
    assert not (p.messageries & p.plateformes_a_chemin)
    assert not (p.hebergeurs & p.plateformes_a_chemin)


@pytest.mark.parametrize(
    ("texte", "attendu"),
    [
        (
            "https://www.banque-elysee-fictive.fr/offre",
            Identite(Genre.DOMAINE, "banque-elysee-fictive.fr"),
        ),
        ("espace.banque-élysée.fr", Identite(Genre.DOMAINE, "xn--banque-lyse-hbbd.fr")),
        ("conseil-fictif.wixsite.com", Identite(Genre.DOMAINE, "conseil-fictif.wixsite.com")),
        # Catégorie A réservée aux courriels : un site sur orange.fr suit la règle ordinaire.
        ("https://boutique.orange.fr/offre", Identite(Genre.DOMAINE, "orange.fr")),
        ("conseil-fictif.wordpress.com", Identite(Genre.HEBERGEUR, "conseil-fictif.wordpress.com")),
        (
            "https://sites.google.com/view/placement-fictif?x=1",
            Identite(Genre.PLATEFORME, "sites.google.com", chemin="view/placement-fictif"),
        ),
        (
            "https://bit.ly/AbC123",
            Identite(Genre.PLATEFORME, "bit.ly", chemin="AbC123", mention=LIEN_RACCOURCI),
        ),
        (
            "https://wa.me/33600000000",
            Identite(Genre.PLATEFORME, "wa.me", chemin_retire=True),
        ),
        (
            "https://fr.linkedin.com/in/conseiller-fictif",
            Identite(Genre.PLATEFORME, "linkedin.com", chemin_retire=True),
        ),
        ("https://calendly.com/", Identite(Genre.PLATEFORME, "calendly.com")),
    ],
)
def test_identite_d_un_site(texte: str, attendu: Identite) -> None:
    assert identifier(texte) == attendu


@pytest.mark.parametrize(
    ("texte", "attendu"),
    [
        ("conseiller.fictif@gmail.com", Identite(Genre.MESSAGERIE, "gmail.com")),
        ("service@orange.fr", Identite(Genre.MESSAGERIE, "orange.fr")),
        ("contact@banque-elysee-fictive.fr", Identite(Genre.DOMAINE, "banque-elysee-fictive.fr")),
        ("contact@mail.conseil-fictif.co.uk", Identite(Genre.DOMAINE, "conseil-fictif.co.uk")),
    ],
)
def test_identite_d_une_adresse_de_courriel(texte: str, attendu: Identite) -> None:
    identite = identifier(texte, courriel=True)
    assert identite == attendu
    assert "@" not in identite.nom  # la partie avant le @ n'est jamais gardée


def test_seul_un_domaine_propre_est_interrogeable() -> None:
    assert identifier("banque-elysee-fictive.fr").interrogeable
    assert not identifier("x@gmail.com", courriel=True).interrogeable
    assert not identifier("https://t.me/canal").interrogeable
    assert not identifier("conseil-fictif.weebly.com").interrogeable


def test_suffixe_public_seul_refuse() -> None:
    with pytest.raises(NomInvalideError) as erreur:
        identifier("co.uk")
    assert erreur.value.motif == "suffixe public seul"
