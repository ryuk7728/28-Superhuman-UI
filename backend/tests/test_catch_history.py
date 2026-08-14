from app.engine.cards_adapter import from_card_id
from app.engine.play_engine import init_play_state, resolve_if_catch_complete
from app.engine.state import GameState


def _completed_trick_state() -> GameState:
    state = GameState(
        game_id="catch-history",
        phase="PLAY",
        starting_bidder_index=2,
        bidding_order=[2, 3, 0, 1],
        players_cards=[[], [], [], []],
        draw_pile=[],
        event_log=[],
    )
    state.final_bidder_seat = 2
    state.final_bid_value = 14
    state.player_trump = from_card_id("Spades_Seven")
    init_play_state(state)

    state.leaderIndex = 2
    state.currentSuit = "Hearts"
    state.s = [
        from_card_id("Hearts_Ace"),   # P3 leads
        from_card_id("Hearts_Seven"), # P4
        from_card_id("Hearts_Jack"),  # P1 wins
        from_card_id("Hearts_Nine"),  # P2
    ]
    state.trumpPlayed = False
    state.trumpIndice = [0, 0, 0, 0]
    return state


def test_completed_catch_preserves_play_order_seats_winner_and_points() -> None:
    state = _completed_trick_state()

    resolve_if_catch_complete(state)

    assert len(state.completed_catches) == 1
    public_history = state.to_public_dict()["play"]["completedCatches"]
    assert public_history == [
        {
            "catchNumber": 1,
            "leaderSeatIndex": 2,
            "plays": [
                {
                    "seatIndex": 2,
                    "card": {
                        "cardId": "Hearts_Ace",
                        "suit": "Hearts",
                        "rank": "Ace",
                        "points": 1,
                        "order": 5,
                        "label": "Ace of Hearts",
                    },
                    "wasTrump": False,
                },
                {
                    "seatIndex": 3,
                    "card": {
                        "cardId": "Hearts_Seven",
                        "suit": "Hearts",
                        "rank": "Seven",
                        "points": 0,
                        "order": 0,
                        "label": "Seven of Hearts",
                    },
                    "wasTrump": False,
                },
                {
                    "seatIndex": 0,
                    "card": {
                        "cardId": "Hearts_Jack",
                        "suit": "Hearts",
                        "rank": "Jack",
                        "points": 3,
                        "order": 7,
                        "label": "Jack of Hearts",
                    },
                    "wasTrump": False,
                },
                {
                    "seatIndex": 1,
                    "card": {
                        "cardId": "Hearts_Nine",
                        "suit": "Hearts",
                        "rank": "Nine",
                        "points": 2,
                        "order": 6,
                        "label": "Nine of Hearts",
                    },
                    "wasTrump": False,
                },
            ],
            "winnerSeatIndex": 0,
            "winnerTeam": 1,
            "points": 6,
        }
    ]


def test_viewer_state_exposes_history_but_keeps_current_opponent_hands_hidden() -> None:
    state = _completed_trick_state()
    resolve_if_catch_complete(state)
    state.players_cards[0].append(from_card_id("Clubs_Ace"))

    viewer_state = state.to_public_dict_for_viewer(1)

    assert viewer_state["play"]["completedCatches"][0]["plays"][2]["card"][
        "cardId"
    ] == "Hearts_Jack"
    assert viewer_state["players"][0]["cards"][0]["suit"] == "Hidden"
