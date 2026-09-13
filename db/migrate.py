import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv


def main() -> None:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    config = {
        "host": os.environ["host"],
        "port": int(os.environ["port"]),
        "dbname": os.environ["database"],
        "user": os.environ["user"],
        "password": os.environ["password"],
        "connect_timeout": 5,
    }
    migration_dir = Path(__file__).resolve().parent / "migrations"
    with psycopg2.connect(**config) as connection, connection.cursor() as cursor:
        for migration in sorted(migration_dir.glob("*.sql")):
            cursor.execute(migration.read_text(encoding="utf-8"))
            print(f"Applied {migration.name}")


if __name__ == "__main__":
    main()