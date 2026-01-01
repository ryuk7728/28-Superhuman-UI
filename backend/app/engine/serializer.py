from __future__ import annotations

from app.legacy.cards import Cards
from app.engine.cards_adapter import to_card_id


def serialize_card(card: Cards) -> dict:
    return {
        "cardId": to_card_id(card),
        "suit": card.suit,
        "rank": card.rank,
        "points": card.points,
        "order": card.order,
        "label": card.identity(),
    }