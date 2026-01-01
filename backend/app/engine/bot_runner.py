from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor

from app.bots.rollout_bot import choose_action_with_rollouts_parallel
from app.engine.play_engine import (
    apply_play_card,
    apply_reveal_choice,
    resolve_if_catch_complete,
)


BOT_SEATS = {0, 2}


async def advance_bots_until_human(state, pool: ProcessPoolExecutor, bot_sem) -> None:
    """
    Runs bot turns (seats 0 and 2) until current actor is human (1 or 3) or game ends.
    Uses multiprocessing rollouts to decide bot actions.
    """
    while state.phase == "PLAY":
        actor = (state.leaderIndex + len(state.s)) % 4
        if actor not in BOT_SEATS:
            return

        # Limit concurrent bot computations globally
        async with bot_sem:
            action_type, payload = await choose_action_with_rollouts_parallel(
                state, actor, pool
            )

        if action_type == "REVEAL":
            apply_reveal_choice(state, payload["seatIndex"], bool(payload["reveal"]))
        else:
            apply_play_card(state, payload["seatIndex"], str(payload["cardId"]))

        resolve_if_catch_complete(state)