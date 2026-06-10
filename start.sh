#!/bin/bash
# Start both frontend and backend
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Starting backend on port 30000..."
(
  cd "$SCRIPT_DIR/backend"
  .venv/bin/python -m uvicorn main:app --host localhost --port 30000
) &

echo "Starting frontend on port 31000..."
(
  cd "$SCRIPT_DIR/frontend"
  npm run dev
) &

echo "Done! Frontend: http://localhost:31000, Backend: http://localhost:30000"