from __future__ import annotations

from app.settings import settings


def compute_k(catch_number: int) -> int:
    """
    k selection precedence:
    1) APP_K_OVERRIDE (single constant for all catches)
    2) APP_K_BY_CATCH map (per-catch override, e.g. "1:3,2:3,3:4,...")
    3) Default policy below

    Default policy:
    - catches 1-2 -> k=3
    - catches 3-4 -> k=4
    - catches 5-8 -> k = max(1, 9 - catch_number)
    """
    if settings.k_override is not None:
        return settings.k_override

    k_for_catch = settings.k_by_catch.get(catch_number)
    if k_for_catch is not None:
        return k_for_catch

    if catch_number <= 2:
        return 3
    elif catch_number <= 4:
        return 4
    else:
        return max(1, 9 - catch_number)
