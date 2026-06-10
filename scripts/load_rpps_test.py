#!/usr/bin/env python3
"""Quick test loader - loads first 500 lines for testing pipeline."""
import os
import sys
import requests

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, backend_path)
from models import Neurologue, SessionLocal, init_db

API_URL = "https://www.data.gouv.fr/api/2/datasets/annuaire-sante-extractions-des-donnees-en-libre-acces-des-professionnels-intervenant-dans-le-systeme-de-sante-rpps/resources/"

def get_urls():
    resp = requests.get(API_URL, timeout=30)
    resources = resp.json().get('data', [])
    urls = {}
    for r in resources:
        title, url = r.get('title', ''), r.get('url', '')
        if 'personne' in title:
            urls['personne'] = url
        elif 'dipl' in title:
            urls['diplomes'] = url
        elif 'savoir' in title:
            urls['savoirfaire'] = url
    return urls

DEPT_TO_REGION = {'01':'AURA','02':'GRA','03':'AURA','04':'ARA','05':'ARA','06':'PAC','07':'ARA','08':'GRA','09':'OCC','10':'GRA','11':'OCC','12':'OCC','13':'PAC','14':'NOR','15':'OCC','16':'AQU','17':'AQU','18':'CEN','19':'AQU','21':'BIF','22':'BIF','23':'CEN','24':'CEN','25':'BFC','26':'ARA','27':'NOR','28':'CEN','29':'BIF','30':'OCC','31':'OCC','32':'AQU','33':'AQU','34':'LRE','35':'BIF','36':'CEN','37':'PIE','38':'AQU','39':'BFC','40':'AQU','41':'AQU','42':'GRA','43':'AURA','44':'ARA','45':'GRA','46':'OCC','47':'OCC','48':'LRE','49':'PIE','50':'NOR','51':'NOR','53':'PDL','54':'GRA','55':'LRE','56':'ARA','57':'GRA','58':'AURA','59':'BFC','60':'PIC','61':'NOR','62':'AURA','63':'AURA','64':'OCC','65':'AQU','66':'ARA','67':'PIC','68':'CEN','69':'ARA','70':'BFC','71':'BFC','72':'BFC','73':'ARA','74':'ARA','75':'IDF','76':'NOR','77':'PIC','78':'NOR','79':'NAQ','80':'GF','81':'GF','971':'GP','972':'FP','973':'RE','974':'RE','976':'SM','977':'SM','978':'PM'}

def fix_encoding(s):
    if not s: return s
    try: return s.encode('latin1').decode('utf-8')
    except: return str(s)

def load_test():
    urls = get_urls()
    db = SessionLocal()
    init_db()
    db.query(Neurologue).delete()
    
    # Get neuro IDs from diplomes + savoir-faire
    diplomes = requests.get(urls['diplomes'], timeout=120).text.split('\n')[:5000]
    neuro_ids = set()
    for line in diplomes[1:]:
        if '|' in line and line.split('|')[7] in ('CESM15','DSM30','DIP143'):
            neuro_ids.add(line.split('|')[1])
    
    print(f"Neuro IDs from diplomes: {len(neuro_ids)}")
    
    # Load personne sample
    pa = requests.get(urls['personne'], timeout=120).text.split('\n')[:5000]
    count = 0
    for line in pa[1:]:
        if '|' not in line or len(line.split('|')) < 45: continue
        parts = line.split('|')
        if parts[1] not in neuro_ids: continue
        
        com_code = parts[36] if len(parts) > 36 else ''
        dept = parts[44] if len(parts) > 44 and parts[44] else (com_code[:3] if len(com_code) >= 3 and com_code[:3] in ('971','972','973','974','976','977','978') else com_code[:2]) if com_code else None
        
        doc = Neurologue(
            id_ppss=parts[1], numero_rpps=parts[1], ine=parts[2] if len(parts) > 2 else None,
            nom=fix_encoding(parts[7]), prenom=fix_encoding(parts[8]), sexe=parts[5],
            adresse=fix_encoding(f"{parts[31]} {parts[32]}" if len(parts) > 32 else ""),
            code_postal=parts[35], commune=fix_encoding(parts[37]), departement=dept,
            region=DEPT_TO_REGION.get(dept,None), tel=parts[40], mail=parts[43],
            code_profession=parts[9], libelle_profession=fix_encoding(parts[10]),
            mode_exercice=fix_encoding(parts[17]), code_mode_exercice=parts[16],
            structure=fix_encoding(parts[24]), type_etablissement=fix_encoding(parts[23]),
            diplome_neuro="1", statut="ACTIF"
        )
        db.add(doc)
        count += 1
    
    db.commit()
    print(f"Loaded {count} test neurologues")
    db.close()

if __name__ == "__main__":
    load_test()