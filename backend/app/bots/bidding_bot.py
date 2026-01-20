from __future__ import annotations

from dataclasses import dataclass
from typing import List

from app.engine.canonical_key import build_canonical_key_and_mapping
from app.engine.rules_infer import predict_bid_and_trump_index


@dataclass(frozen=True)
class BotR1Plan:
    bid: int
    trump_card_id: str
    canonical_groups: List[List[str]]


def plan_bid_and_trump_from_first4(first4_card_ids: List[str]) -> BotR1Plan:
    canon = build_canonical_key_and_mapping(first4_card_ids)
    bid, trump_index = predict_bid_and_trump_index(canon.canonical_groups)

    if trump_index < 0 or trump_index >= len(canon.flat_card_ids):
        raise RuntimeError("trump_index out of range for canonical mapping.")

    return BotR1Plan(
        bid=bid,
        trump_card_id=canon.flat_card_ids[trump_index],
        canonical_groups=canon.canonical_groups,
    )