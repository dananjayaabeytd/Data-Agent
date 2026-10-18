## Data Agent

A LangGraph agent that routes natural-language requests to a read-only SQL workflow, an
ETL workflow, or a direct chat reply. It is served by a FastAPI backend and a Next.js UI.

```
frontend/ (Next.js) ──/api/*──► Next.js proxy route ──► FastAPI (api_app.py) ──► LangGraph agents ──► PostgreSQL
```

### Project layout

| Path | Purpose |
|---|---|
| `api_app.py` | FastAPI app, the single backend entry point |
| `services/agent_service.py` | Builds the request with conversation history and runs the agent |
| `agents/` | LangGraph graphs: router (`data_agent.py`), `sql_analyst.py`, `etl_analyst.py` |
| `Models/schema.py` | Pydantic state and structured-output schemas |
| `utils/` | Database access, ETL tools, LLM selection, session stores |
| `db/bootstrap.py`, `db/migrations/` | Migrations and seed loading, run at API startup |
| `data/*.csv` | Seed data for the ride-sharing database |
| `frontend/` | Next.js chat UI |

### Setup

1. Copy `.env.example` to `.env` and set real values. Never commit or share `.env`.
2. Start PostgreSQL with `docker compose up -d postgres`.
3. Install backend dependencies with `uv sync`.
4. Install frontend dependencies with `cd frontend && npm install`.

### Run

Start the backend (the only entry point):

```
.venv\Scripts\python.exe -m uvicorn api_app:app --host 127.0.0.1 --port 8000
```

On startup the API applies `db/migrations/*.sql` and, when the business tables are empty, loads
the seed CSV files. Control this with `DB_MIGRATE_ON_STARTUP` and `DB_SEED_ON_STARTUP`
(seeding defaults to on in development and off in production).
OpenAPI documentation is available at `http://127.0.0.1:8000/docs` outside production.

Start the UI in a second terminal and open `http://localhost:3000`:

```
cd frontend
npm run dev
```

The browser only calls the Next.js server. Its proxy route forwards `/api/sessions...` to
FastAPI at `BACKEND_URL` and adds `DATA_AGENT_API_KEY` / `DATA_AGENT_USER_ID` server-side, so the
API key never reaches the browser. See `frontend/.env.example`.

### Authentication

For local API authentication, set `DATA_AGENT_API_KEY` in `.env` and the same value in
`frontend/.env.local`. Production must use `APP_ENV=production`, a 32+ character `JWT_SECRET`, and
an external issuer that provides JWTs with `sub`, `iss`, `aud`, and `exp` claims.

If an API key has appeared in logs, screenshots, or terminal output, revoke it and create a new one before deployment.

In production, create a separate PostgreSQL read-only role for analytics and set `db_readonly_user` and `db_readonly_password`. Grant it `CONNECT`, `USAGE` on the application schema, and `SELECT` only on business tables. Do not grant it access to `agent_sessions`.

### Docker

`docker compose up --build -d` runs PostgreSQL and the API. The API container runs migrations at
startup. Before production Compose startup, `.env` must define `APP_ENV=production`, `JWT_SECRET`,
`JWT_ISSUER`, `JWT_AUDIENCE`, database credentials, `db_readonly_user`, `db_readonly_password`, and
`ALLOWED_ORIGINS`. Production API docs are disabled by default.

### Safety

The SQL workflow uses a read-only database transaction. ETL paths must remain inside the project directory, and transformations use an allowlisted structured plan rather than executing model-generated Python.

### Tests

- Backend: `.venv\Scripts\python.exe -m unittest discover -s tests -v`
- Frontend: `cd frontend && npm run lint && npm run build`
