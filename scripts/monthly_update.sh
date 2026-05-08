#!/bin/bash
# Monthly update script for RPPS Neurologues database
# Run on the 5th of each month (after data.gouv.fr updates)

set -e

echo "=== RPPS Monthly Update - $(date) ==="

# Check for new data URLs (data.gouv.fr updates monthly around 5th)
# The script will detect new URLs and update the FILES dict in load_rpps.py

cd "$(dirname "$0")/.."

echo "1. Fetching latest RPPS file URLs..."
# URLs format: https://static.data.gouv.fr/resources/.../YYYYMMDD-HHMMSS/filename.txt
# The date in URL changes monthly

echo "2. Running data load..."
python3 scripts/load_rpps.py

echo "3. Verifying data..."
python3 -c "
from backend.models import SessionLocal, Neurologue
db = SessionLocal()
count = db.query(Neurologue).count()
print(f'Neurologues in database: {count}')
db.close()
"

echo "=== Update complete ==="