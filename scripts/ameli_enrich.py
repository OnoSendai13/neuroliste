#!/usr/bin/env python3
"""Enrichissement des neurologues RPPS par le repertoire Ameli des praticiens.

Le fichier Ameli ("Liste des professionnels de sante (PS) de l'Annuaire sante
Ameli", data.gouv.fr) apporte l'adresse d'exercice liberale des praticiens :
voie, code postal, ville, telephone, specialite.

RPPS laisse souvent ces champs vides (674 neurologues sur 3 629 sans commune ni
departement). Ce module complete les champs manquants :

  - appariement sur nom + prenom normalises (NFKD, sans accents ni ponctuation)
  - uniquement les lignes Ameli de specialite neurologique
  - uniquement si l'appariement est UNIQUE (pas d'homonymie acceptee)
  - coherence verifiee : si le RPPS a deja une commune, on exige que la ville
    Ameli soit la meme (au sens de la normalisation) avant de complete
  - departement et region deduits du code postal via l'API Geo de l'Etat,
    avec cache disque et repli CP[:2]

Usage :
    python scripts/ameli_enrich.py --db chemin/neurologues.db
    python scripts/ameli_enrich.py --db ... --csv /chemin/ameli.csv
"""
import argparse
import csv
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

AMELI_FALLBACK_URL = (
    "https://static.data.gouv.fr/resources/annuaire-sante-ameli/"
    "20261109-014545/liste-ps-20261109-023054.csv"
)
AMELI_DATASET_ID = "annuaire-sante-ameli"
GEO_URL = "https://geo.api.gouv.fr/communes?codePostal={cp}&fields=codeDepartement&format=json"
CACHE_DIR = Path("/tmp/rpps_cache")
CHUNK_SIZE = 1024 * 1024
MAX_RETRIES = 5


# --------------------------------------------------------------------------
# Normalisation / index
# --------------------------------------------------------------------------
def norm_key(s):
    """Nom ou prenom normalise : minuscules, sans accents, sans ponctuation."""
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def norm_city(s):
    """Ville normalisee pour comparer deux libelles de commune."""
    s = norm_key(s)
    s = re.sub(r"\b(st|saint|ste|sainte|le|la|les|sur|sous|ville|ville d)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


# --------------------------------------------------------------------------
# Telechargement
# --------------------------------------------------------------------------
def resolve_ameli_url():
    """URL du dernier fichier Ameli, via l'API data.gouv.fr."""
    api = ("https://www.data.gouv.fr/api/1/datasets/%s/" % AMELI_DATASET_ID)
    try:
        with urllib.request.urlopen(api, timeout=30) as r:
            ds = json.loads(r.read().decode("utf-8"))
        best = None
        for res in ds.get("resources", []) or []:
            title = (res.get("title") or "").lower()
            url = res.get("url") or ""
            if not url.lower().endswith(".csv"):
                continue
            if "professionnels" in title or "liste des ps" in title:
                best = url
        if best:
            return best
    except Exception as e:
        print("Resolution Ameli impossible (%s), URL de secours" % e)
    return AMELI_FALLBACK_URL


def download_ameli(url=None, cache_dir=CACHE_DIR):
    """Telecharge le CSV Ameli en streaming, avec reprise sur coupure."""
    import requests

    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    url = url or resolve_ameli_url()
    target = cache_dir / "ameli_liberaux.csv"
    part = cache_dir / "ameli_liberaux.csv.part"

    if target.exists() and target.stat().st_size > 10_000_000:
        print("Ameli deja en cache: %s (%d octets)" % (target, target.stat().st_size))
        return target

    print("Telechargement Ameli: %s" % url)
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, stream=True, timeout=180)
            resp.raise_for_status()
            with open(part, "wb") as f:
                for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                    if chunk:
                        f.write(chunk)
            part.replace(target)
            print("Ameli telecharge: %d octets" % target.stat().st_size)
            return target
        except Exception as e:
            print("Telechargement Ameli echoue (essai %d/%d): %s" % (attempt + 1, MAX_RETRIES, e))
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
    raise RuntimeError("Telechargement Ameli impossible apres %d essais" % MAX_RETRIES)


def build_index(csv_path, specialty_contains="neurolog"):
    """Index (nom, prenom) -> liste d'entrees Ameli de la specialite demandee."""
    index = {}
    nrows = 0
    nkept = 0
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            nrows += 1
            spec = (row.get("specialite_libelle") or "").lower()
            if specialty_contains not in spec:
                continue
            key = (norm_key(row.get("ps_activite_nom")), norm_key(row.get("ps_activite_prenom")))
            if not key[0] or not key[1]:
                continue
            cp = (row.get("coordonnees_code_postal") or "").strip()
            ville = (row.get("coordonnees_ville") or "").strip()
            if not cp and not ville:
                continue
            index.setdefault(key, []).append({
                "cp": cp,
                "ville": ville,
                "voie": (row.get("coordonnees_voie") or "").strip(),
                "complement": (row.get("coordonnees_complement") or "").strip(),
                "lieu_dit": (row.get("coordonnees_lieu_dit") or "").strip(),
                "tel": (row.get("coordonnees_num_tel") or "").strip(),
                "raison_sociale": (row.get("ps_activite_raison_sociale") or "").strip(),
                "specialite": (row.get("specialite_libelle") or "").strip(),
                "nature": (row.get("nature_exercice_libelle") or "").strip(),
            })
            nkept += 1
    print("Ameli: %d lignes lues, %d neurologicques indexes sur %d cles"
          % (nrows, nkept, len(index)))
    return index


# --------------------------------------------------------------------------
# Departement / region a partir du code postal
# --------------------------------------------------------------------------
class CpResolver:
    """Code postal -> (departement, region), via l'API Geo, avec cache disque."""

    def __init__(self, cache_path=None, dept_to_region=None):
        self.cache_path = Path(cache_path or (CACHE_DIR / "cp_dept.json"))
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache = {}
        if self.cache_path.exists():
            try:
                self.cache = json.loads(self.cache_path.read_text(encoding="utf-8"))
            except Exception:
                self.cache = {}
        self.dept_to_region = dept_to_region or {}
        self.nhits = 0
        self.nmiss = 0

    def _save(self):
        try:
            self.cache_path.write_text(json.dumps(self.cache, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            print("Ecriture cache CP impossible: %s" % e)

    def resolve(self, cp):
        if not cp or not re.fullmatch(r"\d{5}", cp):
            return None, None
        if cp in self.cache:
            val = self.cache[cp]
        else:
            url = GEO_URL.format(cp=urllib.parse.quote(cp))
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=20) as r:
                    data = json.loads(r.read().decode("utf-8"))
                val = data[0].get("codeDepartement") if data else None
            except Exception:
                val = None
            self.cache[cp] = val
            self.nhits += 1
            self._save()
        if not val:
            self.nmiss += 1
            # repli : CP[:2], DOM 3 chiffres
            if cp.startswith(("971", "972", "973", "974", "976")):
                val = cp[:3]
            else:
                val = cp[:2]
        return val, self.dept_to_region.get(val)


# --------------------------------------------------------------------------
# Enrichissement
# --------------------------------------------------------------------------
def enrich_doc(doc, index, cp_resolver):
    """Complete les champs manquants d'un document. Retourne la liste des champs
    completes, ou [] si rien n'a pu etre complete."""
    key = (norm_key(doc.nom), norm_key(doc.prenom))
    candidates = index.get(key) or []
    if not candidates:
        return []

    # Deduplication : meme adresse compte une seule fois
    uniq = {}
    for c in candidates:
        sig = (c["cp"], norm_city(c["ville"]))
        uniq.setdefault(sig, c)
    candidates = list(uniq.values())

    # Si le RPPS a deja une commune, on exige la coherence avec Ameli
    if doc.commune:
        existing = norm_city(doc.commune)
        coherent = [c for c in candidates if norm_city(c["ville"]) == existing]
        if coherent:
            candidates = coherent
        else:
            return []

    # Appariement unique obligatoire (pas d'homonymie)
    if len(candidates) != 1:
        return []

    hit = candidates[0]
    filled = []

    if not doc.code_postal and hit["cp"]:
        doc.code_postal = hit["cp"]
        filled.append("code_postal")
    if not doc.commune and hit["ville"]:
        doc.commune = hit["ville"]
        filled.append("commune")
    if not doc.adresse:
        parts = [p for p in (hit["complement"], hit["voie"], hit["lieu_dit"]) if p]
        if parts:
            doc.adresse = " ".join(parts)
            filled.append("adresse")
    if not doc.tel and hit["tel"]:
        doc.tel = hit["tel"]
        filled.append("tel")

    if (not doc.departement or not doc.region) and doc.code_postal:
        dep, reg = cp_resolver.resolve(doc.code_postal)
        if dep and not doc.departement:
            doc.departement = dep
            filled.append("departement")
        if reg and not doc.region:
            doc.region = reg
            filled.append("region")

    return filled


def enrich_database(db, index, cp_resolver, only_missing=True, verbose=True):
    """Applique l'enrichissement a tous les neurologues de la session."""
    from models import Neurologue

    stats = {"total": 0, "candidats": 0, "enrichis": 0, "sans_appariement": 0,
             "champs": {}}
    docs = db.query(Neurologue).all()
    for doc in docs:
        stats["total"] += 1
        key = (norm_key(doc.nom), norm_key(doc.prenom))
        if key not in index:
            stats["sans_appariement"] += 1
            continue
        stats["candidats"] += 1
        filled = enrich_doc(doc, index, cp_resolver)
        if filled:
            stats["enrichis"] += 1
            for f in filled:
                stats["champs"][f] = stats["champs"].get(f, 0) + 1
    db.commit()
    if verbose:
        print("Enrichissement Ameli: %d/%d lignes enrichies (%d candidats, %d sans appariement)"
              % (stats["enrichis"], stats["total"], stats["candidats"], stats["sans_appariement"]))
        print("Champs completes: %s" % stats["champs"])
    return stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, help="chemin de neurologues.db")
    parser.add_argument("--csv", help="CSV Ameli local (sinon telecharge)")
    parser.add_argument("--download-only", action="store_true")
    args = parser.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    # backend/ peut etre a cote de scripts/ (dev) ou a la racine (image Docker)
    for cand in (os.path.join(here, "..", "backend"), os.path.join(here, ".."), here):
        if os.path.isfile(os.path.join(cand, "models.py")):
            sys.path.insert(0, os.path.abspath(cand))
            break
    if here not in sys.path:
        sys.path.insert(0, here)
    # DATABASE_URL doit etre pose AVANT l'import de models (il est lu a l'import)
    os.environ["DATABASE_URL"] = "sqlite:///%s" % os.path.abspath(args.db)
    from models import SessionLocal, init_db
    from load_rpps import DEPT_TO_REGION  # noqa: F401  (mapping partage)

    csv_path = Path(args.csv) if args.csv else download_ameli()
    if args.download_only:
        print("CSV: %s" % csv_path)
        return 0

    index = build_index(csv_path)
    init_db()
    db = SessionLocal()
    try:
        enrich_database(db, index, CpResolver(dept_to_region=DEPT_TO_REGION))
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
