"""Tout appel réseau passe par le client de reseau.py.

Aucun autre module de src/ n'importe de bibliothèque réseau ni n'ouvre de connexion.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from urllib.parse import urlsplit

from investment_offer_check.reseau import HOTES_FIXES

SRC = Path(__file__).resolve().parents[1] / "src" / "investment_offer_check"
CLIENT = SRC / "reseau.py"
MODULES_INTERDITS = ("urllib.request", "requests", "httpx", "http.client")


def _interdit(nom: str) -> bool:
    return any(nom == m or nom.startswith(m + ".") for m in MODULES_INTERDITS)


def ecarts(chemin: Path) -> list[str]:
    """Imports de bibliothèques réseau et usages de HTTPSConnection trouvés dans un fichier."""
    arbre = ast.parse(chemin.read_text(encoding="utf-8"), filename=str(chemin))
    trouves: list[str] = []
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            trouves += [a.name for a in noeud.names if _interdit(a.name)]
        elif isinstance(noeud, ast.ImportFrom) and noeud.module:
            if _interdit(noeud.module):
                trouves.append(noeud.module)
            else:
                trouves += [
                    f"{noeud.module}.{a.name}"
                    for a in noeud.names
                    if _interdit(f"{noeud.module}.{a.name}")
                ]
        elif (isinstance(noeud, ast.Attribute) and noeud.attr == "HTTPSConnection") or (
            isinstance(noeud, ast.Name) and noeud.id == "HTTPSConnection"
        ):
            trouves.append("HTTPSConnection")
    return trouves


def test_aucun_module_hors_du_client_n_ouvre_de_connexion() -> None:
    fichiers = [f for f in sorted(SRC.rglob("*.py")) if f != CLIENT]
    trouves = {str(f.relative_to(SRC)): e for f in fichiers if (e := ecarts(f))}
    assert trouves == {}


def test_le_controle_detecte_les_ecarts(tmp_path: Path) -> None:
    fautif = tmp_path / "fautif.py"
    fautif.write_text(
        "import requests\n"
        "import urllib.request\n"
        "from urllib import request\n"
        "from httpx import Client\n"
        "import http.client as hc\n"
        "c = hc.HTTPSConnection('x')\n",
        encoding="utf-8",
    )
    assert sorted(ecarts(fautif)) == sorted(
        [
            "requests",
            "urllib.request",
            "urllib.request",
            "httpx",
            "http.client",
            "HTTPSConnection",
        ]
    )


def test_le_client_reste_le_seul_point_d_acces() -> None:
    assert "HTTPSConnection" in ecarts(CLIENT)


def adresses_ecrites(chemin: Path) -> list[str]:
    """Chaînes du code qui commencent par un schéma d'adresse (http, https, ftp...)."""
    arbre = ast.parse(chemin.read_text(encoding="utf-8"), filename=str(chemin))
    return [
        n.value
        for n in ast.walk(arbre)
        if isinstance(n, ast.Constant)
        and isinstance(n.value, str)
        and re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", n.value)
    ]


def test_chaque_adresse_ecrite_vise_un_hote_de_la_liste_fermee() -> None:
    hors_liste = {
        str(f.relative_to(SRC)): adresse
        for f in sorted(SRC.rglob("*.py"))
        for adresse in adresses_ecrites(f)
        if urlsplit(adresse).scheme != "https" or urlsplit(adresse).hostname not in HOTES_FIXES
    }
    assert hors_liste == {}


def test_le_controle_des_adresses_detecte_un_hote_hors_liste(tmp_path: Path) -> None:
    fautif = tmp_path / "fautif.py"
    fautif.write_text('URL = "https://site-de-l-entite.test/"\nX = "http://crt.sh/"\n', "utf-8")
    assert adresses_ecrites(fautif) == ["https://site-de-l-entite.test/", "http://crt.sh/"]
