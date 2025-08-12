#!/usr/bin/env zsh
set -euo pipefail

# Colors
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

echo "${BLUE}Starting Jira AI backend (Flask) and frontend (Vite)${NC}"

# Start backend
PYTHONUNBUFFERED=1 python backend/app.py &
BACKEND_PID=$!
echo "${YELLOW}Backend PID: ${BACKEND_PID}${NC}"

cleanup() {
  echo "\n${YELLOW}Shutting down...${NC}"
  if ps -p ${BACKEND_PID} > /dev/null 2>&1; then
    kill ${BACKEND_PID} || true
    wait ${BACKEND_PID} 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

# Wait for backend health (optional, timeout ~15s)
ATTEMPTS=0
until curl -sSf http://localhost:4000/health >/dev/null 2>&1 || [ ${ATTEMPTS} -ge 15 ]; do
  ATTEMPTS=$((ATTEMPTS+1))
  sleep 1
done

if curl -sSf http://localhost:4000/health >/dev/null 2>&1; then
  echo "${GREEN}Backend is up on http://localhost:4000${NC}"
else
  echo "${YELLOW}Backend health check not responding, continuing anyway...${NC}"
fi

# Start frontend in foreground
echo "${BLUE}Starting frontend dev server (Vite) on http://localhost:5173${NC}"
cd frontend
npm run dev
