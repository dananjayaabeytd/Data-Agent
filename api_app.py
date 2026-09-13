import hmac
import logging
import os
import re
import threading
import time
import uuid
from pathlib import Path

import jwt
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from jwt import InvalidTokenError
from pydantic import BaseModel, Field

from agents.sql_analyst import database_config
from main import ask_question
from utils.database import DatabaseUtil
from utils.session_store import create_session_store

load_dotenv(Path(__file__).resolve().parent / ".env")
LOGGER = logging.getLogger(__name__)
API_KEY = os.getenv("DATA_AGENT_API_KEY")
APP_ENV = os.getenv("APP_ENV", "development").lower()
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ISSUER = os.getenv("JWT_ISSUER", "data-agent")
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "data-agent-api")
USER_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
if APP_ENV == "production" and (not JWT_SECRET or len(JWT_SECRET) < 32):
    raise RuntimeError("Production requires JWT_SECRET with at least 32 characters")
store = create_session_store()
app = FastAPI(
    title="Data Agent API",
    version="1.0.0",
    docs_url=None if APP_ENV == "production" else "/docs",
    redoc_url=None if APP_ENV == "production" else "/redoc",
)
agent_slots = threading.BoundedSemaphore(int(os.getenv("AGENT_MAX_CONCURRENCY", "4")))
allowed_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
default_hosts = "*" if APP_ENV != "production" else "127.0.0.1,localhost"
allowed_hosts = [
    host.strip()
    for host in os.getenv("ALLOWED_HOSTS", default_hosts).split(",")
    if host.strip()
]
if APP_ENV == "production" and not allowed_hosts:
    raise RuntimeError("ALLOWED_HOSTS must be configured in production")
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts or ["*"])
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-User-ID"],
)


@app.middleware("http")
async def request_logging(request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1000
    response.headers["X-Request-ID"] = request_id
    LOGGER.info(
        "request_id=%s method=%s path=%s status=%s duration_ms=%.2f",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


class SessionCreateRequest(BaseModel):
    title: str = Field(default="New session", min_length=1, max_length=120)


class MessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20_000)


def current_user(
    x_api_key: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> str:
    if APP_ENV == "production":
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")
        try:
            claims = jwt.decode(
                authorization.removeprefix("Bearer "),
                JWT_SECRET,
                algorithms=["HS256"],
                issuer=JWT_ISSUER,
                audience=JWT_AUDIENCE,
            )
            user_id = claims.get("sub")
        except InvalidTokenError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token")
        if not isinstance(user_id, str):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token subject required")
        if x_user_id and x_user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User identity mismatch")
    elif API_KEY:
        if not hmac.compare_digest(x_api_key or "", API_KEY):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
        user_id = x_user_id
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="X-User-ID is required")
    else:
        user_id = x_user_id or "local"
    if not USER_ID_PATTERN.fullmatch(user_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID")
    return user_id


def session_payload(session) -> dict:
    return {
        "session_id": session.session_id,
        "title": session.title,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "messages": session.messages,
    }


@app.get("/health", tags=["system"])
def health() -> dict:
    return {"status": "ok", "environment": APP_ENV}


@app.get("/ready", tags=["system"])
def ready() -> dict:
    result = DatabaseUtil(database_config()).execute_sql("SELECT 1")
    if result.startswith("Error"):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database is unavailable")
    return {"status": "ready"}


@app.get("/api/v1/sessions", tags=["sessions"])
def list_sessions(user_id: str = Depends(current_user)) -> list[dict]:
    return [
        {
            "session_id": session.session_id,
            "title": session.title,
            "updated_at": session.updated_at,
            "message_count": len(session.messages),
        }
        for session in store.list(user_id)
    ]


@app.post("/api/v1/sessions", status_code=status.HTTP_201_CREATED, tags=["sessions"])
def create_session(request: SessionCreateRequest, user_id: str = Depends(current_user)) -> dict:
    return session_payload(store.create(request.title, user_id))


@app.get("/api/v1/sessions/{session_id}", tags=["sessions"])
def get_session(session_id: str, user_id: str = Depends(current_user)) -> dict:
    try:
        return session_payload(store.get(session_id, user_id))
    except HTTPException:
        raise
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")


@app.post("/api/v1/sessions/{session_id}/messages", tags=["agent"])
def send_message(
    session_id: str,
    request: MessageRequest,
    user_id: str = Depends(current_user),
) -> dict:
    if not agent_slots.acquire(blocking=False):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Agent capacity is full")
    try:
        session = store.get(session_id, user_id)
        message = request.message.strip()
        if not message:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Message cannot be empty",
            )
        session, answer = ask_question(
            store, session, message, owner_id=user_id
        )
        return {"session": session_payload(session), "answer": answer}
    except HTTPException:
        raise
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    except Exception:
        LOGGER.exception("Agent request failed for session %s", session_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Agent request failed")
    finally:
        agent_slots.release()


@app.delete("/api/v1/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["sessions"])
def delete_session(session_id: str, user_id: str = Depends(current_user)) -> None:
    try:
        store.delete(session_id, user_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
