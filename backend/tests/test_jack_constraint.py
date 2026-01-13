import pytest

import app.bots.rollout_bot as rb
from app.engine.cards_adapter import to_card_id
from app.settings import Settings


def _count_card(players, card_id: str) -> list[int]:
    counts = []
    for seat in range(4):
        seat_cards = [to_card_id(c) for c in players[seat]["cards"]]
        counts.append(seat_cards.count(card_id))
    return counts


def test_case1_first_time_spades_jack_forced_to_p4_after_actor(monkeypatch) -> None:
    """
    Case 1 (First time Spades being played in the game; within current trick
    everyone followed led suit so far).

    Seats: 0=P1 (bidder), 1=P2, 2=P3 (bot), 3=P4
    Trump: bidder has concealed indicator Clubs_Ten (P1 bid 14).
    Current trick:
      seat0 played Spades_Eight
      seat1 played Spades_Ten
      actor is seat2 (bot)

    After actor (seat2), only seat3 remains in this trick.
    The heuristic must force Spades_Jack into seat3 for every rollout.
    """

    rb.settings = Settings(
        debug=True,
        rollouts=500,
        workers=20,
        rollout_deal_retries=30,
        max_concurrent_bot_thinking=1,
        k_override=None,
        cors_origins=("http://localhost:5173", "http://127.0.0.1:5173"),
    )

    bot_seat = 2
    bidder_seat = 0
    jack_id = "Spades_Jack"

    snapshot = {
        "botSeat": bot_seat,
        "finalBid": bidder_seat + 1,
        "bidderSeat": bidder_seat,
        "leaderIndex": 0,
        "catchNumber": 1,
        "k": 1,
        # Keep trump revealed to avoid "sample a random trump from pool" noise.
        "trumpReveal": True,
        "knownTrumpSuit": "Clubs",
        "chose": False,
        "currentSuit": "Spades",
        "trumpPlayed": False,
        "trumpIndice": [0, 0, 0, 0],
        "sCardIds": ["Spades_Eight", "Spades_Ten"],
        "playedCardIds": ["Spades_Eight", "Spades_Ten"],
        # P1 (bidder) chose concealed trump indicator = Ten of Clubs
        "concealedTrumpCardId": "Clubs_Ten",
        # Bot hand: exactly 8 cards, includes only King+Nine of spades (no Jack)
        "botHandCardIds": [
            "Spades_King",
            "Spades_Nine",
            "Hearts_Ace",
            "Hearts_Seven",
            "Diamonds_Ace",
            "Diamonds_Seven",
            "Clubs_Ace",
            "Clubs_Seven",
        ],
        # Remaining cards in hands at this moment:
        # seat0 played 1 => 7 (and should include trump indicator in revealed world)
        # seat1 played 1 => 7
        # seat2 (bot) not played => 8
        # seat3 not played => 8
        "handSizes": [7, 7, 8, 8],
        "suitMatrix": [[1, 1, 1, 1] for _ in range(4)],
    }

    calls = {"n": 0}

    def fake_minimax_extended(*args, **kwargs):
        players = args[7]
        reward_distribution = args[15]

        counts = _count_card(players, jack_id)

        # Must be in seat3 only
        assert counts == [0, 0, 0, 1], (
            f"Expected {jack_id} forced to seat3 only, got counts={counts}"
        )

        calls["n"] += 1
        reward_distribution.append((True, 0.0))
        return 0.0

    monkeypatch.setattr(rb.legacy_minimax, "minimax_extended", fake_minimax_extended)

    out = rb.rollout_worker(snapshot=snapshot, n=30, seed=123)
    assert calls["n"] == 30
    assert out.get(True) == 30


def test_case2_first_time_hearts_jack_not_in_p2_must_be_p1_or_p4(monkeypatch) -> None:
    """
    Case 2 (First time Hearts being played in the game; within current trick
    everyone followed led suit so far).

    Current trick:
      seat1 (P2) played Hearts_King
      actor is seat2 (P3 bot)

    Remaining after actor (seat2) are seats [3, 0] in that order.
    The heuristic must force Hearts_Jack into either seat3 or seat0,
    and specifically NOT into seat1 (already played) nor seat2 (bot hand).
    """

    rb.settings = Settings(
        debug=True,
        rollouts=500,
        workers=20,
        rollout_deal_retries=30,
        max_concurrent_bot_thinking=1,
        k_override=None,
        cors_origins=("http://localhost:5173", "http://127.0.0.1:5173"),
    )

    bot_seat = 2
    bidder_seat = 0
    jack_id = "Hearts_Jack"

    snapshot = {
        "botSeat": bot_seat,
        "finalBid": bidder_seat + 1,
        "bidderSeat": bidder_seat,
        "leaderIndex": 1,
        "catchNumber": 1,
        "k": 1,
        "trumpReveal": True,
        "knownTrumpSuit": "Clubs",
        "chose": False,
        "currentSuit": "Hearts",
        "trumpPlayed": False,
        "trumpIndice": [0, 0, 0, 0],
        "sCardIds": ["Hearts_King"],
        "playedCardIds": ["Hearts_King"],
        "concealedTrumpCardId": "Clubs_Ten",
        # Bot hand: exactly 8 cards, includes only Ace+Eight of hearts (no Jack)
        "botHandCardIds": [
            "Hearts_Ace",
            "Hearts_Eight",
            "Spades_Ace",
            "Spades_Seven",
            "Diamonds_Ace",
            "Diamonds_Seven",
            "Clubs_Ace",
            "Clubs_Seven",
        ],
        # seat1 played 1 => 7, others 8
        "handSizes": [8, 7, 8, 8],
        "suitMatrix": [[1, 1, 1, 1] for _ in range(4)],
    }

    calls = {"n": 0}

    def fake_minimax_extended(*args, **kwargs):
        players = args[7]
        reward_distribution = args[15]

        counts = _count_card(players, jack_id)

        # Must appear exactly once total
        assert sum(counts) == 1, (
            f"Expected exactly one {jack_id} across all hands, got counts={counts}"
        )

        # Must NOT be in seat1 (already played) or seat2 (actor/bot)
        assert counts[1] == 0, (
            f"Expected {jack_id} not in seat1 (already played), got counts={counts}"
        )
        assert counts[2] == 0, (
            f"Expected {jack_id} not in seat2 (bot), got counts={counts}"
        )

        # Must be in seat0 or seat3
        assert counts[0] + counts[3] == 1, (
            f"Expected {jack_id} in seat0 or seat3, got counts={counts}"
        )

        calls["n"] += 1
        reward_distribution.append((True, 0.0))
        return 0.0

    monkeypatch.setattr(rb.legacy_minimax, "minimax_extended", fake_minimax_extended)

    # Use a higher n to make it essentially impossible to pass if the heuristic
    # were not applied (since without it, Hearts_Jack would land in seat1 often).
    out = rb.rollout_worker(snapshot=snapshot, n=80, seed=456)
    assert calls["n"] == 80
    assert out.get(True) == 80


def test_case3_second_time_spades_heuristic_not_applied_jack_stays_in_pool(
    monkeypatch,
) -> None:
    """
    Case 3:
      Trick 1 already had Spades played (first time).
      Trick 2 is Spades again (second time), so heuristic must NOT apply.

    We verify "not applied" by wrapping _deal_unknown_with_suit_constraints and
    asserting that Spades_Jack is still present in pool_ids at dealing time.

    Note: To make actor==bot_seat for the heuristic check, we set leaderIndex=3
    with sCardIds length=1 so actor is seat0.
    """

    rb.settings = Settings(
        debug=True,
        rollouts=500,
        workers=20,
        rollout_deal_retries=30,
        max_concurrent_bot_thinking=1,
        k_override=None,
        cors_origins=("http://localhost:5173", "http://127.0.0.1:5173"),
    )

    bot_seat = 0  # P1 bidder bot in this test
    bidder_seat = 0
    jack_id = "Spades_Jack"

    # Spades already appeared in prior trick:
    prior_spades = ["Spades_Eight", "Spades_Ace", "Spades_King", "Spades_Queen"]

    # Current trick (second time spades):
    # leaderIndex=3 played Spades_Seven, actor now seat0
    s_card_ids = ["Spades_Seven"]

    snapshot = {
        "botSeat": bot_seat,
        "finalBid": bidder_seat + 1,
        "bidderSeat": bidder_seat,
        "leaderIndex": 3,
        "catchNumber": 2,
        "k": 1,
        # Keep trump unrevealed here; bot is bidder so no random trump sampling.
        "trumpReveal": False,
        "knownTrumpSuit": None,
        "chose": False,
        "currentSuit": "Spades",
        "trumpPlayed": False,
        "trumpIndice": [0, 0, 0, 0],
        "sCardIds": s_card_ids,
        "playedCardIds": prior_spades + s_card_ids,
        "concealedTrumpCardId": "Clubs_Ten",
        # Bidder/bot hand should exclude concealed trump indicator (so 7 cards)
        "botHandCardIds": [
            "Hearts_Nine",
            "Hearts_Ace",
            "Hearts_Jack",
            "Diamonds_Nine",
            "Diamonds_Jack",
            "Clubs_Ace",
            "Clubs_Queen",
        ],
        # Total consistency:
        # bot has 7 + concealed 1 + played 5 => 13 known, pool 19
        # others needs sum to 19
        "handSizes": [7, 6, 6, 7],
        "suitMatrix": [[1, 1, 1, 1] for _ in range(4)],
    }

    # Wrap the deal function to assert the Jack is still in pool when dealing starts
    orig_deal = rb._deal_unknown_with_suit_constraints

    def wrapped_deal(*, rng, pool_ids, seats_to_fill, hand_sizes, suit_matrix):
        assert jack_id in pool_ids, (
            f"Expected {jack_id} to remain in pool_ids because Spades is not "
            f"first-time suit anymore. pool_ids sample={pool_ids[:20]}"
        )
        return orig_deal(
            rng=rng,
            pool_ids=pool_ids,
            seats_to_fill=seats_to_fill,
            hand_sizes=hand_sizes,
            suit_matrix=suit_matrix,
        )

    monkeypatch.setattr(rb, "_deal_unknown_with_suit_constraints", wrapped_deal)

    # Stub minimax to keep test fast
    def fake_minimax_extended(*args, **kwargs):
        reward_distribution = args[15]
        reward_distribution.append((True, 0.0))
        return 0.0

    monkeypatch.setattr(rb.legacy_minimax, "minimax_extended", fake_minimax_extended)

    out = rb.rollout_worker(snapshot=snapshot, n=25, seed=789)
    assert out.get(True) == 25