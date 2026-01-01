from __future__ import annotations

import random
import uuid

from app.engine.cards_adapter import from_card_id
from app.engine.state import GameState
from app.engine.validator import validate_first4_hands
from app.legacy.cards import Cards


class GameManager:
    def __init__(self) -> None:
        self._games: dict[str, GameState] = {}

    def create_game_manual_first4(
        self,
        *,
        starting_bidder_index: int,
        first4_hands: list[list[str]],
    ) -> GameState:
        if starting_bidder_index < 0 or starting_bidder_index > 3:
            raise ValueError("startingBidderIndex must be in 0..3")

        validate_first4_hands(first4_hands)

        players_cards = [[from_card_id(cid) for cid in hand] for hand in first4_hands]

        used_identities = {c.identity() for hand in players_cards for c in hand}
        full_deck = Cards.packOf28()  # 32 cards
        remaining = [c for c in full_deck if c.identity() not in used_identities]
        random.shuffle(remaining)

        bidding_order = [
            (starting_bidder_index + i) % 4 for i in range(4)
        ]

        game_id = str(uuid.uuid4())
        state = GameState(
            game_id=game_id,
            phase="BIDDING_R1",
            starting_bidder_index=starting_bidder_index,
            bidding_order=bidding_order,
            players_cards=players_cards,
            draw_pile=remaining,
            event_log=[
                "Game created (manual first-4).",
                f"Starting bidder: P{starting_bidder_index + 1}",
            ],
        )

        self._games[game_id] = state
        return state

    def get_game(self, game_id: str) -> GameState | None:
        return self._games.get(game_id)


game_manager = GameManager()