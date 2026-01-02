from __future__ import annotations

import json
import traceback
from pathlib import Path
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


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "y", "on")


def _dump_dir_backend_root() -> Path:
    # rollout_bot.py is: backend/app/bots/rollout_bot.py
    # parents: bots -> app -> backend
    backend_root = Path(__file__).resolve().parents[2]
    dump_dir = backend_root / "rollout_crash_dumps"
    dump_dir.mkdir(parents=True, exist_ok=True)
    return dump_dir


def _safe_card_id(x):
    try:
        if x is None:
            return None
        return to_card_id(x)
    except Exception:
        return None


def _players_to_cardids(players):
    out = []
    for i in range(4):
        out.append([_safe_card_id(c) for c in players[i]["cards"]])
    return out


def _find_none_positions(players):
    pos = []
    for i in range(4):
        idxs = [j for j, c in enumerate(players[i]["cards"]) if c is None]
        if idxs:
            pos.append({"seat": i, "indices": idxs})
    return pos

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
    if concealed_trump_card_id and (bot_seat == bidder_seat or trumpReveal):
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

        # If trump is revealed, the suit is known.
        # BUT legacy logic may still need playerTrump to be non-None when chose=True,
        # especially for bidder branches. So if snapshot has concealedTrumpCardId,
        # keep it available (public once revealed anyway).
        if trumpReveal:
            sim_trump_suit = known_trump_suit

            if concealed_trump_card_id is not None:
                # Prefer using the same object instance if it exists in bidder's hand
                # (important because legacy uses `a == playerTrump` to consume it).
                found = None
                # We haven't built `players` yet, but we do have bot_hand which may contain it.
                for c in bot_hand:
                    if to_card_id(c) == concealed_trump_card_id:
                        found = c
                        break
                sim_player_trump = found if found is not None else from_card_id(concealed_trump_card_id)

        else:
            if bot_seat == bidder_seat:
                # bidder knows true concealed trump
                if concealed_trump_card_id is not None:
                    # same-instance preference if present
                    found = None
                    for c in bot_hand:
                        if to_card_id(c) == concealed_trump_card_id:
                            found = c
                            break
                    sim_player_trump = found if found is not None else from_card_id(concealed_trump_card_id)
                    sim_trump_suit = sim_player_trump.suit
                else:
                    sim_player_trump = None
                    sim_trump_suit = None
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

        dump_enabled = _env_bool("APP_DUMP_ROLLOUT_CRASHES", False)
        call_log_max = int(os.getenv("APP_RESULT_CALL_LOG_SIZE", "80"))
        result_call_log = []

        orig_result = legacy_minimax.result

        def traced_result(
            s,
            a,
            currentSuit,
            trumpReveal,
            chose,
            playerTrump,
            trumpPlayed,
            trumpIndice,
            players,
            trumpSuit,
            finalBid,
            playerChance,
        ):
            # Detect corruption BEFORE legacy.result crashes
            none_pos = _find_none_positions(players)
            if none_pos:
                raise RuntimeError(f"None already present in players hands: {none_pos}")

            actor = (playerChance + len(s)) % 4

            entry = {
                "actor": actor,
                "leaderIndex_playerChance": playerChance,
                "sLenBefore": len(s),
                "currentSuit": currentSuit,
                "trumpReveal": trumpReveal,
                "chose": chose,
                "finalBid": finalBid,
                "playerTrumpCardId": _safe_card_id(playerTrump),
                "action": (
                    {"type": "bool", "value": a}
                    if isinstance(a, bool)
                    else {"type": "card", "cardId": _safe_card_id(a), "isNone": a is None}
                ),
                "playersHandSizes": [len(players[i]["cards"]) for i in range(4)],
            }
            result_call_log.append(entry)
            if len(result_call_log) > call_log_max:
                result_call_log.pop(0)

            out = orig_result(
                s,
                a,
                currentSuit,
                trumpReveal,
                chose,
                playerTrump,
                trumpPlayed,
                trumpIndice,
                players,
                trumpSuit,
                finalBid,
                playerChance,
            )

            # Detect corruption AFTER result() too
            (
                _cs2,
                _s2,
                _tr2,
                _ch2,
                _pt2,
                _tp2,
                _ti2,
                players2,
                _ts2,
                _fb2,
                _undo,
            ) = out

            none_pos2 = _find_none_positions(players2)
            if none_pos2:
                raise RuntimeError(f"None introduced into players hands: {none_pos2}")

            return out

        if dump_enabled:
            legacy_minimax.result = traced_result

        try:
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
        except Exception as e:
            if dump_enabled:
                dump = {
                    "kind": "rollout_crash_dump",
                    "pid": os.getpid(),
                    "seed": seed,
                    "n": n,
                    "exception": {
                        "type": type(e).__name__,
                        "message": str(e),
                        "traceback": traceback.format_exc(),
                    },
                    "snapshot": snapshot,
                    "simulated": {
                        "simPlayerTrumpCardId": _safe_card_id(sim_player_trump),
                        "simTrumpSuit": sim_trump_suit,
                        "sCardIds": [_safe_card_id(c) for c in s_cards],
                        "playersCardsCardIds": _players_to_cardids(players),
                    },
                    "minimaxCall": {
                        "sCardIds": [_safe_card_id(c) for c in s_cards],
                        "first": True,
                        "secondary": True,
                        "trumpPlayed": trumpPlayed,
                        "trumpIndice": list(trumpIndice),
                        "leaderIndex_playerChance": leaderIndex,
                        "currentSuit": currentSuit,
                        "trumpReveal": trumpReveal,
                        "trumpSuit": sim_trump_suit,
                        "chose": chose,
                        "finalBid": finalBid,
                        "playerTrumpCardId": _safe_card_id(sim_player_trump),
                        "k": k,
                    },
                    "resultCallLogTail": result_call_log,
                }

                fn = f"crash_{int(time.time()*1000)}_pid{os.getpid()}_seed{seed}.json"
                path = _dump_dir_backend_root() / fn
                path.write_text(json.dumps(dump, indent=2), encoding="utf-8")

                # Raise an error that includes the path so the parent can log it
                raise RuntimeError(f"ROLL_OUT_CRASH_DUMP={str(path)}") from e

            raise
        finally:
            legacy_minimax.result = orig_result

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

    bidder_seat = state.finalBid - 1

    # IMPORTANT:
    # - bidder always knows the indicator card if it exists
    # - once trumpReveal is True, indicator identity is public, so include it for everyone
    concealed_id = None
    if state.player_trump is not None:
        if bot_seat == bidder_seat or state.trumpReveal:
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

    try:
        results = await asyncio.gather(*tasks)
    except Exception as e:
        # If worker wrote a dump, surface it in logs and fall back safely.
        msg = str(e)
        if "ROLL_OUT_CRASH_DUMP=" in msg:
            dump_path = msg.split("ROLL_OUT_CRASH_DUMP=", 1)[1].strip()
            try:
                state.event_log.append(f"BOT CRASH DUMP: {dump_path}")
            except Exception:
                pass
            print("BOT CRASH DUMP:", dump_path)
        else:
            print("Bot rollout crashed:", repr(e))

        # Fallback: choose first legal action so the server doesn't die
        if legal.type == "REVEAL_CHOICE":
            return ("REVEAL", {"seatIndex": bot_seat, "reveal": False})
        return ("PLAY", {"seatIndex": bot_seat, "cardId": legal.cardIds[0]})

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