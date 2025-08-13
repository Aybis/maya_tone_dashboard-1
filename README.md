# Jira AI Dashboard (Flask + React)

Modern Jira dashboard with AI-powered conversational search + direct aggregation endpoints.

## High-Level Architecture

| Layer | Description |
|-------|-------------|
| frontend/ | React (Vite + Tailwind) SPA (Dashboard, Canvas Chat, AI Search) |
| backend/ | Flask app (app factory + blueprints + SocketIO) |
| backend/api/chat.py | Conversational AI (OpenAI function calling + Jira tool dispatcher) |
| backend/api/chart.py | Direct non-LLM aggregation -> chart spec JSON |
| backend/api/dashboard.py | Summary metrics & distributions for main dashboard |
| backend/services/ | Jira CRUD, OpenAI helpers, tool dispatcher abstractions |
| backend/jira_utils.py | JiraManager + aggregation logic (counts, distributions) |
| backend/db.py | SQLite helpers (chat messages & sessions) |

Key design choices:
- Separation of concerns: Chat logic isolated from raw Jira operations.
- Tool dispatcher pattern: Chat pipeline only knows function names + JSON args.
- Two paths for charts: (a) direct /api/chart/aggregate (fast) and (b) AI-generated within chat fenced as ```chart blocks.
- Caching (frontend): DashboardContext caches /api/dashboard-stats to avoid duplicate fetches.

## Data Flow Overview

User asks for Jira insight -> chat endpoint builds context -> OpenAI may request a tool -> tool_dispatcher executes (Jira CRUD or aggregate) -> result optionally summarized -> response returned (with chart spec when aggregation).

Direct dashboard/aggregation bypasses LLM entirely for speed.

## Prerequisites

- Python 3.10+
- Node.js 18+

## Environment Setup

Create `backend/.env`:
```
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_USERNAME=your.jira.username
JIRA_PASSWORD=your.jira.api.token
OPENAI_API_KEY=sk-...
SECRET_KEY=dev-secret
```

Install backend deps:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run backend (preferred):
```bash
python -m backend.run
```
Legacy alternative:
```bash
python backend/app.py
```

Install + run frontend:
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:5173

## Core Endpoints

Health: GET /api/health
Dashboard Stats: GET /api/dashboard-stats
Aggregate (direct chart): POST /api/chart/aggregate
Chat lifecycle:
- POST /api/chat/new
- GET  /api/chat/history
- GET  /api/chat/<chat_id>
- PUT  /api/chat/<chat_id>/title
- DELETE /api/chat/<chat_id>/delete
Ask AI: POST /api/chat/<chat_id>/ask  { "message": "..." }

### Aggregate Request Example
```bash
curl -X POST http://localhost:4000/api/chart/aggregate \
  -H 'Content-Type: application/json' \
  -d '{"group_by":"status","from":"2025-08-01","to":"2025-08-12","filters":{"project":["ABC"]}}'
```
Response (truncated):
```json
{
  "success": true,
  "chart": {"type":"bar","labels":["To Do","In Progress"],"datasets":[...]},
  "raw": {"counts": [...], "total": 42}
}
```

### Chat Chart Response Format
When the AI returns a chart it uses a fenced block:
````
```chart
{ "title": "Distribusi Issue", "type": "bar", ... }
```
````
The frontend can parse these blocks to render charts directly.

## Frontend Notes

Key providers:
- ChatProvider: manages chat sessions & message history.
- DashboardProvider: caches dashboard stats (stale-while-revalidate pattern).

Pages:
- Dashboard: visual summaries, uses cached stats.
- Canvas / Chat routes: conversational interface (LLM + charts in messages).
- AI Search: targeted exploration (future expansion).

Styling via Tailwind (see `tailwind.config.js`). Charts via Chart.js wrapper components.

## Extensibility

Add new Jira tools:
1. Implement function in `backend/services/jira_crud.py` or reuse JiraManager.
2. Map it in `backend/services/tool_dispatcher.execute`.
3. Add tool schema to `tools` list in `chat.ask` endpoint if exposed to LLM.

Add new blueprint:
1. Create file in `backend/api/` and register inside `create_app()` in `backend/__init__.py`.

Add socket events:
- Extend `backend/extensions.py` socketio instance.
- Create `backend/sockets.py` and import in `create_app()` (not yet implemented).

## Testing (Suggested Next Steps)
- Unit: aggregation logic, tool dispatcher dispatcher paths, OpenAI intent fallback.
- Integration: chat ask flow with mocked OpenAI.

## Troubleshooting
OpenAI errors: validate key, model availability.
Jira auth failures: confirm API token & email/username pairing.
SQLite locked: ensure single writer or switch to a server DB (Postgres) for concurrency.

## Repository Scripts
`Makefile` contains dev helpers (e.g., `make dev`). Adjust ports via env vars if needed.

## Security Considerations
- Move plaintext Jira credentials to a secrets manager in production.
- Rate-limit chat endpoint if exposed publicly.
- Sanitize tool outputs before echoing in AI responses (currently raw JSON).

## Roadmap Ideas
- Real-time push for new dashboard stats via SocketIO.
- React suspense/data fetching library (React Query) instead of hand-rolled context caches.
- Persistent chart templates & user-defined saved filters.
- Role-based auth & multi-user separation.

---
Maintainer Handoff: See inline docstrings across backend/ for detailed flow explanations. Start at `backend/__init__.py` → blueprint modules → services.
