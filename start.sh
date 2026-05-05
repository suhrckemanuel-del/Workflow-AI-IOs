#!/usr/bin/env bash
set -e

if [ ! -f .env ]; then
    echo "[ERROR] .env not found. Run ./setup.sh first."
    exit 1
fi

echo ""
echo " AI-OS v2 — Starting servers"
echo " ============================"
echo ""

# Start backend in background
echo "Starting FastAPI backend on http://localhost:8000 ..."
uvicorn api.main:app --reload --port 8000 &
BACKEND_PID=$!

# Brief pause so backend starts before frontend
sleep 5

echo "Starting Next.js frontend on http://localhost:3000 ..."
cd frontend
npm run start &
FRONTEND_PID=$!
cd ..

echo ""
echo " Both servers are running."
echo " Open http://localhost:3000 in your browser."
echo " API docs at http://localhost:8000/docs"
echo ""
echo " Press Ctrl+C to stop both servers."
echo ""

# Wait and clean up on exit
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo ''; echo ' Servers stopped.'" EXIT
wait
