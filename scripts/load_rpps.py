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
        if len(parts) < 45:
            continue
        
        # Columns from personne file header:
        # 0=TypeId, 1=Id_PP, 2=Ine, 7=Nom, 8=Prenom, 5=Sexe, 9=CodeProf, 10=LibelleProf,
        # 16=CodeMode, 17=Mode, 30=TypeVoie, 31=Voie, 35=CodePostal, 37=Commune,
        # 40=Tel, 43=Email, 44=Dept
        id_ppss = parts[1]  # Id_PP is column 1
        if id_ppss not in neuro_ids:
            continue
        
        # Skip if already processed (deduplication)
        if id_ppss in seen_ids:
            continue
        seen_ids.add(id_ppss)
        
        adresse = f"{parts[31]} {parts[32]}" if len(parts) > 32 else None
        
        doc = Neurologue(
            id_ppss=id_ppss,
            numero_rpps=id_ppss,
            ine=parts[2] if len(parts) > 2 else None,
            nom=parts[7] if len(parts) > 7 else None,
            prenom=parts[8] if len(parts) > 8 else None,
            sexe=parts[5] if len(parts) > 5 else None,
            adresse=adresse,
            code_postal=parts[35] if len(parts) > 35 else None,
            commune=parts[37] if len(parts) > 37 else None,
            departement=parts[44] if len(parts) > 44 else None,
            tel=parts[40] if len(parts) > 40 else None,
            mail=parts[43] if len(parts) > 43 else None,
            code_profession=parts[9] if len(parts) > 9 else None,
            libelle_profession=parts[10] if len(parts) > 10 else None,
            mode_exercice=parts[17] if len(parts) > 17 else None,
            code_mode_exercice=parts[16] if len(parts) > 16 else None,
            specialite_code="NEURO",
            specialite_libelle="Neurologie",
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