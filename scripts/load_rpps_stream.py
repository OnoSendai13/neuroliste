#!/usr/bin/env python3
"""Optimized loader using chunked processing."""
import os, sys, requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, backend_path)
sys.path.insert(0, backend_path)
from models import Neurologue, Base

# Use direct connection
engine = create_engine("sqlite:////mnt/g/Neuro-liste/rpps-neuro-app/backend/data/neurologues.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base.metadata.create_all(bind=engine)

API_URL = "https://www.data.gouv.fr/api/2/datasets/annuaire-sante-extractions-des-donnees-en-libre-acces-des-professionnels-intervenant-dans-le-systeme-de-sante-rpps/resources/"

DEPT_TO_REGION = {'01':'AURA','02':'GRA','03':'AURA','04':'ARA','05':'ARA','06':'PAC','07':'ARA','08':'GRA','09':'OCC','10':'GRA','11':'OCC','12':'OCC','13':'PAC','14':'NOR','15':'OCC','16':'AQU','17':'AQU','18':'CEN','19':'AQU','21':'BIF','22':'BIF','23':'CEN','24':'CEN','25':'BFC','26':'ARA','27':'NOR','28':'CEN','29':'BIF','30':'OCC','31':'OCC','32':'AQU','33':'AQU','34':'LRE','35':'BIF','36':'CEN','37':'PIE','38':'AQU','39':'BFC','40':'AQU','41':'AQU','42':'GRA','43':'AURA','44':'ARA','45':'GRA','46':'OCC','47':'OCC','48':'LRE','49':'PIE','50':'NOR','51':'NOR','53':'PDL','54':'GRA','55':'LRE','56':'ARA','57':'GRA','58':'AURA','59':'BFC','60':'PIC','61':'NOR','62':'AURA','63':'AURA','64':'OCC','65':'AQU','66':'ARA','67':'PIC','68':'CEN','69':'ARA','70':'BFC','71':'BFC','72':'BFC','73':'ARA','74':'ARA','75':'IDF','76':'NOR','77':'PIC','78':'NOR','79':'NAQ','80':'GF','81':'GF','971':'GP','972':'FP','973':'RE','974':'RE','976':'SM','977':'SM','978':'PM'}

def get_urls():
    resp = requests.get(API_URL, timeout=30)
    for r in resp.json().get('data', []):
        t, u = r.get('title',''), r.get('url','')
        if 'personne' in t: yield 'personne', u
        elif 'dipl' in t: yield 'diplomes', u
        elif 'savoir' in t: yield 'savoirfaire', u

def stream_url(url, chunk_size=50000):
    """Stream file in chunks instead of loading all in memory"""
    resp = requests.get(url, timeout=300, stream=True)
    buffer = ""
    count = 0
    for chunk in resp.iter_content(chunk_size=50000, decode_unicode=True):
        buffer += chunk
        while '\n' in buffer:
            line, buffer = buffer.split('\n', 1)
            if count > 0:  # skip header
                yield line.split('|')
            count += 1

def main():
    urls = dict(get_urls())
    print(f"URLs: {list(urls.keys())}")
    
    # Phase 1: get neuro IDs
    neuro_ids = set()
    print("Scanning diplômes...")
    resp = requests.get(urls['diplomes'], timeout=300)
    for line in resp.text.split('\n')[1:]:
        p = line.split('|')
        if len(p) >= 8 and p[7] in ('CESM15','DSM30','DIP143'):
            neuro_ids.add(p[1])
    print(f"Neuro IDs from diplômes: {len(neuro_ids)}")
    
    # Phase 2: scan savoir-faire
    neuro_sf_ids = set()
    print("Scanning savoir-faire...")
    resp = requests.get(urls['savoirfaire'], timeout=120)
    for line in resp.text.split('\n')[1:]:
        p = line.split('|')
        if len(p) >= 12 and p[11] == 'SM32':
            neuro_sf_ids.add(p[1])
    print(f"Neuro IDs from savoir-faire: {len(neuro_sf_ids)}")
    
    # Intersection
    final_ids = neuro_ids & neuro_sf_ids
    print(f"Final neuro IDs to load: {len(final_ids)}")
    
    # Phase 3: stream personne file  
    db = SessionLocal()
    db.query(Neurologue).delete()
    db.commit()
    
    count = 0
    seen_ids = set()
    print("Streaming personne file...")
    resp = requests.get(urls['personne'], timeout=600, stream=True)
    buffer = ""
    lines_read = 0
    for chunk in resp.iter_content(chunk_size=100000, decode_unicode=True):
        buffer += chunk
        while '\n' in buffer:
            line, buffer = buffer.split('\n', 1)
            lines_read += 1
            if lines_read == 1: continue  # header
            p = line.split('|')
            if len(p) < 45: continue
            if p[1] in seen_ids: continue  # deduplication
            if p[1] not in final_ids: continue
            
            dept = p[44] if p[44] else (p[36][:3] if p[36][:3] in ('971','972','973','974','976','977','978') else p[36][:2])
            try:
                nom = p[7].encode('latin1').decode('utf-8') if p[7] else ''
            except: nom = p[7]
            
            doc = Neurologue(
                id_ppss=p[1], numero_rpps=p[1], ine=p[2],
                nom=nom, prenom=(p[8] or '').encode('latin1').decode('utf-8') if p[8] else '', sexe=p[5],
                adresse=f"{p[31]} {p[32]}".strip(), code_postal=p[35], commune=(p[37] or '').encode('latin1').decode('utf-8') if p[37] else '',
                departement=dept, region=DEPT_TO_REGION.get(dept), tel=p[40], mail=p[43],
                code_profession=p[9], libelle_profession=(p[10] or '').encode('latin1').decode('utf-8') if p[10] else '',
                mode_exercice=(p[17] or '').encode('latin1').decode('utf-8') if p[17] else '', code_mode_exercice=p[16],
                structure=(p[24] or '').encode('latin1').decode('utf-8') if p[24] else '',
                type_etablissement=(p[23] or '').encode('latin1').decode('utf-8') if p[23] else '',
                diplome_neuro="1", statut="ACTIF"
            )
            db.add(doc)
            seen_ids.add(p[1])  # mark as seen
            count += 1
            if count % 500 == 0:
                db.commit()
                print(f"Loaded {count}...")
    
    db.commit()
    print(f"Total loaded: {count}")
    db.close()

if __name__ == "__main__":
    main()