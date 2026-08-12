#!/usr/bin/env python3
"""Génère un CSV de revue pour valider les corrections d'adresse RPPS.

Lecture seule : ne modifie jamais la DB.
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path

FIELDS = ["adresse", "code_postal", "commune", "departement", "region"]


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main() -> int:
    default_project = Path("G:\\Neuro-liste\\rpps-neuro-app")
    parser = argparse.ArgumentParser(description="Génère un CSV de revue pour valider les corrections d'adresse.")
    parser.add_argument(
        "--db",
        default=str(default_project / "data" / "neurologues.db"),
        help="DB SQLite à inspecter en lecture seule.",
    )
    parser.add_argument(
        "--corrections",
        default=str(default_project / "data" / "corrections" / "adresse_corrections.csv"),
        help="CSV de corrections à comparer avec la DB.",
    )
    parser.add_argument(
        "--out",
        default=str(default_project / "data" / "corrections" / "adresse_corrections_db_check.csv"),
        help="CSV de revue à ouvrir dans Excel/VS Code.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Limiter le nombre de lignes pour un test rapide.")
    args = parser.parse_args()

    db_path = Path(args.db)
    corrections_path = Path(args.corrections)
    out_path = Path(args.out)
    rows = read_csv(corrections_path)
    if args.limit is not None:
        rows = rows[: args.limit]

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    out_columns = [
        "id_ppss",
        "nom",
        "prenom",
        "status",
        "apply_allowed",
        "confidence_recherche",
        "score",
        "source_url",
        "db_status",
    ]
    for field in FIELDS:
        out_columns.append(f"db_{field}")
    for field in FIELDS:
        out_columns.append(f"old_{field}")
    for field in FIELDS:
        out_columns.append(f"new_{field}")
    out_columns.extend(["correction_fields", "notes"])

    counts = {"total": len(rows), "found": 0, "missing": 0, "already_equal": 0, "different": 0}
    out_rows = []

    for row in rows:
        id_ppss = clean(row.get("id_ppss"))
        current = cur.execute(
            """
            SELECT adresse, code_postal, commune, departement, region
            FROM neurologues
            WHERE id_ppss = ?
            """,
            (id_ppss,),
        ).fetchone()

        if current is None:
            counts["missing"] += 1
            db_status = "missing"
            current_values = {field: "" for field in FIELDS}
        else:
            counts["found"] += 1
            db_status = "found"
            current_values = {field: clean(current[field]) for field in FIELDS}

        old_values = {field: clean(row.get(f"{field}_old")) for field in FIELDS}
        new_values = {field: clean(row.get(f"{field}_new")) for field in FIELDS}

        if current is not None:
            if all(clean(current_values[field]) == clean(new_values[field]) for field in FIELDS):
                counts["already_equal"] += 1
            else:
                counts["different"] += 1

        out_rows.append(
            {
                "id_ppss": id_ppss,
                "nom": clean(row.get("nom")),
                "prenom": clean(row.get("prenom")),
                "status": clean(row.get("status")),
                "apply_allowed": clean(row.get("apply_allowed")),
                "confidence_recherche": clean(row.get("confidence_recherche")),
                "score": clean(row.get("score")),
                "source_url": clean(row.get("source_url")),
                "db_status": db_status,
                **{f"db_{field}": current_values[field] for field in FIELDS},
                **{f"old_{field}": old_values[field] for field in FIELDS},
                **{f"new_{field}": new_values[field] for field in FIELDS},
                "correction_fields": clean(row.get("correction_fields")),
                "notes": clean(row.get("notes")),
            }
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=out_columns)
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"db : {db_path}")
    print(f"corrections : {corrections_path}")
    print(f"out : {out_path}")
    print(f"total : {counts['total']}")
    print(f"found_in_db : {counts['found']}")
    print(f"missing_in_db : {counts['missing']}")
    print(f"already_equal_in_db : {counts['already_equal']}")
    print(f"different_from_db : {counts['different']}")
    print("lecture seule : aucune modification DB effectuée")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
