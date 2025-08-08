# Jira AI Dashboard (Flask + React)

Modern Jira dashboard with AI-powered search. Backend is Flask (port 4000). Frontend is React (Vite + Tailwind, port 5173).

## Prerequisites

- Python 3.10+ and pip
- Node.js 18+ and npm

## 1) Configure environment

Create `backend/.env` (already referenced by the app):

```
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_USERNAME=your.jira.username
JIRA_PASSWORD=your.jira.api.token
OPENAI_API_KEY=sk-...
```

## 2) Backend (Flask)

Install dependencies and run the API on port 4000:

```bash
# From repo root
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Start Flask app
python backend/app.py
```

Useful endpoints:
- Health: http://localhost:4000/health
- Dashboard stats: http://localhost:4000/api/dashboard-stats
- AI query (POST): http://localhost:4000/query

Request example:

```bash
curl -X POST http://localhost:4000/query \
  -H 'Content-Type: application/json' \
  -d '{"query":"My tickets updated today"}'
```

## 3) Frontend (React + Vite + Tailwind)

The frontend lives in `frontend/` and proxies API calls to port 4000 during development.

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:5173
```

Build for production:

```bash
npm run build
npm run preview    # optional local preview
```

Project entry points:
- App shell and routing: `frontend/src/App.jsx`
- Dashboard page: `frontend/src/pages/Dashboard.jsx`
- AI Search page: `frontend/src/pages/AiSearch.jsx`

Styling: TailwindCSS is configured in `tailwind.config.js` and `postcss.config.js`, with utilities imported in `src/index.css`.

## Dev proxy and CORS

- Vite dev server proxies `/api`, `/query`, and `/health` to `http://localhost:4000` (see `frontend/vite.config.js`).
- Flask also has CORS enabled for flexibility when serving the frontend separately.

## 4) One command to run both (dev)

Use the provided Makefile/dev script:

```bash
make dev
```

This will:
- start Flask on http://localhost:4000
- wait briefly for /health
- start Vite on http://localhost:5173

## Troubleshooting

- Missing Python packages: `pip install -r requirements.txt`
- Node/Tailwind warnings in editor: Tailwind directives (`@tailwind`, `@apply`) are processed at build-time by PostCSS.
- 401/403 from Jira: verify `.env` values and Jira API token/permissions.
- OpenAI errors: check `OPENAI_API_KEY` and usage limits.

## Folder structure

```
backend/
  app.py
  templates/  # legacy HTML templates (now replaced by React in /frontend)
frontend/
  src/
    pages/
      Dashboard.jsx
      AiSearch.jsx
requirements.txt
README.md
```

## Notes

- The Flask server runs on port 4000 by default as configured in `backend/app.py`.
- You can keep using the backend only (JSON) and iterate UI entirely in React.
