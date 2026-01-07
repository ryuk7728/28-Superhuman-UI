from __future__ import annotations

from dataclasses import dataclass
import os

from dotenv import load_dotenv

load_dotenv()


def _get_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "y", "on")


def _get_int(name: str, default: int) -> int:
    val = os.getenv(name)
    if val is None or val.strip() == "":
        return default
    return int(val)


def _get_int_optional(name: str) -> int | None:
    val = os.getenv(name)
    if val is None or val.strip() == "":
        return None
    return int(val)


@dataclass(frozen=True)
class Settings:
    debug: bool = _get_bool("APP_DEBUG", True)

    # Rollout bot config
    rollouts: int = _get_int("APP_ROLLOUTS", 200)
    workers: int = _get_int("APP_WORKERS", 8)

    # NEW: retries for constraint-aware rollout dealing
    rollout_deal_retries: int = _get_int("APP_ROLLOUT_DEAL_RETRIES", 30)

    max_concurrent_bot_thinking: int = _get_int(
        "APP_MAX_CONCURRENT_BOT_THINKING", 1
    )

    # k control
    k_override: int | None = _get_int_optional("APP_K_OVERRIDE")

    cors_origins: tuple[str, ...] = (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    )


settings = Settings()