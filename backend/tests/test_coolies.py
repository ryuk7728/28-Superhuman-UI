from __future__ import annotations

import pytest

from app.engine.cards_adapter import from_card_id
from app.engine.play_engine import resolve_if_catch_complete
from app.engine.replay_tracking import (
    award_coolies_for_completed_deal,
    initialize_deal_replay,
)
from app.engine.state import GameState


def _state(*, bidder_seat: int, winner_team: int) -> GameState:
    state = GameState(
        game_id="coolie-test",
        phase="GAME_OVER",
        starting_bidder_index=0,
        bidding_order=[0, 1, 2, 3],
    )
    state.final_bidder_seat = bidder_seat
    state.winnerTeam = winner_team
    return state


@pytest.mark.parametrize(
    ("bidder_seat", "winner_team", "expected"),
    [
        (0, 1, (0, 1)),  # Team 1 called and won: Team 2 gets one.
        (0, 2, (2, 0)),  # Team 1 called and lost: Team 1 gets two.
        (1, 2, (1, 0)),  # Team 2 called and won: Team 1 gets one.
        (1, 1, (0, 2)),  # Team 2 called and lost: Team 2 gets two.
    ],
)
def test_coolie_award_matches_call_result(
    bidder_seat: int, winner_team: int, expected: tuple[int, int]
) -> None:
    state = _state(bidder_seat=bidder_seat, winner_team=winner_team)
    bidder_team = 1 if bidder_seat % 2 == 0 else 2

    award_coolies_for_completed_deal(state, bidder_team=bidder_team)

    assert (state.team1Coolies, state.team2Coolies) == expected
    assert state.coolies_awarded_for_deal is True
    assert state.deal_coolie_award is not None
    assert state.deal_coolie_award["amount"] in (1, 2)


def test_coolies_are_awarded_only_once_for_a_deal() -> None:
    state = _state(bidder_seat=0, winner_team=2)

    award_coolies_for_completed_deal(state, bidder_team=1)
    award_coolies_for_completed_deal(state, bidder_team=1)

    assert state.team1Coolies == 2
    assert state.team2Coolies == 0


def test_new_deal_keeps_totals_and_resets_only_award_marker() -> None:
    state = _state(bidder_seat=0, winner_team=1)
    state.team1Coolies = 3
    state.team2Coolies = 4
    award_coolies_for_completed_deal(state, bidder_team=1)

    initialize_deal_replay(state, increment_deal=True)

    assert state.deal_number == 2
    assert state.team1Coolies == 3
    assert state.team2Coolies == 5
    assert state.coolies_awarded_for_deal is False
    assert state.deal_coolie_award is None


def test_public_state_exposes_team_coolies() -> None:
    state = _state(bidder_seat=1, winner_team=1)
    award_coolies_for_completed_deal(state, bidder_team=2)

    play = state.to_public_dict()["play"]
    assert play["team1Coolies"] == 0
    assert play["team2Coolies"] == 2
    assert play["dealCoolieAward"] == {
        "team": 2,
        "amount": 2,
        "reason": "caller_lost",
    }


def test_finishing_eighth_catch_awards_coolies(monkeypatch: pytest.MonkeyPatch) -> None:
    state = GameState(
        game_id="coolie-finish",
        phase="PLAY",
        starting_bidder_index=0,
        bidding_order=[0, 1, 2, 3],
    )
    state.final_bidder_seat = 0
    state.final_bid_value = 14
    state.finalBid = 1
    state.finalBidValue = 14
    state.catchNumber = 8
    state.leaderIndex = 0
    state.team1Points = 10
    state.team2Points = 8
    state.s = [
        from_card_id("Hearts_Seven"),
        from_card_id("Hearts_Eight"),
        from_card_id("Hearts_Queen"),
        from_card_id("Hearts_King"),
    ]
    state.play_players = [
        {"team": 1, "cards": []},
        {"team": 2, "cards": []},
        {"team": 1, "cards": []},
        {"team": 2, "cards": []},
    ]
    monkeypatch.setattr(
        "app.engine.play_engine.legacy_minimax.checkwin_extended",
        lambda *_args: (0, 5),
    )
    monkeypatch.setattr(
        "app.engine.play_engine.legacy_minimax.reset",
        lambda *_args: ("", [], False, [0, 0, 0, 0], False),
    )

    resolve_if_catch_complete(state)

    assert state.phase == "GAME_OVER"
    assert state.winnerTeam == 1
    assert state.team1Points == 15
    assert (state.team1Coolies, state.team2Coolies) == (0, 1)
