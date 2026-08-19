from __future__ import annotations

import time
from typing import Any

from app.engine.cards_adapter import to_card_id


def now_epoch_ms() -> int:
    return int(time.time() * 1000)


def effective_hand_card_ids(state, seat_index: int) -> list[str]:
    """Return every card the seat can still own, including concealed trump."""
    cards = [to_card_id(card) for card in state.players_cards[seat_index]]
    if (
        state.final_bidder_seat == seat_index
        and state.player_trump is not None
        and to_card_id(state.player_trump) not in cards
    ):
        cards.append(to_card_id(state.player_trump))
    return cards


def all_effective_hands(state) -> list[list[str]]:
    return [effective_hand_card_ids(state, seat) for seat in range(4)]


def initialize_deal_replay(state, *, increment_deal: bool = False) -> None:
    if increment_deal:
        state.deal_number += 1
    state.deal_started_at_epoch_ms = now_epoch_ms()
    state.deal_completed_at_epoch_ms = None
    state.initial_first4_card_ids = [
        [to_card_id(card) for card in hand] for hand in state.players_cards
    ]
    state.initial_full_hand_card_ids = [[], [], [], []]
    state.bid_history = []
    state.trump_selection_history = []
    state.reveal_history = []
    state.play_history = []
    state.completed_catches = []
    state.replay_revision += 1


def capture_full_hands(state) -> None:
    state.initial_full_hand_card_ids = all_effective_hands(state)
    state.replay_revision += 1


def record_bid(
    state,
    *,
    round_number: int,
    seat_index: int,
    bid_value: int,
    bid_position: int,
    min_bid_exclusive: int,
    max_bid_inclusive: int,
    can_pass: bool,
    can_redeal: bool = False,
) -> None:
    state.bid_history.append(
        {
            "sequence": len(state.bid_history) + 1,
            "round": round_number,
            "seatIndex": seat_index,
            "bidPosition": bid_position,
            "bidValue": bid_value,
            "action": "redeal" if bid_value == -1 else ("pass" if bid_value == 0 else "bid"),
            "minBidExclusive": min_bid_exclusive,
            "maxBidInclusive": max_bid_inclusive,
            "canPass": can_pass,
            "canRedeal": can_redeal,
            "handCardIds": effective_hand_card_ids(state, seat_index),
            "atEpochMs": now_epoch_ms(),
        }
    )
    state.replay_revision += 1


def record_trump_selection(state, *, seat_index: int, card_id: str, round_number: int) -> None:
    state.trump_selection_history.append(
        {
            "sequence": len(state.trump_selection_history) + 1,
            "round": round_number,
            "seatIndex": seat_index,
            "selectedCardId": card_id,
            "handBeforeCardIds": effective_hand_card_ids(state, seat_index),
            "atEpochMs": now_epoch_ms(),
        }
    )
    state.replay_revision += 1


def mark_deal_completed(state) -> None:
    if state.deal_completed_at_epoch_ms is None:
        state.deal_completed_at_epoch_ms = now_epoch_ms()
        state.replay_revision += 1


def card_play_context(state, *, seat_index: int, legal_card_ids: list[str]) -> dict[str, Any]:
    return {
        "sequence": len(state.play_history) + 1,
        "catchNumber": state.catchNumber,
        "playNumberInCatch": len(state.s) + 1,
        "seatIndex": seat_index,
        "leaderSeatIndex": state.leaderIndex,
        "selectedCardId": None,
        "legalCardIds": list(legal_card_ids),
        "allHandsBeforeCardIds": all_effective_hands(state),
        "handBeforeCardIds": effective_hand_card_ids(state, seat_index),
        "trickBeforeCardIds": [to_card_id(card) for card in state.s],
        "ledSuit": state.currentSuit or None,
        "trumpWasRevealed": bool(state.trumpReveal),
        "trumpSuit": state.trumpSuit,
        "atEpochMs": now_epoch_ms(),
    }
