import pytest

import app.bots.rollout_bot as rb
from app.engine.cards_adapter import to_card_id
from app.settings import Settings


def test_rollout_worker_fixes_revealed_trump_indicator_into_bidder_hand(
    monkeypatch,
) -> None:
    """
    Tests the rollout_worker feature:

    Scenario (real-game narrative):
      - P2 (seat 1) is bidder, bid=14, concealed indicator = King of Hearts.
      - P2 leads Jack of Diamonds.
      - P3 is void in Diamonds, reveals trump (True), and plays Eight of Hearts.
      - P4 follows Diamonds with Eight of Diamonds.
      - Now it's P1's turn. P1 is a non-bidder bot doing rollouts.

    Assertion (rollout-time requirement):
      If trumpReveal=True and bot is non-bidder and indicator not played,
      then every rollout simulation must have:
        - Hearts_King present in bidder's simulated hand (seat 1) exactly once
        - Hearts_King absent from all other simulated hands
        - simulated hand lengths match the snapshot handSizes
          (with the bidder effectively getting the indicator + one fewer unknown)

    We verify this by monkeypatching legacy_minimax.minimax_extended and inspecting
    the `players` argument constructed by rollout_worker before it calls minimax.
    """

    bot_seat = 0  # P1 (bot in your system)
    bidder_seat = 1  # P2
    indicator_cid = "Hearts_King"

    # Configure rollout_bot settings used by rollout_worker (for retries).
    # (Not strictly necessary, but keeps behavior stable.)
    rb.settings = Settings(
        debug=True,
        rollouts=500,
        workers=20,
        rollout_deal_retries=30,
        max_concurrent_bot_thinking=1,
        k_override=None,
        cors_origins=("http://localhost:5173", "http://127.0.0.1:5173"),
    )

    # Snapshot at the moment right before P1 plays to the current trick.
    # Trick so far (leaderIndex=1):
    #   seat1: Diamonds_Jack
    #   seat2: Hearts_Eight  (trump cut after reveal)
    #   seat3: Diamonds_Eight
    # Actor now: (leaderIndex + len(s)) % 4 = (1 + 3) % 4 = 0 => P1.
    snapshot = {
        "botSeat": bot_seat,
        "finalBid": bidder_seat + 1,  # legacy expects 1-indexed bidder seat
        "bidderSeat": bidder_seat,
        "leaderIndex": 1,
        "catchNumber": 1,
        "k": 1,
        "trumpReveal": True,
        "knownTrumpSuit": "Hearts",
        "chose": False,
        "currentSuit": "Diamonds",
        "trumpPlayed": True,
        "trumpIndice": [0, 1, 0, 0],
        "sCardIds": ["Diamonds_Jack", "Hearts_Eight", "Diamonds_Eight"],
        "playedCardIds": ["Diamonds_Jack", "Hearts_Eight", "Diamonds_Eight"],
        "concealedTrumpCardId": indicator_cid,
        # Bot's known hand (P1's full hand, since P1 hasn't played yet)
        "botHandCardIds": [
            "Hearts_Nine",
            "Clubs_Ten",
            "Clubs_Ace",
            "Spades_Ten",
            "Clubs_Jack",
            "Clubs_Queen",
            "Hearts_Seven",
            "Diamonds_Nine",
        ],
        # Remaining hand sizes at this exact moment:
        # P1: 8 (hasn't played yet)
        # P2: 7 (played Diamonds_Jack; also has Hearts_King as the revealed indicator)
        # P3: 7 (played Hearts_Eight)
        # P4: 7 (played Diamonds_Eight)
        "handSizes": [8, 7, 7, 7],
        "suitMatrix": [[1, 1, 1, 1] for _ in range(4)],
    }

    seen_calls = {"n": 0}

    orig_minimax_extended = rb.legacy_minimax.minimax_extended

    def fake_minimax_extended(*args, **kwargs):
        """
        rollout_worker calls:
          minimax_extended(
              s_cards[:], True, True, trumpPlayed, s_cards[:], trumpIndice[:],
              leaderIndex, players, currentSuit, trumpReveal, sim_trump_suit,
              chose, finalBid, sim_player_trump, -1, reward_distribution,
              0, 0, k
          )
        So:
          players is args[7]
          trumpReveal is args[9]
          trumpSuit is args[10]
          finalBid is args[12]
          playerTrump is args[13]
          reward_distribution is args[15]
        """
        players = args[7]
        tr = args[9]
        ts = args[10]
        final_bid_1idx = args[12]
        player_trump_obj = args[13]
        reward_distribution = args[15]

        assert tr is True
        assert ts == "Hearts"
        assert final_bid_1idx == bidder_seat + 1

        # The indicator card object passed as playerTrump should match Hearts_King
        assert player_trump_obj is not None
        assert to_card_id(player_trump_obj) == indicator_cid

        # Validate simulated hand sizes (after fixing indicator into bidder)
        assert len(players[0]["cards"]) == 8
        assert len(players[1]["cards"]) == 7
        assert len(players[2]["cards"]) == 7
        assert len(players[3]["cards"]) == 7

        # Validate indicator placement: ONLY in bidder hand, exactly once
        counts = []
        for seat in range(4):
            seat_cards = [to_card_id(c) for c in players[seat]["cards"]]
            counts.append(seat_cards.count(indicator_cid))

        assert counts[bidder_seat] == 1, (
            f"Expected {indicator_cid} fixed in bidder seat {bidder_seat} hand "
            f"exactly once, got counts={counts}"
        )
        for seat in range(4):
            if seat == bidder_seat:
                continue
            assert counts[seat] == 0, (
                f"Expected {indicator_cid} NOT in seat {seat} hand, got counts={counts}"
            )

        seen_calls["n"] += 1

        # Provide a trivial best action so rollout_worker can finish cleanly
        reward_distribution.append((True, 0.0))
        return 0.0

    monkeypatch.setattr(rb.legacy_minimax, "minimax_extended", fake_minimax_extended)

    try:
        out = rb.rollout_worker(snapshot=snapshot, n=25, seed=123)
    finally:
        # Not strictly needed because monkeypatch fixture undoes,
        # but keeping explicit restoration makes intent clear.
        rb.legacy_minimax.minimax_extended = orig_minimax_extended

    assert seen_calls["n"] == 25, "Expected one minimax call per rollout iteration"
    assert out.get(True) == 25