# Jira AI Dashboard (Flask + React)

Modern Jira dashboard with AI-powered conversational search + direct aggregation endpoints.

## High-Level Architecture

| Layer                    | Description                                                        |
| ------------------------ | ------------------------------------------------------------------ |
| frontend/                | React (Vite + Tailwind) SPA (Dashboard, Canvas Chat, AI Search)    |
| backend/                 | Flask app (app factory + blueprints + SocketIO)                    |
| backend/api/chat.py      | Conversational AI (OpenAI function calling + Jira tool dispatcher) |
| backend/api/chart.py     | Direct non-LLM aggregation -> chart spec JSON                      |
| backend/api/dashboard.py | Summary metrics & distributions for main dashboard                 |
| backend/services/        | Jira CRUD, OpenAI helpers, tool dispatcher abstractions            |
| backend/jira_utils.py    | JiraManager + aggregation logic (counts, distributions)            |
| backend/db.py            | SQLite helpers (chat messages & sessions)                          |

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

Create `.env` in project root:
```
JIRA_BASE_URL=https://your-domain.atlassian.net
OPENAI_API_KEY=sk-...
SECRET_KEY=your-secret-key

# Legacy credentials (no longer used - now using session-based authentication)
# JIRA_USERNAME=your.jira.username
# JIRA_PASSWORD=your.jira.api.token
```

**Note**: The application now uses session-based authentication. Users log in through the web interface with their Jira credentials, which are validated against the Jira API and stored securely in the session.

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

**Authentication:**
- POST /api/login - Authenticate with Jira credentials
- POST /api/logout - Clear session
- GET /api/check-auth - Check authentication status

**Core Features:**
- Health: GET /api/health
- Dashboard Stats: GET /api/dashboard-stats
- Aggregate (direct chart): POST /api/chart/aggregate

**Chat lifecycle:**
- POST /api/chat/new
- GET  /api/chat/history
- GET  /api/chat/<chat_id>
- PUT  /api/chat/<chat_id>/title
- DELETE /api/chat/<chat_id>/delete
- Ask AI: POST /api/chat/<chat_id>/ask  { "message": "..." }

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

### Smart User Assignment Workflow

The AI now intelligently handles user assignment with fuzzy search:

**Example Conversation:**
```
User: "Can you create a ticket for project ABC and assign it to John?"

AI: "I found these users matching 'John':
- John Smith (john.smith@company.com)
- John Doe (john.doe@company.com) 
- John Wilson (j.wilson@company.com)

Which John did you mean?"

User: "John Smith"

AI: "Perfect! I'll create the ticket and assign it to John Smith. Please confirm..."
```

**How it works:**
1. AI detects name mention in assignment context
2. Calls `search_users` tool with fuzzy matching
3. If exact match found → proceeds
4. If multiple matches → presents options to user
5. Waits for user clarification before proceeding
6. Uses confirmed exact username for assignment

## Frontend Notes

**Authentication Flow:**
- Modern login interface with enhanced UI/UX
- Real-time credential validation against Jira API
- Password visibility toggle for better user experience
- Session-based authentication with automatic redirects

**Key providers:**
- ChatProvider: manages chat sessions & message history.
- DashboardProvider: caches dashboard stats (stale-while-revalidate pattern).

**Pages:**
- Login: Enhanced authentication interface with gradient design and visual feedback
- Dashboard: visual summaries, uses cached stats.
- Canvas / Chat routes: conversational interface (LLM + charts in messages).
- AI Search: targeted exploration (future expansion).

**UI/UX Features:**
- Modern gradient backgrounds with subtle animations
- Enhanced form inputs with icons and focus states
- Smooth transitions and hover effects
- Responsive design with improved visual hierarchy
- Loading states with animated spinners

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

**Authentication Issues:**
- **Invalid credentials**: The app now validates credentials against Jira in real-time. Ensure your Jira username and password/API token are correct
- **Connection errors**: Check JIRA_BASE_URL in .env file and network connectivity
- **Timeout errors**: Jira server may be slow or unreachable - try again later

**General Issues:**
- OpenAI errors: validate key, model availability
- SQLite locked: ensure single writer or switch to a server DB (Postgres) for concurrency
- Session issues: Clear browser cookies/localStorage if experiencing login problems

## Repository Scripts
`Makefile` contains dev helpers (e.g., `make dev`). Adjust ports via env vars if needed.

## Security Considerations
- **Enhanced Authentication**: Credentials are now validated against Jira API before session creation
- **Session Security**: User credentials are stored securely in Flask sessions with configurable secret key
- **API Validation**: All Jira API calls validate credentials in real-time using `/rest/api/2/myself` endpoint
- **Error Handling**: Proper error messages for invalid credentials, network issues, and timeouts
- Rate-limit chat endpoint if exposed publicly
- Sanitize tool outputs before echoing in AI responses (currently raw JSON)
- Consider implementing session timeout and refresh mechanisms for production use

## Recent Updates

**Smart User Assignment (Latest):**
- ✅ Fuzzy user search for ticket assignment
- ✅ AI automatically searches for users when names are mentioned
- ✅ Intelligent matching with exact and partial name support
- ✅ User confirmation workflow for ambiguous names
- ✅ Example: "assign to John" → AI finds John Smith, John Doe, etc. and asks for clarification

**Authentication & Security:**
- ✅ Real-time Jira credential validation using `/rest/api/2/myself` endpoint
- ✅ Enhanced login UI with modern gradient design and animations
- ✅ Password visibility toggle for better UX
- ✅ Proper error handling for invalid credentials and network issues
- ✅ Session-based authentication replacing static credentials

**UI/UX Improvements:**
- ✅ Modern login interface with gradient backgrounds and blur effects
- ✅ Enhanced form inputs with icons and improved focus states
- ✅ Smooth animations and transitions throughout the interface
- ✅ Better loading states with animated spinners
- ✅ Improved visual hierarchy and spacing

## Roadmap Ideas
- Real-time push for new dashboard stats via SocketIO
- React suspense/data fetching library (React Query) instead of hand-rolled context caches
- Persistent chart templates & user-defined saved filters
- Role-based auth & multi-user separation
- Session timeout and refresh mechanisms
- Remember me functionality with secure token storage

---
Maintainer Handoff: See inline docstrings across backend/ for detailed flow explanations. Start at `backend/__init__.py` → blueprint modules → services.
