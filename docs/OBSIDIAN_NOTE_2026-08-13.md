---
tags: [rpps-neuro, standalone-app, progress, electron, kanban]
date: 2026-08-13
project: rpps-neuro-standalone
---

# RPPS-Neuro Standalone App - Progress (2026-08-13)

## �� Done
- **Phase 1**: App runs without Docker (FastAPI + React/Vite + SQLite)
- **Phase 2**: Electron wrapper (`electron/main.js`, `preload.js`, updated `package.json`)
- **Phase 3**: Embedded data strategy (userData paths, DB init, corrupt handling, migrations)
- **Phase 4**: electron-builder config (Win/macOS/Linux)

## ��� Remaining
- **Phase 5**: Icons, splash, auto-updater, docs, data freshness check
- **Data cleanup**: 489 empty mode_exercice entries, stale addresses
- **Correction workflow UI**: wire `apply_adresse_corrections.py` into app

## ��� Kanban
- Board: `rpps-neuro-standalone`
- Auto-reclaim cron: `kanban-auto-reclaim` (5min)
- Gateway: `hermes gateway start`

## ��� Files
- Progress detail: `docs/PROGRESS_SUMMARY_2026-08-13.md`
- Electron: `electron/main.js`, `electron/preload.js`
- Config: `package.json` (electron-builder)

## ��� Next
1. Create icons → `frontend/public/icon.png` + `icon.icns`
2. Test `npm run electron:build`
3. Add `/api/check-updates` endpoint to backend
4. Build correction review UI in React
