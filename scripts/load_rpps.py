#!/usr/bin/env python3
"""
Load RPPS data directly from data.gouv.fr static files.
Filters for neurologues based on diplômes and savoir-faire.
"""
import os
import sys
import io
import requests
from sqlalchemy import text

# Add backend to path - use absolute path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, backend_path)
from models import Neurologue, SessionLocal, init_db

# RPPS static file URLs - updated monthly by Santé Publique France
FILES = {
    "personne": "https://static.data.gouv.fr/resources/annuaire-sante-extractions-des-donnees-en-libre-acces-des-professionnels-intervenant-dans-le-systeme-de-sante-rpps/20260505-082255/ps-libreacces-personne-activite.txt",
    "diplomes": "https://static.data.gouv.fr/resources/annuaire-sante-extractions-des-donnees-en-libre-acces-des-professionnels-intervenant-dans-le-systeme-de-sante-rpps/20260505-081946/ps-libreacces-dipl-autexerc.txt",
    "savoirfaire": "https://static.data.gouv.fr/resources/annuaire-sante-extractions-des-donnees-en-libre-acces-des-professionnels-intervenant-dans-le-systeme-de-sante-rpps/20260505-082529/ps-libreacces-savoirfaire.txt"
}

def download_file(url):
    """Download txt file and return lines."""
    print(f"Downloading {url}...")
    resp = requests.get(url, timeout=600)
    resp.raise_for_status()
    return io.StringIO(resp.text).readlines()

def load_neurologues():
    """Load and filter neurologues from RPPS data."""
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
        # 16=CodeMode, 17=Mode, 24=RaisonSocialeSite (structure), 30=TypeVoie, 31=Voie, 35=CodePostal, 
        # 36=CodeCommune, 37=Commune, 40=Tel, 43=Email, 44=DeptCode
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
            tel=parts[40] if len(parts) > 40 else None,
            mail=parts[43] if len(parts) > 43 else None,
            code_profession=parts[9] if len(parts) > 9 else None,
            libelle_profession=parts[10] if len(parts) > 10 else None,
            mode_exercice=parts[17] if len(parts) > 17 else None,
            code_mode_exercice=parts[16] if len(parts) > 16 else None,
            structure=fix_encoding(parts[24]) if len(parts) > 24 else None,  # Raison sociale site (col 25)
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