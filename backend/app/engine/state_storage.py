from __future__ import annotations

from dataclasses import fields
from typing import Any

from app.bots.bid_policy import BidPolicyConfig, BidThresholds
from app.engine.cards_adapter import from_card_id, to_card_id
from app.engine.k_policy import KPolicyConfig
from app.engine.state import GameState
from app.legacy.cards import Cards


def _encode(value: Any) -> Any:
    if isinstance(value, Cards):
        return {"__type": "card", "cardId": to_card_id(value)}
    if isinstance(value, BidPolicyConfig):
        return {"__type": "bidPolicy", **value.to_public_dict()}
    if isinstance(value, KPolicyConfig):
        return {"__type": "kPolicy", "mode": value.mode}
    if isinstance(value, list):
        return [_encode(item) for item in value]
    if isinstance(value, tuple):
        return [_encode(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _encode(item) for key, item in value.items()}
    return value


def _decode(value: Any) -> Any:
    if isinstance(value, list):
        return [_decode(item) for item in value]
    if not isinstance(value, dict):
        return value
    marker = value.get("__type")
    if marker == "card":
        return from_card_id(str(value["cardId"]))
    if marker == "kPolicy":
        return KPolicyConfig(mode=str(value.get("mode", "regular")))
    if marker == "bidPolicy":
        thresholds = value.get("thresholds") or {}
        mode = str(value.get("mode", "aggressive"))
        position_aware = bool(value.get("positionAware", False))
        if mode == "optimal":
            return BidPolicyConfig.optimal(position_aware=position_aware)
        if mode == "custom":
            return BidPolicyConfig.custom(
                BidThresholds(
                    opening_15=int(thresholds["opening15"]),
                    opening_16=int(thresholds["opening16"]),
                    later_bid=int(thresholds["laterBid"]),
                    jump_to_16=int(thresholds["jumpTo16"]),
                ),
                position_aware=position_aware,
            )
        return BidPolicyConfig.aggressive(position_aware=position_aware)
    return {key: _decode(item) for key, item in value.items()}


def game_state_to_storage_dict(state: GameState) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "fields": {item.name: _encode(getattr(state, item.name)) for item in fields(state)},
    }


def game_state_from_storage_dict(payload: dict[str, Any]) -> GameState:
    if payload.get("schemaVersion") != 1 or not isinstance(payload.get("fields"), dict):
        raise ValueError("Unsupported stored game-state schema.")
    decoded = {key: _decode(value) for key, value in payload["fields"].items()}
    allowed = {item.name for item in fields(GameState)}
    state = GameState(**{key: value for key, value in decoded.items() if key in allowed})

    # PLAY relies on these lists sharing the exact same objects.
    if state.play_players:
        for seat, player in enumerate(state.play_players):
            player["cards"] = state.players_cards[seat]
            if seat == state.final_bidder_seat:
                player["trump"] = state.player_trump
    return state
