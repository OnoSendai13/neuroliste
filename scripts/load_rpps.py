#!/usr/bin/env python3
"""Load RPPS data directly from data.gouv.fr static files.
Filters for neurologues based on diplômes and savoir-faire.
Streaming download with resume, chunk retry, robust URL discovery.
"""
import os
import sys
import io
import requests
import gzip
import tempfile
import threading
import time
from pathlib import Path
from sqlalchemy import text

# Add backend to path - use absolute path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, backend_path)
from models import Neurologue, SessionLocal, init_db

# RPPS static file URLs - auto-discovered from data.gouv.fr API
FILES = {
    "personne": "https://static.data.gouv.fr/resources/annuaire-sante-extractions-des-donnees-en-libre-acces-des-professionnels-intervenant-dans-le-systeme-de-sante-rpps/20260610-120843/ps-libreacces-personne-activite.txt",
    "diplomes": "https://static.data.gouv.fr/resources/annuaire-sante-extractions-des-donnees-en-libre-acces-des-professionnels-intervenant-dans-le-systeme-de-sante-rpps/20260610-120547/ps-libreacces-dipl-autexerc.txt",
    "savoirfaire": "https://static.data.gouv.fr/resources/annuaire-sante-extractions-des-donnees-en-libre-acces-des-professionnels-intervenant-dans-le-systeme-de-sante-rpps/20260610-120956/ps-libreacces-savoirfaire.txt"
}

# Department to Region mapping (2024 - post 2016 reform)
# Uses standard 3-letter codes: AuRA, BFC, BIF, etc.
DEPT_TO_REGION = {
    '01': 'AuRA', '02': 'HDF', '03': 'AuRA', '04': 'PAC', '05': 'PAC', '06': 'PAC',
    '07': 'AuRA', '08': 'Grand Est', '09': 'Occitanie', '10': 'Grand Est',
    '11': 'Occitanie', '12': 'Occitanie', '13': 'PAC', '14': 'Normandie', '15': 'AuRA',
    '16': 'NAQ', '17': 'NAQ', '18': 'Centre-Val', '19': 'NAQ', '21': 'BFC', '22': 'BIF',
    '23': 'NAQ', '24': 'NAQ', '25': 'BFC', '26': 'AuRA', '27': 'Normandie',
    '28': 'Centre-Val', '29': 'BIF', '2A': 'Corse', '2B': 'Corse', '30': 'Occitanie',
    '31': 'Occitanie', '32': 'Occitanie', '33': 'NAQ', '34': 'Occitanie', '35': 'BIF',
    '36': 'Centre-Val', '37': 'Centre-Val', '38': 'AuRA', '39': 'BFC', '40': 'NAQ',
    '41': 'Centre-Val', '42': 'AuRA', '43': 'AuRA', '44': 'PDL', '45': 'Centre-Val',
    '46': 'Occitanie', '47': 'NAQ', '48': 'Occitanie', '49': 'PDL', '50': 'Normandie',
    '51': 'Grand Est', '52': 'Grand Est', '53': 'PDL', '54': 'Grand Est', '55': 'Grand Est',
    '56': 'BIF', '57': 'Grand Est', '58': 'BFC', '59': 'HDF', '60': 'HDF',
    '61': 'Normandie', '62': 'HDF', '63': 'AuRA', '64': 'NAQ', '65': 'Occitanie',
    '66': 'Occitanie', '67': 'Grand Est', '68': 'Grand Est', '69': 'AuRA', '70': 'BFC',
    '71': 'BFC', '72': 'PDL', '73': 'AuRA', '74': 'AuRA', '75': 'IDF', '76': 'Normandie',
    '77': 'IDF', '78': 'IDF', '79': 'NAQ', '80': 'HDF', '81': 'Occitanie',
    '82': 'Occitanie', '83': 'PAC', '84': 'PAC', '85': 'PDL', '86': 'NAQ', '87': 'NAQ',
    '88': 'Grand Est', '89': 'BFC', '90': 'BFC', '91': 'IDF', '92': 'IDF', '93': 'IDF',
    '94': 'IDF', '95': 'IDF', '971': 'GP', '972': 'FP', '973': 'GF', '974': 'RE',
    '975': 'SPM', '976': 'YT', '977': 'SM', '978': 'SM', '98': 'PF'
}

CACHE_DIR = Path("/tmp/rpps_cache")
CACHE_DIR.mkdir(exist_ok=True)

CHUNK_SIZE = 1024 * 1024  # 1MB chunks
MAX_RETRIES = 5
BASE_BACKOFF = 2


def get_latest_urls() -> dict | None:
    """Fetch current resource URLs from data.gouv.fr API (fallback to hardcoded)"""
    try:
        api_url = "https://www.data.gouv.fr/api/2/datasets/annuaire-sante-extractions-des-donnees-en-libre-acces-des-professionnels-intervenant-dans-le-systeme-de-sante-rpps/resources/"
        resp = requests.get(api_url, timeout=30)
        resp.raise_for_status()
        resources = resp.json()
        urls = {}
        for r in resources.get('data', []):
            title = r.get('title', '').lower()
            url = r.get('url', '')
            if 'personne' in title:
                urls['personne'] = url
            elif 'dipl' in title:
                urls['diplomes'] = url
            elif 'savoir' in title:
                urls['savoirfaire'] = url
        if urls and all(k in urls for k in ('personne', 'diplomes', 'savoirfaire')):
            print("Using auto-discovered URLs from data.gouv.fr API")
            return urls
    except Exception as e:
        print(f"URL discovery failed: {e}, using fallback URLs")
    return None


def download_file_streaming(url: str, cache_name: str) -> list[str]:
    """Download large txt file with streaming, resume, and chunk retry."""
    cache_path = CACHE_DIR / f"{cache_name}.txt"
    temp_path = CACHE_DIR / f"{cache_name}.txt.part"

    # Reutilisation du cache : si le fichier est deja complet (taille identique
    # a celle annoncee par le serveur), on ne retelecharge pas ~1 Go.
    if cache_path.exists():
        try:
            head = requests.head(url, timeout=30, allow_redirects=True)
            expected = int(head.headers.get('Content-Length', 0))
            actual = cache_path.stat().st_size
            if expected and actual == expected:
                print(f"Cache hit for {cache_name} ({actual} bytes), skipping download")
                with open(cache_path, 'r', encoding='utf-8', errors='replace') as f:
                    lines = f.read().splitlines()
                print(f"Parsed {len(lines)} lines from cache")
                return lines
            if expected:
                print(f"Cache stale for {cache_name} ({actual}/{expected} bytes), re-downloading")
            else:
                print(f"Cache size unknown for {cache_name}, re-downloading")
        except Exception as e:
            print(f"Cache check failed for {cache_name} ({e}), re-downloading")

    # Determine resume position
    resume_byte = 0
    if temp_path.exists():
        resume_byte = temp_path.stat().st_size
        print(f"Resuming {cache_name} from byte {resume_byte}")

    headers = {}
    if resume_byte > 0:
        headers['Range'] = f'bytes={resume_byte}-'

    for attempt in range(MAX_RETRIES):
        try:
            print(f"Downloading {url} (attempt {attempt + 1}/{MAX_RETRIES})...")
            resp = requests.get(url, headers=headers, stream=True, timeout=120)
            resp.raise_for_status()

            mode = 'ab' if resume_byte > 0 else 'wb'
            with open(temp_path, mode) as f:
                for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                    if chunk:
                        f.write(chunk)

            # Verify complete download (content-length or 200 OK without range)
            if 'Content-Length' in resp.headers:
                expected = int(resp.headers['Content-Length']) + resume_byte
                actual = temp_path.stat().st_size
                if actual < expected:
                    raise RuntimeError(f"Incomplete download: {actual}/{expected} bytes")

            # Atomic move
            temp_path.replace(cache_path)
            print(f"Downloaded {cache_path.stat().st_size} bytes to cache")

            # Read and return lines
            with open(cache_path, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.read().splitlines()
            print(f"Parsed {len(lines)} lines")
            return lines

        except Exception as e:
            print(f"Attempt {attempt + 1}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                wait = BASE_BACKOFF ** attempt
                print(f"Retrying in {wait}s...")
                time.sleep(wait)
                resume_byte = temp_path.stat().st_size if temp_path.exists() else 0
            else:
                raise RuntimeError(f"Failed to download {url} after {MAX_RETRIES} attempts: {e}")

    # Fallback: try without streaming if all retries failed
    try:
        print("Trying non-streaming fallback...")
        resp = requests.get(url, timeout=300)
        resp.raise_for_status()
        lines = resp.text.splitlines()
        with open(cache_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        return lines
    except Exception as e:
        raise RuntimeError(f"Fallback download also failed: {e}")


def load_neurologues():
    """Load and filter neurologues from RPPS data."""
    global FILES
    latest = get_latest_urls()
    if latest:
        FILES = latest

    db = SessionLocal()
    init_db()

    # L'enrichissement Ameli tourne EN PARALLELE du chargement RPPS :
    # le fichier Ameli (156 Mo) est telecharge et indexe dans un thread, puis
    # applique quand les neurologues RPPS sont en base.
    ameli_state: dict = {"index": None, "error": None}

    def _ameli_worker():
        try:
            import ameli_enrich
            print("Ameli (parallel): download...")
            csv_path = ameli_enrich.download_ameli()
            print("Ameli (parallel): indexing...")
            ameli_state["index"] = ameli_enrich.build_index(csv_path)
        except Exception as e:
            ameli_state["error"] = e
            print("Ameli (parallel) failed: %s" % e)

    ameli_thread = threading.Thread(target=_ameli_worker, name="ameli-enrich", daemon=True)
    ameli_thread.start()

    db.query(Neurologue).delete()
    db.commit()

    print("Step 1/3: Loading diplômes...")
    neuro_diplome_ids = set()
    diplomes = download_file_streaming(FILES["diplomes"], "diplomes")
    for i, line in enumerate(diplomes):
        if i == 0:
            continue
        parts = line.strip().split('|')
        if len(parts) >= 8:
            id_ppss = parts[1]
            code_diplome = parts[7]
            if code_diplome in ("CESM15", "DSM30", "DIP143"):
                neuro_diplome_ids.add(id_ppss)
    print(f"Found {len(neuro_diplome_ids)} doctors with Neurologie diploma")

    print("Step 2/3: Loading savoir-faire...")
    neuro_sf_ids = set()
    sf = download_file_streaming(FILES["savoirfaire"], "savoirfaire")
    for i, line in enumerate(sf):
        if i == 0:
            continue
        parts = line.strip().split('|')
        if len(parts) >= 12:
            id_ppss = parts[1]
            code_sf = parts[11]
            if code_sf == "SM32":
                neuro_sf_ids.add(id_ppss)
    print(f"Found {len(neuro_sf_ids)} doctors with Neurologie savoir-faire")

    neuro_ids = neuro_diplome_ids & neuro_sf_ids
    print(f"Neurologues with both: {len(neuro_ids)}")

    print("Step 3/3: Loading personne activité...")
    seen_ids = set()
    count = 0
    pa = download_file_streaming(FILES["personne"], "personne")

    for i, line in enumerate(pa):
        if i == 0:
            continue
        parts = line.strip().split('|')
        if len(parts) < 45:
            continue
        id_ppss = parts[1]
        if id_ppss not in neuro_ids:
            continue
        if id_ppss in seen_ids:
            continue
        seen_ids.add(id_ppss)

        def fix_encoding(s):
            if not s:
                return s
            try:
                return s.encode('latin1').decode('utf-8')
            except:
                return s

        adresse = f"{parts[31]} {parts[32]}" if len(parts) > 32 else None

        dept_from_col = parts[44] if len(parts) > 44 and parts[44] else None
        commune_code = parts[36] if len(parts) > 36 else None

        if dept_from_col:
            departement = dept_from_col
        elif commune_code and len(commune_code) >= 2:
            # DOM-TOM: 971, 972, 973, 974, 975, 976 - keep full 3 digits
            if commune_code[:3] in ('971', '972', '973', '974', '975', '976', '977', '978'):
                departement = commune_code[:3]
            else:
                departement = commune_code[:2]
        else:
            departement = None
        region = DEPT_TO_REGION.get(departement, None) if departement else None

        doc = Neurologue(
            id_ppss=id_ppss,
            numero_rpps=id_ppss,
            ine=parts[2] if len(parts) > 2 else None,
            nom=fix_encoding(parts[7]) if len(parts) > 7 else None,
            prenom=fix_encoding(parts[8]) if len(parts) > 8 else None,
            sexe=parts[5] if len(parts) > 5 else None,
            adresse=fix_encoding(adresse),
            code_postal=parts[35] if len(parts) > 35 else None,
            commune=fix_encoding(parts[37]) if len(parts) > 37 else None,
            departement=departement,
            region=region,
            tel=parts[40] if len(parts) > 40 else None,
            mail=parts[43] if len(parts) > 43 else None,
            code_profession=parts[9] if len(parts) > 9 else None,
            libelle_profession=parts[10] if len(parts) > 10 else None,
            mode_exercice=parts[18] if len(parts) > 18 else None,
            code_mode_exercice=parts[17] if len(parts) > 17 else None,
            structure=fix_encoding(parts[25]) if len(parts) > 25 else None,
            type_etablissement=fix_encoding(parts[24]) if len(parts) > 24 else None,
            diplome_neuro="1",
            statut="ACTIF"
        )
        db.add(doc)
        count += 1

        if count % 100 == 0:
            print(f"Added {count} neurologues...")
            db.commit()

    db.commit()
    print(f"Total neurologues loaded: {count}")

    # Enrichissement Ameli (le thread a tourne en parallele pendant le load)
    print("Waiting for the parallel Ameli thread...")
    ameli_thread.join(timeout=3600)
    if ameli_state.get("index"):
        try:
            import ameli_enrich
            resolver = ameli_enrich.CpResolver(dept_to_region=DEPT_TO_REGION)
            ameli_enrich.enrich_database(db, ameli_state["index"], resolver)
        except Exception as e:
            print("Ameli enrichment failed: %s" % e)
    elif ameli_state.get("error"):
        print("Ameli enrichment skipped: %s" % ameli_state["error"])
    else:
        print("Ameli enrichment skipped: index unavailable")

    db.close()


if __name__ == "__main__":
    load_neurologues()