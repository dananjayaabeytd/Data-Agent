import logging
import os

from langchain_core.runnables import RunnableConfig

from utils.llm_pick import active_profile

LOGGER = logging.getLogger(__name__)

# Tag traces with the deployment environment unless it is set explicitly.
os.environ.setdefault(
    "LANGFUSE_TRACING_ENVIRONMENT", os.getenv("APP_ENV", "development").lower()
)


def tracing_enabled() -> bool:
    """Langfuse tracing is on when both keys are configured and it is not switched off."""
    return (
        bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))
        and os.getenv("LANGFUSE_TRACING_ENABLED", "true").lower() != "false"
    )


def agent_run_config(
    *,
    session_id: str | None = None,
    user_id: str | None = None,
    tags: list[str] | None = None,
) -> RunnableConfig:
    """LangChain run config that sends the whole agent run to Langfuse when it is configured.

    Nested graphs, LLM calls, and tools inherit the callback through LangChain's run context,
    so one handler on the top-level invoke traces every step.
    """
    config: RunnableConfig = {"run_name": "data-agent"}
    if not tracing_enabled():
        return config

    from langfuse.langchain import CallbackHandler

    # Tag the model profile so traces and costs can be filtered per profile.
    tags = [*(tags or []), f"models:{active_profile().name}"]
    metadata: dict = {}
    if session_id:
        metadata["langfuse_session_id"] = session_id
    if user_id:
        metadata["langfuse_user_id"] = user_id
    metadata["langfuse_tags"] = tags
    config["callbacks"] = [CallbackHandler()]
    config["metadata"] = metadata
    return config


def flush_tracing() -> None:
    """Send buffered spans; call before the process exits."""
    if not tracing_enabled():
        return
    from langfuse import get_client

    try:
        get_client().flush()
    except Exception:
        LOGGER.warning("Langfuse flush failed", exc_info=True)
