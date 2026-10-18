import logging
import os
import re

import psycopg2
from psycopg2 import sql

LOGGER = logging.getLogger(__name__)
READ_ONLY_PREFIX = re.compile(r"^(SELECT|WITH|EXPLAIN)\b", re.IGNORECASE)


class DatabaseUtil:
    def __init__(self, db_config: dict, max_rows: int = 1000):
        self.db_config = {**db_config}
        self.max_rows = max_rows
        self.db_config.setdefault("connect_timeout", 5)
        options = self.db_config.get("options", "")
        timeout_options = (
            "-c statement_timeout=15000 "
            "-c lock_timeout=5000 "
            "-c idle_in_transaction_session_timeout=30000"
        )
        self.db_config["options"] = f"{options} {timeout_options}".strip()

    def _connect(self):
        return psycopg2.connect(**self.db_config)

    def schema_details(self, schema_name: str) -> str:
        schema_info = [f"Database Schema: {schema_name}\n"]
        include_samples = os.getenv("DB_INCLUDE_SAMPLES", "false").lower() == "true"

        try:
            with self._connect() as connection:
                connection.set_session(readonly=True)
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT table_name
                        FROM information_schema.tables
                        WHERE table_schema = %s
                        AND table_name NOT LIKE 'agent\\_%%'
                        ORDER BY table_name;
                        """,
                        (schema_name,),
                    )
                    tables = cursor.fetchall()

                    for (table_name,) in tables:
                        schema_info.append(f"\nTable: {table_name}\n")
                        cursor.execute(
                            """
                            SELECT column_name, data_type
                            FROM information_schema.columns
                            WHERE table_schema = %s AND table_name = %s
                            ORDER BY ordinal_position;
                            """,
                            (schema_name, table_name),
                        )
                        for column_name, data_type in cursor.fetchall():
                            schema_info.append(
                                f"  Column: {column_name}, Data Type: {data_type}\n"
                            )

                        if include_samples:
                            query = sql.SQL("SELECT * FROM {}.{} LIMIT 5").format(
                                sql.Identifier(schema_name), sql.Identifier(table_name)
                            )
                            cursor.execute(query)
                            schema_info.append("  Sample Data:\n")
                            schema_info.extend(f"    {row}\n" for row in cursor.fetchmany(5))
        except psycopg2.Error as error:
            LOGGER.exception("Schema inspection failed")
            return f"Error fetching schema details: {error}"

        return "".join(schema_info)

    @staticmethod
    def _clean_query(query: str) -> str:
        query = query.strip()
        if query.startswith("```"):
            query = query.removeprefix("```").removeprefix("sql").strip()
            query = query.removesuffix("```").strip()
        return query

    @classmethod
    def validate_read_only(cls, query: str) -> str:
        """Return the cleaned query, or raise ValueError if it is not a single read-only statement."""
        query = cls._clean_query(query)
        if not query or not READ_ONLY_PREFIX.match(query):
            raise ValueError("only read-only SQL statements are allowed.")
        if ";" in query.rstrip(";"):
            raise ValueError("multiple SQL statements are not allowed.")
        return query

    def run_query(self, query: str) -> tuple[list[str], list[tuple]] | None:
        """Run a validated read-only query and return (columns, rows), or None for no result set.

        Raises ValueError when the query is rejected and psycopg2.Error when it fails.
        """
        query = self.validate_read_only(query)
        with self._connect() as connection:
            connection.set_session(readonly=True)
            with connection.cursor() as cursor:
                cursor.execute(query)
                if cursor.description is None:
                    return None
                columns = [column.name for column in cursor.description]
                return columns, cursor.fetchmany(self.max_rows)

    def execute_sql(self, query: str) -> str:
        try:
            result = self.run_query(query)
        except ValueError as error:
            return f"Rejected: {error}"
        except psycopg2.Error as error:
            LOGGER.exception("SQL execution failed")
            return f"Error executing query: {error}"
        if result is None:
            return "Statement produced no tabular result."
        columns, rows = result
        return f"Columns: {columns}\nRows: {rows}"
