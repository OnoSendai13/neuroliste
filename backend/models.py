from sqlalchemy import Column, Integer, String, Date, DateTime, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
import os

Base = declarative_base()

class Neurologue(Base):
    __tablename__ = "neurologues"
    
    id_ppss = Column(String, primary_key=True)
    numero_rpps = Column(String)
    ine = Column(String)
    nom = Column(String, nullable=False)
    prenom = Column(String, nullable=False)
    date_naissance = Column(Date)
    sexe = Column(String)
    adresse = Column(String)
    code_postal = Column(String)
    commune = Column(String)
    departement = Column(String)
    region = Column(String)
    tel = Column(String)
    mail = Column(String)
    code_profession = Column(String)
    libelle_profession = Column(String)
    mode_exercice = Column(String)
    code_mode_exercice = Column(String)
    diplome_neuro = Column(String)
    specialite_code = Column(String)
    specialite_libelle = Column(String)
    date_extraction = Column(Date)
    date_import = Column(DateTime, default=func.now())
    statut = Column(String, default="ACTIF")

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/neurologues.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    Base.metadata.create_all(bind=engine)