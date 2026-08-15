#!/usr/bin/env python3
"""Résume un audit CSV d'adresses/départements vides.

Le script est lecture seule : il lit le CSV produit par audit_adresses_manquantes.py
et écrit uniquement des fichiers de synthèse.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


FIELDS = [
    "categorie",
    "count",
    "adresse_vide",
    "departement_vide",
    "mode_vide",
]


def is_empty(value: str) -> bool:
    return value.strip() == ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Résume un CSV d'audit RPPS.")
    parser.add_argument(
        "--input",
        default="G:\\Neuro-liste\\rpps-neuro-app\\data\\analysis\\adresses-manquantes\\audit_adresses_vides.csv",
        help="CSV d'audit en entrée.",
    )
    parser.add_argument(
        "--out-base",
        default="G:\\Neuro-liste\\rpps-neuro-app\\data\\analysis\\adresses-manquantes\\audit_resume_detail",
        help="Base de chemin pour les sorties CSV/JSON.",
    )

    args = parser.parse_args()
    input_path = Path(args.input)
    out_base = Path(args.out_base)

    if not input_path.exists():
        raise FileNotFoundError(f"CSV introuvable : {input_path}")

    grouped: dict[str, dict[str, int]] = defaultdict(lambda: {"count": 0, "adresse_vide": 0, "departement_vide": 0, "mode_vide": 0})
    total_rows = 0

    with input_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_rows += 1
            categorie = row.get("categorie", "inconnu") or "inconnu"
            bucket = grouped[categorie]
            bucket["count"] += 1
            if is_empty(row.get("adresse", "")):
                bucket["adresse_vide"] += 1
            if is_empty(row.get("departement", "")):
                bucket["departement_vide"] += 1
            if is_empty(row.get("code_mode_exercice", "")):
                bucket["mode_vide"] += 1

    rows = [
        {"categorie": categorie, **values}
        for categorie, values in sorted(grouped.items(), key=lambda item: (-item[1]["count"], item[0]))
    ]

    out_base.parent.mkdir(parents=True, exist_ok=True)
    csv_path = out_base.with_suffix(".csv")
    json_path = out_base.with_suffix(".json")

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "source": str(input_path),
                "total_rows": total_rows,
                "categories": rows,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
        f.write("\n")

    print(f"source_rows : {total_rows}")
    print(f"csv : {csv_path}")
    print(f"json : {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
