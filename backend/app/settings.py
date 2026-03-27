from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path

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


def _get_float(name: str, default: float) -> float:
    val = os.getenv(name)
    if val is None or val.strip() == "":
        return default
    return float(val)


def _get_int_optional(name: str) -> int | None:
    val = os.getenv(name)
    if val is None or val.strip() == "":
        return None
    return int(val)


def _get_str(name: str, default: str) -> str:
    val = os.getenv(name)
    if val is None:
        return default
    return val


def _get_str_optional(name: str) -> str | None:
    val = os.getenv(name)
    if val is None or val.strip() == "":
        return None
    return val


def _get_csv(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    val = os.getenv(name)
    if val is None or val.strip() == "":
        return default
    parts = [x.strip() for x in val.split(",")]
    return tuple(x for x in parts if x)


def _get_k_by_catch_map(name: str) -> dict[int, int]:
    """
    Parse per-trick k mapping from env.
    Format:
      APP_K_BY_CATCH=1:2,2:2,3:3,4:4,5:4,6:3,7:2,8:1
    """
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return {}

    out: dict[int, int] = {}
    for item in raw.replace(";", ",").split(","):
        part = item.strip()
        if not part:
            continue
        if ":" not in part:
            raise ValueError(
                f"Invalid {name} entry '{part}'. Expected format catch:k (e.g. 5:4)."
            )
        left, right = part.split(":", 1)
        catch_num = int(left.strip())
        k_val = int(right.strip())
        if catch_num < 1 or catch_num > 8:
            raise ValueError(
                f"Invalid {name} catch '{catch_num}'. Catch number must be in [1, 8]."
            )
        if k_val < 1:
            raise ValueError(
                f"Invalid {name} k '{k_val}' for catch {catch_num}. k must be >= 1."
            )
        out[catch_num] = k_val
    return out


@dataclass(frozen=True)
class Settings:
    app_dir: Path = Path(__file__).resolve().parent
    backend_dir: Path = app_dir.parent
    debug: bool = _get_bool("APP_DEBUG", True)

    # Rollout bot config
    rollouts: int = _get_int("APP_ROLLOUTS", 200)
    workers: int = _get_int("APP_WORKERS", 8)

    # NEW: retries for constraint-aware rollout dealing
    rollout_deal_retries: int = _get_int("APP_ROLLOUT_DEAL_RETRIES", 30)

    # Rollout metrics logging
    rollout_metrics: bool = _get_bool("APP_ROLLOUT_METRICS", False)
    rollout_metrics_interval: float = _get_float("APP_ROLLOUT_METRICS_INTERVAL", 10.0)

    max_concurrent_bot_thinking: int = _get_int(
        "APP_MAX_CONCURRENT_BOT_THINKING", 1
    )

    # Rollout backend (local or ray)
    rollout_backend: str = _get_str("APP_ROLLOUT_BACKEND", "local").strip().lower()
    ray_address: str | None = _get_str_optional("RAY_ADDRESS") or _get_str_optional(
        "APP_RAY_ADDRESS"
    )

    # k control
    k_override: int | None = _get_int_optional("APP_K_OVERRIDE")
    k_by_catch: dict[int, int] = field(
        default_factory=lambda: _get_k_by_catch_map("APP_K_BY_CATCH")
    )

    # Fixed-deck mode (for deterministic reproduction)
    fixed_deck_enabled: bool = _get_bool("APP_FIXED_DECK_ENABLED", False)
    fixed_deck_path: str = _get_str(
        "APP_FIXED_DECK_PATH",
        str((Path(__file__).resolve().parent.parent / "fixed_deck.txt").as_posix()),
    )

    cors_origins: tuple[str, ...] = _get_csv(
        "APP_CORS_ORIGINS",
        (
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "https://28-superhuman-ui.vercel.app",
        ),
    )
    cors_origin_regex: str | None = _get_str_optional("APP_CORS_ORIGIN_REGEX")


settings = Settings()
