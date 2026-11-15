#!/usr/bin/env python3
"""Verifie l'integrite de la base RPPS apres un chargement.

Sort avec un code != 0 si la base est inexploitable : c'est le garde-fou
qui empeche le script de mise a jour mensuel de remetter en service une
base vide ou tronquee.

Controles :
  - la base existe et s'ouvre
  - le nombre de neurologues est dans une fourchette plausible
  - chaque departement porte la region officielle (table unique de verite)
  - aucune region inconnue de la table
  - le schema expose les colonnes attendues par l'API

Usage :
    python scripts/verify_load.py --db chemin/neurologues.db
    python scripts/verify_load.py --db ... --min-rows 3000 --max-rows 5000
"""
import argparse
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# Colonnes lues par backend/main.py : si l'une disparait, l'API casse.
REQUIRED_COLUMNS = (
    "id_ppss", "nom", "prenom", "departement", "region",
    "code_postal", "commune", "tel", "statut",
)


def load_mapping():
    """Lit DEPT_TO_REGION depuis load_rpps.py (source unique de verite)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "load_rpps_mod", os.path.join(HERE, "load_rpps.py"))
    if spec is None or spec.loader is None:
        raise RuntimeError("impossible de charger load_rpps.py")
    # load_rpps.py importe models a l'import : on neutralise ce side-effect
    stub = type(sys)("models")
    stub.Neurologue = object  # type: ignore[attr-defined]
    stub.SessionLocal = lambda: None  # type: ignore[attr-defined]
    stub.init_db = lambda: None  # type: ignore[attr-defined]
    sys.modules.setdefault("models", stub)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.DEPT_TO_REGION


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--min-rows", type=int, default=3000,
                        help="nombre minimal de neurologues attendu")
    parser.add_argument("--max-rows", type=int, default=5000,
                        help="nombre maximal de neurologues attendu")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    errors = []
    warnings = []

    if not os.path.isfile(args.db):
        print("ECHEC: base absente: %s" % args.db)
        return 2

    try:
        c = sqlite3.connect("file:%s?mode=ro" % args.db, uri=True)
    except sqlite3.Error as e:
        print("ECHEC: base illisible (%s)" % e)
        return 2

    try:
        tables = [r[0] for r in c.execute(
            "select name from sqlite_master where type='table'")]
        if "neurologues" not in tables:
            print("ECHEC: table 'neurologues' absente (tables: %s)" % tables)
            return 2

        cols = [r[1] for r in c.execute("pragma table_info(neurologues)")]
        missing = [c for c in REQUIRED_COLUMNS if c not in cols]
        if missing:
            errors.append("colonnes manquantes: %s" % ", ".join(missing))

        total = c.execute("select count(*) from neurologues").fetchone()[0]
        if total < args.min_rows:
            errors.append("seulement %d neurologues (minimum %d) : "
                          "chargement incomplet ?" % (total, args.min_rows))
        elif total > args.max_rows:
            warnings.append("%d neurologues (maximum attendu %d)"
                            % (total, args.max_rows))

        regions = c.execute(
            "select count(distinct region) from neurologues "
            "where region is not null and region<>''").fetchone()[0]
        no_region = c.execute(
            "select count(*) from neurologues "
            "where region is null or region=''").fetchone()[0]
        with_tel = c.execute(
            "select count(*) from neurologues "
            "where tel is not null and tel<>''").fetchone()[0]
        depts = c.execute(
            "select count(distinct departement) from neurologues "
            "where departement is not null and departement<>''").fetchone()[0]

        mapping = load_mapping()
        official = set(mapping.values())

        mismatches = []
        for dep, reg, n in c.execute(
                "select departement, region, count(*) from neurologues "
                "where departement is not null and departement<>'' "
                "group by 1, 2"):
            if mapping.get(dep) != reg:
                mismatches.append((dep, reg, mapping.get(dep), n))
        if mismatches:
            errors.append("%d couples departement/region incoherents : %s"
                          % (len(mismatches), mismatches[:5]))

        unknown = sorted({
            r[0] for r in c.execute(
                "select distinct region from neurologues "
                "where region is not null and region<>''")
            if r[0] not in official})
        if unknown:
            errors.append("regions inconnues de la table officielle: %s"
                          % ", ".join(unknown))
    finally:
        c.close()

    if not args.quiet:
        print("Base       : %s" % args.db)
        print("Neurologues: %d" % total)
        print("Regions    : %d distinctes, %d sans region" % (regions, no_region))
        print("Departements: %d distincts" % depts)
        print("Avec tel   : %d" % with_tel)

    for w in warnings:
        print("AVERTISSEMENT: %s" % w)
    for e in errors:
        print("ERREUR: %s" % e)

    if errors:
        print("ECHEC: base non conforme, ne pas la remettre en service")
        return 1
    print("OK: base conforme")
    return 0


if __name__ == "__main__":
    sys.exit(main())
