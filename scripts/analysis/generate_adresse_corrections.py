#!/usr/bin/env python3
"""Génère des corrections candidates externes pour les adresses manquantes.

Ce script ne touche jamais la base SQLite. Il lit uniquement le CSV d'audit
produit par audit_adresses_manquantes.py et écrit des fichiers de travail dans
data/corrections.

Sorties :
- adresse_corrections_candidates.csv : lignes à vérifier avant application
- adresse_a_rechercher.csv : sous-ensemble des lignes sans suggestion exploitable
- adresse_corrections_summary.json : comptes et garde-fous
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


AUDIT_COLUMNS = [
    "id_ppss",
    "nom",
    "prenom",
    "code_mode_exercice",
    "mode_exercice",
    "adresse",
    "code_postal",
    "commune",
    "departement",
    "region",
    "tel",
    "mail",
    "structure",
    "categorie",
]

CANDIDATE_COLUMNS = [
    "id_ppss",
    "nom",
    "prenom",
    "code_mode_exercice",
    "categorie_audit",
    "adresse_current",
    "code_postal_current",
    "commune_current",
    "departement_current",
    "region_current",
    "correction_type",
    "suggested_adresse",
    "suggested_code_postal",
    "suggested_commune",
    "suggested_departement",
    "suggested_region",
    "confidence",
    "source",
    "source_url",
    "source_snippet",
    "search_query",
    "status",
    "notes",
]

REGION_BY_DEPARTEMENT = {
    "01": "Auvergne-Rhône-Alpes",
    "03": "Auvergne-Rhône-Alpes",
    "07": "Auvergne-Rhône-Alpes",
    "15": "Auvergne-Rhône-Alpes",
    "26": "Auvergne-Rhône-Alpes",
    "38": "Auvergne-Rhône-Alpes",
    "42": "Auvergne-Rhône-Alpes",
    "43": "Auvergne-Rhône-Alpes",
    "63": "Auvergne-Rhône-Alpes",
    "69": "Auvergne-Rhône-Alpes",
    "73": "Auvergne-Rhône-Alpes",
    "74": "Auvergne-Rhône-Alpes",
    "21": "Bourgogne-Franche-Comté",
    "25": "Bourgogne-Franche-Comté",
    "39": "Bourgogne-Franche-Comté",
    "58": "Bourgogne-Franche-Comté",
    "70": "Bourgogne-Franche-Comté",
    "71": "Bourgogne-Franche-Comté",
    "89": "Bourgogne-Franche-Comté",
    "90": "Bourgogne-Franche-Comté",
    "22": "Bretagne",
    "29": "Bretagne",
    "35": "Bretagne",
    "56": "Bretagne",
    "18": "Centre-Val de Loire",
    "28": "Centre-Val de Loire",
    "36": "Centre-Val de Loire",
    "37": "Centre-Val de Loire",
    "41": "Centre-Val de Loire",
    "45": "Centre-Val de Loire",
    "2A": "Corse",
    "2B": "Corse",
    "67": "Grand Est",
    "68": "Grand Est",
    "54": "Grand Est",
    "55": "Grand Est",
    "57": "Grand Est",
    "08": "Grand Est",
    "10": "Grand Est",
    "51": "Grand Est",
    "52": "Grand Est",
    "02": "Hauts-de-France",
    "60": "Hauts-de-France",
    "80": "Hauts-de-France",
    "59": "Hauts-de-France",
    "76": "Normandie",
    "27": "Normandie",
    "14": "Normandie",
    "50": "Normandie",
    "61": "Normandie",
    "75": "Île-de-France",
    "77": "Île-de-France",
    "78": "Île-de-France",
    "91": "Île-de-France",
    "92": "Île-de-France",
    "93": "Île-de-France",
    "94": "Île-de-France",
    "95": "Île-de-France",
    "72": "Pays de la Loire",
    "44": "Pays de la Loire",
    "49": "Pays de la Loire",
    "53": "Pays de la Loire",
    "85": "Pays de la Loire",
    "04": "Provence-Alpes-Côte d'Azur",
    "05": "Provence-Alpes-Côte d'Azur",
    "06": "Provence-Alpes-Côte d'Azur",
    "13": "Provence-Alpes-Côte d'Azur",
    "83": "Provence-Alpes-Côte d'Azur",
    "84": "Provence-Alpes-Côte d'Azur",
    "11": "Occitanie",
    "12": "Occitanie",
    "30": "Occitanie",
    "31": "Occitanie",
    "32": "Occitanie",
    "34": "Occitanie",
    "46": "Occitanie",
    "48": "Occitanie",
    "65": "Occitanie",
    "66": "Occitanie",
    "81": "Occitanie",
    "82": "Occitanie",
    "16": "Nouvelle-Aquitaine",
    "17": "Nouvelle-Aquitaine",
    "19": "Nouvelle-Aquitaine",
    "23": "Nouvelle-Aquitaine",
    "24": "Nouvelle-Aquitaine",
    "33": "Nouvelle-Aquitaine",
    "40": "Nouvelle-Aquitaine",
    "47": "Nouvelle-Aquitaine",
    "64": "Nouvelle-Aquitaine",
    "79": "Nouvelle-Aquitaine",
    "86": "Nouvelle-Aquitaine",
    "87": "Nouvelle-Aquitaine",
    "971": "Guadeloupe",
    "972": "Martinique",
    "973": "Guyane",
    "974": "La Réunion",
    "976": "Mayotte",
    "984": "Terres australes et antarctiques françaises",
    "986": "Wallis-et-Futuna",
    "987": "Polynésie française",
    "988": "Nouvelle-Calédonie",
}


@dataclass(frozen=True)
class AuditRow:
    raw: dict[str, str]

    @property
    def id_ppss(self) -> str:
        return self.raw.get("id_ppss", "").strip()

    @property
    def nom(self) -> str:
        return self.raw.get("nom", "").strip()

    @property
    def prenom(self) -> str:
        return self.raw.get("prenom", "").strip()

    @property
    def code_mode_exercice(self) -> str:
        return self.raw.get("code_mode_exercice", "").strip()

    @property
    def adresse(self) -> str:
        return self.raw.get("adresse", "").strip()

    @property
    def code_postal(self) -> str:
        return self.raw.get("code_postal", "").strip()

    @property
    def commune(self) -> str:
        return self.raw.get("commune", "").strip()

    @property
    def departement(self) -> str:
        return self.raw.get("departement", "").strip()

    @property
    def region(self) -> str:
        return self.raw.get("region", "").strip()

    @property
    def categorie(self) -> str:
        return self.raw.get("categorie", "").strip()

    @property
    def adresse_vide(self) -> bool:
        return self.adresse == ""

    @property
    def departement_vide(self) -> bool:
        return self.departement == ""

    @property
    def code_postal_vide(self) -> bool:
        return self.code_postal == ""


def normalize(value: object) -> str:
    return "" if value is None else str(value).strip()


def read_audit_rows(path: Path) -> list[AuditRow]:
    if not path.exists():
        raise FileNotFoundError(f"CSV d'audit introuvable : {path}")

    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = set(AUDIT_COLUMNS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Colonnes manquantes dans le CSV d'audit : {sorted(missing)}")
        return [AuditRow({key: normalize(value) for key, value in row.items()}) for row in reader]


def infer_department_from_postal_code(code_postal: str) -> tuple[str, str] | None:
    """Déduit un département/région depuis un code postal français.

    Retourne None si le code postal n'est pas exploitable. La Corse est traitée
    par plage : 20000-20299 => 2A, 20300-20699 => 2B.
    """

    if not code_postal.isdigit() or len(code_postal) != 5:
        return None

    numeric = int(code_postal)

    if 20000 <= numeric <= 20299:
        department = "2A"
    elif 20300 <= numeric <= 20699:
        department = "2B"
    elif numeric in {97100, 97200, 97300, 97400, 97600}:
        department = code_postal[:3]
    elif 97100 <= numeric < 97500:
        department = code_postal[:3]
    elif 98400 <= numeric < 98900:
        department = code_postal[:3]
    elif 1 <= numeric <= 95999:
        department = code_postal[:2]
    else:
        return None

    region = REGION_BY_DEPARTEMENT.get(department, "")
    return department, region


def build_search_query(row: AuditRow) -> str:
    name = " ".join(part for part in [row.nom, row.prenom] if part)
    locality = " ".join(part for part in [row.commune, row.departement] if part)
    return " ".join(part for part in [name, "neurologue", locality] if part)


def candidate_from_department(row: AuditRow) -> dict[str, str]:
    inferred = infer_department_from_postal_code(row.code_postal)
    if inferred is None:
        raise ValueError(f"Code postal non exploitable : {row.id_ppss} {row.code_postal}")

    department, region = inferred
    return {
        "id_ppss": row.id_ppss,
        "nom": row.nom,
        "prenom": row.prenom,
        "code_mode_exercice": row.code_mode_exercice,
        "categorie_audit": row.categorie,
        "adresse_current": row.adresse,
        "code_postal_current": row.code_postal,
        "commune_current": row.commune,
        "departement_current": row.departement,
        "region_current": row.region,
        "correction_type": "departement_from_postal_code",
        "suggested_adresse": row.adresse,
        "suggested_code_postal": row.code_postal,
        "suggested_commune": row.commune,
        "suggested_departement": department,
        "suggested_region": region,
        "confidence": "confirmed",
        "source": "code_postal_french_department_mapping",
        "source_url": "",
        "source_snippet": f"code_postal={row.code_postal}",
        "search_query": "",
        "status": "candidate",
        "notes": "Département déduit du code postal. À vérifier avant application.",
    }


def candidate_to_search(row: AuditRow) -> dict[str, str]:
    return {
        "id_ppss": row.id_ppss,
        "nom": row.nom,
        "prenom": row.prenom,
        "code_mode_exercice": row.code_mode_exercice,
        "categorie_audit": row.categorie,
        "adresse_current": row.adresse,
        "code_postal_current": row.code_postal,
        "commune_current": row.commune,
        "departement_current": row.departement,
        "region_current": row.region,
        "correction_type": "adresse_to_search",
        "suggested_adresse": "",
        "suggested_code_postal": "",
        "suggested_commune": "",
        "suggested_departement": "",
        "suggested_region": "",
        "confidence": "ambigu",
        "source": "to_verify_external_search",
        "source_url": "",
        "source_snippet": "",
        "search_query": build_search_query(row),
        "status": "to_verify",
        "notes": "Aucune suggestion déterministe ; recherche externe requise.",
    }


def iter_candidates(rows: Iterable[AuditRow]) -> Iterable[dict[str, str]]:
    for row in rows:
        if row.departement_vide and not row.code_postal_vide:
            inferred = infer_department_from_postal_code(row.code_postal)
            if inferred is not None:
                yield candidate_from_department(row)
                continue

        if row.adresse_vide:
            yield candidate_to_search(row)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_summary(path: Path, audit_rows: list[AuditRow], candidates: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    by_type = Counter(row["correction_type"] for row in candidates)
    by_status = Counter(row["status"] for row in candidates)
    missing_audit_rows = [row for row in audit_rows if row.adresse_vide or row.departement_vide]
    by_audit_category = Counter(row.categorie for row in missing_audit_rows)
    by_mode = Counter(row.code_mode_exercice or "vide" for row in missing_audit_rows)

    summary = {
        "total_audit_rows": len(audit_rows),
        "missing_address_rows": sum(1 for row in audit_rows if row.adresse_vide),
        "missing_department_rows": sum(1 for row in audit_rows if row.departement_vide),
        "candidate_rows": len(candidates),
        "by_correction_type": dict(sorted(by_type.items())),
        "by_status": dict(sorted(by_status.items())),
        "missing_rows_by_audit_category": dict(sorted(by_audit_category.items())),
        "missing_rows_by_mode": dict(sorted(by_mode.items())),
        "guardrails": [
            "Ce script lit uniquement le CSV d'audit.",
            "Aucune connexion SQLite n'est ouverte.",
            "Aucune correction n'est appliquée en base.",
            "Les lignes code_mode_exercice/mode_exercice ne sont jamais proposées à la correction.",
        ],
    }

    with path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main() -> int:
    default_project = Path("/mnt/g/Neuro-liste/rpps-neuro-app")
    parser = argparse.ArgumentParser(
        description="Génère des corrections candidates externes pour adresses/départements manquants."
    )
    parser.add_argument(
        "--audit",
        default=default_project / "data/analysis/adresses-manquantes/audit_adresses_vides.csv",
        type=Path,
        help="CSV produit par audit_adresses_manquantes.py.",
    )
    parser.add_argument(
        "--out-dir",
        default=default_project / "data/corrections",
        type=Path,
        help="Dossier de sortie pour les corrections candidates.",
    )
    parser.add_argument(
        "--limit",
        default=None,
        type=int,
        help="Optionnel : limite le nombre de lignes candidates générées, utile pour tester.",
    )
    args = parser.parse_args()

    audit_rows = read_audit_rows(args.audit)
    candidates = list(iter_candidates(audit_rows))
    if args.limit is not None:
        candidates = candidates[: args.limit]

    candidates_path = args.out_dir / "adresse_corrections_candidates.csv"
    search_path = args.out_dir / "adresse_a_rechercher.csv"
    summary_path = args.out_dir / "adresse_corrections_summary.json"

    write_csv(candidates_path, CANDIDATE_COLUMNS, candidates)
    search_rows = [row for row in candidates if row["correction_type"] == "adresse_to_search"]
    write_csv(search_path, CANDIDATE_COLUMNS, search_rows)
    write_summary(summary_path, audit_rows, candidates)

    print(f"audit : {args.audit}")
    print(f"candidates : {candidates_path}")
    print(f"a_rechercher : {search_path}")
    print(f"summary : {summary_path}")
    print(f"candidate_rows : {len(candidates)}")
    print(f"adresse_to_search : {sum(1 for row in candidates if row['correction_type'] == 'adresse_to_search')}")
    print(f"departement_from_postal_code : {sum(1 for row in candidates if row['correction_type'] == 'departement_from_postal_code')}")
    print("aucune modification DB effectuée")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
