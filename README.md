## Data Agent

This project routes natural-language requests to either an ETL workflow or a read-only SQL workflow.

### Setup

1. Create a `.env` file with `OPENAI_API_KEY`, `host`, `port`, `database`, `user`, and `password`.
2. Start PostgreSQL with `docker compose up -d`.
3. Install dependencies into the project environment with `uv sync`.
4. Load the seed CSV files with `.venv\Scripts\python.exe feed_db.py`.

### Run

Use `.venv\Scripts\python.exe main.py`.

The SQL workflow uses a read-only database transaction. ETL paths must remain inside the project directory, and generated transformation code is restricted before execution.

### Tests

Run `.venv\Scripts\python.exe -m unittest discover -s tests -v`.
