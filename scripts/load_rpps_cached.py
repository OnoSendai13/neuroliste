#!/usr/bin/env python3
"""Optimized loader - downloads all files first, then processes locally."""
import os, sys, requests, time
from concurrent.futures import ThreadPoolExecutor

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, backend_path)
from models import Neurologue, SessionLocal, init_db

URLS = [
    ('diplomes', 'https://static.data.gouv.fr/resources/annuaire-sante-extractions-des-donnees-en-libre-acces-des-professionnels-intervenant-dans-le-systeme-de-sante-rpps/20260610-120547/ps-libreacces-dipl-autexerc.txt'),
    ('savoirfaire', 'https://static.data.gouv.fr/resources/annuaire-sante-extractions-des-donnees-en-libre-acces-des-professionnels-intervenant-dans-le-systeme-de-sante-rpps/20260610-120956/ps-libreacces-savoirfaire.txt'),
    ('personne', 'https://static.data.gouv.fr/resources/annuaire-sante-extractions-des-donnees-en-libre-acces-des-professionnels-intervenant-dans-le-systeme-de-sante-rpps/20260610-120843/ps-libreacces-personne-activite.txt')
]

CACHE_DIR = '/tmp/rpps_cache'
os.makedirs(CACHE_DIR, exist_ok=True)

def download(name, url):
    print(f"Downloading {name}...")
    start = time.time()
    r = requests.get(url, timeout=600)
    path = os.path.join(CACHE_DIR, f"{name}.txt")
    with open(path, 'wb') as f:
        f.write(r.content)
    print(f"{name} done in {time.time()-start:.1f}s")
    return name, path

def main():
    # Download all in parallel
    with ThreadPoolExecutor(max_workers=3) as ex:
        results = list(ex.map(lambda x: download(x[0], x[1]), URLS))
    
    paths = dict(results)
    
    # Process files locally
    db = SessionLocal()
    init_db()
    db.query(Neurologue).delete()
    
    # Get neuro IDs
    neuro_ids = set()
    with open(paths['diplomes']) as f:
        for line in f:
            p = line.strip().split('|')
            if len(p) >= 8 and p[7] in ('CESM15','DSM30','DIP143'):
                neuro_ids.add(p[1])
    print(f"Neuro from diplomes: {len(neuro_ids)}")
    
    neuro_sf_ids = set()
    with open(paths['savoirfaire']) as f:
        for line in f:
            p = line.strip().split('|')
            if len(p) >= 12 and p[11] == 'SM32':
                neuro_sf_ids.add(p[1])
    print(f"Neuro from savoir-faire: {len(neuro_sf_ids)}")
    
    final_ids = neuro_ids & neuro_sf_ids
    print(f"Final IDs: {len(final_ids)}")
    
    # Lookup dict
    seen = set()
    DEPT_TO_REGION = {'01':'AURA','02':'GRA','03':'AURA','04':'ARA','05':'ARA','06':'PAC','07':'ARA','08':'GRA','09':'OCC','10':'GRA','11':'OCC','12':'OCC','13':'PAC','14':'NOR','15':'OCC','16':'AQU','17':'AQU','18':'CEN','19':'AQU','21':'BIF','22':'BIF','23':'CEN','24':'CEN','25':'BFC','26':'ARA','27':'NOR','28':'CEN','29':'BIF','30':'OCC','31':'OCC','32':'AQU','33':'AQU','34':'LRE','35':'BIF','36':'CEN','37':'PIE','38':'AQU','39':'BFC','40':'AQU','41':'AQU','42':'GRA','43':'AURA','44':'ARA','45':'GRA','46':'OCC','47':'OCC','48':'LRE','49':'PIE','50':'NOR','51':'NOR','53':'PDL','54':'GRA','55':'LRE','56':'ARA','57':'GRA','58':'AURA','59':'BFC','60':'PIC','61':'NOR','62':'AURA','63':'AURA','64':'OCC','65':'AQU','66':'ARA','67':'PIC','68':'CEN','69':'ARA','70':'BFC','71':'BFC','72':'BFC','73':'ARA','74':'ARA','75':'IDF','76':'NOR','77':'PIC','78':'NOR','79':'NAQ','80':'GF','81':'GF','971':'GP','972':'FP','973':'RE','974':'RE','976':'SM','977':'SM','978':'PM'}
    
    count = 0
    with open(paths['personne']) as f:
        for line in f:
            p = line.strip().split('|')
            if len(p) < 45: continue
            if p[1] in seen: continue
            if p[1] not in final_ids: continue
            seen.add(p[1])
            
            dept = p[44] if p[44] else (p[36][:3] if p[36][:3] in ('971','972','973','974','976','977','978') else p[36][:2])
            try:
                nom = p[7].encode('latin1').decode('utf-8')
                prenom = p[8].encode('latin1').decode('utf-8')
                commune = p[37].encode('latin1').decode('utf-8')
            except:
                nom = prenom = commune = p[7] if p[7] else ''
            
            doc = Neurologue(id_ppss=p[1], numero_rpps=p[1], ine=p[2], nom=nom, prenom=prenom,
                sexe=p[5], adresse=f"{p[31]} {p[32]}".strip(), code_postal=p[35], commune=commune,
                departement=dept, region=DEPT_TO_REGION.get(dept), tel=p[40], mail=p[43],
                code_profession=p[9], libelle_profession=p[10], mode_exercice=p[17], code_mode_exercice=p[16],
                structure=p[24], type_etablissement=p[23], diplome_neuro="1", statut="ACTIF")
            db.add(doc)
            count += 1
            if count % 1000 == 0:
                db.commit()
                print(f"Loaded {count}...")
    
    db.commit()
    print(f"Total loaded: {count}")
    db.close()

if __name__ == "__main__":
    main()