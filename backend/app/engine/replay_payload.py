from __future__ import annotations

from typing import Any

from app.engine.cards_adapter import to_card_id
from app.engine.legal_actions import get_legal_actions
from app.engine.replay_tracking import all_effective_hands


def _completed_catches(state) -> list[dict[str, Any]]:
    return [
        {
            "catchNumber": item["catchNumber"],
            "leaderSeatIndex": item["leaderSeatIndex"],
            "plays": [
                {
                    "seatIndex": play["seatIndex"],
                    "cardId": to_card_id(play["card"]),
                    "wasTrump": bool(play["wasTrump"]),
                }
                for play in item["plays"]
            ],
            "winnerSeatIndex": item["winnerSeatIndex"],
            "winnerTeam": item["winnerTeam"],
            "points": item["points"],
        }
        for item in state.completed_catches
    ]


def build_replay_payload(state, *, room_code: str) -> dict[str, Any]:
    bidder = state.final_bidder_seat
    caller_first4 = (
        list(state.initial_first4_card_ids[bidder])
        if bidder is not None and bidder < len(state.initial_first4_card_ids)
        else []
    )
    current_trick = [
        {
            "seatIndex": (state.leaderIndex + offset) % 4,
            "cardId": to_card_id(card),
            "wasTrump": bool(
                offset < len(state.trumpIndice) and state.trumpIndice[offset] == 1
            ),
        }
        for offset, card in enumerate(state.s)
    ]
    status = (
        "aborted"
        if state.phase == "GAME_OVER" and state.winnerTeam == -1
        else ("completed" if state.phase == "GAME_OVER" else "live")
    )
    return {
        "schemaVersion": 1,
        "replayId": f"{room_code.upper()}-{state.deal_number:04d}",
        "roomCode": room_code.upper(),
        "joinCode": room_code.upper(),
        "gameId": state.game_id,
        "dealNumber": state.deal_number,
        "status": status,
        "phase": state.phase,
        "revision": state.replay_revision,
        "startedAtEpochMs": state.deal_started_at_epoch_ms,
        "updatedAtEpochMs": __import__("time").time_ns() // 1_000_000,
        "completedAtEpochMs": state.deal_completed_at_epoch_ms,
        "playerNames": list(state.player_names),
        "seatTypes": list(state.seat_types),
        "startingBidderIndex": state.starting_bidder_index,
        "biddingOrder": list(state.bidding_order),
        "round1BidderSeat": state.round1_bidder_seat,
        "round1BidValue": state.round1_bid_value,
        "finalBidderSeat": bidder,
        "finalBidValue": state.final_bid_value,
        "callerFirst4CardIds": caller_first4,
        "initialFirst4Hands": [list(hand) for hand in state.initial_first4_card_ids],
        "initialFullHands": [list(hand) for hand in state.initial_full_hand_card_ids],
        "selectedTrumpCardId": (
            state.trump_selection_history[-1]["selectedCardId"]
            if state.trump_selection_history
            else (to_card_id(state.player_trump) if state.player_trump is not None else None)
        ),
        "trumpSuit": state.trumpSuit,
        "trumpRevealed": bool(state.trumpReveal),
        "bidHistory": list(state.bid_history),
        "trumpSelectionHistory": list(state.trump_selection_history),
        "revealHistory": list(state.reveal_history),
        "playHistory": list(state.play_history),
        "completedCatches": _completed_catches(state),
        "currentCatchNumber": state.catchNumber,
        "currentLeaderSeatIndex": state.leaderIndex,
        "currentTrick": current_trick,
        "currentHands": all_effective_hands(state),
        "currentLegalActions": get_legal_actions(state),
        "team1Points": state.team1Points,
        "team2Points": state.team2Points,
        "winnerTeam": state.winnerTeam,
        "botBiddingPolicy": state.bot_bidding_policy.to_public_dict(),
        "botKPolicy": (state.bot_k_policy).to_public_dict() if state.bot_k_policy else None,
        "botThinkTimeSeconds": state.bot_think_timeout_seconds,
        "eventLog": list(state.event_log),
    }
