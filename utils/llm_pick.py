import os
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ConfigDict

load_dotenv()

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "models.yaml"
LEVELS = ("low", "medium", "high")


class ModelSettings(BaseModel):
    """Settings for one level; unknown keys are rejected so typos fail at startup."""

    model_config = ConfigDict(extra="forbid")

    model: str
    reasoning_effort: str | None = None
    temperature: float | None = None
    timeout: float = 60
    max_retries: int = 2


class ModelProfile(BaseModel):
    name: str
    description: str = ""
    levels: dict[str, ModelSettings]


@lru_cache(maxsize=None)
def active_profile() -> ModelProfile:
    """Load the profile named by MODEL_PROFILE, or by `active` in config/models.yaml."""
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    profiles = config.get("profiles") or {}
    name = os.getenv("MODEL_PROFILE") or config.get("active")
    if name not in profiles:
        raise ValueError(
            f"Unknown model profile {name!r} in {CONFIG_PATH.name}; "
            f"available: {', '.join(profiles) or 'none'}"
        )

    entry = profiles[name]
    defaults = entry.get("defaults") or {}
    levels = entry.get("levels") or {}
    missing = [level for level in LEVELS if level not in levels]
    if missing:
        raise ValueError(f"Model profile {name!r} is missing levels: {', '.join(missing)}")

    return ModelProfile(
        name=name,
        description=" ".join(str(entry.get("description", "")).split()),
        levels={level: ModelSettings(**{**defaults, **levels[level]}) for level in LEVELS},
    )


def pick_llm(level: str):
    """
    Picks the appropriate LLM based on the level of the question.

    Args:
        level (str): The level of the question, can be "low", "medium", or "high".

    Returns:
        ChatOpenAI: The LLM instance configured by the active model profile.
    """
    level = level.lower()
    if level not in LEVELS:
        raise ValueError(f"Unsupported level: {level}")

    options = active_profile().levels[level].model_dump(exclude_none=True)
    return ChatOpenAI(model_name=options.pop("model"), **options)
