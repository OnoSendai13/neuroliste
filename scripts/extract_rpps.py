#!/usr/bin/env python3
"""
Extract neurologues from RPPS data files
"""
import httpx
import gzip
from pathlib import Path
import re

# RPPS field positions (fixed-width format)
# Source: https://esante.gouv.fr/sites/default/files/fiches-techniques_ps-libreacces.pdf

SAVIORFAIRE_FIELDS = 48  # Approximate, need to verify
DIPL_FIELDS = 20
PERS_FIELDS = 65

def download_file(url: str, dest: Path):
    """Download and extract RPPS file"""
    dest.parent.mkdir(parents=True, exist_ok=True)
    
    with httpx.Client(follow_redirects=True, timeout=300.0) as client:
        with client.stream("GET", url) as response:
            response.raise_for_status()
            with open(dest, 'wb') as f:
                for chunk in response.iter_bytes():
                    f.write(chunk)
    
    # If gzipped
    if dest.suffix == '.gz':
        dest.extract(decompress=True)

def parse_savoirfaire(filepath: Path, neuro_codes=None):
    """
    Parse ps-libreacces-savoirfaire.txt
    Returns set of PPSS IDs with neurology qualification
    """
    neuro_codes = neuro_codes or ['NEURO', 'NEUROLOGIE']
    neurologues = set()
    
    with open(filepath, 'r', encoding='utf-8') as f:
        # Skip header
        next(f)
        for line in f:
            # Field positions from RPPS spec
            # Code savoir-faire at position varies
            line = line.strip()
            if not line:
                continue
            
            parts = line.split('\t')
            if len(parts) >= 5:
                code_sf = parts[4] if len(parts) > 4 else ''
                if any(neuro in code_sf.upper() for neuro in neuro_codes):
                    ppss = parts[0]  # PPSS identifier
                    neurologues.add(ppss)
    
    return neurologues

def parse_diplomes(filepath: Path, neuro_diplomes=None):
    """
    Parse ps-libreacces-dipl-autexerc.txt  
    Returns dict of PPSS -> diploma info
    """
    neuro_diplomes = neuro_diplomes or ['NEUROLOGIE', 'NEURO']
    diplomes = {}
    
    with open(filepath, 'r', encoding='utf-8') as f:
        next(f)  # Skip header
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 10:
                ppss = parts[0]
                libelle_diplome = parts[8] if len(parts) > 8 else ''
                
                if any(neuro in libelle_diplome.upper() for neuro in neuro_diplomes):
                    diplomes[ppss] = {
                        'code': parts[7] if len(parts) > 7 else '',
                        'libelle': libelle_diplome,
                        'date': parts[9] if len(parts) > 9 else ''
                    }
    
    return diplomes

def parse_personnes(filepath: Path, neuro_ppss, diplomes):
    """
    Parse ps-libreacces-personne-activite.txt
    Returns list of neurologue dicts
    """
    neurologues = []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        next(f)
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 50:
                ppss = parts[0]
                
                # Cross-check: must have both savoirfaire AND diplome
                if ppss in neuro_ppss and ppss in diplomes:
                    neuro = {
                        'id_ppss': ppss,
                        'numero_rpps': parts[3] if len(parts) > 3 else '',
                        'nom': parts[1] if len(parts) > 1 else '',
                        'prenom': parts[2] if len(parts) > 2 else '',
                        'date_naissance': parts[4] if len(parts) > 4 else '',
                        'sexe': parts[5] if len(parts) > 5 else '',
                        'adresse': parts[6] if len(parts) > 6 else '',
                        'code_postal': parts[7] if len(parts) > 7 else '',
                        'commune': parts[8] if len(parts) > 8 else '',
                        'departement': parts[9] if len(parts) > 9 else '',
                        'region': parts[10] if len(parts) > 10 else '',
                        'tel': parts[11] if len(parts) > 11 else '',
                        'mail': parts[12] if len(parts) > 12 else '',
                        'code_profession': parts[13] if len(parts) > 13 else '',
                        'libelle_profession': parts[14] if len(parts) > 14 else '',
                        'mode_exercice': parts[30] if len(parts) > 30 else '',
                        'code_mode_exercice': parts[29] if len(parts) > 29 else '',
                        'diplome_neuro': diplomes[ppss]['date'],
                        'specialite_code': diplomes[ppss]['code'],
                        'specialite_libelle': diplomes[ppss]['libelle'],
                    }
                    neurologues.append(neuro)
    
    return neurologues

if __name__ == "__main__":
    print("RPPS Extraction Script - Ready")
    print("Usage: python extract_rpps.py --savoirfaire file --diplomes file --personnes file")