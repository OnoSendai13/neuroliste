#!/usr/bin/env python3
"""
Load RPPS data directly from data.gouv.fr static files.
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
# Falls back to hardcoded if API fails

def get_latest_urls():
    """Fetch current resource URLs from data.gouv.fr API (fallback to hardcoded)"""
    try:
        api_url = "https://www.data.gouv.fr/api/2/datasets/annuaire-sante-extractions-des-donnees-en-libre-acces-des-professionnels-intervenant-dans-le-systeme-de-sante-rpps/resources/"
        resp = requests.get(api_url, timeout=30)
        resp.raise_for_status()
        resources = resp.json()
        
        urls = {}
        for r in resources.get('data', []):
            # API v2: fields are at root level, not in attributes
            title = r.get('title', '')
            url = r.get('url', '')
            if 'personne' in title:
                urls['personne'] = url
            elif 'dipl' in title:
                urls['diplomes'] = url
            elif 'savoir' in title:
                urls['savoirfaire'] = url
        return urls if urls else None
    except Exception as e:
        print(f"Warning: Could not fetch latest URLs ({e}), using fallback")
        return None

FILES = {
    "personne": "https://static.data.gouv.fr/resources/annuaire-sante-extractions-des-donnees-en-libre-acces-des-professionnels-intervenant-dans-le-systeme-de-sante-rpps/20260610-120843/ps-libreacces-personne-activite.txt",
    "diplomes": "https://static.data.gouv.fr/resources/annuaire-sante-extractions-des-donnees-en-libre-acces-des-professionnels-intervenant-dans-le-systeme-de-sante-rpps/20260610-120547/ps-libreacces-dipl-autexerc.txt",
    "savoirfaire": "https://static.data.gouv.fr/resources/annuaire-sante-extractions-des-donnees-en-libre-acces-des-professionnels-intervenant-dans-le-systeme-de-sante-rpps/20260610-120956/ps-libreacces-savoirfaire.txt"
}

def download_file(url, filename_hint=None):
    """Download txt file and return lines using wget for reliability."""
    print(f"Downloading {url}...")
    
    # Use wget for large files - more reliable
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as tmp:
            tmp_path = tmp.name
        
        result = subprocess.run(
            ['wget', '-qO', tmp_path, url],
            capture_output=True,
            text=True,
            timeout=900
        )
        
        if result.returncode != 0:
            # Fallback to requests
            print(f"wget failed, trying requests...")
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

def load_neurologues():
    """Load and filter neurologues from RPPS data."""
    global FILES
    # Try to get latest URLs from API first
    latest = get_latest_urls()
    if latest:
        FILES = latest
        print(f"Using auto-discovered URLs")
    
    db = SessionLocal()
    init_db()
    
    # Clear table
    db.query(Neurologue).delete()
    db.commit()
    
    print("Step 1/3: Loading diplômes to identify neurologues...")
    neuro_diplome_ids = set()
    diplomes = download_file(FILES["diplomes"])
    
    for i, line in enumerate(diplomes):
        if i == 0:  # Skip header
            continue
        parts = line.strip().split('|')
        if len(parts) >= 8:
            id_ppss = parts[1]  # Id_PP is column 1
            code_diplome = parts[7]  # Code diplome is column 7: CESM15, DSM30, DIP143 = Neuro
            # Neurologie codes: CESM15, DSM30, DIP143
            if code_diplome in ("CESM15", "DSM30", "DIP143"):
                neuro_diplome_ids.add(id_ppss)
    
    print(f"Found {len(neuro_diplome_ids)} doctors with Neurologie diploma")
    
    print("Step 2/3: Loading savoir-faire...")
    neuro_sf_ids = set()
    sf = download_file(FILES["savoirfaire"])
    
    for i, line in enumerate(sf):
        if i == 0:  # Skip header
            continue
        parts = line.strip().split('|')
        if len(parts) >= 12:
            id_ppss = parts[1]  # Id_PP is column 1
            code_sf = parts[11]  # Code savoir-faire is column 11: SM32 = Neurologie
            # SM32 = Neurologie uniquement (pas neuro-chirurgien SM31 ou neuro-psychiatrique SM33)
            if code_sf == "SM32":
                neuro_sf_ids.add(id_ppss)
    
    print(f"Found {len(neuro_sf_ids)} doctors with Neurologie savoir-faire")
    
    # Intersection: doctors with BOTH
    neuro_ids = neuro_diplome_ids & neuro_sf_ids
    print(f"Neurologues with both diplome and savoir-faire: {len(neuro_ids)}")
    
    print("Step 3/3: Loading personne activité...")
    seen_ids = set()
    count = 0
    pa = download_file(FILES["personne"])
    
    for i, line in enumerate(pa):
        if i == 0:  # Skip header
            continue
        parts = line.strip().split('|')
        if len(parts) < 45:  # Need at least 45 for email (col 44)
            continue
        
        # Columns from personne file header (0-indexed):
        # 1=Id_PP, 7=Nom, 8=Prenom, 5=Sexe, 9=CodeProf, 10=LibelleProf,
        # 15=CodeSavoirFaire, 17=CodeMode, 18=Mode, 24=RaisonSocialeSite (structure),
        # 30=TypeVoie, 31=Voie, 35=CodePostal, 36=CodeCommune, 37=Commune, 40=Tel, 44=Email
        id_ppss = parts[1]  # Id_PP is column 1
        if id_ppss not in neuro_ids:
            continue
        
        # Skip if already processed (deduplication)
        if id_ppss in seen_ids:
            continue
        seen_ids.add(id_ppss)
        
        # Fix encoding issues (NÃ®mes -> Nîmes)
        def fix_encoding(s):
            if not s:
                return s
            try:
                return s.encode('latin1').decode('utf-8')
            except:
                return s
        
        adresse = f"{parts[31]} {parts[32]}" if len(parts) > 32 else None
        
        # Derive departement from commune code if not in col 44
        def derive_dept(commune_code):
            if not commune_code or len(commune_code) < 2:
                return None
            # DOM-TOM: 971, 972, 973, 974, 976
            if commune_code[:3] in ('971', '972', '973', '974', '976', '977', '978'):
                return commune_code[:3]
            return commune_code[:2]
        
        dept_from_col = parts[44] if len(parts) > 44 and parts[44] else None
        commune_code = parts[36] if len(parts) > 36 else None
        departement = dept_from_col or derive_dept(commune_code)
        
        # Mapping département -> région
        DEPT_TO_REGION = {'01':'AURA', '02':'GRA', '03':'AURA', '04':'ARA', '05':'ARA', '06':'PAC', '07':'ARA', '08':'GRA', '09':'OCC', '10':'GRA', '11':'OCC', '12':'OCC', '13':'PAC', '14':'NOR', '15':'OCC', '16':'AQU', '17':'AQU', '18':'CEN', '19':'AQU', '2A':'COR', '2B':'COR', '21':'BIF', '22':'BIF', '23':'CEN', '24':'CEN', '25':'BFC', '26':'ARA', '27':'NOR', '28':'CEN', '29':'BIF', '30':'OCC', '31':'OCC', '32':'AQU', '33':'AQU', '34':'LRE', '35':'BIF', '36':'CEN', '37':'PIE', '38':'AQU', '39':'BFC', '40':'AQU', '41':'AQU', '42':'GRA', '43':'AURA', '44':'ARA', '45':'GRA', '46':'OCC', '47':'OCC', '48':'LRE', '49':'PIE', '50':'NOR', '51':'NOR', '53':'PDL', '54':'GRA', '55':'LRE', '56':'ARA', '57':'GRA', '58':'AURA', '59':'BFC', '60':'PIC', '61':'NOR', '62':'AURA', '63':'AURA', '64':'OCC', '65':'AQU', '66':'ARA', '67':'PIC', '68':'CEN', '69':'ARA', '70':'BFC', '71':'BFC', '72':'BFC', '73':'ARA', '74':'ARA', '75':'IDF', '76':'NOR', '77':'PIC', '78':'NOR', '79':'NAQ', '80':'GF', '81':'GF', '971':'GP', '972':'FP', '973':'RE', '974':'RE', '976':'SM', '977':'SM', '978':'PM'}
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
            structure=fix_encoding(parts[25]) if len(parts) > 25 else None,  # Raison sociale site
            type_etablissement=fix_encoding(parts[24]) if len(parts) > 24 else None,  # Type etablissement
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