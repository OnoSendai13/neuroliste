# Neuroliste - Annuaire des Neurologues Français

Application desktop autonome (Electron) et web pour explorer et exporter les neurologues français depuis la base RPPS.

## Démarrage rapide

### Application desktop (Electron)

```bash
# Développement
npm install
npm run electron:dev

# Build production (Linux AppImage)
npm run electron:build
# → dist-electron/Neuroliste-1.0.0.AppImage
```

L'AppImage est autonome : backend FastAPI embarqué, SQLite bundlé, pas de Docker requis.

### Mode web (Docker)

```bash
docker-compose up -d
# Frontend: http://127.0.0.1:5173  (nginx + React build)
# API:      http://127.0.0.1:50000 (FastAPI direct)
```

**Architecture** : `nginx` (port 80 → 5173) sert le build React statique et reverse-proxy `/api/*` vers le container `rpps-api:8000` (backend FastAPI). Le `docker-compose.yml` expose l'API directement sur 50000 pour accès direct si besoin.

### Mode web local (sans Docker)

```bash
# Backend
cd backend && pip install -r requirements.txt
python ../scripts/load_rpps.py  # Chargement initial (~10-15 min)
uvicorn main:app --reload --port 50000

# Frontend
cd frontend && npm install && npm run dev
```

## Architecture

```
neuroliste/
├── electron/
│   ├── main.js              # Process principal Electron (spawn backend, IPC, DB init)
│   ├── preload.js           # Bridge contextIsolation (API corrections)
│   └── migrations/          # Migrations SQLite schéma
├── backend/
│   ├── main.py              # API FastAPI (doctors, stats, export, check-updates, load-data)
│   ├── models.py            # Modèles SQLAlchemy
│   └── data/                # SQLite persistante
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── FilterPanel.jsx
│   │   │   ├── DoctorTable.jsx
│   │   │   ├── StatsDashboard.jsx
│   │   │   ├── CorrectionsPanel.jsx  # Workflow corrections d'adresses
│   │   │   ├── Pagination.jsx
│   │   │   └── ThemeToggle.jsx
│   │   └── index.css
│   └── public/
│       ├── icon.svg icon.ico icon.png icon.iconset/  # Multi-plateforme
├── scripts/
│   ├── load_rpps.py         # Chargement RPPS depuis data.gouv.fr
│   ├── apply_adresse_corrections.py
│   └── build-all-platforms.sh
├── data/corrections/        # CSV corrections (pending_review, confirmed, apply)
├── docs/                    # Notes de progression
└── package.json             # electron-builder config (win/nsis, mac/dmg, linux/AppImage)
```

## Fonctionnalités

- Filtres géographiques (région, département, commune) indépendants
- Mode exercice : Libéral (L), Salarié (S), Bénévole (B)
- Statistiques interactives (Recharts) rafraîchies avec les filtres
- Export CSV avec filtres appliqués
- Dark mode (clair / sombre / système)
- Vérification automatique des MAJ data.gouv.fr au démarrage (`GET /api/check-updates`)
- Workflow corrections d'adresses : review CSV → promote to confirmed → apply
- Application desktop multiplateforme : AppImage Linux, NSIS Windows, DMG macOS
- Auto-updater configuré (electron-updater + GitHub releases)
- Gestion DB corrompue (backup auto + re-copie bundled)
- Migrations SQLite schéma via `npm run migrate`

## API Endpoints

```
GET  /api/doctors?region=NAQ&departement=33&commune=Bordeaux&mode_exercice=L
GET  /api/locations?region=NAQ
GET  /api/stats?region=NAQ
GET  /api/export?region=NAQ&departement=33
GET  /api/check-updates          # Compare date import local vs data.gouv.fr
POST /api/load-data              # Rechargement RPPS
```

## Données RPPS

Source : data.gouv.fr (extraction mensuelle)

- `ps-libreacces-personne-activite.txt` (~200MB)
- `ps-libreacces-dipl-autexerc.txt` (~271MB)
- `ps-libreacces-savoirfaire.txt` (~51MB)

Filtrage neurologues : diplôme CESM15/DSM30/DIP143 ET savoir-faire SM32.

## Build multi-plateforme

```bash
# Linux (depuis Linux)
npm run electron:build

# Windows (depuis Windows ou CI)
npx electron-builder --win

# macOS (depuis macOS)
npx electron-builder --mac
```

Configuration `electron-builder` dans `package.json` → `build` :
- Win: NSIS, icon.ico
- Mac: DMG, icon.iconset, category=Medical
- Linux: AppImage, icon.png, category=Science
- Publish: GitHub releases (OnoSendai13/neuroliste)

## License

MIT
