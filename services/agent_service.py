from collections.abc import Sequence

from langchain_core.messages import HumanMessage

from agents.data_agent import data_agent
from utils.session_store import Session

MAX_CONTEXT_MESSAGES = 10


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
    store,
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
