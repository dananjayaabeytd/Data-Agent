import psycopg2
from psycopg2 import sql
import re


class DatabaseUtil:
    def __init__(self, db_config: dict):
        self.db_config = db_config

    def _connect(self):
        return psycopg2.connect(**self.db_config)

    def schema_details(self, schema_name: str) -> str:
        schema_info = [f"Database Schema: {schema_name}\n"]

        try:
            with self._connect() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT table_name
                        FROM information_schema.tables
                        WHERE table_schema = %s
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

                        query = sql.SQL("SELECT * FROM {}.{} LIMIT 5").format(
                            sql.Identifier(schema_name), sql.Identifier(table_name)
                        )
                        cursor.execute(query)
                        schema_info.append("  Sample Data:\n")
                        schema_info.extend(f"    {row}\n" for row in cursor.fetchall())
        except psycopg2.Error as error:
            return f"Error fetching schema details: {error}"

        return "".join(schema_info)

    def execute_sql(self, query: str) -> str:
        query = query.strip()
        if query.startswith("```"):
            query = query.removeprefix("```").removeprefix("sql").strip()
            query = query.removesuffix("```").strip()
        if not re.match(r"^(SELECT|WITH|EXPLAIN)\b", query, re.IGNORECASE):
            return "Rejected: only read-only SQL statements are allowed."

        try:
            with self._connect() as connection:
                connection.set_session(readonly=True)
                with connection.cursor() as cursor:
                    cursor.execute(query)
                    if cursor.description is None:
                        return "Statement produced no tabular result."
                    return str(cursor.fetchall())
        except psycopg2.Error as error:
            return f"Error executing query: {error}"
