import json
import os
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime

import psycopg2
from psycopg2.extras import Json, RealDictCursor

from utils.session_store import Session


class PostgresSessionStore:
    def __init__(self, db_config: dict):
        self.db_config = {**db_config}
        self.db_config.setdefault("connect_timeout", 5)
        if os.getenv("SESSION_AUTO_MIGRATE", "true").lower() == "true":
            self._initialize()
        else:
            self._verify_schema()

    @classmethod
    def from_environment(cls):
        required = ("host", "port", "user", "password", "database")
        missing = [name for name in required if not os.getenv(name)]
        if missing:
            raise RuntimeError(
                f"Missing session database environment variables: {', '.join(missing)}"
            )
        return cls(
            {
                "host": os.environ["host"],
                "port": int(os.environ["port"]),
                "user": os.environ["user"],
                "password": os.environ["password"],
                "dbname": os.environ["database"],
            }
        )

    @contextmanager
    def _transaction(self):
        connection = psycopg2.connect(**self.db_config)
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                    CREATE TABLE IF NOT EXISTS agent_sessions (
                        session_id TEXT PRIMARY KEY,
                        owner_id TEXT NOT NULL,
                        title TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL,
                        messages_json JSONB NOT NULL DEFAULT '[]'::jsonb
                    )
                    """
            )

    def _verify_schema(self) -> None:
        with self._transaction() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM agent_sessions LIMIT 1")
            cursor.execute(
                """
                    CREATE INDEX IF NOT EXISTS idx_agent_sessions_owner_updated
                    ON agent_sessions(owner_id, updated_at DESC)
                    """
            )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _to_session(row: dict) -> Session:
        messages = row["messages_json"]
        if isinstance(messages, str):
            messages = json.loads(messages)
        return Session(
            session_id=row["session_id"],
            owner_id=row["owner_id"],
            title=row["title"],
            created_at=row["created_at"].isoformat(),
            updated_at=row["updated_at"].isoformat(),
            messages=messages,
        )

    def create(self, title: str = "New session", owner_id: str = "local") -> Session:
        session_id = uuid.uuid4().hex[:8]
        now = self._now()
        with self._transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                    INSERT INTO agent_sessions
                        (session_id, owner_id, title, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                (session_id, owner_id, title.strip() or "New session", now, now),
            )
        return self.get(session_id, owner_id)

    def get(self, session_id: str, owner_id: str = "local") -> Session:
        with self._transaction() as connection, connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    "SELECT * FROM agent_sessions WHERE session_id = %s AND owner_id = %s",
                    (session_id, owner_id),
                )
                row = cursor.fetchone()
        if row is None:
            raise KeyError(f"Session not found: {session_id}")
        return self._to_session(row)

    def list(self, owner_id: str = "local") -> list[Session]:
        with self._transaction() as connection, connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    "SELECT * FROM agent_sessions WHERE owner_id = %s ORDER BY updated_at DESC",
                    (owner_id,),
                )
                rows = cursor.fetchall()
        return [self._to_session(row) for row in rows]

    def append(
        self, session_id: str, role: str, content: str, owner_id: str = "local"
    ) -> Session:
        if role not in {"user", "assistant"}:
            raise ValueError("Session message role must be user or assistant")
        if not content.strip():
            raise ValueError("Session message cannot be empty")

        with self._transaction() as connection, connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT messages_json FROM agent_sessions
                    WHERE session_id = %s AND owner_id = %s
                    FOR UPDATE
                    """,
                    (session_id, owner_id),
                )
                row = cursor.fetchone()
                if row is None:
                    raise KeyError(f"Session not found: {session_id}")
                messages = row["messages_json"]
                if isinstance(messages, str):
                    messages = json.loads(messages)
                messages = [*messages, {"role": role, "content": content}][-100:]
                cursor.execute(
                    """
                    UPDATE agent_sessions
                    SET updated_at = %s, messages_json = %s
                    WHERE session_id = %s AND owner_id = %s
                    """,
                    (self._now(), Json(messages), session_id, owner_id),
                )
        return self.get(session_id, owner_id)

    def delete(self, session_id: str, owner_id: str = "local") -> None:
        with self._transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM agent_sessions WHERE session_id = %s AND owner_id = %s",
                (session_id, owner_id),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"Session not found: {session_id}")
