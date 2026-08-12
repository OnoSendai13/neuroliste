# Changelog

All notable changes to Neuroliste are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Streaming download with resume capability in `scripts/load_rpps.py`
- Exponential backoff retry (5 attempts) for RPPS file downloads
- Auto-discovery of data.gouv.fr resource URLs with fallback to hardcoded URLs
- Cache at `/tmp/rpps_cache/` to avoid re-downloading on retry
- Docker healthcheck for API service (`/api/stats` every 30s)
- Frontend production build with nginx + API proxy (`/api/*` → `api:8000/api/`)
- Address corrections pipeline: audit → candidates → apply
- Applied 524 address corrections from external research (duckduckgo)

### Changed
- `load_rpps.py`: replaced `requests.get()` with streaming download + Range header resume
- `docker-compose.yml`: build context = project root; frontend multi-stage (Node → nginx)
- `backend/Dockerfile`: added `curl` for healthcheck; copies `scripts/` to `/app/scripts`
- `backend/main.py`: `/api/load-data` now uses container path `/app/scripts/load_rpps.py`
- `frontend/nginx.conf`: proxies `/api/` to `rpps-api:8000/api/`

### Fixed
- ChunkedEncodingError on large RPPS file downloads (personne-activite.txt ~200MB)
- Healthcheck failing due to missing `curl` in API container
- API proxy 404 due to wrong upstream path (`/api/` → `/api/api/`)
- Load script not found in container (context path fix)

## [1.0.0] - 2026-06-11

### Added
- Initial release: FastAPI backend + React frontend + SQLite
- RPPS data loading from data.gouv.fr (diplômes CESM15/DSM30/DIP143 + savoir-faire SM32)
- Geographic filters: region, department, commune (independent)
- Mode exercice filter: Libéral (L), Salarié (S)
- Interactive statistics dashboard with Recharts
- CSV export with applied filters
- Dark mode toggle (light/dark/system)
- Docker Compose deployment
- Electron desktop app plan (STANDALONE_APP_PLAN.md)

### Data
- 3,540 neurologues loaded from RPPS (June 2026 extraction)
- Department → Region mapping (2024 post-2016 reform)
- Corsican departments (2A/2B) and DOM-TOM (971-976) handled