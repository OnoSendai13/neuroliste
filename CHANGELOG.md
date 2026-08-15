# Changelog

All notable changes to Neuroliste are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-08-14

### Added — Application desktop autonome (Electron)
- Electron wrapper : `electron/main.js` (spawn backend, DB init, corrupt handling, IPC)
- `electron/preload.js` : bridge contextIsolation avec API corrections
- Migrations SQLite : `electron/migrations.js` + `electron/migrations/001_indexes.js`
- DB strategy : bundled SQLite copié vers `userData` au premier lancement, gestion DB corrompue (backup + re-copie)
- Build multi-plateforme : AppImage Linux (122MB), NSIS Windows, DMG macOS
- Icônes multi-plateforme générées depuis `icon.svg` : PNG (16→1024px), ICO (Windows), iconset (macOS)
- Auto-updater : `electron-updater` configuré pour GitHub releases
- `GET /api/check-updates` : compare date import locale vs data.gouv.fr
- `CorrectionsPanel.jsx` : UI React pour workflow corrections d'adresses
  - List pending_review CSV
  - Promouvoir entrées à confirmed + apply_allowed
  - Apply confirmées via `apply_adresse_corrections.py`
  - Vérifier MAJ data.gouv.fr + rechargement RPPS
- IPC handlers : `corrections:list-pending`, `corrections:promote-to-confirmed`, `corrections:apply-confirmed`, `corrections:check-updates`, `corrections:trigger-load-data`
- `package.json` : config `electron-builder` (appId, productName, extraResources, publish GitHub)
- Script `scripts/build-all-platforms.sh`

### Added — Data cleanup
- Audit 489 entrées avec `mode_exercice` vide → `data/corrections/empty_mode_exercice_review.csv`
- Audit 166 entrées avec adresse/code_postal/commune manquants → `data/corrections/empty_address_review.csv`
- CSV de review pour practitioniens potentiellement à la retraite ou adresses périmées

### Changed
- `backend/main.py` : ajout endpoint `check-updates` (data.gouv.fr CKAN API)
- `frontend/src/App.jsx` : import + rendu `CorrectionsPanel`
- `package.json` : `electron-builder` config (win→ico, mac→iconset, linux→png)
- README réécrit pour refléter l'architecture Electron

## [1.0.0] - 2026-06-11

### Added
- FastAPI backend + React frontend + SQLite
- RPPS data loading from data.gouv.fr (diplômes CESM15/DSM30/DIP143 + savoir-faire SM32)
- Geographic filters: region, department, commune (independent)
- Mode exercice filter: Libéral (L), Salarié (S)
- Interactive statistics dashboard with Recharts
- CSV export with applied filters
- Dark mode toggle (light/dark/system)
- Docker Compose deployment
- Streaming download with resume + exponential backoff retry
- Auto-discovery of data.gouv.fr resource URLs
- Address corrections pipeline: audit → candidates → apply
- 524 address corrections applied from external research

### Data
- 3,540 neurologues loaded from RPPS (June 2026 extraction)
- Department → Region mapping (2024 post-2016 reform)
- Corsican departments (2A/2B) and DOM-TOM (971-976) handled
