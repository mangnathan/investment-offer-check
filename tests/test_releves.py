"""Relevés RDAP et crt.sh : réponses fictives, aucun appel réseau.

Les réponses RDAP simulées contiennent des coordonnées de personne fictives : elles ne doivent
apparaître nulle part (résultat, journaux, fichiers, messages d'erreur).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from pathlib import Path

import pytest

from investment_offer_check.releves import (
    URL_AMORCAGE,
    ReleveCrt,
    ReleveRdap,
    lire_amorcage,
    relever_crt,
    relever_rdap,
)
from investment_offer_check.reseau import Autorisation, Client, HoteRefuseError, Reponse

SERVEUR = "https://rdap.registre-fictif.test/v1/"
PERSONNE = ("Jeanne Fictive", "+33.600000000", "jeanne.fictive@courriel-fictif.test")

AMORCAGE = {
    "services": [
        [["test", "exemple"], ["http://rdap.registre-fictif.test/v1/", SERVEUR]],
        [["sanshttps"], ["http://rdap.ancien-fictif.test/"]],
    ]
}

RDAP = {
    "events": [
        {"eventAction": "registration", "eventDate": "2025-10-06T12:00:00Z"},
        {"eventAction": "expiration", "eventDate": "2026-10-06T12:00:00Z"},
    ],
    "entities": [
        {
            "roles": ["registrant"],
            "vcardArray": ["vcard", [["fn", {}, "text", PERSONNE[0]]]],
        },
        {
            "roles": ["registrar"],
            "vcardArray": [
                "vcard",
                [["version", {}, "text", "4.0"], ["fn", {}, "text", "Bureau Fictif SAS"]],
            ],
            "entities": [
                {
                    "roles": ["abuse"],
                    "vcardArray": [
                        "vcard",
                        [["tel", {}, "uri", PERSONNE[1]], ["email", {}, "text", PERSONNE[2]]],
                    ],
                }
            ],
        },
    ],
}

CRT = [
    {"not_before": "2025-10-07T00:00:00", "issuer_name": "C=XX, O=Autorite Fictive, CN=F2"},
    {"not_before": "2025-10-06T08:00:00", "issuer_name": "C=XX, O=Autorite Fictive, CN=F1"},
]


class Simule:
    def __init__(self, reponses: dict[str, Reponse]) -> None:
        self.reponses = reponses
        self.urls: list[str] = []

    def __call__(
        self, url: str, entetes: Mapping[str, str], delai: float, autorise: Autorisation
    ) -> Reponse:
        self.urls.append(url)
        return self.reponses.get(url, Reponse(404, b""))


def _client(reponses: dict[str, Reponse]) -> tuple[Client, Simule]:
    simule = Simule(reponses)
    client = Client(
        plafonds={"iana": 1, "rdap": 5, "crt": 5},
        pauses={"iana": 0.0, "rdap": 0.0, "crt": 0.0},
        transport=simule,
    )
    return client, simule


def _json(objet: object) -> Reponse:
    return Reponse(200, json.dumps(objet).encode())


def test_amorcage_garde_les_serveurs_https_et_les_declare() -> None:
    client, _ = _client({URL_AMORCAGE: _json(AMORCAGE)})
    serveurs = lire_amorcage(client)
    assert serveurs == {"test": SERVEUR, "exemple": SERVEUR}
    assert client.serveurs_rdap == {"rdap.registre-fictif.test"}


def _pret(reponses: dict[str, Reponse]) -> tuple[Client, Simule, dict[str, str]]:
    client, simule = _client({URL_AMORCAGE: _json(AMORCAGE), **reponses})
    return client, simule, lire_amorcage(client)


def test_releve_rdap_ne_garde_que_deux_champs() -> None:
    url = SERVEUR + "domain/conseil-fictif.test"
    client, simule, serveurs = _pret({url: _json(RDAP)})
    releve = relever_rdap(client, serveurs, "conseil-fictif.test")
    assert releve == ReleveRdap("trouvé", "2025-10-06", "Bureau Fictif SAS")
    assert simule.urls[-1] == url


@pytest.mark.parametrize(
    ("reponse", "attendu"),
    [
        (Reponse(404, b""), ReleveRdap("absent")),
        (Reponse(502, b""), ReleveRdap("échec 502")),
        (Reponse(200, b"{pas du json"), ReleveRdap("illisible")),
        (Reponse(200, b"[]"), ReleveRdap("illisible")),
    ],
)
def test_releve_rdap_sans_donnees(reponse: Reponse, attendu: ReleveRdap) -> None:
    client, _, serveurs = _pret({SERVEUR + "domain/conseil-fictif.test": reponse})
    assert relever_rdap(client, serveurs, "conseil-fictif.test") == attendu


def test_extension_sans_serveur_rdap() -> None:
    client, simule, serveurs = _pret({})
    assert relever_rdap(client, serveurs, "conseil-fictif.sanshttps") == ReleveRdap(
        "pas de serveur"
    )
    assert len(simule.urls) == 1  # seul l'amorçage a été demandé


def test_releve_crt_premier_certificat() -> None:
    url = "https://crt.sh/?q=conseil-fictif.test&output=json"
    client, simule = _client({url: _json(CRT)})
    client.hotes_fixes = frozenset({"crt.sh"})
    assert relever_crt(client, "conseil-fictif.test") == ReleveCrt(
        "trouvé", "2025-10-06", "C=XX, O=Autorite Fictive, CN=F1"
    )
    assert simule.urls == [url]


@pytest.mark.parametrize(
    ("reponse", "attendu"),
    [
        (Reponse(200, b"[]"), ReleveCrt("aucun certificat")),
        (Reponse(200, b""), ReleveCrt("aucun certificat")),
        (Reponse(502, b""), ReleveCrt("échec 502")),
        (Reponse(200, b"<html>"), ReleveCrt("illisible")),
    ],
)
def test_releve_crt_sans_donnees(reponse: Reponse, attendu: ReleveCrt) -> None:
    client, _ = _client({"https://crt.sh/?q=conseil-fictif.test&output=json": reponse})
    assert relever_crt(client, "conseil-fictif.test") == attendu


def test_jamais_d_appel_vers_le_domaine_recherche() -> None:
    client, simule = _client({})
    client.declarer_serveurs_rdap(["https://rdap.conseil-fictif.test/"])
    serveurs = {"test": "https://rdap.conseil-fictif.test/"}
    with pytest.raises(HoteRefuseError):
        relever_rdap(client, serveurs, "conseil-fictif.test")
    assert simule.urls == []


def test_aucune_donnee_personnelle_ne_sort_du_releve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.chdir(tmp_path)
    caplog.set_level(logging.DEBUG)
    corps_casse = json.dumps(RDAP).encode()[:-5]  # réponse tronquée : chemin d'erreur
    resultats: list[object] = []
    for corps in (json.dumps(RDAP).encode(), corps_casse):
        client, _, serveurs = _pret({SERVEUR + "domain/conseil-fictif.test": Reponse(200, corps)})
        resultats.append(relever_rdap(client, serveurs, "conseil-fictif.test"))
    sortie = repr(resultats) + caplog.text
    sortie += "".join(f.read_text(errors="replace") for f in tmp_path.rglob("*") if f.is_file())
    for trace in PERSONNE:
        assert trace not in sortie
    assert list(tmp_path.iterdir()) == []
