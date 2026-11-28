"""Liste de l'AMF : fichiers et réponses fictifs, aucun appel réseau."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping

import pytest

from investment_offer_check import liste_amf
from investment_offer_check.liste_amf import (
    Entree,
    ListeAmfError,
    Metadonnees,
    ecart,
    empreintes,
    instantane_json,
    lire_csv,
    lire_instantane,
    lire_metadonnees,
    telecharger,
    versions,
)
from investment_offer_check.reseau import Autorisation, Client, Reponse

CSV_FICTIF = (
    "﻿nom;categorie;date_inscription\n"
    "banque-elysee-fictive.fr;Usurpation;2026-01-05\n"
    "contact@banque-elysee-fictive.fr;Usurpation;2026-01-05\n"
    "conseiller.fictif@gmail.com;Forex;2025-03-01\n"
    "Conseil Fictif SARL;Autres;2025-04-01\n"
    "https://wa.me/33600000000;Crypto-actifs;2025-05-01\n"
    "https://bit.ly/AbC123;Forex;2025-05-02\n"
    "conseil_mauvais.fr;Forex;2025-05-03\n"
    "banque-elysee-fictive.fr;Usurpation;2026-01-05\n"
    "placement-fictif.fr;Forex;23/11/2026\n"
    "prenom.fictif@domaine-sans-point;Forex;2025-01-01\n"
).encode()


def test_colonnes_inattendues_arretent_la_lecture() -> None:
    with pytest.raises(ListeAmfError):
        lire_csv(b"nom;categorie\nx.fr;Forex\n")


def test_bilan_de_lecture() -> None:
    bilan = lire_csv(CSV_FICTIF).bilan()
    assert bilan == {
        "lignes": 10,
        "entrees": 5,
        "texte_libre_ecarte": 1,
        "doublons": 1,
        "rejets": {"caractère interdit": 1, "date invalide": 1, "un seul morceau": 1},
        "par_genre": {"domaine": 2, "messagerie": 1, "plateforme": 2, "hebergeur": 0},
        "chemins_retires": 1,
        "liens_raccourcis": 1,
    }


def test_site_et_courriel_du_meme_domaine_sont_deux_entrees() -> None:
    entrees = [e for e in lire_csv(CSV_FICTIF).entrees if e.nom == "banque-elysee-fictive.fr"]
    assert sorted(e.origine for e in entrees) == ["courriel", "site"]
    assert len({e.cle() for e in entrees}) == 2


def test_jamais_de_partie_avant_le_arobase_ni_de_texte_libre() -> None:
    texte = instantane_json(lire_csv(CSV_FICTIF), {"versions": versions()})
    for interdit in ("conseiller.fictif", "prenom.fictif", "contact@", "Conseil Fictif SARL"):
        assert interdit not in texte
    assert "33600000000" not in texte  # chemin retiré : il peut désigner une personne


def _entree(nom: str, origine: str = "site", categorie: str = "Forex") -> Entree:
    return Entree("domaine", nom, None, False, None, origine, categorie, "2026-01-05")


def test_ecart_sur_la_cle() -> None:
    veille = [_entree("a-fictif.fr"), _entree("b-fictif.fr")]
    jour = [_entree("b-fictif.fr", categorie="Autres"), _entree("c-fictif.fr")]
    nouvelles, retirees = ecart(veille, jour)
    assert [e.nom for e in nouvelles] == ["c-fictif.fr"]
    assert [e.nom for e in retirees] == ["a-fictif.fr"]


def test_ecart_distingue_site_et_courriel() -> None:
    nouvelles, retirees = ecart([_entree("a-fictif.fr")], [_entree("a-fictif.fr", "courriel")])
    assert [e.origine for e in nouvelles] == ["courriel"]
    assert [e.origine for e in retirees] == ["site"]


def test_instantane_relu_a_l_identique() -> None:
    lecture = lire_csv(CSV_FICTIF)
    meta, entrees = lire_instantane(instantane_json(lecture, {"versions": versions()}))
    assert entrees == lecture.entrees
    assert meta["versions"]["filtre"] == liste_amf.VERSION_FILTRE


def test_empreintes() -> None:
    assert empreintes(b"abc") == {
        "sha1": hashlib.sha1(b"abc", usedforsecurity=False).hexdigest(),
        "sha256": hashlib.sha256(b"abc").hexdigest(),
    }


class Simule:
    def __init__(self, reponses: dict[str, Reponse]) -> None:
        self.reponses = reponses
        self.urls: list[str] = []

    def __call__(
        self, url: str, entetes: Mapping[str, str], delai: float, autorise: Autorisation
    ) -> Reponse:
        self.urls.append(url)
        return self.reponses[url]


def _client(reponses: dict[str, Reponse]) -> tuple[Client, Simule]:
    simule = Simule(reponses)
    client = Client(plafonds={"datagouv": 3}, pauses={"datagouv": 0.0}, transport=simule)
    return client, simule


def _jeu(ressources: list[dict[str, object]]) -> Reponse:
    return Reponse(200, json.dumps({"resources": ressources}).encode())


def test_metadonnees_de_la_ressource() -> None:
    ressource: dict[str, object] = {
        "id": liste_amf.RESSOURCE,
        "last_modified": "2026-11-27T07:30:02+00:00",
        "extras": {"analysis:checksum": "abc", "analysis:content-length": 194601},
    }
    client, simule = _client({liste_amf.URL_JEU: _jeu([{"id": "autre"}, ressource])})
    meta = lire_metadonnees(client)
    assert meta == Metadonnees("2026-11-27T07:30:02+00:00", "abc", 194601)
    assert simule.urls == [liste_amf.URL_JEU]
    assert meta.identiques(Metadonnees("2026-11-27T07:30:02+00:00", "abc", None))
    assert not meta.identiques(Metadonnees("2026-11-28T07:30:02+00:00", "abc", 194601))
    assert not meta.identiques(None)


def test_ressource_absente_ou_statut_inattendu() -> None:
    client, _ = _client({liste_amf.URL_JEU: _jeu([{"id": "autre"}])})
    with pytest.raises(ListeAmfError):
        lire_metadonnees(client)
    client, _ = _client({liste_amf.URL_FICHIER: Reponse(404, b"")})
    with pytest.raises(ListeAmfError):
        telecharger(client)


def test_telechargement_par_le_lien_permanent() -> None:
    client, simule = _client({liste_amf.URL_FICHIER: Reponse(200, CSV_FICTIF)})
    assert telecharger(client) == CSV_FICTIF
    assert simule.urls == [liste_amf.URL_FICHIER]
