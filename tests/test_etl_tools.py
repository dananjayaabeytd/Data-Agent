import unittest

from utils.etl_tools import ETLTools


class ETLToolsTests(unittest.TestCase):
    def setUp(self):
        self.tools = ETLTools()

    def test_reads_local_extract_context(self):
        context = self.tools.transform_load_context("data/extract/extracted_data.csv")
        self.assertIn("bulbasaur", context)

    def test_rejects_code_imports(self):
        result = self.tools.execute_code("import os")
        self.assertIn("Imports are not allowed", result)

    def test_rejects_paths_outside_project(self):
        result = self.tools.transform_load_context("../outside.csv")
        self.assertIn("Path must remain inside", result)


if __name__ == "__main__":
    unittest.main()
