#!/usr/bin/env python3
"""Recalcule la region de chaque neurologue a partir de son departement.

Necessaire apres une correction de DEPT_TO_REGION : la colonne `region` est
ecrite au chargement, une base deja chargee garde l'ancienne valeur.

Usage :
    python scripts/fix_regions.py --db chemin/neurologues.db
    python scripts/fix_regions.py --db ... --dry-run
"""
import argparse
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))


def load_mapping():
    """Lit DEPT_TO_REGION depuis load_rpps.py (source unique de verite)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "load_rpps_mod", os.path.join(HERE, "load_rpps.py"))
    # load_rpps.py importe models a l'import : on neutralise ce side-effect
    sys.modules.setdefault("models", type(sys)("models"))
    sys.modules["models"].Neurologue = object
    sys.modules["models"].SessionLocal = lambda: None
    sys.modules["models"].init_db = lambda: None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.DEPT_TO_REGION


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    here = os.path.abspath(HERE)
    for cand in (os.path.join(here, "..", "backend"), os.path.join(here, ".."), here):
        if os.path.isfile(os.path.join(cand, "models.py")):
            sys.path.insert(0, os.path.abspath(cand))
            break
    os.environ["DATABASE_URL"] = "sqlite:///%s" % os.path.abspath(args.db)
    from models import Neurologue, SessionLocal, init_db

    mapping = load_mapping()
    init_db()
    db = SessionLocal()

    changed = Counter()
    fixed = 0
    unresolved = 0
    try:
        for doc in db.query(Neurologue).all():
            dep = (doc.departement or "").strip()
            if not dep:
                unresolved += 1
                continue
            new_region = mapping.get(dep)
            if new_region is None:
                unresolved += 1
                continue
            if doc.region != new_region:
                changed["%s -> %s" % (doc.region, new_region)] += 1
                if not args.dry_run:
                    doc.region = new_region
                fixed += 1
        if not args.dry_run:
            db.commit()
    finally:
        db.close()

    print("Corrections de region: %d" % fixed)
    for k, v in changed.most_common():
        print("   %-30s %d" % (k, v))
    print("Departements sans region officielle (laisses inchanges): %d" % unresolved)
    if args.dry_run:
        print("DRY RUN: aucune ecriture")
    return 0


if __name__ == "__main__":
    sys.exit(main())
