import os
import sys
import gzip
import io
import requests
from datetime import datetime

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_
import csv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from models import Neurologue, get_db, init_db

app = FastAPI(title="RPPS Neurologues API")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:31000", "http://localhost:30000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    init_db()

@app.get("/")
def root():
    return {"message": "RPPS Neurologues API", "docs": "/docs"}

@app.get("/api/neurologues")
def get_neurologues(
    departement: str = Query(None),
    commune: str = Query(None),
    mode_exercice: str = Query(None),
    search: str = Query(None),
    sort: str = Query(None),
    order: str = Query("asc"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """Alias for /api/doctors for backwards compatibility."""
    return get_doctors(
        region=None,
        departement=departement,
        commune=commune,
        mode_exercice=mode_exercice,
        search=search,
        sort=sort,
        order=order,
        skip=skip,
        limit=limit,
        db=db
    )

@app.get("/api/doctors")
def get_doctors(
    region: str = Query(None),
    departement: str = Query(None),
    commune: str = Query(None),
    mode_exercice: str = Query(None),
    search: str = Query(None),
    sort: str = Query(None),
    order: str = Query("asc"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    query = db.query(Neurologue)
    
    if region:
        query = query.filter(Neurologue.region == region)
    if departement:
        query = query.filter(Neurologue.departement == departement)
    if commune:
        query = query.filter(Neurologue.commune.ilike(f"%{commune}%"))
    if mode_exercice:
        query = query.filter(Neurologue.mode_exercice == mode_exercice)
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Neurologue.nom.ilike(search_term),
                Neurologue.prenom.ilike(search_term),
                Neurologue.commune.ilike(search_term)
            )
        )
    
    # Apply sorting
    if sort:
        sort_col = getattr(Neurologue, sort, None)
        if sort_col:
            if order == "desc":
                query = query.order_by(sort_col.desc())
            else:
                query = query.order_by(sort_col.asc())
    
    total = query.count()
    doctors = query.offset(skip).limit(limit).all()
    
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "doctors": [
            {
                "id_ppss": d.id_ppss,
                "nom": d.nom,
                "prenom": d.prenom,
                "commune": d.commune,
                "departement": d.departement,
                "region": d.region,
                "tel": d.tel,
                "mail": d.mail,
                "mode_exercice": d.mode_exercice,
                "numero_rpps": d.numero_rpps,
                "structure": d.structure
            }
            for d in doctors
        ]
    }

@app.get("/api/locations")
def get_locations(
    region: str = Query(None),
    departement: str = Query(None),
    search: str = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(Neurologue)
    
    if region:
        query = query.filter(Neurologue.region == region)
    if departement:
        query = query.filter(Neurologue.departement == departement)
    
    results = query.distinct().with_entities(
        Neurologue.departement,
        Neurologue.commune
    ).filter(Neurologue.departement.is_not(None), Neurologue.departement != '').all()
    
    locations = {}
    for dep, com in results:
        if dep not in locations:
            locations[dep] = []
        if com and com not in locations[dep]:
            locations[dep].append(com)
    
    if search and search in locations:
        return {"communes": locations[search][:10]}
    
    return {"departements": locations}

@app.get("/api/export")
def export_csv(
    region: str = Query(None),
    departement: str = Query(None),
    commune: str = Query(None),
    mode_exercice: str = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(Neurologue)
    
    if region:
        query = query.filter(Neurologue.region == region)
    if departement:
        query = query.filter(Neurologue.departement == departement)
    if commune:
        query = query.filter(Neurologue.commune.ilike(f"%{commune}%"))
    if mode_exercice:
        query = query.filter(Neurologue.mode_exercice == mode_exercice)
    
    def generate_csv():
        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow([
            "Nom", "Prénom", "Commune", "Département", "Région",
            "Téléphone", "Email", "Mode Exercice", "Numéro RPPS"
        ])
        output.seek(0)
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)
        
        for doc in query.yield_per(100):
            writer.writerow([
                doc.nom, doc.prenom, doc.commune, doc.departement,
                doc.region, doc.tel, doc.mail, doc.mode_exercice,
                doc.numero_rpps
            ])
            output.seek(0)
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)
    
    filename = "neurologues"
    if departement:
        filename += f"_{departement}"
    if commune:
        filename += f"_{commune}"
    filename += ".csv"
    
    return StreamingResponse(
        generate_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.post("/api/load-data")
async def load_data():
    """Load RPPS neurologue data from data.gouv.fr"""
    import subprocess
    import os
    try:
        script_path = os.path.join(os.path.dirname(__file__), "..", "scripts", "load_rpps.py")
        python_path = os.path.join(os.path.dirname(__file__), ".venv", "bin", "python")
        if not os.path.exists(python_path):
            python_path = "python3"
        
        result = subprocess.run(
            [python_path, script_path],
            cwd=os.path.dirname(__file__),
            capture_output=True,
            text=True,
            timeout=600
        )
        if result.returncode == 0:
            return {"status": "success", "message": "Data loaded"}
        raise HTTPException(status_code=500, detail=result.stderr)
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Loading timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))