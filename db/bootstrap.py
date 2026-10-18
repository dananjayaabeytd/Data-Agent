import logging
import os
from pathlib import Path

import psycopg2
from psycopg2 import sql

LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
SEED_DIR = PROJECT_ROOT / "data"

# Load order matters because of foreign keys.
SEED_TABLES = {
    "users": [
        "user_id", "first_name", "last_name", "email", "phone",
        "city", "province", "user_type", "signup_date", "is_active",
    ],
    "vehicles": [
        "vehicle_id", "driver_id", "make", "model", "year",
        "license_plate", "color", "is_active",
    ],
    "rides": [
        "ride_id", "rider_id", "driver_id", "requested_at", "pickup_time",
        "dropoff_time", "pickup_latitude", "pickup_longitude", "dropoff_latitude",
        "dropoff_longitude", "distance_km", "fare", "surge_multiplier",
        "status", "cancellation_reason",
    ],
    "payments": [
        "payment_id", "ride_id", "user_id", "amount", "payment_method",
        "payment_status", "transaction_id", "payment_time",
    ],
    "ratings": [
        "rating_id", "ride_id", "rider_id", "driver_id", "rating", "comment", "rated_at",
    ],
}


def admin_config() -> dict:
    """Connection settings for the owner role, which may create tables and load data."""
    required = ("host", "port", "user", "password", "database")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"Missing database environment variables: {', '.join(missing)}")
    return {
        "host": os.environ["host"],
        "port": int(os.environ["port"]),
        "dbname": os.environ["database"],
        "user": os.environ["user"],
        "password": os.environ["password"],
        "connect_timeout": 5,
    }


def run_migrations(config: dict) -> None:
    """Apply every SQL file in db/migrations in name order. Migrations must be idempotent."""
    with psycopg2.connect(**config) as connection, connection.cursor() as cursor:
        for migration in sorted(MIGRATIONS_DIR.glob("*.sql")):
            cursor.execute(migration.read_text(encoding="utf-8"))
            LOGGER.info("Applied migration %s", migration.name)


def seed_database(config: dict) -> bool:
    """Load the seed CSV files into empty business tables. Returns True when data was loaded."""
    with psycopg2.connect(**config) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT EXISTS (SELECT 1 FROM public.users)")
        if cursor.fetchone()[0]:
            LOGGER.info("Seed skipped: business tables already contain data")
            return False

        for table, columns in SEED_TABLES.items():
            copy_sql = sql.SQL(
                "COPY {} ({}) FROM STDIN WITH (FORMAT CSV, HEADER TRUE, NULL '')"
            ).format(
                sql.Identifier("public", table),
                sql.SQL(", ").join(sql.Identifier(column) for column in columns),
            )
            with open(SEED_DIR / f"{table}.csv", encoding="utf-8") as file:
                cursor.copy_expert(copy_sql, file)
            LOGGER.info("Seeded %s", table)
    return True


def ensure_readonly_role(config: dict) -> bool:
    """Create or update the analytics role the SQL agent connects as.

    The role can log in and SELECT from the business tables only: no access to
    agent_sessions, no superuser rights, and therefore no pg_read_file and similar
    server functions. Returns False when no separate role is configured.
    """
    role = os.getenv("db_readonly_user")
    password = os.getenv("db_readonly_password")
    if not role or not password or role == config["user"]:
        return False

    with psycopg2.connect(**config) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
        verb = "ALTER" if cursor.fetchone() else "CREATE"
        cursor.execute(
            sql.SQL(
                verb + " ROLE {} WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD {}"
            ).format(sql.Identifier(role), sql.Literal(password))
        )
        identifier = sql.Identifier(role)
        cursor.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(config["dbname"]), identifier
            )
        )
        cursor.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(identifier))
        cursor.execute(
            sql.SQL("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {}").format(identifier)
        )
        cursor.execute(
            sql.SQL("GRANT SELECT ON {} TO {}").format(
                sql.SQL(", ").join(sql.Identifier("public", table) for table in SEED_TABLES),
                identifier,
            )
        )
    LOGGER.info("Read-only role %s is limited to SELECT on %s", role, ", ".join(SEED_TABLES))
    return True


def bootstrap_database() -> None:
    """Run migrations, provision the read-only role, and optionally seed. Called at API startup."""
    app_env = os.getenv("APP_ENV", "development").lower()
    config = admin_config()

    if os.getenv("DB_MIGRATE_ON_STARTUP", "true").lower() == "true":
        run_migrations(config)

    # Managed databases often forbid CREATE ROLE for the app user, so production opts in.
    manage_default = "false" if app_env == "production" else "true"
    if os.getenv("DB_MANAGE_READONLY_ROLE", manage_default).lower() == "true":
        ensure_readonly_role(config)

    seed_default = "false" if app_env == "production" else "true"
    if os.getenv("DB_SEED_ON_STARTUP", seed_default).lower() == "true":
        seed_database(config)
