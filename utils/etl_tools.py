import ipaddress
import json
import os
import socket
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import requests

from Models.schema import TransformationPlan


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

    def _validate_url(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Only HTTP and HTTPS URLs are allowed")

        allowed_hosts = {
            host.strip().lower()
            for host in os.getenv("ETL_ALLOWED_HOSTS", "").split(",")
            if host.strip()
        }
        if os.getenv("APP_ENV", "development").lower() == "production" and not allowed_hosts:
            raise ValueError("ETL_ALLOWED_HOSTS must be configured in production")
        hostname = parsed.hostname.lower()
        if allowed_hosts and hostname not in allowed_hosts:
            raise ValueError("API host is not on the ETL allowlist")
        if hostname in allowed_hosts:
            return

        try:
            addresses = socket.getaddrinfo(hostname, parsed.port or 443, type=socket.SOCK_STREAM)
        except socket.gaierror as error:
            raise ValueError(f"Unable to resolve API host: {hostname}") from error
        for address in addresses:
            ip_address = ipaddress.ip_address(address[4][0])
            if ip_address.is_private or ip_address.is_loopback or ip_address.is_link_local or ip_address.is_reserved:
                raise ValueError("Requests to private or reserved network addresses are not allowed")

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
            self._validate_url(url)
            output_path = self._resolve_project_path(output_folder)
            response = requests.get(url, timeout=(5, 30), stream=True, allow_redirects=False)
            if 300 <= response.status_code < 400:
                response.close()
                raise ValueError("API redirects are not allowed")
            response.raise_for_status()
            raw_response = bytearray()
            max_download_bytes = int(os.getenv("ETL_MAX_DOWNLOAD_BYTES", "26214400"))
            try:
                for chunk in response.iter_content(chunk_size=64 * 1024):
                    raw_response.extend(chunk)
                    if len(raw_response) > max_download_bytes:
                        raise ValueError("API response exceeds the configured size limit")
            finally:
                response.close()
            data = json.loads(raw_response.decode("utf-8"))

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

            max_output_bytes = int(os.getenv("ETL_MAX_OUTPUT_BYTES", "52428800"))
            if filename.stat().st_size > max_output_bytes:
                filename.unlink(missing_ok=True)
                return "Failed to extract data: output exceeds the configured size limit"

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

        try:
            df = self.load_dataframe(file_path)
        except (OSError, ValueError) as error:
            return str(error)

        top_3_rows = str(df.head(3))

        return top_3_rows

    def load_dataframe(self, file_path: str | Path) -> pd.DataFrame:
        resolved_path = self._resolve_project_path(str(file_path))
        max_input_bytes = int(os.getenv("ETL_MAX_INPUT_BYTES", "52428800"))
        if resolved_path.stat().st_size > max_input_bytes:
            raise ValueError("Input file exceeds the configured size limit")
        file_extension = resolved_path.suffix.lower()
        if file_extension == ".csv":
            return pd.read_csv(resolved_path)
        if file_extension == ".json":
            return pd.read_json(resolved_path, lines=True)
        if file_extension == ".parquet":
            return pd.read_parquet(resolved_path)
        raise ValueError(f"Unsupported file format: {file_extension}")

    def apply_transformation_plan(
        self,
        input_file_path: str,
        output_folder: str,
        output_format: str,
        plan: TransformationPlan,
    ) -> str:
        output_format = output_format.lower()
        if output_format not in {"csv", "json", "parquet"}:
            return f"Unsupported format: {output_format}"

        try:
            dataframe = self.load_dataframe(input_file_path)
            for step in plan.steps:
                if (
                    step.operation in {"filter_equals", "filter_contains", "sort"}
                    and (not step.column or step.column not in dataframe.columns)
                ):
                    raise ValueError(f"Unknown transformation column: {step.column}")
                if step.operation == "filter_equals":
                    dataframe = dataframe[dataframe[step.column] == step.value]
                elif step.operation == "filter_contains":
                    values = dataframe[step.column].astype(str)
                    dataframe = dataframe[values.str.contains(str(step.value), case=False, na=False, regex=False)]
                elif step.operation == "select_columns":
                    missing = set(step.columns) - set(dataframe.columns)
                    if missing:
                        raise ValueError(f"Unknown transformation columns: {sorted(missing)}")
                    dataframe = dataframe[step.columns]
                elif step.operation == "sort":
                    dataframe = dataframe.sort_values(step.column, ascending=step.ascending)
                elif step.operation == "limit":
                    if step.limit is None:
                        raise ValueError("A limit value is required for limit operations")
                    dataframe = dataframe.head(step.limit)

            output_path = self._resolve_project_path(output_folder)
            output_path.mkdir(parents=True, exist_ok=True)
            output_file = output_path / f"transformed_data.{output_format}"
            if output_format == "csv":
                dataframe.to_csv(output_file, index=False)
            elif output_format == "json":
                dataframe.to_json(output_file, orient="records", lines=True)
            else:
                dataframe.to_parquet(output_file, index=False)
            max_output_bytes = int(os.getenv("ETL_MAX_OUTPUT_BYTES", "52428800"))
            if output_file.stat().st_size > max_output_bytes:
                output_file.unlink(missing_ok=True)
                return "Transformation failed: output exceeds the configured size limit"
            return f"Data successfully transformed and saved to {output_file}"
        except (OSError, TypeError, ValueError, KeyError) as error:
            return f"Transformation failed: {error}"


if __name__ == "__main__":
    obj = ETLTools()
    path = "C:\\Data_Agent\\data\\extract\\extracted_data.csv"
    print(obj.transform_load_context(path))
