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

### Models

Every step uses `gpt-5-nano` (OpenAI's cheapest model) with `reasoning_effort=minimal`, about
$0.0002 per question across the five LLM calls. Set `LLM_MODEL` to change all steps, or
`LLM_MODEL_LOW` / `LLM_MODEL_MEDIUM` / `LLM_MODEL_HIGH` to upgrade one tier. `medium` covers routing,
SQL generation, and the safety judge, so it has the most effect on accuracy. Run the evaluation
after any model change.

### Tracing (Langfuse)

Set `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and `LANGFUSE_BASE_URL` in `.env` and restart the API.
Every chat request becomes one Langfuse trace containing the router, each SQL or ETL step, every
LLM call with tokens and cost, and tool calls. Traces are grouped by `session_id` and tagged with
the user id and environment (`APP_ENV`). Tracing is disabled when the keys are empty; use
`LANGFUSE_SAMPLE_RATE` to trace a fraction of requests.

Traces include user questions, generated SQL, and query results. Review what may be sent to
Langfuse Cloud before enabling it on production data.

### Evaluation

`evals/golden_set.json` holds 35 cases: 25 SQL questions (including follow-ups that need history),
4 destructive requests, and 6 routing checks. Each SQL case has a reference query, and the agent is
scored by **execution accuracy**: its SQL must return the same rows as the reference (extra columns
and 2-decimal rounding are allowed; order matters only for rankings). Reference results are computed
at run time, so they stay correct if the seed data changes.

```
$env:RUN_AGENT_EVALS = "1"; .venv\Scripts\python.exe -m unittest tests.test_agent_eval -v
```

The run fails if routing accuracy drops below `EVAL_MIN_ROUTE` (0.9), execution accuracy below
`EVAL_MIN_EXECUTION` (0.8), any destructive request is not blocked, or business table row counts
change. With Langfuse keys set, the golden set is synced to the `data-agent-golden` dataset and each
run is recorded as an experiment you can compare across prompt or model changes. The **Agent
evaluation** GitHub workflow runs the same check on demand against a fresh seeded database.
