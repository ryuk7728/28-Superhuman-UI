from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BidTurnRules:
    seat_index: int
    min_bid_exclusive: int
    max_bid_inclusive: int
    can_pass: bool
    can_redeal: bool


def _is_zero_point_first4(points_sum: int) -> bool:
    return points_sum == 0


def compute_r1_turn_rules(
    *,
    bidding_order: list[int],
    step: int,
    bids_by_pos: list[int],
    passes_by_pos: list[bool],
    final_pos: int,
    first4_points_by_seat: list[int],
) -> BidTurnRules:
    """
    Mirrors the exact min-bid logic in your legacy `game.py` first bidding loop,
    but generalized to a rotated `bidding_order`.
    """
    seat = bidding_order[step]
    max_bid = 23

    if step == 0:
        # In your code: min=13, pass not allowed; special redeal allowed via -1
        min_excl = 13
        can_pass = False
        can_redeal = _is_zero_point_first4(first4_points_by_seat[seat])
        return BidTurnRules(
            seat_index=seat,
            min_bid_exclusive=min_excl,
            max_bid_inclusive=max_bid,
            can_pass=can_pass,
            can_redeal=can_redeal,
        )

    if step == 1:
        min_excl = bids_by_pos[0]
    elif step == 2:
        # In your code: if P2 didn't pass => min=bids[1] else min=max(bids[0],19)
        if not passes_by_pos[1]:
            min_excl = bids_by_pos[1]
        else:
            min_excl = max(bids_by_pos[0], 19)
    else:
        # step == 3
        # In your code:
        # if finalBid==2 => min=max(bids[finalBid-1],19) else min=bids[finalBid-1]
        if final_pos == 1:
            min_excl = max(bids_by_pos[final_pos], 19)
        else:
            min_excl = bids_by_pos[final_pos]

    return BidTurnRules(
        seat_index=seat,
        min_bid_exclusive=min_excl,
        max_bid_inclusive=max_bid,
        can_pass=True,
        can_redeal=False,
    )


def validate_r1_bid_value(*, rules: BidTurnRules, bid_value: int) -> None:
    if bid_value == -1:
        if not rules.can_redeal:
            raise ValueError("Redeal not allowed for this player.")
        return

    if bid_value == 0:
        if not rules.can_pass:
            raise ValueError("Pass not allowed for this player.")
        return

    if bid_value <= rules.min_bid_exclusive:
        raise ValueError(f"Bid must be > {rules.min_bid_exclusive}.")
    if bid_value > rules.max_bid_inclusive:
        raise ValueError(f"Bid must be <= {rules.max_bid_inclusive}.")


def compute_r2_turn_rules(
    *,
    bidding_order: list[int],
    step: int,
    bids_so_far_by_pos: list[int],
) -> BidTurnRules:
    """
    Mirrors your `performBidding(23, 28)`:
    min is the current max bid (or 23 if none),
    player must bid > min, or pass (0).
    """
    seat = bidding_order[step]
    max_bid = 28
    max_current = max([b for b in bids_so_far_by_pos if b != 0] + [23])
    return BidTurnRules(
        seat_index=seat,
        min_bid_exclusive=max_current,
        max_bid_inclusive=max_bid,
        can_pass=True,
        can_redeal=False,
    )


def validate_r2_bid_value(*, rules: BidTurnRules, bid_value: int) -> None:
    if bid_value == 0:
        return
    if bid_value <= rules.min_bid_exclusive:
        raise ValueError(f"Bid must be > {rules.min_bid_exclusive}.")
    if bid_value > rules.max_bid_inclusive:
        raise ValueError(f"Bid must be <= {rules.max_bid_inclusive}.")