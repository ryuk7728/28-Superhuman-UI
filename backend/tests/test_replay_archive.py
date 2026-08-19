from __future__ import annotations

from fastapi.testclient import TestClient

from app.engine.cards_adapter import from_card_id
from app.engine.game_manager import game_manager
from app.engine.play_engine import apply_play_card, init_play_state
from app.engine.replay_payload import build_replay_payload
from app.engine.replay_store import replay_store
from app.engine.room_manager import room_manager
from app.engine.state import GameState
from app.engine.state_storage import game_state_from_storage_dict, game_state_to_storage_dict
from app.main import app


def _play_state() -> GameState:
    state = GameState(
        game_id="replay-options",
        phase="PLAY",
        starting_bidder_index=0,
        bidding_order=[0, 1, 2, 3],
        players_cards=[
            [from_card_id("Hearts_Ace"), from_card_id("Clubs_Seven")],
            [from_card_id("Hearts_Seven"), from_card_id("Clubs_Ace")],
            [from_card_id("Diamonds_Ace")],
            [from_card_id("Hearts_Nine")],
        ],
        player_names=["Alpha", "Beta", "Gamma", "Delta"],
    )
    state.final_bidder_seat = 2
    state.final_bid_value = 14
    state.player_trump = from_card_id("Spades_Seven")
    init_play_state(state)
    return state


def test_card_play_records_exact_legal_options_and_every_hand_before_play() -> None:
    state = _play_state()

    apply_play_card(state, 0, "Hearts_Ace")
    first = state.play_history[0]
    assert set(first["legalCardIds"]) == {"Hearts_Ace", "Clubs_Seven"}
    assert first["selectedCardId"] == "Hearts_Ace"
    assert first["allHandsBeforeCardIds"][0] == ["Hearts_Ace", "Clubs_Seven"]
    assert set(first["allHandsBeforeCardIds"][2]) == {
        "Diamonds_Ace",
        "Spades_Seven",
    }

    apply_play_card(state, 1, "Hearts_Seven")
    second = state.play_history[1]
    assert second["legalCardIds"] == ["Hearts_Seven"]
    assert second["handBeforeCardIds"] == ["Hearts_Seven", "Clubs_Ace"]
    assert second["trickBeforeCardIds"] == ["Hearts_Ace"]


def test_stored_game_state_round_trip_preserves_cards_and_shared_play_hands() -> None:
    state = _play_state()
    apply_play_card(state, 0, "Hearts_Ace")

    restored = game_state_from_storage_dict(game_state_to_storage_dict(state))

    assert restored.game_id == state.game_id
    assert restored.play_history == state.play_history
    assert restored.players_cards[1][0].identity() == "Seven of Hearts"
    assert restored.play_players[1]["cards"] is restored.players_cards[1]
    assert restored.play_players[2]["trump"] is restored.player_trump


def test_password_protected_replay_api_returns_full_audit() -> None:
    replay_store.clear_memory()
    state = _play_state()
    state.room_code = "BANANA"
    state.initial_first4_card_ids = [
        ["Hearts_Ace", "Clubs_Seven"],
        ["Hearts_Seven", "Clubs_Ace"],
        ["Diamonds_Ace", "Spades_Seven"],
        ["Hearts_Nine"],
    ]
    apply_play_card(state, 0, "Hearts_Ace")
    replay = build_replay_payload(state, room_code="BANANA")
    replay_store.save(
        session={"roomCode": "BANANA", "gameId": state.game_id},
        replay=replay,
        state_storage=game_state_to_storage_dict(state),
    )

    with TestClient(app) as client:
        assert client.get("/replays/BANANA").status_code == 401
        assert client.get(
            "/replays/BANANA", headers={"X-Replay-Password": "wrong"}
        ).status_code == 401
        response = client.get(
            "/replays/BANANA", headers={"X-Replay-Password": "banana123"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["joinCode"] == "BANANA"
        assert body["playHistory"][0]["legalCardIds"] == [
            "Hearts_Ace",
            "Clubs_Seven",
        ]
        assert len(body["playHistory"][0]["allHandsBeforeCardIds"]) == 4


def test_original_code_and_name_restore_same_seat_after_rematch_and_process_loss() -> None:
    replay_store.clear_memory()
    alice = room_manager.create_room(player_name="Alice", starting_bidder_index=0)
    bob = room_manager.join_room(room_code=alice.room_code, player_name="Bob")
    assert bob.game_id
    state = game_manager.get_game(bob.game_id)
    assert state is not None
    state.phase = "GAME_OVER"
    state.winnerTeam = 2
    room_manager.persist_state(room_code=alice.room_code, state=state)

    room_manager.request_rematch(room_code=alice.room_code, player_token=alice.player_token)
    room_manager.request_rematch(room_code=alice.room_code, player_token=bob.player_token)
    assert state.deal_number == 2
    room_manager.persist_state(room_code=alice.room_code, state=state)

    room_manager._rooms.pop(alice.room_code, None)
    game_manager.delete_game(state.game_id)

    restored = room_manager.join_room(room_code=alice.room_code, player_name="Alice")
    assert restored.seat_index == alice.seat_index
    assert restored.player_token == alice.player_token
    restored_state = game_manager.get_game(restored.game_id or "")
    assert restored_state is not None
    assert restored_state.deal_number == 2
