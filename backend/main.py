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
from sqlalchemy import or_, func
import csv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from models import Neurologue, get_db, init_db

app = FastAPI(title="RPPS Neurologues API")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:31000", "http://localhost:30000", "http://localhost:5173", "http://127.0.0.1:5173", "http://127.0.0.1:50000"],
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
        # Map codes to labels (L/Cabinet, S/Salarié, H/Hospitalier)
        mode_map = {'L': 'Lib,indép,artis,com', 'S': 'Salarié', 'H': 'Hospitalier', 'B': 'Mixte'}
        mode_label = mode_map.get(mode_exercice, mode_exercice)
        query = query.filter(Neurologue.mode_exercice == mode_label)
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

@app.get("/api/stats")
def get_stats(
    region: str = Query(None),
    departement: str = Query(None),
    db: Session = Depends(get_db)
):
    """Get statistics for charts and dashboards."""
    # Stats by departement (filtered if region provided)
    dep_query = db.query(Neurologue.departement, func.count(Neurologue.id_ppss).label("count"))
    dep_query = dep_query.filter(Neurologue.departement.is_not(None), Neurologue.departement != '')
    if region:
        dep_query = dep_query.filter(Neurologue.region == region)
    if departement:
        dep_query = dep_query.filter(Neurologue.departement == departement)
    dep_stats = dep_query.group_by(Neurologue.departement).order_by(func.count().desc()).limit(20).all()
    
    # Stats by mode_exercice (filtered)
    mode_query = db.query(Neurologue.mode_exercice, func.count(Neurologue.id_ppss).label("count"))
    if region:
        mode_query = mode_query.filter(Neurologue.region == region)
    if departement:
        mode_query = mode_query.filter(Neurologue.departement == departement)
    mode_query = mode_query.filter(Neurologue.mode_exercice.is_not(None), Neurologue.mode_exercice != '')
    mode_stats = mode_query.group_by(Neurologue.mode_exercice).all()
    
    # Stats by region (full list unless filtered)
    if region:
        region_stats = [(region, dep_stats[0][1] if departement else sum(d[1] for d in dep_stats))]
    else:
        region_query = db.query(Neurologue.region, func.count(Neurologue.id_ppss).label("count"))
        region_query = region_query.filter(Neurologue.region.is_not(None), Neurologue.region != '')
        region_stats = region_query.group_by(Neurologue.region).order_by(func.count().desc()).all()
    
    # Stats by type_etablissement (filtered)
    type_query = db.query(Neurologue.type_etablissement, func.count(Neurologue.id_ppss).label("count"))
    if region:
        type_query = type_query.filter(Neurologue.region == region)
    if departement:
        type_query = type_query.filter(Neurologue.departement == departement)
    type_query = type_query.filter(Neurologue.type_etablissement.is_not(None), Neurologue.type_etablissement != '')
    type_stats = type_query.group_by(Neurologue.type_etablissement).order_by(func.count().desc()).limit(15).all()
    
    # Total count (filtered)
    total_query = db.query(Neurologue)
    if region:
        total_query = total_query.filter(Neurologue.region == region)
    if departement:
        total_query = total_query.filter(Neurologue.departement == departement)
    total = total_query.count()
    
    # Get last extraction date
    last_neurologue = db.query(Neurologue.date_extraction).filter(
        Neurologue.date_extraction.is_not(None)
    ).order_by(Neurologue.date_extraction.desc()).first()
    last_import = db.query(Neurologue.date_import).filter(
        Neurologue.date_import.is_not(None)
    ).order_by(Neurologue.date_import.desc()).first()

    return {
        "total": total,
        "departements": [{"name": d[0], "value": d[1]} for d in dep_stats],
        "modes": [{"name": m[0] or "Autre", "value": m[1]} for m in mode_stats],
        "regions": [{"name": r[0] or "Inconnu", "value": r[1]} for r in region_stats],
        "types_etablissement": [{"name": t[0] or "Inconnu", "value": t[1]} for t in type_stats],
        "last_extraction": last_neurologue[0].isoformat() if last_neurologue and last_neurologue[0] else None,
        "last_import": last_import[0].isoformat() if last_import and last_import[0] else None
    }

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
        # Map codes to labels
        mode_map = {'L': 'Lib,indép,artis,com', 'S': 'Salarié', 'H': 'Hospitalier', 'B': 'Mixte'}
        mode_label = mode_map.get(mode_exercice, mode_exercice)
        query = query.filter(Neurologue.mode_exercice == mode_label)
    
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