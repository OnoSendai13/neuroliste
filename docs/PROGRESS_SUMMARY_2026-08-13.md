# RPPS-Neuro Standalone App - Progress Summary (2026-08-13)

## Completed Phases

### �� Phase 1: Verify app runs without Docker
- Tested `./start.sh` - backend + frontend run standalone
- Backend: FastAPI on port 30000, SQLite at `/home/laurent/.local/share/rpps-neuro/data/neurologues.db` (3544 neurologues)
- Frontend: React/Vite on port 31000

### �� Phase 2: Electron wrapper (main.js + preload.js)
**Files created:**
- `/mnt/g/Neuro-liste/rpps-neuro-app/electron/main.js` (276 lines)
- `/mnt/g/Neuro-liste/rpps-neuro-app/electron/preload.js` (6 lines)
- Updated `package.json` with electron scripts and electron-builder config

**Key features:**
- Launches FastAPI backend as sidecar (python -m uvicorn)
- Waits for backend readiness before opening window
- Secure IPC bridge via contextBridge (getAppVersion, getBackendStatus)
- Graceful shutdown (window-all-closed, before-quit)
- Dev mode: concurrent Vite + Electron with DevTools
- Prod mode: loads built frontend from `frontend/dist`

### �� Phase 3: Embedded data strategy
**Added to main.js:**
- `getUserDataPath()` - OS-specific paths (AppData/Application Support/.config)
- `getDbPath()` - SQLite in userData directory
- `getBundledDbPath()` - bundled DB in extraResources
- `isValidSQLite()` - validates SQLite header
- `backupCorruptDb()` - timestamps corrupt DBs before removal
- `initializeDatabase()` - copies bundled DB or lets backend create fresh
- `checkAndMigrate()` - placeholder for future schema migrations
- `startBackend(dbPath)` - passes DATABASE_URL env var to backend

### �� Phase 4: Multi-platform builds
- electron-builder configured in package.json
- Windows: NSIS installer
- macOS: DMG
- Linux: AppImage
- Icons needed: `frontend/public/icon.png` (win/linux), `icon.icns` (mac)
- Extra resources: backend folder (excludes .venv, __pycache__, data)

## Remaining Work

### ��� Phase 5: Polish & hardening
- App icons (need to create/convert)
- Splash screen
- Error handling UI
- Auto-updater (electron-updater + GitHub releases)
- User documentation
- Data freshness check at startup (compare data.gouv.fr metadata vs local date_import)

### ��� Data cleanup: Identify retired/outdated entries
- 489 entries with empty `mode_exercice` - investigate
- Cross-ref with data.gouv.fr latest extraction
- Flag stale addresses (old commune codes, missing postal codes)

### ��� Data cleanup: Integrate correction workflow in app
- Wire `apply_adresse_corrections.py` into Electron app
- UI to review pending_review CSV, promote to confirmed, trigger apply
- Auto-check on startup for new corrections from data.gouv.fr

## Kanban Board State
- Board: `rpps-neuro-standalone` (in ~/.hermes/kanban/boards/)
- Auto-reclaim cron job: `kanban-auto-reclaim` (every 5min)
- Gateway running: `hermes gateway start`

## Next Steps
1. Create icons for all platforms
2. Test `npm run electron:build` on current platform
3. Add data freshness check endpoint to backend (`GET /api/check-updates`)
4. Build correction workflow UI in React frontend
