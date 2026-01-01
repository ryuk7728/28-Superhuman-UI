from __future__ import annotations

from dataclasses import dataclass

from app.legacy.cards import Cards

SUITS = ("Hearts", "Clubs", "Diamonds", "Spades")
RANKS = ("Seven", "Eight", "Queen", "King", "Ten", "Ace", "Nine", "Jack")


def points_and_order(rank: str) -> tuple[int, int]:
    if rank in ("Ten", "Ace"):
        points = 1
    elif rank == "Nine":
        points = 2
    elif rank == "Jack":
        points = 3
    else:
        points = 0
    return points, RANKS.index(rank)


def to_card_id(card: Cards) -> str:
    return f"{card.suit}_{card.rank}"


def from_card_id(card_id: str) -> Cards:
    try:
        suit, rank = card_id.split("_", 1)
    except ValueError as e:
        raise ValueError(f"Invalid cardId: {card_id}") from e

    if suit not in SUITS:
        raise ValueError(f"Invalid suit: {suit}")
    if rank not in RANKS:
        raise ValueError(f"Invalid rank: {rank}")

    points, order = points_and_order(rank)
    return Cards(suit=suit, rank=rank, points=points, order=order)


def card_identity_from_id(card_id: str) -> str:
    c = from_card_id(card_id)
    return c.identity()