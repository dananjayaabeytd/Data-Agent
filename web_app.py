import argparse
import json
import logging
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from main import ask_question
from utils.session_store import SessionStore

LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parent
TEMPLATES_DIR = PROJECT_ROOT / "templates"
STATIC_DIR = PROJECT_ROOT / "static"


class WebHandler(BaseHTTPRequestHandler):
    store = SessionStore()

    def _send_bytes(self, body: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload: dict | list, status: int = 200) -> None:
        self._send_bytes(
            json.dumps(payload).encode("utf-8"),
            "application/json; charset=utf-8",
            status,
        )

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length > 1_000_000:
            raise ValueError("Request body is too large")
        return json.loads(self.rfile.read(length) or b"{}")

    @staticmethod
    def _session_payload(session) -> dict:
        return {
            "session_id": session.session_id,
            "title": session.title,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "messages": session.messages,
        }

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        try:
            if path == "/":
                self._send_bytes(
                    (TEMPLATES_DIR / "index.html").read_bytes(),
                    "text/html; charset=utf-8",
                )
                return
            if path.startswith("/static/"):
                relative_path = Path(unquote(path.removeprefix("/static/")))
                file_path = (STATIC_DIR / relative_path).resolve()
                if STATIC_DIR not in file_path.parents or not file_path.is_file():
                    self._send_json({"error": "Not found"}, 404)
                    return
                content_type = (
                    mimetypes.guess_type(file_path.name)[0]
                    or "application/octet-stream"
                )
                self._send_bytes(file_path.read_bytes(), content_type)
                return
            if path == "/api/sessions":
                payload = [
                    {
                        "session_id": session.session_id,
                        "title": session.title,
                        "updated_at": session.updated_at,
                        "message_count": len(session.messages),
                    }
                    for session in self.store.list()
                ]
                self._send_json(payload)
                return
            if path.startswith("/api/sessions/"):
                session_id = unquote(path.rsplit("/", 1)[-1])
                self._send_json(self._session_payload(self.store.get(session_id)))
                return
            self._send_json({"error": "Not found"}, 404)
        except KeyError as error:
            self._send_json({"error": error.args[0]}, 404)
        except Exception as error:
            LOGGER.exception("GET request failed")
            self._send_json({"error": str(error)}, 500)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            body = self._read_json()
            if path == "/api/sessions":
                session = self.store.create(str(body.get("title", "New session")))
                self._send_json(self._session_payload(session), 201)
                return
            if path.startswith("/api/sessions/") and path.endswith("/messages"):
                session_id = unquote(
                    path.split("/api/sessions/", 1)[1].rsplit("/", 1)[0]
                )
                message = str(body.get("message", "")).strip()
                if not message:
                    self._send_json({"error": "Message cannot be empty"}, 400)
                    return
                session, answer = ask_question(
                    self.store, self.store.get(session_id), message
                )
                self._send_json(
                    {"session": self._session_payload(session), "answer": answer}
                )
                return
            self._send_json({"error": "Not found"}, 404)
        except KeyError as error:
            self._send_json({"error": error.args[0]}, 404)
        except ValueError as error:
            self._send_json({"error": str(error)}, 400)
        except Exception:
            LOGGER.exception("POST request failed")
            self._send_json({"error": "Request failed. Check the server logs."}, 500)

    def do_DELETE(self) -> None:
        path = urlparse(self.path).path
        try:
            if path.startswith("/api/sessions/"):
                session_id = unquote(path.rsplit("/", 1)[-1])
                self.store.delete(session_id)
                self._send_json({"deleted": session_id})
                return
            self._send_json({"error": "Not found"}, 404)
        except KeyError as error:
            self._send_json({"error": error.args[0]}, 404)
        except Exception as error:
            LOGGER.exception("DELETE request failed")
            self._send_json({"error": str(error)}, 500)

    def log_message(self, format: str, *args) -> None:
        LOGGER.info("%s - %s", self.address_string(), format % args)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Data Agent web UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    server = ThreadingHTTPServer((args.host, args.port), WebHandler)
    print(f"Data Agent UI running at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Data Agent UI")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
