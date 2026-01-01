from __future__ import annotations

from app.engine.cards_adapter import card_identity_from_id


def validate_first4_hands(hands: list[list[str]]) -> None:
    if len(hands) != 4:
        raise ValueError("hands must be a list of 4 lists (one per player).")

    for i, h in enumerate(hands):
        if len(h) != 4:
            raise ValueError(f"Player {i} must have exactly 4 cards in first4.")

    flat = [cid for h in hands for cid in h]
    if len(flat) != 16:
        raise ValueError("Total first4 cards must be 16.")

    if len(set(flat)) != 16:
        raise ValueError("Duplicate cards found in first4 hands.")

    # Validate format + ensure they map to valid Cards identity
    _ = [card_identity_from_id(cid) for cid in flat]