## Data Agent

This project routes natural-language requests to either an ETL workflow or a read-only SQL workflow.

### Setup

1. Create a `.env` file with `OPENAI_API_KEY`, `host`, `port`, `database`, `user`, and `password`.
2. Start PostgreSQL with `docker compose up -d`.
3. Install dependencies into the project environment with `uv sync`.
4. Load the seed CSV files with `.venv\Scripts\python.exe feed_db.py`.

### Run

Start the interactive session manager with `.venv\Scripts\python.exe main.py`.

For the browser UI, start `.venv\Scripts\python.exe web_app.py` and open `http://127.0.0.1:8000`.
Use `--port 8080` to choose another local port.

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

The SQL workflow uses a read-only database transaction. ETL paths must remain inside the project directory, and generated transformation code is restricted before execution.

### Tests

Run `.venv\Scripts\python.exe -m unittest discover -s tests -v`.
