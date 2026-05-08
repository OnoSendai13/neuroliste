#!/bin/bash
# Start both frontend and backend
cd "$(dirname "$0")"

echo "Starting backend on port 30000..."
cd backend && .venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 30000 &

echo "Starting frontend on port 31000..."
cd ../frontend && npm run dev &

echo "Done! Frontend: http://localhost:31000, Backend: http://localhost:30000"