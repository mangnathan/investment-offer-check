"""Commandes de collecte, de bout en bout sur des réponses fictives, sans aucun appel réseau."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from investment_offer_check import collecte
from investment_offer_check.liste_amf import RESSOURCE, URL_FICHIER, URL_JEU
from investment_offer_check.releves import URL_AMORCAGE
from investment_offer_check.reseau import Autorisation, Client, Reponse, ReseauError

SERVEUR = "https://rdap.registre-fictif.test/v1/"
PERSONNE = "Jeanne Fictive"
CSV = (
    b"nom;categorie;date_inscription\n"
    b"ancien-fictif.test;Forex;2026-06-01\n"
    b"exclu-fictif.test;Forex;2026-07-01\n"
    b"nouveau-fictif.test;Usurpation;2026-12-01\n"
    b"contact@nouveau-fictif.test;Usurpation;2026-12-01\n"
    b"conseiller@gmail.com;Forex;2026-12-02\n"
    b"autre-fictif.test;Forex;2026-12-02\n"
)


def _rdap(date: str) -> Reponse:
    document = {
        "events": [{"eventAction": "registration", "eventDate": date}],
        "entities": [
            {"roles": ["registrant"], "vcardArray": ["vcard", [["fn", {}, "text", PERSONNE]]]},
            {
                "roles": ["registrar"],
                "vcardArray": ["vcard", [["fn", {}, "text", "Bureau Fictif"]]],
            },
        ],
    }
    return Reponse(200, json.dumps(document).encode())


class Simule:
    def __init__(self, reponses: dict[str, Reponse | Exception]) -> None:
        self.reponses = reponses
        self.urls: list[str] = []

    def __call__(
        self, url: str, entetes: Mapping[str, str], delai: float, autorise: Autorisation
    ) -> Reponse:
        self.urls.append(url)
        reponse = self.reponses.get(url, Reponse(404, b""))
        if isinstance(reponse, Exception):
            raise reponse
        return reponse


def _reponses(last_modified: str = "2026-12-02T07:30:02+00:00") -> dict[str, Reponse | Exception]:
    jeu = {
        "resources": [
            {
                "id": RESSOURCE,
                "last_modified": last_modified,
                "extras": {
                    "analysis:checksum": hashlib.sha1(CSV, usedforsecurity=False).hexdigest()
                },
            }
        ]
    }
    amorcage = {"services": [[["test"], [SERVEUR]]]}
    reponses: dict[str, Reponse | Exception] = {
        URL_JEU: Reponse(200, json.dumps(jeu).encode()),
        URL_FICHIER: Reponse(200, CSV),
        URL_AMORCAGE: Reponse(200, json.dumps(amorcage).encode()),
    }
    for domaine in (
        "ancien-fictif.test",
        "exclu-fictif.test",
        "nouveau-fictif.test",
        "autre-fictif.test",
    ):
        reponses[SERVEUR + "domain/" + domaine] = _rdap("2026-05-01T00:00:00Z")
        reponses[f"https://crt.sh/?q={domaine}&output=json"] = Reponse(
            200, b'[{"not_before": "2026-05-01T10:00:00", "issuer_name": "O=Autorite Fictive"}]'
        )
    return reponses


def _client(reponses: dict[str, Reponse | Exception], rdap: int = 30) -> tuple[Client, Simule]:
    simule = Simule(reponses)
    plafonds = collecte.PLAFONDS_QUOTIDIENS | {"rdap": rdap}
    pauses = dict.fromkeys(collecte.PAUSES, 0.0)
    return Client(plafonds=plafonds, pauses=pauses, transport=simule), simule


def _releves(dossier: Path) -> list[dict[str, Any]]:
    texte = (dossier / "releves.jsonl").read_text("utf-8")
    return [json.loads(ligne) for ligne in texte.splitlines()]


def test_premiere_collecte(tmp_path: Path) -> None:
    client, simule = _client(_reponses())
    assert collecte.quotidienne(tmp_path, client, "2026-12-02") == 0
    assert (tmp_path / "instantanes" / "2026-12-02.json").exists()
    domaines = [r["domaine"] for r in _releves(tmp_path)]
    assert domaines == ["nouveau-fictif.test", "autre-fictif.test"]  # inscrits depuis le 28/11
    bilan = json.loads((tmp_path / "bilans" / "2026-12-02.json").read_text("utf-8"))
    assert bilan["fichier_inchange"] is False
    assert bilan["ecart_somme_de_controle"] is False
    assert bilan["releves"] == {
        "a_relever": 2,
        "releves": 2,
        "erreurs_techniques": 0,
        "rdap_absents": 0,
        "abandonnes": 0,
        "arret": None,
    }
    assert URL_FICHIER in simule.urls


def test_jour_sans_mise_a_jour(tmp_path: Path) -> None:
    collecte.quotidienne(tmp_path, _client(_reponses())[0], "2026-12-02")
    client, simule = _client(_reponses())
    assert collecte.quotidienne(tmp_path, client, "2026-12-03") == 0
    bilan = json.loads((tmp_path / "bilans" / "2026-12-03.json").read_text("utf-8"))
    assert bilan["fichier_inchange"] is True
    assert simule.urls == [URL_JEU]  # ni téléchargement, ni relevé refait
    assert not (tmp_path / "instantanes" / "2026-12-03.json").exists()


def test_plafond_atteint_reprise_le_lendemain(tmp_path: Path) -> None:
    client, _ = _client(_reponses(), rdap=1)
    collecte.quotidienne(tmp_path, client, "2026-12-02")
    assert [r["domaine"] for r in _releves(tmp_path)] == ["nouveau-fictif.test"]
    client, _ = _client(_reponses("2026-12-03T07:30:02+00:00"))
    collecte.quotidienne(tmp_path, client, "2026-12-03")
    assert [r["domaine"] for r in _releves(tmp_path)] == [
        "nouveau-fictif.test",
        "autre-fictif.test",
    ]


def test_refus_de_quota_arrete_et_le_signale(tmp_path: Path) -> None:
    reponses = _reponses()
    reponses[SERVEUR + "domain/nouveau-fictif.test"] = Reponse(429, b"")
    assert collecte.quotidienne(tmp_path, _client(reponses)[0], "2026-12-02") == 2
    bilan = json.loads((tmp_path / "bilans" / "2026-12-02.json").read_text("utf-8"))
    assert bilan["releves"]["arret"] == "refus de quota"
    assert not (tmp_path / "releves.jsonl").exists()


def test_aucune_donnee_personnelle_dans_les_fichiers(tmp_path: Path) -> None:
    collecte.quotidienne(tmp_path, _client(_reponses())[0], "2026-12-02")
    for fichier in tmp_path.rglob("*"):
        if fichier.is_file():
            texte = fichier.read_text("utf-8")
            assert PERSONNE not in texte
            assert "conseiller@" not in texte


@pytest.fixture
def exclus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    fichier = tmp_path / "exclus.txt"
    fichier.write_bytes(b"exclu-fictif.test\n")
    monkeypatch.setattr(
        collecte, "EMPREINTE_EXCLUS", hashlib.sha256(b"exclu-fictif.test\n").hexdigest()
    )
    return fichier


def test_rattrapage_sans_les_domaines_exclus_et_avec_reprise(tmp_path: Path, exclus: Path) -> None:
    liste = tmp_path / "liste.csv"
    liste.write_bytes(CSV)
    donnees = tmp_path / "donnees"
    client, _ = _client(_reponses())
    code = collecte.rattrapage(
        donnees, client, liste, exclus, "2026-01-01", "2026-11-27", "2026-12-04"
    )
    assert code == 0
    assert [r["domaine"] for r in _releves(donnees)] == ["ancien-fictif.test"]
    bilan = json.loads((donnees / "bilans" / "rattrapage-2026-12-04.json").read_text("utf-8"))
    assert set(bilan) == {
        "date",
        "periode",
        "domaines_exclus",
        "limite",
        "releves",
        "appels",
        "redirections_refusees",
    }
    client, simule = _client(_reponses())
    collecte.rattrapage(donnees, client, liste, exclus, "2026-01-01", "2026-11-27", "2026-12-05")
    assert simule.urls == []  # tout est déjà relevé : aucun appel


def test_rattrapage_refuse_une_liste_d_exclusion_modifiee(tmp_path: Path) -> None:
    fichier = tmp_path / "exclus.txt"
    fichier.write_bytes(b"autre-liste.test\n")
    with pytest.raises(ValueError):
        collecte.domaines_exclus(fichier)


def test_bilan_separe_erreurs_techniques_et_domaines_absents(tmp_path: Path) -> None:
    reponses = _reponses()
    reponses[SERVEUR + "domain/nouveau-fictif.test"] = Reponse(404, b"")
    reponses["https://crt.sh/?q=autre-fictif.test&output=json"] = Reponse(502, b"")
    collecte.quotidienne(tmp_path, _client(reponses)[0], "2026-12-02")
    bilan = json.loads((tmp_path / "bilans" / "2026-12-02.json").read_text("utf-8"))
    assert bilan["releves"]["rdap_absents"] == 1
    assert bilan["releves"]["erreurs_techniques"] == 1


def test_essai_limite_puis_reprise_sans_appel(tmp_path: Path, exclus: Path) -> None:
    liste = tmp_path / "liste.csv"
    liste.write_bytes(CSV)
    donnees = tmp_path / "donnees"
    client, _ = _client(_reponses())
    collecte.rattrapage(donnees, client, liste, exclus, "2026-01-01", "2026-12-31", "2026-12-04", 2)
    assert [r["domaine"] for r in _releves(donnees)] == [
        "ancien-fictif.test",
        "nouveau-fictif.test",
    ]
    assert {tuple(sorted(r)) for r in _releves(donnees)} == {
        ("crt", "date_inscription", "date_releve", "domaine", "rdap", "tentative")
    }
    assert {tuple(sorted(r["rdap"])) for r in _releves(donnees)} == {
        ("bureau", "creation", "statut")
    }
    assert {tuple(sorted(r["crt"])) for r in _releves(donnees)} == {
        ("emetteur", "premier", "statut")
    }
    client, simule = _client(_reponses())
    collecte.rattrapage(donnees, client, liste, exclus, "2026-01-01", "2026-12-31", "2026-12-04", 2)
    assert simule.urls == []  # même essai relancé : tout est déjà relevé
    bilans = sorted(p.name for p in (donnees / "bilans").iterdir())
    assert bilans == ["rattrapage-2026-12-04-2.json", "rattrapage-2026-12-04.json"]


RDAP_NOUVEAU = SERVEUR + "domain/nouveau-fictif.test"
CRT_NOUVEAU = "https://crt.sh/?q=nouveau-fictif.test&output=json"


def _tentatives(tmp_path: Path) -> list[int]:
    return [r["tentative"] for r in _releves(tmp_path) if r["domaine"] == "nouveau-fictif.test"]


def _relancer(tmp_path: Path, jour: str, reponses: dict[str, Reponse | Exception]) -> Simule:
    client, simule = _client(reponses)
    collecte.quotidienne(tmp_path, client, jour)
    return simule


@pytest.mark.parametrize(
    ("url", "panne"),
    [
        (RDAP_NOUVEAU, Reponse(502, b"")),  # réponse 5xx
        (RDAP_NOUVEAU, ReseauError("TimeoutError sur rdap.registre-fictif.test")),  # délai
        (CRT_NOUVEAU, ReseauError("ConnectionResetError sur crt.sh")),  # connexion coupée
        (CRT_NOUVEAU, Reponse(503, b"")),
    ],
)
def test_erreur_technique_retentee_sur_la_seule_source_en_echec(
    tmp_path: Path, url: str, panne: Reponse | Exception
) -> None:
    reponses = _reponses()
    reponses[url] = panne
    _relancer(tmp_path, "2026-12-02", reponses)
    simule = _relancer(tmp_path, "2026-12-03", _reponses())
    autre = CRT_NOUVEAU if url == RDAP_NOUVEAU else RDAP_NOUVEAU
    assert url in simule.urls and autre not in simule.urls
    assert _tentatives(tmp_path) == [1, 2]
    assert _releves(tmp_path)[-1]["rdap"]["statut"] == "trouvé"
    assert _releves(tmp_path)[-1]["crt"]["statut"] == "trouvé"


@pytest.mark.parametrize(
    ("url", "reponse"),
    [
        (RDAP_NOUVEAU, Reponse(404, b"")),  # domaine introuvable
        (CRT_NOUVEAU, Reponse(200, b"[]")),  # aucun certificat
        (RDAP_NOUVEAU, Reponse(403, b"")),  # erreur 4xx : pas une panne passagère
        (RDAP_NOUVEAU, Reponse(200, b"{pas du json")),  # réponse illisible
    ],
)
def test_une_reponse_n_est_jamais_retentee(tmp_path: Path, url: str, reponse: Reponse) -> None:
    reponses = _reponses()
    reponses[url] = reponse
    _relancer(tmp_path, "2026-12-02", reponses)
    simule = _relancer(tmp_path, "2026-12-03", _reponses("2026-12-03T07:30:02+00:00"))
    assert RDAP_NOUVEAU not in simule.urls and CRT_NOUVEAU not in simule.urls
    assert _tentatives(tmp_path) == [1]


def test_absence_de_serveur_rdap_jamais_retentee(tmp_path: Path) -> None:
    csv = CSV + b"sans-serveur-fictif.inconnue;Forex;2026-12-02\n"
    reponses = _reponses()
    reponses[URL_FICHIER] = Reponse(200, csv)
    _relancer(tmp_path, "2026-12-02", reponses)
    ligne = next(r for r in _releves(tmp_path) if r["domaine"] == "sans-serveur-fictif.inconnue")
    assert ligne["rdap"]["statut"] == "pas de serveur"
    simule = _relancer(tmp_path, "2026-12-03", reponses)
    assert not [u for u in simule.urls if "sans-serveur-fictif" in u]


def test_abandon_apres_trois_tentatives(tmp_path: Path) -> None:
    reponses = _reponses()
    reponses[CRT_NOUVEAU] = Reponse(502, b"")
    for jour in ("2026-12-02", "2026-12-03", "2026-12-04"):
        _relancer(tmp_path, jour, reponses)
    assert _tentatives(tmp_path) == [1, 2, 3]
    bilan = json.loads((tmp_path / "bilans" / "2026-12-04.json").read_text("utf-8"))
    assert bilan["releves"]["abandonnes"] == 1
    simule = _relancer(tmp_path, "2026-12-05", reponses)
    assert CRT_NOUVEAU not in simule.urls  # abandonné : valeur manquante, plus d'appel
    assert _releves(tmp_path)[-1]["crt"]["statut"] == "échec 502"


def test_refus_de_quota_ne_consomme_pas_de_tentative(tmp_path: Path) -> None:
    reponses = _reponses()
    reponses[CRT_NOUVEAU] = Reponse(429, b"")
    assert _relancer(tmp_path, "2026-12-02", reponses) is not None
    assert not (tmp_path / "releves.jsonl").exists()
    _relancer(tmp_path, "2026-12-03", _reponses())
    assert _tentatives(tmp_path) == [1]
