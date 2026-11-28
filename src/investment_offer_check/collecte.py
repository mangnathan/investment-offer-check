"""Commandes de collecte : « quotidienne » et « rattrapage ».

Dossier de données (le dépôt privé de la collecte) :
- instantanes/AAAA-MM-JJ.json : liste de l'AMF filtrée, avec ses métadonnées et ses versions ;
- releves.jsonl : une ligne par domaine relevé (quatre champs RDAP et crt.sh). Un domaine déjà
  présent n'est jamais relevé à nouveau : ce fichier tient lieu de cache et permet la reprise ;
- bilans/AAAA-MM-JJ.json et bilans/rattrapage-AAAA-MM-JJ.json : comptages de l'exécution.

La collecte quotidienne relève les domaines inscrits à partir de DEBUT_PROSPECTIF, le lendemain
de la fermeture du test rétrospectif. Le rattrapage relève une seule fois les domaines du test
rétrospectif, moins les 20 domaines de la mesure de faisabilité, et ne calcule aucune
statistique sur eux : seulement le nombre d'appels, de relevés et d'échecs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Iterable
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from investment_offer_check.liste_amf import (
    Entree,
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
from investment_offer_check.plateformes import Genre, identifier
from investment_offer_check.releves import (
    ReleveCrt,
    ReleveRdap,
    lire_amorcage,
    relever_crt,
    relever_rdap,
)
from investment_offer_check.reseau import (
    Client,
    HoteRefuseError,
    PlafondAtteintError,
    RedirectionRefuseeError,
    RefusDeQuotaError,
    ReponseTropGrosseError,
    ReseauError,
)

DEBUT_PROSPECTIF = "2026-11-28"
# Empreinte publiée dans docs/exclusions-test.md le 27 novembre 2026.
EMPREINTE_EXCLUS = "a5584dc36f0062a55eefdaf34edf579adaa865f95dbbdd41a0d3402056bae80a"
PLAFONDS_QUOTIDIENS = {"datagouv": 3, "iana": 1, "rdap": 30, "crt": 30}
PAUSES = {"datagouv": 1.0, "iana": 0.0, "rdap": 2.0, "crt": 15.0}
CODE_ARRET_QUOTA = 2


def _ecrire(chemin: Path, texte: str) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("w", encoding="utf-8", newline="\n") as f:
        f.write(texte)


def _json(objet: Any) -> str:
    return json.dumps(objet, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def dernier_instantane(dossier: Path) -> tuple[dict[str, Any], list[Entree]] | None:
    fichiers = sorted((dossier / "instantanes").glob("*.json"))
    if not fichiers:
        return None
    return lire_instantane(fichiers[-1].read_text(encoding="utf-8"))


def releves_faits(dossier: Path) -> set[str]:
    chemin = dossier / "releves.jsonl"
    if not chemin.exists():
        return set()
    return {json.loads(ligne)["domaine"] for ligne in chemin.read_text("utf-8").splitlines()}


def a_relever(
    entrees: Iterable[Entree], faits: set[str], du: str, au: str | None = None
) -> list[tuple[str, str]]:
    """Domaines propres aux entités, inscrits dans la période, pas encore relevés."""
    premiers: dict[str, str] = {}
    for e in entrees:
        if e.genre != Genre.DOMAINE.value or e.nom in faits or e.date_inscription < du:
            continue
        if au is not None and e.date_inscription > au:
            continue
        if e.nom not in premiers or e.date_inscription < premiers[e.nom]:
            premiers[e.nom] = e.date_inscription
    return sorted((date, domaine) for domaine, date in premiers.items())


def _sans_exception(appel: Any, *args: Any) -> Any:
    """Un échec sur un domaine est noté pour ce domaine ; seuls le plafond et le quota arrêtent."""
    try:
        return appel(*args)
    except RedirectionRefuseeError:
        return "redirection refusée"
    except HoteRefuseError:
        return "hôte refusé"
    except (ReseauError, ReponseTropGrosseError) as erreur:
        return f"échec réseau ({type(erreur).__name__})"


def relever_domaines(
    client: Client, dossier: Path, domaines: list[tuple[str, str]], jour: str
) -> dict[str, Any]:
    compte: dict[str, Any] = {"a_relever": len(domaines), "releves": 0, "echecs": 0, "arret": None}
    if not domaines:
        return compte
    try:
        serveurs = lire_amorcage(client)
        for date_inscription, domaine in domaines:
            rdap = _sans_exception(relever_rdap, client, serveurs, domaine)
            crt = _sans_exception(relever_crt, client, domaine)
            rdap = rdap if isinstance(rdap, ReleveRdap) else ReleveRdap(rdap)
            crt = crt if isinstance(crt, ReleveCrt) else ReleveCrt(crt)
            ligne = {
                "domaine": domaine,
                "date_inscription": date_inscription,
                "date_releve": jour,
                "rdap": asdict(rdap),
                "crt": asdict(crt),
            }
            chemin = dossier / "releves.jsonl"
            chemin.parent.mkdir(parents=True, exist_ok=True)
            with chemin.open("a", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps(ligne, ensure_ascii=False, sort_keys=True) + "\n")
            compte["releves"] += 1
            compte["echecs"] += int(rdap.statut != "trouvé") + int(crt.statut != "trouvé")
    except PlafondAtteintError as erreur:
        compte["arret"] = f"plafond {erreur}"
    except RefusDeQuotaError:
        compte["arret"] = "refus de quota"
    return compte


def quotidienne(dossier: Path, client: Client, jour: str) -> int:
    precedent = dernier_instantane(dossier)
    meta = lire_metadonnees(client)
    meta_precedente = Metadonnees(**precedent[0]["source"]) if precedent else None
    bilan: dict[str, Any] = {"date": jour, "fichier_inchange": meta.identiques(meta_precedente)}
    if bilan["fichier_inchange"] and precedent:
        entrees = precedent[1]
    else:
        contenu = telecharger(client)
        calcul = empreintes(contenu)
        lecture = lire_csv(contenu)
        meta_instantane = {
            "date_collecte": jour,
            "source": asdict(meta),
            "empreintes": calcul,
            "taille": len(contenu),
            "versions": versions(),
        }
        _ecrire(dossier / "instantanes" / f"{jour}.json", instantane_json(lecture, meta_instantane))
        entrees = lecture.entrees
        nouvelles, retirees = ecart(precedent[1] if precedent else [], entrees)
        bilan |= {
            "lecture": lecture.bilan(),
            "nouvelles": len(nouvelles),
            "retirees": len(retirees),
            "ecart_somme_de_controle": meta.analysis_checksum not in (None, calcul["sha1"]),
        }
    domaines = a_relever(entrees, releves_faits(dossier), DEBUT_PROSPECTIF)
    bilan["releves"] = relever_domaines(client, dossier, domaines, jour)
    bilan["appels"] = dict(client.appels)
    bilan["redirections_refusees"] = dict(client.redirections_refusees)
    _ecrire(dossier / "bilans" / f"{jour}.json", _json(bilan))
    print(_json(bilan), end="")
    return CODE_ARRET_QUOTA if bilan["releves"]["arret"] == "refus de quota" else 0


def domaines_exclus(fichier: Path) -> set[str]:
    contenu = fichier.read_bytes()
    if hashlib.sha256(contenu).hexdigest() != EMPREINTE_EXCLUS:
        raise ValueError("liste des domaines exclus différente de celle publiée le 27 novembre")
    return {identifier(ligne).nom for ligne in contenu.decode("utf-8").split()}


def rattrapage(
    dossier: Path, client: Client, liste: Path, exclus: Path, du: str, au: str, jour: str
) -> int:
    retires = domaines_exclus(exclus)
    entrees = [e for e in lire_csv(liste.read_bytes()).entrees if e.nom not in retires]
    domaines = a_relever(entrees, releves_faits(dossier), du, au)
    releves = relever_domaines(client, dossier, domaines, jour)
    bilan = {
        "date": jour,
        "periode": [du, au],
        "domaines_exclus": len(retires),
        "releves": releves,
        "appels": dict(client.appels),
        "redirections_refusees": dict(client.redirections_refusees),
    }
    _ecrire(dossier / "bilans" / f"rattrapage-{jour}.json", _json(bilan))
    print(_json(bilan), end="")
    return CODE_ARRET_QUOTA if releves["arret"] == "refus de quota" else 0


def main(arguments: list[str] | None = None) -> int:
    analyse = argparse.ArgumentParser(prog="python -m investment_offer_check.collecte")
    commandes = analyse.add_subparsers(dest="commande", required=True)
    q = commandes.add_parser(
        "quotidienne", help="instantané du jour et relevé des nouveaux domaines"
    )
    q.add_argument("--donnees", type=Path, required=True)
    r = commandes.add_parser("rattrapage", help="relevé unique des domaines du test rétrospectif")
    r.add_argument("--donnees", type=Path, required=True)
    r.add_argument("--liste", type=Path, required=True, help="fichier CSV de l'AMF")
    r.add_argument("--exclus", type=Path, required=True)
    r.add_argument("--du", default="2026-01-01")
    r.add_argument("--au", default="2026-11-27")
    r.add_argument("--plafond", type=int, default=300, help="appels RDAP et crt.sh au plus")
    args = analyse.parse_args(arguments)
    jour = datetime.now(UTC).date().isoformat()
    if args.commande == "quotidienne":
        client = Client(plafonds=PLAFONDS_QUOTIDIENS, pauses=PAUSES)
        return quotidienne(args.donnees, client, jour)
    plafonds = {"iana": 1, "rdap": args.plafond, "crt": args.plafond}
    client = Client(plafonds=plafonds, pauses=PAUSES)
    return rattrapage(args.donnees, client, args.liste, args.exclus, args.du, args.au, jour)


if __name__ == "__main__":
    sys.exit(main())
