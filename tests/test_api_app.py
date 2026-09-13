import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import jwt
from fastapi import HTTPException
from fastapi.testclient import TestClient

import api_app
from utils.session_store import SessionStore


class ApiAppTests(unittest.TestCase):
    def test_health_and_owner_scoped_sessions(self):
        original_store = api_app.store
        original_api_key = api_app.API_KEY
        with TemporaryDirectory() as directory:
            api_app.store = SessionStore(Path(directory) / "sessions.sqlite3")
            api_app.API_KEY = "test-secret"
            client = TestClient(api_app.app)
            headers_a = {"X-API-Key": "test-secret", "X-User-ID": "user-a"}
            headers_b = {"X-API-Key": "test-secret", "X-User-ID": "user-b"}
            try:
                self.assertEqual(client.get("/health").status_code, 200)
                self.assertEqual(client.get("/api/v1/sessions").status_code, 401)
                self.assertEqual(client.get("/api/v1/sessions", headers={"X-API-Key": "bad", "X-User-ID": "user-a"}).status_code, 401)

                created = client.post(
                    "/api/v1/sessions",
                    headers=headers_a,
                    json={"title": "User A"},
                )
                self.assertEqual(created.status_code, 201)
                session_id = created.json()["session_id"]

                self.assertEqual(len(client.get("/api/v1/sessions", headers=headers_a).json()), 1)
                self.assertEqual(client.get("/api/v1/sessions", headers=headers_b).json(), [])
                self.assertEqual(
                    client.get(f"/api/v1/sessions/{session_id}", headers=headers_b).status_code,
                    404,
                )
                self.assertEqual(
                    client.post(
                        f"/api/v1/sessions/{session_id}/messages",
                        headers=headers_a,
                        json={"message": "   "},
                    ).status_code,
                    400,
                )
                self.assertEqual(
                    client.delete(f"/api/v1/sessions/{session_id}", headers=headers_a).status_code,
                    204,
                )
            finally:
                api_app.store = original_store
                api_app.API_KEY = original_api_key

    def test_production_jwt_identity(self):
        original_environment = api_app.APP_ENV
        original_secret = api_app.JWT_SECRET
        original_api_key = api_app.API_KEY
        try:
            api_app.APP_ENV = "production"
            api_app.JWT_SECRET = "x" * 40
            api_app.API_KEY = None
            token = jwt.encode(
                {
                    "sub": "jwt-user",
                    "iss": api_app.JWT_ISSUER,
                    "aud": api_app.JWT_AUDIENCE,
                    "exp": 4102444800,
                },
                api_app.JWT_SECRET,
                algorithm="HS256",
            )
            self.assertEqual(
                api_app.current_user(x_user_id=None, authorization=f"Bearer {token}"),
                "jwt-user",
            )
            with self.assertRaises(HTTPException):
                api_app.current_user(x_user_id=None, authorization="Bearer invalid")
        finally:
            api_app.APP_ENV = original_environment
            api_app.JWT_SECRET = original_secret
            api_app.API_KEY = original_api_key


if __name__ == "__main__":
    unittest.main()
