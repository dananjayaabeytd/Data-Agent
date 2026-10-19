import unittest
from types import SimpleNamespace
from unittest.mock import patch

from agents import sql_analyst
from Models.schema import JudgeSchema


class FakeLLM:
    """Answers each SQL-workflow prompt from a script instead of calling a model."""

    def __init__(self, generated: str, repairs: list[str], verdicts: list[str] | None = None):
        self.generated = generated
        self.repairs = list(repairs)
        self.verdicts = list(verdicts or [])
        self.repair_prompts: list[str] = []

    def invoke(self, prompt: str):
        if "previous SQL query failed" in prompt:
            self.repair_prompts.append(prompt)
            return SimpleNamespace(content=self.repairs.pop(0))
        if "Database Schema Details" in prompt:
            return SimpleNamespace(content=self.generated)
        if "provide a final answer" in prompt:
            return SimpleNamespace(content="final answer")
        return SimpleNamespace(content="rewritten question")

    def with_structured_output(self, _schema):
        judge = SimpleNamespace()
        judge.invoke = lambda _prompt: JudgeSchema(
            answer=self.verdicts.pop(0) if self.verdicts else "Yes", comments="ok"
        )
        return judge


class FakeDatabase:
    """Fails every query except the ones listed as working."""

    executed: list[str] = []
    working: set[str] = set()

    def __init__(self, _config):
        pass

    def schema_details(self, _schema):
        return "Table: rides\n  Column: fare, Data Type: numeric\n"

    def execute_sql(self, query):
        FakeDatabase.executed.append(query)
        if query.startswith("Rejected"):
            return "Rejected: multiple SQL statements are not allowed."
        if query in FakeDatabase.working:
            return "Columns: ['sum']\nRows: [(42,)]"
        return f'Error executing query: relation "{query}" does not exist'


def run_workflow(llm: FakeLLM, working: set[str]) -> dict:
    FakeDatabase.executed = []
    FakeDatabase.working = working
    with patch.object(sql_analyst, "pick_llm", return_value=llm), patch.object(
        sql_analyst, "DatabaseUtil", FakeDatabase
    ), patch.object(sql_analyst, "database_config", return_value={}):
        return sql_analyst.sql_analyst.invoke(
            {
                "messages": [],
                "user_question": "What is the total fare?",
                "curated_question": "",
                "prompt_query_context": "",
                "generated_sql_query": "",
                "is_safe": "No",
                "comments": "",
                "sql_query_execution_result": "",
                "final_answer": "",
            }
        )


class SqlRepairTests(unittest.TestCase):
    def test_failed_query_is_repaired_with_the_database_error(self):
        llm = FakeLLM("bad_query", repairs=["good_query"])
        state = run_workflow(llm, working={"good_query"})

        self.assertEqual(FakeDatabase.executed, ["bad_query", "good_query"])
        self.assertEqual(state["sql_repairs"], 1)
        self.assertEqual(state["generated_sql_query"], "good_query")
        self.assertIn('relation "bad_query" does not exist', llm.repair_prompts[0])
        self.assertEqual(state["final_answer"], "final answer")

    def test_repairs_stop_after_the_limit(self):
        llm = FakeLLM("bad_1", repairs=["bad_2", "bad_3", "never_used"])
        state = run_workflow(llm, working=set())

        self.assertEqual(state["sql_repairs"], sql_analyst.MAX_SQL_REPAIRS)
        self.assertEqual(FakeDatabase.executed, ["bad_1", "bad_2", "bad_3"])
        self.assertTrue(state["sql_query_execution_result"].startswith("Error executing query"))

    def test_validator_rejections_are_not_retried(self):
        llm = FakeLLM("Rejected_multi_statement", repairs=["should_not_run"])
        state = run_workflow(llm, working=set())

        self.assertEqual(state.get("sql_repairs", 0), 0)
        self.assertEqual(FakeDatabase.executed, ["Rejected_multi_statement"])

    def test_repaired_query_is_judged_again(self):
        # The judge accepts the first query and rejects the repair, so the repair never runs.
        llm = FakeLLM("bad_query", repairs=["DROP TABLE rides"], verdicts=["Yes", "No"])
        state = run_workflow(llm, working=set())

        self.assertEqual(FakeDatabase.executed, ["bad_query"])
        self.assertIn("deemed unsafe", state["final_answer"])
