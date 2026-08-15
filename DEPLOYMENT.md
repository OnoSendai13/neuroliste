# Deployment & Monthly Update Guide

## Initial Setup

```bash
# Clone the repository (or copy files to production server)
cd /opt/apps/rpps-neuro-app

# Install dependencies
pip install -r backend/requirements.txt

# Create data directory
mkdir -p data logs

# Run initial load (takes 10-15 minutes)
python scripts/load_rpps.py

# Start the API server
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

## Monthly Update Script

Located at: `scripts/monthly_update.sh`

```bash
#!/bin/bash
# Run monthly after the 5th (data.gouv.fr updates around this date)

cd /opt/apps/rpps-neuro-app
source venv/bin/activate
python scripts/load_rpps.py
```

## Cron Job (Monthly)

Add to crontab (`crontab -e`):

```
# RPPS monthly update - runs on 6th at 2:00 AM
0 2 6 * * cd /opt/apps/rpps-neuro-app && /bin/bash scripts/monthly_update.sh >> logs/monthly_update.log 2>&1
```

## Data.gouv.fr URL Pattern

The RPPS data URLs change monthly. The format is:
```
https://static.data.gouv.fr/resources/annuaire-sante-extractions-des-donnees-en-libre-acces-des-professionnels-intervenant-dans-le-systeme-de-sante-rpps/YYYYMMDD-HHMMSS/filename.txt
```

Update the `FILES` dictionary in `scripts/load_rpps.py` each month by:
1. Visiting https://www.data.gouv.fr/fr/datasets/annuaire-sante-extractions-des-donnees-en-libre-acces-des-professionnels-intervenant-dans-le-systeme-de-sante-rpps/
2. Copying the new file URLs

## Production Environment Variables

```env
DATABASE_URL=sqlite:////opt/apps/rpps-neuro-app/data/neurologues.db
```

## Monitoring

Check the monthly update log:
```bash
tail -f logs/monthly_update.log
```

Expected output:
```
Step 1/3: Loading diplômes to identify neurologues...
Found ~4000 doctors with Neurologie diploma
Step 2/3: Loading savoir-faire...
Found ~5500 doctors with Neurologie savoir-faire
Neurologues with both diplome and savoir-faire: ~3000
Total neurologues loaded: ~3000
```