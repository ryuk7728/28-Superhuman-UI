from __future__ import annotations

import asyncio
import os
import time
import random
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from typing import Any

from app.engine.cards_adapter import from_card_id, to_card_id
from app.engine.k_policy import compute_k
from app.settings import settings
from app.legacy.cards import Cards
from app.legacy import minimax as legacy_minimax


# -----------------------------
# Worker-side helpers (picklable)
# -----------------------------

def _full_deck_card_ids() -> list[str]:
    return [to_card_id(c) for c in Cards.packOf28()]


def _seed_entropy() -> int:
    # Non-deterministic seed with high diversity across workers
    return (
        int.from_bytes(os.urandom(8), "little")
        ^ os.getpid()
        ^ time.time_ns()
    )


def rollout_worker(snapshot: dict[str, Any], n: int, seed: int) -> dict[Any, int]:
    """
    Runs n rollouts and returns a Counter-like dict mapping:
      - bool -> count
      - card_identity_string -> count
    This function MUST be top-level for Windows spawn pickling.
    """
    rng = random.Random(seed)

    bot_seat: int = snapshot["botSeat"]
    finalBid: int = snapshot["finalBid"]  # 1-indexed
    bidder_seat: int = snapshot["bidderSeat"]

    leaderIndex: int = snapshot["leaderIndex"]
    catchNumber: int = snapshot["catchNumber"]
    k: int = snapshot["k"]

    trumpReveal: bool = snapshot["trumpReveal"]
    chose: bool = snapshot["chose"]
    currentSuit: str = snapshot["currentSuit"]
    trumpPlayed: bool = snapshot["trumpPlayed"]
    trumpIndice: list[int] = snapshot["trumpIndice"]

    s_card_ids: list[str] = snapshot["sCardIds"]
    s_cards = [from_card_id(cid) for cid in s_card_ids]

    bot_hand = [from_card_id(cid) for cid in snapshot["botHandCardIds"]]
    hand_sizes: list[int] = snapshot["handSizes"]

    played_set = set(snapshot["playedCardIds"])
    deck_ids = _full_deck_card_ids()

    # Base known set for this bot (own hand + played)
    base_known = set(snapshot["botHandCardIds"]) | played_set

    # If bot is bidder and concealed trump exists, include it as known
    concealed_trump_card_id = snapshot.get("concealedTrumpCardId")
    if concealed_trump_card_id and bot_seat == bidder_seat:
        base_known.add(concealed_trump_card_id)

    # If trump is already revealed, suit is known for all
    known_trump_suit = snapshot.get("knownTrumpSuit") if trumpReveal else None

    counts: Counter = Counter()

    for _ in range(n):
        # Build unknown pool
        pool_ids = [cid for cid in deck_ids if cid not in base_known]

        # Determine sim_player_trump and sim_trump_suit
        sim_player_trump = None
        sim_trump_suit = None

        if trumpReveal:
            sim_trump_suit = known_trump_suit
        else:
            if bot_seat == bidder_seat:
                # bidder knows true concealed trump
                if not concealed_trump_card_id:
                    # should not happen if state is consistent
                    sim_player_trump = None
                    sim_trump_suit = None
                else:
                    sim_player_trump = from_card_id(concealed_trump_card_id)
                    sim_trump_suit = sim_player_trump.suit
            else:
                # non-bidder: trump unknown -> sample from pool
                idx = rng.randrange(len(pool_ids))
                sampled = pool_ids.pop(idx)
                sim_player_trump = from_card_id(sampled)
                sim_trump_suit = sim_player_trump.suit

        # Shuffle pool for distribution
        rng.shuffle(pool_ids)

        # Build hands
        hands: list[list] = [[], [], [], []]
        hands[bot_seat] = bot_hand[:]  # keep bot's real hand

        pool_idx = 0
        for seat in range(4):
            if seat == bot_seat:
                continue
            need = hand_sizes[seat]
            slice_ids = pool_ids[pool_idx : pool_idx + need]
            pool_idx += need
            hands[seat] = [from_card_id(cid) for cid in slice_ids]

        # Build legacy players structure
        players = []
        for i in range(4):
            players.append(
                {
                    "cards": hands[i],
                    "isTrump": i == bidder_seat,
                    "team": 1 if i % 2 == 0 else 2,
                    "trump": sim_player_trump if i == bidder_seat else None,
                }
            )

        reward_distribution: list[tuple[object, float]] = []

        legacy_minimax.minimax_extended(
            s_cards[:],
            True,
            True,
            trumpPlayed,
            s_cards[:],
            trumpIndice[:],
            leaderIndex,
            players,
            currentSuit,
            trumpReveal,
            sim_trump_suit,
            chose,
            finalBid,
            sim_player_trump,
            -1,
            reward_distribution,
            0,
            0,
            k,
        )

        for a, _v in reward_distribution:
            counts[a] += 1

    return dict(counts)


# -----------------------------
# Main-process async chooser
# -----------------------------

def _build_snapshot(state, bot_seat: int) -> dict[str, Any]:
    # played cards include completed catches + current trick
    played_cards = []
    for c in state.team1Catches:
        played_cards.extend(c)
    for c in state.team2Catches:
        played_cards.extend(c)
    played_cards.extend(state.s)

    played_ids = [to_card_id(c) for c in played_cards]

    bot_hand_ids = [to_card_id(c) for c in state.play_players[bot_seat]["cards"]]

    concealed_id = None
    bidder_seat = state.finalBid - 1
    if bot_seat == bidder_seat and state.player_trump is not None:
        concealed_id = to_card_id(state.player_trump)

    snap: dict[str, Any] = {
        "botSeat": bot_seat,
        "finalBid": state.finalBid,
        "bidderSeat": bidder_seat,
        "leaderIndex": state.leaderIndex,
        "catchNumber": state.catchNumber,
        "k": compute_k(state.catchNumber),
        "trumpReveal": state.trumpReveal,
        "knownTrumpSuit": state.trumpSuit if state.trumpReveal else None,
        "chose": state.chose,
        "currentSuit": state.currentSuit,
        "trumpPlayed": state.trumpPlayed,
        "trumpIndice": list(state.trumpIndice),
        "sCardIds": [to_card_id(c) for c in state.s],
        "botHandCardIds": bot_hand_ids,
        "handSizes": [len(state.play_players[i]["cards"]) for i in range(4)],
        "playedCardIds": played_ids,
        "concealedTrumpCardId": concealed_id,
    }

    return snap


async def choose_action_with_rollouts_parallel(
    state,
    bot_seat: int,
    pool: ProcessPoolExecutor,
) -> tuple[str, dict]:
    """
    Returns:
      ("REVEAL", {"seatIndex": bot_seat, "reveal": bool})
      or
      ("PLAY", {"seatIndex": bot_seat, "cardId": "Hearts_Jack"})
    """
    from app.engine.play_engine import compute_play_legal_actions

    legal = compute_play_legal_actions(state)
    if legal.type == "NO_ACTION":
        raise RuntimeError("Bot has no legal action.")

    total_rollouts = max(1, int(settings.rollouts))
    worker_count = max(1, min(int(settings.workers), total_rollouts))

    snapshot = _build_snapshot(state, bot_seat)

    # Split rollouts across workers
    base = total_rollouts // worker_count
    rem = total_rollouts % worker_count

    loop = asyncio.get_running_loop()
    tasks = []

    for i in range(worker_count):
        n = base + (1 if i < rem else 0)
        seed = _seed_entropy()

        fut = pool.submit(rollout_worker, snapshot, n, seed)
        tasks.append(asyncio.wrap_future(fut, loop=loop))

    results = await asyncio.gather(*tasks)

    merged: Counter = Counter()
    for d in results:
        merged.update(d)

    if not merged:
        # fallback
        if legal.type == "REVEAL_CHOICE":
            return ("REVEAL", {"seatIndex": bot_seat, "reveal": False})
        return ("PLAY", {"seatIndex": bot_seat, "cardId": legal.cardIds[0]})

    best_action, _ = merged.most_common(1)[0]

    # bool => reveal choice
    if isinstance(best_action, bool):
        return ("REVEAL", {"seatIndex": bot_seat, "reveal": bool(best_action)})

    # string => card identity
    if isinstance(best_action, str):
        if legal.type != "PLAY_CARD" or not legal.cardIds:
            # if server expects reveal choice but rollouts suggested card, fallback
            return ("REVEAL", {"seatIndex": bot_seat, "reveal": False})

        for cid in legal.cardIds:
            if from_card_id(cid).identity() == best_action:
                return ("PLAY", {"seatIndex": bot_seat, "cardId": cid})

        return ("PLAY", {"seatIndex": bot_seat, "cardId": legal.cardIds[0]})

    # Unknown type fallback
    if legal.type == "REVEAL_CHOICE":
        return ("REVEAL", {"seatIndex": bot_seat, "reveal": False})
    return ("PLAY", {"seatIndex": bot_seat, "cardId": legal.cardIds[0]})