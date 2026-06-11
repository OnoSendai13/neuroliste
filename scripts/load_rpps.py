#!/usr/bin/env python3
"""Load RPPS data directly from data.gouv.fr static files.
Filters for neurologues based on diplômes and savoir-faire.
"""
import os
import sys
import io
import requests
import gzip
import tempfile
import subprocess
from sqlalchemy import text

# Add backend to path - use absolute path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
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
    '01': 'AuRA', '03': 'AuRA', '04': 'AuRA', '07': 'AuRA', '15': 'AuRA', 
    '26': 'AuRA', '38': 'AuRA', '42': 'AuRA', '43': 'AuRA', '63': 'AuRA', '69': 'AuRA', '73': 'AuRA', '74': 'AuRA',
    '10': 'AuRA',  # Ain -> AuRA (was missed)
    
    '21': 'BFC', '25': 'BFC', '39': 'BFC', '58': 'BFC', '70': 'BFC', '71': 'BFC', '89': 'BFC',
    
    '22': 'BIF', '29': 'BIF', '35': 'BIF', '56': 'BIF',
    
    '18': 'Centre-Val', '28': 'Centre-Val', '36': 'Centre-Val', '37': 'Centre-Val', '41': 'Centre-Val', '45': 'Centre-Val',
    
    '2A': 'Corse', '2B': 'Corse',
    
    '08': 'Grand Est', '27': 'Grand Est', '86': 'NAQ', '90': 'Grand Est', '97': 'Corse', '98': 'BFC',
    
    '02': 'Grand Est', '05': 'Grand Est', '51': 'Grand Est', '54': 'Grand Est', '55': 'Grand Est', '57': 'Grand Est', 
    '67': 'Grand Est', '68': 'Grand Est', '88': 'Grand Est', '52': 'Grand Est',  # l'Aube
    
    '59': 'HDF', '60': 'HDF', '62': 'HDF', '80': 'HDF',
    
    '971': 'GP', '972': 'FP', '973': 'GF', '974': 'RE', '975': 'SM', '976': 'SM',
    
    '75': 'IDF', '77': 'IDF', '78': 'IDF', '91': 'IDF', '92': 'IDF', '93': 'IDF', '94': 'IDF', '95': 'IDF',
    
    '14': 'Normandie', '50': 'Normandie', '61': 'Normandie', '76': 'Normandie',
    
    '16': 'NAQ', '17': 'NAQ', '19': 'NAQ', '23': 'NAQ', '24': 'NAQ', '33': 'NAQ', '40': 'NAQ', '47': 'NAQ', 
    '64': 'NAQ', '79': 'NAQ', '87': 'NAQ',
    
    '09': 'Occitanie', '11': 'Occitanie', '12': 'Occitanie', '30': 'Occitanie', '31': 'Occitanie', '32': 'Occitanie', 
    '34': 'Occitanie', '46': 'Occitanie', '48': 'Occitanie', '65': 'Occitanie', '66': 'Occitanie', '81': 'Occitanie', '82': 'Occitanie',
    
    '44': 'PDL', '49': 'PDL', '53': 'PDL', '72': 'PDL', '85': 'PDL',
    
    '06': 'PAC', '13': 'PAC', '83': 'PAC', '84': 'PAC',
}

def download_file(url):
    """Download txt file and return lines using wget for reliability."""
    print(f"Downloading {url}...")
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as tmp:
            tmp_path = tmp.name
        result = subprocess.run(['wget', '-qO', tmp_path, url], capture_output=True, text=True, timeout=900)
        if result.returncode != 0:
            resp = requests.get(url, timeout=600)
            resp.raise_for_status()
            return io.StringIO(resp.text).readlines()
        with open(tmp_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        os.unlink(tmp_path)
        print(f"Downloaded {len(lines)} lines")
        return lines
    except Exception as e:
        print(f"Error downloading {url}: {e}")
        raise

def get_latest_urls():
    """Fetch current resource URLs from data.gouv.fr API (fallback to hardcoded)"""
    try:
        api_url = "https://www.data.gouv.fr/api/2/datasets/annuaire-sante-extractions-des-donnees-en-libre-acces-des-professionnels-intervenant-dans-le-systeme-de-sante-rpps/resources/"
        resp = requests.get(api_url, timeout=30)
        resources = resp.json()
        urls = {}
        for r in resources.get('data', []):
            title = r.get('title', '')
            url = r.get('url', '')
            if 'personne' in title:
                urls['personne'] = url
            elif 'dipl' in title:
                urls['diplomes'] = url
            elif 'savoir' in title:
                urls['savoirfaire'] = url
        return urls if urls else None
    except:
        return None

def load_neurologues():
    """Load and filter neurologues from RPPS data."""
    global FILES
    latest = get_latest_urls()
    if latest:
        FILES = latest
        print("Using auto-discovered URLs")
    
    db = SessionLocal()
    init_db()
    
    db.query(Neurologue).delete()
    db.commit()
    
    print("Step 1/3: Loading diplômes...")
    neuro_diplome_ids = set()
    diplomes = download_file(FILES["diplomes"])
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
    sf = download_file(FILES["savoirfaire"])
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
    pa = download_file(FILES["personne"])
    
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
    db.close()

if __name__ == "__main__":
    load_neurologues()