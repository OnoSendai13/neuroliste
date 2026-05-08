#!/usr/bin/env python3
"""
Initialize the database with sample neurologue data for testing
"""
import sys
sys.path.insert(0, '/app/backend')

from models import Neurologue, engine, init_db
from sqlalchemy.orm import sessionmaker

Session = sessionmaker(bind=engine)

SAMPLE_DOCTORS = [
    {
        "id_ppss": "123456789",
        "numero_rpps": "10000001",
        "nom": "DUPONT",
        "prenom": "Jean",
        "commune": "Lyon",
        "departement": "69",
        "region": "Auvergne-Rhône-Alpes",
        "tel": "0472000000",
        "mail": "j.dupont@lyon.fr",
        "mode_exercice": "LIBERAL",
        "code_mode_exercice": "1",
        "date_naissance": "1970-01-01",
        "sexe": "M",
        "adresse": "12 rue de la République",
        "code_postal": "69002",
        "specialite_code": "NEURO",
        "specialite_libelle": "Neurologie",
        "diplome_neuro": "2005-06-01"
    },
    {
        "id_ppss": "987654321",
        "numero_rpps": "10000002",
        "nom": "MARTIN",
        "prenom": "Marie",
        "commune": "Lyon",
        "departement": "69",
        "region": "Auvergne-Rhône-Alpes",
        "tel": "0472000001",
        "mail": "m.martin@lyon.fr",
        "mode_exercice": "HOSPITALIER",
        "code_mode_exercice": "2",
        "date_naissance": "1975-03-15",
        "sexe": "F",
        "adresse": "Hôpital Édouard Herriot",
        "code_postal": "69003",
        "specialite_code": "NEURO",
        "specialite_libelle": "Neurologie",
        "diplome_neuro": "2010-09-01"
    },
    {
        "id_ppss": "456789123",
        "numero_rpps": "10000003",
        "nom": "BERNARD",
        "prenom": "Pierre",
        "commune": "Clermont-Ferrand",
        "departement": "63",
        "region": "Auvergne-Rhône-Alpes",
        "tel": "0473000000",
        "mail": "p.bernard@cf.fr",
        "mode_exercice": "LIBERAL",
        "code_mode_exercice": "1",
        "date_naissance": "1980-07-20",
        "sexe": "M",
        "adresse": "15 avenue Pasteur",
        "code_postal": "63000",
        "specialite_code": "NEURO",
        "specialite_libelle": "Neurologie",
        "diplome_neuro": "2015-09-01"
    }
]

def populate_sample_data():
    init_db()
    session = Session()
    
    for doc in SAMPLE_DOCTORS:
        neuro = Neurologue(**doc)
        session.add(neuro)
    
    session.commit()
    session.close()
    print(f"Added {len(SAMPLE_DOCTORS)} sample neurologues")

if __name__ == "__main__":
    populate_sample_data()