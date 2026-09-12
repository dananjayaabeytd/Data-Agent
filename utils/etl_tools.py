import ast
import os
from pathlib import Path

import pandas as pd
import requests


class ETLTools:
    def __init__(self):
        pass

    def _resolve_project_path(self, path: str) -> Path:
        project_root = Path(__file__).resolve().parents[1]
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = project_root / candidate
        resolved = candidate.resolve()
        if resolved != project_root and project_root not in resolved.parents:
            raise ValueError("Path must remain inside the project directory")
        return resolved

    def extract_load(self, url: str, output_folder: str, format: str):
        """
        This tool extracts the data from the API (url) and loads it into the
        the desired location (output_folder).

        Args:
            url (str): The API endpoint from which to extract data.
            output_folder (str): The folder where the extracted data will be saved.

        Returns:
            str: A message indicating the success or failure of the operation.

        """

        format = format.lower()
        if format not in {"csv", "json", "parquet"}:
            return f"Unsupported format: {format}"

        try:
            output_path = self._resolve_project_path(output_folder)
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()

            records = data.get("results") if isinstance(data, dict) else data
            if not isinstance(records, list):
                records = [records]

            output_path.mkdir(parents=True, exist_ok=True)
            filename = output_path / f"extracted_data.{format}"
            df = pd.json_normalize(records)
            if format == "csv":
                df.to_csv(filename, index=False)
            elif format == "json":
                df.to_json(filename, orient="records", lines=True)
            elif format == "parquet":
                df.to_parquet(filename, index=False)
            else:
                return f"Unsupported format: {format}"

            return f"Data successfully extracted and saved to {filename}"
        except (
            requests.exceptions.RequestException,
            ValueError,
            OSError,
            TypeError,
        ) as e:
            return f"Failed to extract data: {e}"

    def transform_load_context(self, file_path: str):
        """
        This tool transforms the data from the specified file and loads it into the
        desired location (output_folder).

        Args:
            file_path (str): The path to the file containing the data to be transformed.
            output_folder (str): The folder where the transformed data will be saved.
            output_format (str): The format in which to save the transformed data (csv, json, parquet).
        Returns:
            str: A message indicating the success or failure of the operation.
        """

        try:
            file_path = self._resolve_project_path(file_path)
        except ValueError as error:
            return str(error)

        file_extension = file_path.suffix.lower()
        if file_extension == ".csv":
            df = pd.read_csv(file_path)
        elif file_extension == ".json":
            df = pd.read_json(file_path, lines=True)
        elif file_extension == ".parquet":
            df = pd.read_parquet(file_path)
        else:
            return f"Unsupported file format: {file_extension}"

        top_3_rows = str(df.head(3))

        return top_3_rows

    def execute_code(self, code: str, context: dict | None = None):
        """
        This tool executes the provided code and returns the output.

        Args:
            code (str): The code to be executed.
        Returns:
            str: The output of the executed code or an error message if execution fails.
        """

        forbidden_names = {
            "__import__",
            "eval",
            "exec",
            "compile",
            "open",
            "input",
            "breakpoint",
            "globals",
            "locals",
            "vars",
        }
        forbidden_attributes = {
            "system",
            "popen",
            "remove",
            "unlink",
            "rmdir",
            "rename",
            "replace",
            "walk",
            "listdir",
            "read_pickle",
            "to_pickle",
        }

        try:
            tree = ast.parse(code, mode="exec")
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    raise ValueError("Imports are not allowed in generated ETL code")
                if isinstance(node, ast.Name) and node.id in forbidden_names:
                    raise ValueError(
                        f"The generated code uses forbidden name: {node.id}"
                    )
                if isinstance(node, ast.Attribute):
                    if node.attr.startswith("__") or node.attr in forbidden_attributes:
                        raise ValueError(
                            f"The generated code uses forbidden attribute: {node.attr}"
                        )

            safe_builtins = {
                "len": len,
                "range": range,
                "str": str,
                "int": int,
                "float": float,
            }
            globals_dict = {"__builtins__": safe_builtins, "pd": pd}
            globals_dict.update(context or {})
            exec(compile(tree, "<generated-etl>", "exec"), globals_dict, {})
            return "Code executed successfully."
        except (SyntaxError, ValueError, TypeError, NameError, OSError) as e:
            return f"Failed to execute code: {e}"


if __name__ == "__main__":
    obj = ETLTools()
    path = "C:\\Data_Agent\\data\\extract\\extracted_data.csv"
    print(obj.transform_load_context(path))
