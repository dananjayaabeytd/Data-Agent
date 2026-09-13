import argparse
import logging
from collections.abc import Sequence

from langchain_core.messages import HumanMessage

from agents.data_agent import data_agent
from utils.session_store import Session, SessionStore

LOGGER = logging.getLogger(__name__)
MAX_CONTEXT_MESSAGES = 10


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Interactive Data Agent")
    parser.add_argument(
        "--session",
        help="Resume an existing session by its ID",
    )
    parser.add_argument(
        "--once",
        metavar="QUESTION",
        help="Process one question and exit",
    )
    parser.add_argument(
        "--list-sessions",
        action="store_true",
        help="List saved sessions and exit",
    )
    parser.add_argument(
        "--delete-session",
        metavar="SESSION_ID",
        help="Delete a saved session and exit",
    )
    return parser


def answer_text(response: dict) -> str:
    message = response["messages"][-1]
    content = getattr(message, "content", message)
    if isinstance(content, Sequence) and not isinstance(content, str):
        return "\n".join(str(part) for part in content)
    return str(content)


def build_request(session: Session, question: str) -> str:
    if not session.messages:
        return question

    history = session.messages[-MAX_CONTEXT_MESSAGES:]
    history_text = "\n".join(
        f"{message['role'].title()}: {message['content']}" for message in history
    )
    return (
        "Use this conversation history only as context for the current request. "
        "The current request takes priority.\n\n"
        f"Conversation history:\n{history_text}\n\n"
        f"Current request:\n{question}"
    )


def ask_question(
    store: SessionStore,
    session: Session,
    question: str,
    owner_id: str = "local",
) -> tuple[Session, str]:
    request = build_request(session, question)
    response = data_agent.invoke(
        {
            "messages": [HumanMessage(content=request)],
            "route_response": None,
        }
    )
    answer = answer_text(response)
    store.append(session.session_id, "user", question, owner_id)
    session = store.append(session.session_id, "assistant", answer, owner_id)
    return session, answer


def process_question(store: SessionStore, session: Session, question: str) -> Session:
    session, answer = ask_question(store, session, question)
    print(f"\n{answer}\n")
    return session


def print_sessions(store: SessionStore) -> None:
    sessions = store.list()
    if not sessions:
        print("No saved sessions.")
        return
    for session in sessions:
        message_count = len(session.messages)
        print(f"{session.session_id}  {session.title}  ({message_count} messages)")


def print_history(session: Session) -> None:
    if not session.messages:
        print("This session has no messages.")
        return
    for message in session.messages:
        print(f"{message['role'].title()}: {message['content']}\n")


def print_help() -> None:
    print(
        "Commands:\n"
        "  /help                 Show this help\n"
        "  /sessions             List saved sessions\n"
        "  /new [title]          Start a new session\n"
        "  /use SESSION_ID       Switch to a saved session\n"
        "  /history              Show current session messages\n"
        "  /delete [SESSION_ID]  Delete a session\n"
        "  /exit                 Save and exit\n"
    )


def handle_command(
    store: SessionStore, session: Session, command: str
) -> tuple[Session, bool]:
    parts = command.split(maxsplit=2)
    name = parts[0].lower()

    if name == "/help":
        print_help()
    elif name == "/sessions":
        print_sessions(store)
    elif name == "/history":
        print_history(session)
    elif name == "/new":
        title = " ".join(parts[1:]) if len(parts) > 1 else "New session"
        session = store.create(title)
        print(f"Started session {session.session_id}.")
    elif name == "/use" and len(parts) == 2:
        session = store.get(parts[1])
        print(f"Switched to session {session.session_id}: {session.title}")
    elif name == "/delete":
        session_id = parts[1] if len(parts) > 1 else session.session_id
        store.delete(session_id)
        print(f"Deleted session {session_id}.")
        if session_id == session.session_id:
            session = store.create()
            print(f"Started session {session.session_id}.")
    elif name in {"/exit", "/quit"}:
        return session, True
    else:
        print("Unknown command. Use /help to see available commands.")
    return session, False


def run_interactive(store: SessionStore, session: Session) -> int:
    print(f"Data Agent session {session.session_id}: {session.title}")
    print("Ask an ETL or SQL question. Use /help for commands.")
    while True:
        try:
            question = input(f"\n[{session.session_id}]> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSession saved.")
            return 0

        if not question:
            continue
        if question.startswith("/"):
            try:
                session, should_exit = handle_command(store, session, question)
            except KeyError as error:
                print(f"Error: {error.args[0]}")
            if should_exit:
                return 0
            continue

        try:
            session = process_question(store, session, question)
        except Exception:
            LOGGER.exception("Question processing failed")
            print(
                "The request failed. The session is still available; please try again."
            )


def main() -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    args = build_parser().parse_args()
    store = SessionStore()

    try:
        if args.list_sessions:
            print_sessions(store)
            return 0
        if args.delete_session:
            store.delete(args.delete_session)
            print(f"Deleted session {args.delete_session}.")
            return 0

        session = store.get(args.session) if args.session else store.create()
        if args.once:
            process_question(store, session, args.once)
            return 0
        return run_interactive(store, session)
    except KeyError as error:
        print(f"Error: {error.args[0]}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
