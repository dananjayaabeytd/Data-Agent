import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

# gpt-5-nano is OpenAI's cheapest model. Override per level with LLM_MODEL_LOW,
# LLM_MODEL_MEDIUM, or LLM_MODEL_HIGH, or for every level with LLM_MODEL.
DEFAULT_MODEL = "gpt-5-nano"
LEVELS = ("low", "medium", "high")


def pick_llm(level: str):
    """
    Picks the appropriate LLM based on the level of the question.

    Args:
        level (str): The level of the question, can be "low", "medium", or "high".

    Returns:
        ChatOpenAI: The LLM instance to be used.
    """
    level = level.lower()
    if level not in LEVELS:
        raise ValueError(f"Unsupported level: {level}")

    model = os.getenv(f"LLM_MODEL_{level.upper()}") or os.getenv("LLM_MODEL", DEFAULT_MODEL)
    # gpt-5 reasoning models accept neither temperature=0 nor reasoning_effort="none";
    # "minimal" keeps billed reasoning tokens as low as possible.
    return ChatOpenAI(
        model_name=model,
        reasoning_effort=os.getenv("LLM_REASONING_EFFORT", "minimal"),
        timeout=60,
        max_retries=2,
    )
