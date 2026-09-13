## Data Agent

This project routes natural-language requests to either an ETL workflow or a read-only SQL workflow.

### Setup

1. Copy `.env.example` to `.env` and set real values. Never commit or share `.env`.
2. Start PostgreSQL with `docker compose up -d`.
3. Install dependencies into the project environment with `uv sync`.
4. Load the seed CSV files with `.venv\Scripts\python.exe feed_db.py`. Use `--reset` only when intentionally replacing all existing data.

For local API authentication, set `DATA_AGENT_API_KEY` in `.env`. Production must use `APP_ENV=production`, a 32+ character `JWT_SECRET`, and an external issuer that provides JWTs with `sub`, `iss`, `aud`, and `exp` claims.

If an API key has appeared in logs, screenshots, or terminal output, revoke it and create a new one before deployment.

In production, create a separate PostgreSQL read-only role for analytics and set `db_readonly_user` and `db_readonly_password`. Grant it `CONNECT`, `USAGE` on the application schema, and `SELECT` only on business tables. Do not grant it access to `agent_sessions`.

### Run

Start the interactive session manager with `.venv\Scripts\python.exe main.py`.

For the browser UI, start `.venv\Scripts\python.exe web_app.py` and open `http://127.0.0.1:8000`.
Use `--port 8080` to choose another local port.

For the typed API, start `.venv\Scripts\python.exe -m uvicorn api_app:app --host 127.0.0.1 --port 8000`.
OpenAPI documentation is available at `http://127.0.0.1:8000/docs`.

To run the API and PostgreSQL together with Docker, use `docker compose up --build -d`, then load the seed data with `.venv\Scripts\python.exe feed_db.py`.

Before production Compose startup, `.env` must define `APP_ENV=production`, `JWT_SECRET`, `JWT_ISSUER`, `JWT_AUDIENCE`, database credentials, `db_readonly_user`, `db_readonly_password`, and `ALLOWED_ORIGINS`. Production API docs are disabled by default.

Each session is persisted in `data/sessions.sqlite3`. The CLI supports:

- `/new [title]` to create a session.
- `/sessions` to list saved sessions.
- `/use SESSION_ID` to resume a session.
- `/history` to display the current conversation.
- `/delete [SESSION_ID]` to remove a session.
- `/exit` to leave the CLI while preserving the session.

For scripts and automation, process one request with:

`.venv\Scripts\python.exe main.py --once "What payment methods are available?"`

Use `--session SESSION_ID` with `--once` to continue an existing session. Use `--list-sessions` or `--delete-session SESSION_ID` for non-interactive session management.

The SQL workflow uses a read-only database transaction. ETL paths must remain inside the project directory, and transformations use an allowlisted structured plan rather than executing model-generated Python.

### Tests

Run `.venv\Scripts\python.exe -m unittest discover -s tests -v`.
