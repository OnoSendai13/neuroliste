#!/usr/bin/env python3
"""
Load RPPS data using parquet files (6x faster than txt).
Filters for neurologues based on diplômes and savoir-faire.
"""
import os
import sys
import requests
import pandas as pd

# Add backend to path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, backend_path)
from models import Neurologue, SessionLocal, init_db

API_URL = "https://www.data.gouv.fr/api/2/datasets/annuaire-sante-extractions-des-donnees-en-libre-acces-des-professionnels-intervenant-dans-le-systeme-de-sante-rpps/resources/"

def get_parquet_urls():
    """Fetch parquet URLs from data.gouv.fr API"""
    resp = requests.get(API_URL, timeout=30)
    resp.raise_for_status()
    resources = resp.json()
    
    urls = {}
    for r in resources.get('data', []):
        title = r.get('title', '')
        # Get parquet URL from extras
        extras = r.get('extras', {}) or {}
        parquet_url = extras.get('analysis:parquet_url', '')
        if 'personne' in title and parquet_url:
            urls['personne'] = parquet_url
        elif 'dipl' in title:
            urls['diplomes'] = r.get('url', '')
        elif 'savoir' in title:
            urls['savoirfaire'] = r.get('url', '')
    return urls

DEPT_TO_REGION = {
    '01':'AURA', '02':'GRA', '03':'AURA', '04':'ARA', '05':'ARA', '06':'PAC', '07':'ARA', '08':'GRA',
    '09':'OCC', '10':'GRA', '11':'OCC', '12':'OCC', '13':'PAC', '14':'NOR', '15':'OCC', '16':'AQU',
    '17':'AQU', '18':'CEN', '19':'AQU', '2A':'COR', '2B':'COR', '21':'BIF', '22':'BIF', '23':'CEN',
    '24':'CEN', '25':'BFC', '26':'ARA', '27':'NOR', '28':'CEN', '29':'BIF', '30':'OCC', '31':'OCC',
    '32':'AQU', '33':'AQU', '34':'LRE', '35':'BIF', '36':'CEN', '37':'PIE', '38':'AQU', '39':'BFC',
    '40':'AQU', '41':'AQU', '42':'GRA', '43':'AURA', '44':'ARA', '45':'GRA', '46':'OCC', '47':'OCC',
    '48':'LRE', '49':'PIE', '50':'NOR', '51':'NOR', '53':'PDL', '54':'GRA', '55':'LRE', '56':'ARA',
    '57':'GRA', '58':'AURA', '59':'BFC', '60':'PIC', '61':'NOR', '62':'AURA', '63':'AURA', '64':'OCC',
    '65':'AQU', '66':'ARA', '67':'PIC', '68':'CEN', '69':'ARA', '70':'BFC', '71':'BFC', '72':'BFC',
    '73':'ARA', '74':'ARA', '75':'IDF', '76':'NOR', '77':'PIC', '78':'NOR', '79':'NAQ', '80':'GF',
    '81':'GF', '971':'GP', '972':'FP', '973':'RE', '974':'RE', '976':'SM', '977':'SM', '978':'PM'
}

def derive_dept(commune_code):
    if not commune_code or len(str(commune_code)) < 2:
        return None
    cc = str(commune_code)
    if cc[:3] in ('971', '972', '973', '974', '976', '977', '978'):
        return cc[:3]
    return cc[:2]

def fix_encoding(s):
    if not s:
        return s
    try:
        return s.encode('latin1').decode('utf-8')
    except:
        return str(s)

def load_neurologues():
    urls = get_parquet_urls()
    if not urls.get('personne'):
        print("Error: Could not find parquet URL for personne file")
        return
    
    print("Fetching parquet file...")
    df = pd.read_parquet(urls['personne'])
    
    print(f"Total records in file: {len(df)}")
    print(f"Columns: {list(df.columns)[:10]}...")
    
    # Load diplomes to get neuro IDs
    print("Loading diplômes...")
    diplomes_df = pd.read_csv(urls['diplomes'], sep='|', dtype=str, on_bad_lines='skip')
    neuro_diplome_ids = set(diplomes_df[diplomes_df.iloc[:, 7].isin(['CESM15', 'DSM30', 'DIP143'])].iloc[:, 1])
    print(f"Found {len(neuro_diplome_ids)} with neuro diploma")
    
    # Load savoir-faire
    print("Loading savoir-faire...")
    sf_df = pd.read_csv(urls['savoirfaire'], sep='|', dtype=str, on_bad_lines='skip')
    neuro_sf_ids = set(sf_df[sf_df.iloc[:, 11] == 'SM32'].iloc[:, 1])
    print(f"Found {len(neuro_sf_ids)} with neuro savoir-faire")
    
    # Intersection
    neuro_ids = neuro_diplome_ids & neuro_sf_ids
    print(f"Neurologues to load: {len(neuro_ids)}")
    
    # Filter and load
    db = SessionLocal()
    init_db()
    db.query(Neurologue).delete()
    db.commit()
    
    count = 0
    for id_ppss in neuro_ids:
        row = df[df.iloc[:, 1] == id_ppss].iloc[0] if len(df[df.iloc[:, 1] == id_ppss]) > 0 else None
        if not row:
            continue
        
        dept = row.iloc[44] if len(row) > 44 and pd.notna(row.iloc[44]) else derive_dept(row.iloc[36])
        region = DEPT_TO_REGION.get(dept, None)
        
        doc = Neurologue(
            id_ppss=str(id_ppss),
            numero_rpps=str(id_ppss),
            ine=str(row.iloc[2]) if len(row) > 2 else None,
            nom=fix_encoding(row.iloc[7]) if len(row) > 7 else None,
            prenom=fix_encoding(row.iloc[8]) if len(row) > 8 else None,
            sexe=str(row.iloc[5]) if len(row) > 5 else None,
            adresse=fix_encoding(f"{row.iloc[31] if len(row) > 31 else ''} {row.iloc[32] if len(row) > 32 else ''}"),
            code_postal=str(row.iloc[35]) if len(row) > 35 else None,
            commune=fix_encoding(row.iloc[37]) if len(row) > 37 else None,
            departement=dept,
            region=region,
            tel=str(row.iloc[40]) if len(row) > 40 else None,
            mail=str(row.iloc[43]) if len(row) > 43 else None,
            code_profession=str(row.iloc[9]) if len(row) > 9 else None,
            libelle_profession=fix_encoding(row.iloc[10]) if len(row) > 10 else None,
            mode_exercice=fix_encoding(row.iloc[17]) if len(row) > 17 else None,
            code_mode_exercice=str(row.iloc[16]) if len(row) > 16 else None,
            structure=fix_encoding(row.iloc[24]) if len(row) > 24 else None,
            type_etablissement=fix_encoding(row.iloc[23]) if len(row) > 23 else None,
            diplome_neuro="1",
            statut="ACTIF"
        )
        db.add(doc)
        count += 1
        
        if count % 500 == 0:
            db.commit()
            print(f"Loaded {count} neurologues...")
    
    db.commit()
    print(f"Total neurologues loaded: {count}")
    db.close()

if __name__ == "__main__":
    load_neurologues()