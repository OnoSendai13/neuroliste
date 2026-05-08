from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_
import csv
import io
from models import Neurologue, get_db, init_db
import httpx

app = FastAPI(title="RPPS Neurologues API")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8000"],
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

@app.get("/api/doctors")
def get_doctors(
    region: str = Query(None),
    departement: str = Query(None),
    commune: str = Query(None),
    mode_exercice: str = Query(None),
    search: str = Query(None),
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
                "numero_rpps": d.numero_rpps
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
    ).all()
    
    # Group by departement then commune
    locations = {}
    for dep, com in results:
        if dep not in locations:
            locations[dep] = []
        if com and com not in locations[dep]:
            locations[dep].append(com)
    
    if search and search in locations:
        # Return autocomplete for commune
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
        
        # Header
        writer.writerow([
            "Nom", "Prénom", "Commune", "Département", "Région",
            "Téléphone", "Email", "Mode Exercice", "Numéro RPPS"
        ])
        output.seek(0)
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)
        
        # Data
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

@app.post("/api/update")
async def update_database():
    """Trigger database update via MCP server"""
    try:
        async with httpx.AsyncClient() as client:
            # Call MCP to fetch latest RPPS data
            response = await client.post(
                "http://mcp-server:8007/mcp",
                json={
                    "jsonrpc": "2.0",
                    "method": "update_rpps",
                    "id": 1
                },
                timeout=300.0
            )
            return {"status": "success", "message": "Update triggered"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))