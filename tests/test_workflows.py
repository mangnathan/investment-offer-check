"""Règles de sécurité des workflows GitHub, vérifiées sur le texte des fichiers.

- aucune action n'est référencée par une étiquette, qui peut être déplacée : seulement par SHA ;
- aucun checkout ne garde le jeton dans `.git` ;
- le jeton de GitHub n'est donné qu'étape par étape ;
- aucun déclencheur `pull_request_target`, qui donne des droits d'écriture à du code de fork ;
- une valeur venue de l'extérieur (`inputs`, `github.event`) n'est jamais collée dans un script
  shell : elle passe par une variable d'environnement ;
- chaque job a une durée maximale explicite : le délai du client réseau vaut par opération,
  pas pour une exécution entière.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

DOSSIER = Path(__file__).resolve().parents[1] / ".github" / "workflows"
WORKFLOWS = sorted(DOSSIER.glob("*.yml"))
USES = re.compile(r"^\s*-?\s*uses:\s*(\S+)")
EPINGLEE = re.compile(r"^[\w.-]+/[\w.-]+(/[\w./-]+)?@[0-9a-f]{40}$")
VALEUR_EXTERIEURE = re.compile(r"\$\{\{[^}]*\b(inputs\.|github\.event\.)")
AFFECTATION_ENV = re.compile(r"^\s+[A-Z_][A-Z0-9_]*:\s*\$\{\{")
JETON = re.compile(r"^(\s*)GH_TOKEN:")


def test_les_workflows_sont_trouves() -> None:
    assert DOSSIER / "ci.yml" in WORKFLOWS


@pytest.mark.parametrize("chemin", WORKFLOWS, ids=lambda p: p.name)
def test_actions_epinglees_par_sha(chemin: Path) -> None:
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        trouve = USES.match(ligne)
        if trouve:
            assert EPINGLEE.match(trouve.group(1)), f"{chemin.name} : {trouve.group(1)}"


@pytest.mark.parametrize("chemin", WORKFLOWS, ids=lambda p: p.name)
def test_aucun_checkout_ne_garde_le_jeton(chemin: Path) -> None:
    texte = chemin.read_text(encoding="utf-8")
    checkouts = len(re.findall(r"uses:\s*actions/checkout@", texte))
    assert texte.count("persist-credentials: false") == checkouts


@pytest.mark.parametrize("chemin", WORKFLOWS, ids=lambda p: p.name)
def test_le_jeton_n_est_donne_qu_etape_par_etape(chemin: Path) -> None:
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        trouve = JETON.match(ligne)
        if trouve:
            # Dix espaces : l'env d'une étape ; moins, ce serait tout le job ou tout le workflow.
            assert len(trouve.group(1)) == 10, f"{chemin.name} : {ligne.strip()}"


@pytest.mark.parametrize("chemin", WORKFLOWS, ids=lambda p: p.name)
def test_aucun_declencheur_ne_donne_l_ecriture_a_un_fork(chemin: Path) -> None:
    assert "pull_request_target" not in chemin.read_text(encoding="utf-8")


@pytest.mark.parametrize("chemin", WORKFLOWS, ids=lambda p: p.name)
def test_valeurs_exterieures_par_l_environnement_seulement(chemin: Path) -> None:
    for numero, ligne in enumerate(chemin.read_text(encoding="utf-8").splitlines(), start=1):
        if VALEUR_EXTERIEURE.search(ligne):
            assert AFFECTATION_ENV.match(ligne), f"{chemin.name}, ligne {numero} : {ligne.strip()}"


@pytest.mark.parametrize("chemin", WORKFLOWS, ids=lambda p: p.name)
def test_chaque_job_a_une_duree_maximale(chemin: Path) -> None:
    texte = chemin.read_text(encoding="utf-8")
    assert texte.count("runs-on:") == len(re.findall(r"^\s+timeout-minutes:\s*\d+", texte, re.M))
