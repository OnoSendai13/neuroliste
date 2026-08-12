#!/usr/bin/env python3
"""Applique des corrections d'adresse RPPS avec dry-run sécurisé.

Ce script ne modifie jamais code_mode_exercice ou mode_exercice.
Par défaut, il applique uniquement les lignes avec :
- status = confirmed
- apply_allowed = true
- au moins un champ adresse/code_postal/commune/departement/region non vide

Usage typique :
  python scripts/apply_adresse_corrections.py --db neurologues.db --corrections data/corrections/adresse_corrections.csv --dry-run
  python scripts/apply_adresse_corrections.py --db neurologues.db --corrections data/corrections/adresse_corrections.csv --apply --yes-apply
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

APPLICABLE_FIELDS = ["adresse", "code_postal", "commune", "departement", "region"]
FORBIDDEN_FIELDS = ["code_mode_exercice", "mode_exercice"]


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def truthy(value: object) -> bool:
    return clean(value).lower() in {"1", "true", "oui", "yes", "y"}


def read_corrections(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"CSV de corrections introuvable : {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def correction_fields(row: dict[str, str]) -> list[str]:
    explicit = [field.strip() for field in clean(row.get("correction_fields", "")).split(";") if field.strip()]
    if explicit:
        return [field for field in explicit if field in APPLICABLE_FIELDS]

    fields = []
    for field in APPLICABLE_FIELDS:
        if clean(row.get(f"{field}_new")):
            fields.append(field)
    return fields


def build_updates(row: dict[str, str]) -> dict[str, str]:
    updates = {}
    for field in correction_fields(row):
        new_value = clean(row.get(f"{field}_new"))
        if new_value:
            updates[field] = new_value
    return updates


def values_for(row: dict[str, str], fields: Iterable[str]) -> str:
    return json.dumps({field: clean(row.get(f"{field}_new")) for field in fields}, ensure_ascii=False)


def current_values(cur: sqlite3.Cursor, id_ppss: str) -> dict[str, str]:
    row = cur.execute(
        """
        SELECT id_ppss, adresse, code_postal, commune, departement, region,
               code_mode_exercice, mode_exercice
        FROM neurologues
        WHERE id_ppss = ?
        """,
        (id_ppss,),
    ).fetchone()
    if row is None:
        return {}
    return {key: clean(row[key]) for key in row.keys()}


def changed_updates(current: dict[str, str], updates: dict[str, str]) -> dict[str, str]:
    return {field: value for field, value in updates.items() if clean(current.get(field)) != clean(value)}


def write_report(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "id_ppss",
        "nom",
        "prenom",
        "status",
        "apply_allowed",
        "correction_fields",
        "old_values",
        "new_values",
        "changed_updates",
        "db_status",
        "would_apply",
        "would_apply_if_confirmed",
        "skipped_reason",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    default_project = Path("G:\\Neuro-liste\\rpps-neuro-app")
    parser = argparse.ArgumentParser(description="Applique des corrections d'adresse RPPS avec dry-run sécurisé.")
    parser.add_argument(
        "--db",
        default=str(default_project / "data" / "neurologues.db"),
        help="Chemin de la base SQLite neurologues.db.",
    )
    parser.add_argument(
        "--corrections",
        default=str(default_project / "data" / "corrections" / "adresse_corrections.csv"),
        help="CSV de corrections externe.",
    )
    parser.add_argument(
        "--report",
        default=str(default_project / "data" / "corrections" / "apply_adresse_corrections_report.csv"),
        help="CSV de rapport produit par le dry-run ou l'apply.",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Liste les lignes concernées sans écrire en DB.")
    mode.add_argument("--apply", action="store_true", help="Applique les corrections confirmées en DB.")
    parser.add_argument(
        "--yes-apply",
        action="store_true",
        help="Confirmation explicite requise avec --apply.",
    )
    parser.add_argument(
        "--include-pending",
        action="store_true",
        help="Inclut les lignes pending_review dans le dry-run comme lignes à valider.",
    )
    parser.add_argument(
        "--allow-pending",
        action="store_true",
        help="Avec --apply, autorise aussi les lignes pending_review. Réservé aux tests ou validations explicites.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limite le nombre de lignes traitées, utile pour tester.",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    corrections_path = Path(args.corrections)
    report_path = Path(args.report)

    if not db_path.exists():
        raise FileNotFoundError(f"DB introuvable : {db_path}")

    corrections = read_corrections(corrections_path)
    if args.limit is not None:
        corrections = corrections[: args.limit]

    mode_name = "apply" if args.apply else "dry-run"
    print(f"mode : {mode_name}")
    print(f"db : {db_path}")
    print(f"corrections : {corrections_path}")
    print(f"report : {report_path}")

    if args.apply and not args.yes_apply:
        raise SystemExit("--apply nécessite --yes-apply. Relancez uniquement après validation humaine.")
    if args.apply and args.allow_pending:
        print("warning : --allow-pending applique aussi des lignes pending_review ; à utiliser seulement sur copie DB ou après validation explicite.")

    conn = sqlite3.connect(f"file:{db_path}?mode={'rw' if args.apply else 'ro'}", uri=True)
    conn.row_factory = sqlite3.Row
    report_rows: list[dict[str, str]] = []
    counts = {
        "total": len(corrections),
        "pending_review": 0,
        "confirmed": 0,
        "would_apply": 0,
        "would_apply_if_confirmed": 0,
        "rows_with_updates": 0,
        "not_found_in_db": 0,
        "skipped_no_updates": 0,
        "skipped_missing_fields": 0,
        "skipped_pending_apply": 0,
        "pending_applied": 0,
        "updated": 0,
    }

    try:
        cur = conn.cursor()
        for row in corrections:
            id_ppss = clean(row.get("id_ppss"))
            status = clean(row.get("status")) or "pending_review"
            apply_allowed = truthy(row.get("apply_allowed"))
            fields = correction_fields(row)
            updates = build_updates(row)
            skipped_reason = ""
            would_apply = False
            would_apply_if_confirmed = False

            if not id_ppss:
                skipped_reason = "missing_id_ppss"
            elif not fields:
                counts["skipped_missing_fields"] += 1
                skipped_reason = "no_applicable_address_fields"
            elif not updates:
                counts["skipped_no_updates"] += 1
                skipped_reason = "no_non_empty_new_values"
            elif status == "pending_review":
                counts["pending_review"] += 1
                counts["would_apply_if_confirmed"] += 1
                would_apply_if_confirmed = True
                if args.apply and not args.allow_pending:
                    counts["skipped_pending_apply"] += 1
                    skipped_reason = "pending_review_not_applicable_for_apply"
                elif args.apply and args.allow_pending:
                    counts["pending_applied"] += 1
                    would_apply = True
                    counts["would_apply"] += 1
                elif not args.include_pending:
                    skipped_reason = "pending_review_skipped_in_dry_run_without_include_pending"
            elif status == "confirmed" and apply_allowed:
                counts["confirmed"] += 1
                would_apply = True
                counts["would_apply"] += 1
            elif status == "confirmed" and not apply_allowed:
                counts["confirmed"] += 1
                skipped_reason = "confirmed_but_apply_allowed_false"
            else:
                skipped_reason = f"status_{status}_not_applicable"

            current: dict[str, str] = {}
            changed: dict[str, str] = {}
            db_status = "not_checked"
            if id_ppss and fields and updates and skipped_reason == "":
                current = current_values(cur, id_ppss)
                if not current:
                    counts["not_found_in_db"] += 1
                    db_status = "not_found"
                    skipped_reason = "id_ppss_not_found_in_db"
                else:
                    db_status = "found"
                    changed = changed_updates(current, updates)
                    if not changed:
                        counts["skipped_no_updates"] += 1
                        skipped_reason = "no_difference_with_current_db_values"
                    elif args.apply:
                        assignments = ", ".join(f"{field} = ?" for field in changed)
                        values = list(changed.values()) + [id_ppss]
                        cur.execute(f"UPDATE neurologues SET {assignments} WHERE id_ppss = ?", values)
                        counts["updated"] += 1
                        db_status = "updated"
                    else:
                        counts["rows_with_updates"] += 1
                        db_status = "would_update"

            report_rows.append(
                {
                    "id_ppss": id_ppss,
                    "nom": clean(row.get("nom")),
                    "prenom": clean(row.get("prenom")),
                    "status": status,
                    "apply_allowed": str(apply_allowed).lower(),
                    "correction_fields": ";".join(fields),
                    "old_values": json.dumps({field: clean(current.get(field)) for field in fields}, ensure_ascii=False),
                    "new_values": values_for(row, fields),
                    "changed_updates": json.dumps(changed, ensure_ascii=False),
                    "db_status": db_status,
                    "would_apply": str(would_apply).lower(),
                    "would_apply_if_confirmed": str(would_apply_if_confirmed).lower(),
                    "skipped_reason": skipped_reason,
                }
            )

        if args.apply:
            conn.commit()
        else:
            conn.rollback()

        write_report(report_path, report_rows)

        print(f"total corrections rows : {counts['total']}")
        print(f"pending_review : {counts['pending_review']}")
        print(f"confirmed : {counts['confirmed']}")
        print(f"would_apply_if_confirmed : {counts['would_apply_if_confirmed']}")
        print(f"would_apply : {counts['would_apply']}")
        print(f"rows_with_updates : {counts['rows_with_updates']}")
        print(f"updated : {counts['updated']}")
        print(f"not_found_in_db : {counts['not_found_in_db']}")
        print(f"skipped_missing_fields : {counts['skipped_missing_fields']}")
        print(f"skipped_no_updates : {counts['skipped_no_updates']}")
        print(f"skipped_pending_apply : {counts['skipped_pending_apply']}")
        print(f"pending_applied : {counts['pending_applied']}")
        if args.dry_run:
            print("dry-run : aucune modification DB effectuée")
        else:
            print("apply : transaction commit effectuée")
        print(f"report : {report_path}")
        print(f"generated_at : {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
