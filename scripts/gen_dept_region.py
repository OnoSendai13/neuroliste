"""Genere le bloc DEPT_TO_REGION a partir de l'API Geo officielle de l'Etat.

Source : https://geo.api.gouv.fr/departements?fields=code,nom,region

Usage :
    python scripts/gen_dept_region.py                 # affiche le bloc
    python scripts/gen_dept_region.py --patch FILE    # reecrit le bloc dans FILE
"""
import argparse
import json
import re
import sys
import unicodedata
import urllib.request

URL = "https://geo.api.gouv.fr/departements?fields=code,nom,region&format=json"

# Codes courts utilises par l'UI (frontend/src/components/FilterPanel.jsx)
REGION_CODES = {
    "Auvergne-Rhone-Alpes": "AuRA",
    "Bourgogne-Franche-Comte": "BFC",
    "Bretagne": "BIF",
    "Centre-Val de Loire": "Centre-Val",
    "Corse": "Corse",
    "Grand Est": "Grand Est",
    "Guadeloupe": "GP",
    "Guyane": "GF",
    "Hauts-de-France": "HDF",
    "Ile-de-France": "IDF",
    "La Reunion": "RE",
    "Martinique": "FP",
    "Mayotte": "YT",
    "Normandie": "Normandie",
    "Nouvelle-Aquitaine": "NAQ",
    "Occitanie": "Occitanie",
    "Pays de la Loire": "PDL",
    "Provence-Alpes-Cote d'Azur": "PAC",
}

# Collectivites hors regions : absentes de /departements de l'API Geo
# (ce sont des departements "de facto" pour le RPPS, via le code commune).
EXTRA_REGIONS = {
    "975": ("Saint-Pierre-et-Miquelon", "SPM"),
    "977": ("Saint-Barthelemy", "SM"),
    "978": ("Saint-Martin", "SM"),
    "98": ("Polynesie francaise", "PF"),
}


def norm(s):
    """Retire les accents (NFKD) et normalise l'apostrophe typographique."""
    s = s.replace("\u2019", "'")
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--patch", metavar="FILE",
                        help="reecrit le bloc DEPT_TO_REGION dans FILE")
    args = parser.parse_args()

    with urllib.request.urlopen(URL, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))

    pairs = []
    unknown = set()
    for d in sorted(data, key=lambda x: x["code"]):
        rnom = norm(d["region"]["nom"])
        code = REGION_CODES.get(rnom)
        if code is None:
            unknown.add(rnom)
            continue
        pairs.append((d["code"], code))

    for dep, (_nom, code) in EXTRA_REGIONS.items():
        pairs.append((dep, code))
    pairs.sort()

    if unknown:
        print("REGIONS INCONNUES (code court a definir) : %s" % sorted(unknown), file=sys.stderr)
        return 1

    out = ["DEPT_TO_REGION = {"]
    line = "   "
    for dep, reg in pairs:
        item = " '%s': '%s'," % (dep, reg)
        if len(line) + len(item) > 92:
            out.append(line.rstrip())
            line = "   "
        line += item
    out.append(line.rstrip().rstrip(","))
    out.append("}")
    block = "\n".join(out)

    if args.patch:
        with open(args.patch, "r", encoding="utf-8") as f:
            src = f.read()
        pattern = re.compile(r"DEPT_TO_REGION = \{.*?\n\}", re.S)
        if not pattern.search(src):
            print("Bloc DEPT_TO_REGION introuvable dans %s" % args.patch, file=sys.stderr)
            return 2
        new_src = pattern.sub(block, src, count=1)
        with open(args.patch, "w", encoding="utf-8", newline="\n") as f:
            f.write(new_src)
        print("DEPT_TO_REGION remplace dans %s (%d departements)" % (args.patch, len(pairs)))
    else:
        print(block)

    print("# %d departements, %d regions" % (len(pairs), len({r for _, r in pairs})), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
