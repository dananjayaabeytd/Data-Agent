import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class Session:
    session_id: str
    owner_id: str
    title: str
    created_at: str
    updated_at: str
    messages: list[dict[str, str]]


class SessionStore:
    def __init__(self, database_path: str | Path | None = None):
        project_root = Path(__file__).resolve().parents[1]
        self.database_path = Path(
            database_path or project_root / "data" / "sessions.sqlite3"
        )
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _transaction(self):
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._transaction() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL DEFAULT 'local',
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    messages_json TEXT NOT NULL
                )
                """
            )
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(sessions)")
            }
            if "owner_id" not in columns:
                connection.execute(
                    "ALTER TABLE sessions ADD COLUMN owner_id TEXT NOT NULL DEFAULT 'local'"
                )

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    @staticmethod
    def _to_session(row: sqlite3.Row) -> Session:
        return Session(
            session_id=row["session_id"],
            owner_id=row["owner_id"],
            title=row["title"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            messages=json.loads(row["messages_json"]),
        )

    def create(self, title: str = "New session", owner_id: str = "local") -> Session:
        session_id = uuid.uuid4().hex[:8]
        timestamp = self._now()
        with self._transaction() as connection:
            connection.execute(
                """
                INSERT INTO sessions
                    (session_id, owner_id, title, created_at, updated_at, messages_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    owner_id,
                    title.strip() or "New session",
                    timestamp,
                    timestamp,
                    "[]",
                ),
            )
        return self.get(session_id, owner_id)

    def get(self, session_id: str, owner_id: str = "local") -> Session:
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT * FROM sessions WHERE session_id = ? AND owner_id = ?",
                (session_id, owner_id),
            ).fetchone()
        if row is None:
            raise KeyError(f"Session not found: {session_id}")
        return self._to_session(row)

    def list(self, owner_id: str = "local") -> list[Session]:
        with self._transaction() as connection:
            rows = connection.execute(
                "SELECT * FROM sessions WHERE owner_id = ? ORDER BY updated_at DESC",
                (owner_id,),
            ).fetchall()
        return [self._to_session(row) for row in rows]

    def append(
        self, session_id: str, role: str, content: str, owner_id: str = "local"
    ) -> Session:
        if role not in {"user", "assistant"}:
            raise ValueError("Session message role must be user or assistant")
        if not content.strip():
            raise ValueError("Session message cannot be empty")

        session = self.get(session_id, owner_id)
        max_messages = int(os.getenv("SESSION_MAX_MESSAGES", "100"))
        messages = [*session.messages, {"role": role, "content": content}][-max_messages:]
        with self._transaction() as connection:
            connection.execute(
                """
                UPDATE sessions
                SET updated_at = ?, messages_json = ?
                WHERE session_id = ? AND owner_id = ?
                """,
                (self._now(), json.dumps(messages), session_id, owner_id),
            )
        return self.get(session_id, owner_id)

    def delete(self, session_id: str, owner_id: str = "local") -> None:
        with self._transaction() as connection:
            cursor = connection.execute(
                "DELETE FROM sessions WHERE session_id = ? AND owner_id = ?",
                (session_id, owner_id),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"Session not found: {session_id}")


def create_session_store():
    if os.getenv("SESSION_BACKEND", "sqlite").lower() == "postgres":
        from utils.postgres_session_store import PostgresSessionStore

        return PostgresSessionStore.from_environment()
    return SessionStore()
