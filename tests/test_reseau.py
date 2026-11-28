"""Tests du client réseau, sans aucun appel réseau : transport et connexion simulés."""

from __future__ import annotations

import http.client
import ssl
from collections.abc import Mapping
from typing import Any

import pytest

from investment_offer_check import reseau
from investment_offer_check.reseau import (
    HOTES_FIXES,
    USER_AGENT,
    AdresseRefuseeError,
    Autorisation,
    Client,
    HoteRefuseError,
    PlafondAtteintError,
    RedirectionRefuseeError,
    RefusDeQuotaError,
    Reponse,
    ReponseTropGrosseError,
    SourceNonDeclareeError,
    transport_https,
    verifier_https,
)


class TransportSimule:
    def __init__(self, statuts: list[int] | None = None) -> None:
        self.statuts = statuts or []
        self.appels: list[tuple[str, dict[str, str], float]] = []

    def __call__(
        self, url: str, entetes: Mapping[str, str], delai: float, autorise: Autorisation
    ) -> Reponse:
        self.appels.append((url, dict(entetes), delai))
        statut = self.statuts.pop(0) if self.statuts else 200
        return Reponse(statut, b"{}")


class Horloge:
    def __init__(self) -> None:
        self.t = 0.0
        self.attentes: list[float] = []

    def maintenant(self) -> float:
        return self.t

    def attendre(self, duree: float) -> None:
        self.attentes.append(duree)
        self.t += duree


def client(transport: TransportSimule, horloge: Horloge | None = None, **kw: Any) -> Client:
    h = horloge or Horloge()
    return Client(
        plafonds=kw.pop("plafonds", {"rdap": 3, "crt": 3}),
        pauses=kw.pop("pauses", {"rdap": 0.0, "crt": 15.0}),
        transport=transport,
        hotes_fixes=kw.pop("hotes_fixes", frozenset({"exemple.test", "statique.test"})),
        attendre=h.attendre,
        horloge=h.maintenant,
        **kw,
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://exemple.test/a",
        "file:///etc/passwd",
        "ftp://exemple.test/a",
        "https:///sans-hote",
        "exemple.test/a",
        "HTTPS//exemple.test",
    ],
)
def test_seul_https_est_accepte(url: str) -> None:
    with pytest.raises(AdresseRefuseeError):
        verifier_https(url)
    transport = TransportSimule()
    with pytest.raises(AdresseRefuseeError):
        client(transport).get("rdap", url)
    assert transport.appels == []


def test_user_agent_generique_et_delai_explicite() -> None:
    transport = TransportSimule()
    client(transport).get("rdap", "https://exemple.test/domain/a.test")
    (_, entetes, delai) = transport.appels[0]
    assert entetes == {"User-Agent": USER_AGENT}
    assert "@" not in USER_AGENT
    assert delai == reseau.DELAI_SECONDES
    assert 0 < delai <= 60


def test_plafond_par_source() -> None:
    transport = TransportSimule()
    c = client(transport, plafonds={"rdap": 2, "crt": 1})
    c.get("rdap", "https://exemple.test/1")
    c.get("rdap", "https://exemple.test/2")
    with pytest.raises(PlafondAtteintError):
        c.get("rdap", "https://exemple.test/3")
    c.get("crt", "https://exemple.test/4")
    assert len(transport.appels) == 3
    assert c.appels == {"rdap": 2, "crt": 1}


@pytest.mark.parametrize(
    ("plafonds", "pauses"),
    [
        ({"crt": 3}, {"rdap": 0.0, "crt": 15.0}),  # sans plafond
        ({"rdap": 3, "crt": 3}, {"crt": 15.0}),  # sans pause
    ],
)
def test_source_non_declaree_refusee(plafonds: dict[str, int], pauses: dict[str, float]) -> None:
    transport = TransportSimule()
    with pytest.raises(SourceNonDeclareeError):
        client(transport, plafonds=plafonds, pauses=pauses).get("rdap", "https://exemple.test/")
    assert transport.appels == []


def test_pause_nulle_ecrite_acceptee() -> None:
    horloge = Horloge()
    c = client(TransportSimule(), horloge)
    c.get("rdap", "https://exemple.test/1")
    c.get("rdap", "https://exemple.test/2")
    assert horloge.attentes == []


def test_arret_au_premier_refus_de_quota_pour_toutes_les_sources() -> None:
    transport = TransportSimule(statuts=[429])
    c = client(transport)
    with pytest.raises(RefusDeQuotaError):
        c.get("crt", "https://exemple.test/1")
    with pytest.raises(RefusDeQuotaError):
        c.get("rdap", "https://exemple.test/2")
    assert len(transport.appels) == 1


def test_pause_entre_deux_appels_de_la_meme_source() -> None:
    horloge = Horloge()
    c = client(TransportSimule(), horloge)
    c.get("crt", "https://exemple.test/1")
    horloge.t += 4.0
    c.get("crt", "https://exemple.test/2")
    c.get("rdap", "https://exemple.test/3")
    assert horloge.attentes == [11.0]


class ConnexionSimulee:
    """Remplace http.client.HTTPSConnection ; les réponses sont rejouées dans l'ordre."""

    reponses: list[tuple[int, dict[str, str], bytes]] = []
    creees: list[dict[str, Any]] = []

    def __init__(self, hote: str, port: int | None, *, timeout: float, context: Any) -> None:
        ConnexionSimulee.creees.append({"hote": hote, "timeout": timeout, "context": context})

    def request(self, methode: str, chemin: str, headers: dict[str, str]) -> None:
        ConnexionSimulee.creees[-1].update(methode=methode, chemin=chemin, headers=headers)

    def getresponse(self) -> ReponseSimulee:
        statut, entetes, corps = ConnexionSimulee.reponses.pop(0)
        return ReponseSimulee(statut, entetes, corps)

    def close(self) -> None:
        pass


class ReponseSimulee:
    def __init__(self, statut: int, entetes: dict[str, str], corps: bytes) -> None:
        self.status = statut
        self._entetes = entetes
        self._corps = corps

    def getheader(self, nom: str) -> str | None:
        return self._entetes.get(nom)

    def read(self, n: int) -> bytes:
        return self._corps[:n]


@pytest.fixture
def connexion(monkeypatch: pytest.MonkeyPatch) -> type[ConnexionSimulee]:
    ConnexionSimulee.reponses = []
    ConnexionSimulee.creees = []
    monkeypatch.setattr(http.client, "HTTPSConnection", ConnexionSimulee)
    return ConnexionSimulee


def test_tls_verifie_par_defaut_et_delai_transmis(connexion: type[ConnexionSimulee]) -> None:
    connexion.reponses = [(200, {}, b"ok")]
    rep = transport_https("https://exemple.test/a?b=1", {"User-Agent": USER_AGENT}, 12.0, _tout)
    assert rep == Reponse(200, b"ok")
    cree = connexion.creees[0]
    assert cree["hote"] == "exemple.test"
    assert cree["chemin"] == "/a?b=1"
    assert cree["timeout"] == 12.0
    contexte = cree["context"]
    assert isinstance(contexte, ssl.SSLContext)
    assert contexte.verify_mode == ssl.CERT_REQUIRED
    assert contexte.check_hostname is True


def test_redirection_suivie_en_https(connexion: type[ConnexionSimulee]) -> None:
    connexion.reponses = [(302, {"Location": "https://statique.test/f.csv"}, b""), (200, {}, b"x")]
    assert transport_https("https://exemple.test/r", {}, 5.0, _tout) == Reponse(200, b"x")
    assert connexion.creees[1]["hote"] == "statique.test"


def test_redirection_vers_http_refusee(connexion: type[ConnexionSimulee]) -> None:
    connexion.reponses = [(301, {"Location": "http://statique.test/f.csv"}, b"")]
    with pytest.raises(AdresseRefuseeError):
        transport_https("https://exemple.test/r", {}, 5.0, _tout)
    assert len(connexion.creees) == 1


def test_trop_de_redirections(connexion: type[ConnexionSimulee]) -> None:
    connexion.reponses = [(302, {"Location": "/boucle"}, b"")] * (reseau.REDIRECTIONS_MAX + 1)
    with pytest.raises(AdresseRefuseeError):
        transport_https("https://exemple.test/boucle", {}, 5.0, _tout)


def test_reponse_trop_grosse(
    connexion: type[ConnexionSimulee], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(reseau, "TAILLE_MAX_OCTETS", 4)
    connexion.reponses = [(200, {}, b"12345")]
    with pytest.raises(ReponseTropGrosseError):
        transport_https("https://exemple.test/gros", {}, 5.0, _tout)


def _tout(cible: str) -> bool:
    return True


def test_liste_fermee_des_hotes_figee() -> None:
    assert (
        frozenset({"www.data.gouv.fr", "amf.s3.sbg.io.cloud.ovh.net", "data.iana.org", "crt.sh"})
        == HOTES_FIXES
    )


def test_hote_hors_liste_refuse_sans_appel() -> None:
    transport = TransportSimule()
    with pytest.raises(HoteRefuseError):
        client(transport).get("rdap", "https://site-de-l-entite.test/")
    assert transport.appels == []
    assert client(transport).appels == {}


def test_serveur_rdap_accepte_seulement_s_il_est_declare() -> None:
    transport = TransportSimule()
    c = client(transport)
    with pytest.raises(HoteRefuseError):
        c.get("rdap", "https://rdap.registre-fictif.test/domain/x.test")
    c.declarer_serveurs_rdap(["https://rdap.registre-fictif.test/"])
    c.get("rdap", "https://rdap.registre-fictif.test/domain/x.test")
    assert len(transport.appels) == 1


def test_jamais_le_domaine_recherche_ni_ses_sous_domaines() -> None:
    transport = TransportSimule()
    c = client(transport)
    c.declarer_serveurs_rdap(["https://rdap.conseil-fictif.test/"])
    with pytest.raises(HoteRefuseError):
        c.get("rdap", "https://rdap.conseil-fictif.test/x", domaine_recherche="conseil-fictif.test")
    with pytest.raises(HoteRefuseError):
        c.get("crt", "https://exemple.test/x", domaine_recherche="exemple.test")
    assert transport.appels == []


def test_redirection_vers_hote_non_autorise_refusee_et_comptee(
    connexion: type[ConnexionSimulee],
) -> None:
    connexion.reponses = [(302, {"Location": "https://ailleurs.test/x"}, b"")]
    c = Client(
        plafonds={"rdap": 3},
        pauses={"rdap": 0.0},
        hotes_fixes=frozenset(),
        attendre=lambda _: None,
    )
    c.declarer_serveurs_rdap(["https://rdap.registre-fictif.test/"])
    with pytest.raises(RedirectionRefuseeError):
        c.get("rdap", "https://rdap.registre-fictif.test/domain/x.test")
    assert c.redirections_refusees == {"rdap": 1}
    assert len(connexion.creees) == 1  # la cible de la redirection n'est jamais contactée


def test_redirection_vers_le_domaine_recherche_refusee(connexion: type[ConnexionSimulee]) -> None:
    connexion.reponses = [(302, {"Location": "https://www.conseil-fictif.test/"}, b"")]
    c = Client(plafonds={"crt": 1}, pauses={"crt": 0.0}, hotes_fixes=frozenset({"crt.sh"}))
    with pytest.raises(RedirectionRefuseeError):
        c.get(
            "crt", "https://crt.sh/?q=conseil-fictif.test", domaine_recherche="conseil-fictif.test"
        )
    assert len(connexion.creees) == 1
