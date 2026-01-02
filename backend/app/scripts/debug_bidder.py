from __future__ import annotations

import copy
from concurrent.futures import ProcessPoolExecutor

from app.bots.rollout_bot import rollout_worker
from app.engine.cards_adapter import from_card_id, to_card_id
from app.legacy import minimax as legacy


# ----------------------------
# Exact cards you provided
# ----------------------------

# Player 1 (Team 1) — Bidder (seat 0)
# NOTE: Queen of Hearts is the concealed trump indicator, NOT in bidder's hand.
P1_HAND = [
    "Clubs_Jack",
    "Hearts_King",
    "Clubs_Eight",
    "Clubs_Ace",
    "Hearts_Seven",
    "Hearts_Eight",
    "Clubs_Nine",
]
CONCEALED_TRUMP = "Hearts_Queen"  # indicator outside hand

# Player 2 (seat 1)
P2_FULL = [
    "Hearts_Jack",
    "Clubs_Seven",
    "Hearts_Ace",
    "Hearts_Ten",
    "Spades_Queen",
    "Spades_Eight",
    "Spades_Seven",
    "Spades_Ace",
]

# Player 3 (seat 2)
P3_FULL = [
    "Diamonds_Jack",
    "Clubs_Ten",
    "Clubs_King",
    "Clubs_Queen",
    "Spades_Ten",
    "Diamonds_Nine",
    "Diamonds_Ten",
    "Hearts_Nine",
]

# Player 4 (seat 3) — will lead Spades_Jack (played)
P4_FULL = [
    "Spades_Jack",
    "Spades_Nine",
    "Diamonds_King",
    "Diamonds_Queen",
    "Spades_King",
    "Diamonds_Ace",
    "Diamonds_Eight",
    "Diamonds_Seven",
]


# ----------------------------
# Repro position
# ----------------------------

LEADER_INDEX = 3  # P4 starts the catch
S_CARD_IDS = ["Spades_Jack"]  # P4 leads Jack of Spades
CURRENT_SUIT = "Spades"

FINAL_BID = 1  # bidder is P1 (1-indexed), seat 0
BIDDER_SEAT = 0

TRUMP_REVEAL = False
CHOSE = False
TRUMP_PLAYED = False
TRUMP_INDICE = [0, 0, 0, 0]


def _assert_unique_32():
    all_ids = (
        P1_HAND
        + [CONCEALED_TRUMP]
        + P2_FULL
        + P3_FULL
        + P4_FULL
    )
    if len(all_ids) != 32:
        raise RuntimeError(f"Expected 32 ids, got {len(all_ids)}")

    if len(set(all_ids)) != 32:
        raise RuntimeError("Duplicate cardIds found in provided hands.")


def _hand_sizes_after_p4_lead() -> list[int]:
    # P4 played one card already, so they have 7 left.
    # P1 has 7 because indicator is outside hand.
    return [7, 8, 8, 7]


def build_snapshot() -> dict:
    _assert_unique_32()
    return {
        "botSeat": 0,
        "finalBid": FINAL_BID,
        "bidderSeat": BIDDER_SEAT,
        "leaderIndex": LEADER_INDEX,
        "catchNumber": 1,
        "k": 2,
        "trumpReveal": TRUMP_REVEAL,
        "knownTrumpSuit": None,
        "chose": CHOSE,
        "currentSuit": CURRENT_SUIT,
        "trumpPlayed": TRUMP_PLAYED,
        "trumpIndice": list(TRUMP_INDICE),
        "sCardIds": list(S_CARD_IDS),
        "botHandCardIds": list(P1_HAND),
        "handSizes": _hand_sizes_after_p4_lead(),
        "playedCardIds": list(S_CARD_IDS),
        # bidder knows the concealed indicator card:
        "concealedTrumpCardId": CONCEALED_TRUMP,
    }


def sanity_check_legacy_actions_with_full_real_hands():
    """
    This does NOT run rollouts.
    It just verifies that at this position, legacy.actions says P1 has reveal choice.
    """
    p1 = [from_card_id(cid) for cid in P1_HAND]
    p2 = [from_card_id(cid) for cid in P2_FULL]
    p3 = [from_card_id(cid) for cid in P3_FULL]
    # P4 has played Spades_Jack, so remove it from their remaining hand
    p4_remaining = [cid for cid in P4_FULL if cid != "Spades_Jack"]
    p4 = [from_card_id(cid) for cid in p4_remaining]

    player_trump = from_card_id(CONCEALED_TRUMP)
    trump_suit = player_trump.suit

    players = []
    for i, hand in enumerate([p1, p2, p3, p4]):
        players.append(
            {
                "cards": hand,
                "isTrump": i == BIDDER_SEAT,
                "team": 1 if i % 2 == 0 else 2,
                "trump": player_trump if i == BIDDER_SEAT else None,
            }
        )

    s = [from_card_id("Spades_Jack")]
    acts = legacy.actions(
        s,
        players,
        TRUMP_REVEAL,
        trump_suit,
        CURRENT_SUIT,
        CHOSE,
        FINAL_BID,
        player_trump,
        TRUMP_PLAYED,
        list(TRUMP_INDICE),
        -1,
        LEADER_INDEX,
    )
    print("[Sanity] legacy.actions at P1 turn returned:", acts)


def run_in_process_rollouts(n: int, seed: int):
    """
    Runs the SAME rollout_worker (same code used by multiprocessing),
    but directly in-process so VS Code breakpoints work in:
      - app/bots/rollout_bot.py
      - app/legacy/minimax.py
    """
    snap = build_snapshot()
    print("\n=== In-process rollout_worker ===")
    print("n =", n, "seed =", seed)
    print("snapshot =", snap)

    # Put a breakpoint on the next line to step into rollout_worker
    counts = rollout_worker(snap, n=n, seed=seed)
    print("counts =", counts)


def find_crashing_seed(max_seed: int = 20000):
    """
    If your bug is seed-dependent, this finds a seed that crashes with n=1.
    Once found, re-run run_in_process_rollouts(n=1, seed=<seed>) and step through.
    """
    snap = build_snapshot()
    print("\n=== Searching for a crashing seed (n=1) ===")
    for seed in range(max_seed):
        print(seed)
        try:
            rollout_worker(snap, n=1, seed=seed)
        except Exception as e:
            print("\n✅ Found crashing seed:", seed)
            print("Exception:", repr(e))
            return seed
    print("\n❌ No crash found up to seed", max_seed)
    return None


def confirm_no_state_sharing_via_pool(n: int, seed: int):
    """
    Runs the same function in a subprocess pool (max_workers=1) to demonstrate
    isolation. You generally won't step into this, but it proves 'no state sharing'.
    """
    snap = build_snapshot()
    snap_before = copy.deepcopy(snap)

    print("\n=== ProcessPoolExecutor (1 worker) ===")
    with ProcessPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(rollout_worker, snap, n, seed)
        counts = fut.result()
        print("pool counts =", counts)

    print("snapshot unchanged:", snap == snap_before)


def main():
    sanity_check_legacy_actions_with_full_real_hands()

    # Option A: run like frontend (many rollouts) but in-process for debugging
    # Set breakpoints in rollout_worker and legacy.minimax.{actions,result,undo_result}
    # run_in_process_rollouts(n=10, seed=0)

    # Option B: if it doesn't crash with seed=0, find a crashing seed with n=1
    seed = find_crashing_seed(20)
    if seed:
        run_in_process_rollouts(n=1, seed=seed)
        confirm_no_state_sharing_via_pool(n=1, seed=seed)


if __name__ == "__main__":
    main()