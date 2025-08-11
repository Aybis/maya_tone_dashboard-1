# Jira AI Frontend (React + Vite + Tailwind)

This is a React frontend for the Jira AI project. It consumes the Flask API running on port 4000.

## Setup

1. Install dependencies:

```bash
cd frontend
npm install
```

2. Start the dev server (proxies API requests to Flask):

```bash
npm run dev
```

- React dev server: http://localhost:5173
- Flask backend: http://localhost:4000

## Build

```bash
npm run build
npm run preview
```

## Endpoints used
- GET `/api/dashboard-stats`
- POST `/query` (body: `{ query: string, context?: string }`)
