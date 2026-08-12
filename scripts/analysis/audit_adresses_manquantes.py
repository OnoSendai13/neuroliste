#!/usr/bin/env python3
"""Audit lecture seule des adresses et départements vides.

Ce script ne modifie jamais la base SQLite : il n'exécute que des SELECT.
Il exporte un CSV exploitable pour préparer les corrections externes.
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Iterable, Mapping


COLUMNS = [
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


def normalize(value: object) -> str:
    return "" if value is None else str(value).strip()


def is_empty(value: object) -> bool:
    return normalize(value) == ""


def categorize(row: sqlite3.Row) -> str:
    adresse_vide = is_empty(row["adresse"])
    departement_vide = is_empty(row["departement"])
    mode_code = normalize(row["code_mode_exercice"])
    mode_label = normalize(row["mode_exercice"])

    if not adresse_vide and not departement_vide:
        return "complet"

    if mode_code == "" and mode_label == "":
        return "mode_vide_adresse_departement_vides"

    if mode_code == "L":
        if departement_vide:
            return "liberal_sans_departement"
        if adresse_vide:
            return "liberal_adresse_vide_departement_present"

    if mode_code == "S":
        if departement_vide:
            return "salarie_sans_departement"
        if adresse_vide:
            return "salarie_adresse_vide_departement_present"

    return "autre_auditer"


def iter_rows(conn: sqlite3.Connection) -> Iterable[dict[str, str]]:
    conn.row_factory = sqlite3.Row
    query = """
        SELECT
            id_ppss,
            nom,
            prenom,
            code_mode_exercice,
            mode_exercice,
            adresse,
            code_postal,
            commune,
            departement,
            region,
            tel,
            mail,
            structure
        FROM neurologues
        ORDER BY
            CASE
                WHEN code_mode_exercice IS NULL OR trim(code_mode_exercice) = '' THEN 0
                WHEN code_mode_exercice = 'L' THEN 1
                WHEN code_mode_exercice = 'S' THEN 2
                ELSE 3
            END,
            departement,
            commune,
            nom,
            prenom
    """
    for row in conn.execute(query):
        yield {
            **{key: row[key] for key in row.keys()},
            "categorie": categorize(row),
        }


def write_audit_csv(rows: Iterable[dict[str, str]], out_path: Path) -> dict[str, object]:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    counts: Counter[str] = Counter()
    stats: Counter[str] = Counter()
    total = 0

    with out_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()

        for row in rows:
            adresse_vide = is_empty(row["adresse"])
            departement_vide = is_empty(row["departement"])
            record = {column: row[column] for column in COLUMNS}
            writer.writerow(record)
            counts[record["categorie"]] += 1
            stats["total"] += 1
            if adresse_vide:
                stats["adresses_vides"] += 1
            if departement_vide:
                stats["departements_vides"] += 1
            if adresse_vide and departement_vide:
                stats["adresses_departements_vides"] += 1
            total += 1

    return {"counts": dict(counts), "stats": dict(stats), "total": total}


def write_summary(counts: Mapping[str, int], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path = out_path.with_suffix(".csv")
    json_path = out_path.with_suffix(".json")

    rows = [
        {"categorie": key, "count": value}
        for key, value in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]

    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["categorie", "count"])
        writer.writeheader()
        writer.writerows(rows)

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Exporte un audit lecture seule des adresses et départements vides."
    )
    parser.add_argument(
        "--db",
        default="/home/laurent/.local/share/rpps-neuro/data/neurologues.db",
        help="Chemin de la base SQLite RPPS neurologues.",
    )
    parser.add_argument(
        "--out",
        default="/mnt/g/Neuro-liste/rpps-neuro-app/data/analysis/adresses-manquantes/audit_adresses_vides.csv",
        help="Chemin du CSV de sortie.",
    )
    parser.add_argument(
        "--summary",
        default="/mnt/g/Neuro-liste/rpps-neuro-app/data/analysis/adresses-manquantes/audit_resume",
        help="Base de chemin pour les fichiers résumé CSV/JSON de sortie.",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    out_path = Path(args.out)
    summary_path = Path(args.summary)

    if not db_path.exists():
        raise FileNotFoundError(f"DB introuvable : {db_path}")

    if not db_path.is_file():
        raise FileNotFoundError(f"Ce n'est pas un fichier SQLite : {db_path}")

    print(f"DB : {db_path}")
    print(f"CSV audit : {out_path}")
    print(f"Résumé : {summary_path}.csv / {summary_path}.json")

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        total = conn.execute("SELECT COUNT(*) FROM neurologues").fetchone()[0]
        print(f"total neurologues : {total}")

        result = write_audit_csv(iter_rows(conn), out_path)
        if not isinstance(result["counts"], dict) or not isinstance(result["stats"], dict):
            raise RuntimeError("Audit result has invalid shape")
        counts = result["counts"]
        stats = result["stats"]
        write_summary(counts, summary_path)

        print(f"adresses vides : {stats.get('adresses_vides', 0)}")
        print(f"départements vides : {stats.get('departements_vides', 0)}")
        print(f"adresses + départements vides : {stats.get('adresses_departements_vides', 0)}")
        for key in sorted(counts):
            print(f"{key} : {counts[key]}")

        print("audit terminé : aucune modification DB effectuée")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
