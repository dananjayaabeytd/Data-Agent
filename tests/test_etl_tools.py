import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from main import build_request
from Models.schema import TransformationPlan, TransformationStep
from utils.database import DatabaseUtil
from utils.etl_tools import ETLTools
from utils.session_store import SessionStore
from web_app import STATIC_DIR, TEMPLATES_DIR


class ETLToolsTests(unittest.TestCase):
    def setUp(self):
        self.tools = ETLTools()

    def test_reads_local_extract_context(self):
        context = self.tools.transform_load_context("data/extract/extracted_data.csv")
        self.assertIn("bulbasaur", context)

    def test_applies_allowlisted_transformation_plan(self):
        output_folder = Path("data/transform/_test_plan")
        try:
            result = self.tools.apply_transformation_plan(
                "data/extract/extracted_data.csv",
                str(output_folder),
                "csv",
                TransformationPlan(
                    steps=[
                        TransformationStep(
                            operation="filter_equals",
                            column="name",
                            value="bulbasaur",
                        )
                    ]
                ),
            )
            self.assertIn("successfully transformed", result)
            self.assertIn("bulbasaur", (output_folder / "transformed_data.csv").read_text())
        finally:
            shutil.rmtree(output_folder, ignore_errors=True)

    def test_rejects_paths_outside_project(self):
        result = self.tools.transform_load_context("../outside.csv")
        self.assertIn("Path must remain inside", result)

    def test_rejects_private_api_urls(self):
        with self.assertRaises(ValueError):
            self.tools._validate_url("http://127.0.0.1/internal")


class SessionStoreTests(unittest.TestCase):
    def test_session_round_trip_and_delete(self):
        with TemporaryDirectory() as directory:
            store = SessionStore(Path(directory) / "sessions.sqlite3")
            session = store.create("Test session")
            store.append(session.session_id, "user", "Hello")
            saved = store.append(session.session_id, "assistant", "Hi there")

            self.assertEqual(saved.title, "Test session")
            self.assertEqual(len(saved.messages), 2)
            self.assertIn("Current request", build_request(saved, "Continue"))

            store.delete(session.session_id)
            with self.assertRaises(KeyError):
                store.get(session.session_id)


class WebAssetTests(unittest.TestCase):
    def test_template_and_response_rendering_hook_exist(self):
        template = (TEMPLATES_DIR / "index.html").read_text(encoding="utf-8")
        script = (STATIC_DIR / "app.js").read_text(encoding="utf-8")

        self.assertIn("/static/app.js", template)
        self.assertIn("renderSession(result.session)", script)


class DatabaseSafetyTests(unittest.TestCase):
    def test_rejects_multiple_statements_before_connection(self):
        result = DatabaseUtil({}).execute_sql("SELECT 1; SELECT 2")
        self.assertIn("multiple SQL statements", result)


if __name__ == "__main__":
    unittest.main()
