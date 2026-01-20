from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.bots.bidding_bot import plan_bid_and_trump_from_first4
from app.engine.bidding_engine import (
    compute_r1_turn_rules,
    compute_r2_turn_rules,
    validate_r1_bid_value,
    validate_r2_bid_value,
)
from app.engine.cards_adapter import from_card_id, to_card_id
from app.engine.game_manager import game_manager
from app.engine.legal_actions import get_legal_actions
from app.engine.play_engine import (
    init_play_state,
    apply_play_card,
    apply_reveal_choice,
    resolve_if_catch_complete,
)
from app.engine.bot_runner import advance_bots_until_human

router = APIRouter()

BOT_SEATS = {0, 2}


async def _send_state(websocket: WebSocket, state) -> None:
    actions = get_legal_actions(state)
    await websocket.send_json({"type": "STATE_UPDATE", "state": state.to_public_dict()})
    await websocket.send_json({"type": "LEGAL_ACTIONS", "actions": actions})


def _validate_manual_rest_deal(state, rest_hands: list[list[str]]) -> None:
    if len(rest_hands) != 4:
        raise ValueError("restHands must have 4 lists (one per player).")

    for i, h in enumerate(rest_hands):
        if len(h) != 4:
            raise ValueError(f"Player {i+1} must receive exactly 4 cards.")

    flat = [cid for h in rest_hands for cid in h]
    if len(flat) != 16:
        raise ValueError("Total restHands cards must be 16.")

    if len(set(flat)) != 16:
        raise ValueError("Duplicate cardIds found in restHands.")

    draw_ids = {to_card_id(c) for c in state.draw_pile}
    chosen_ids = set(flat)
    if draw_ids != chosen_ids:
        raise ValueError("restHands must use exactly the 16 remaining draw pile cards.")


def _partner_seat(seat: int) -> int:
    # 0 <-> 2, 1 <-> 3
    return seat ^ 2


def _current_highest_r1(state) -> tuple[int, int | None]:
    """
    Returns (max_bid, seatIndex) among bidsR1 so far (ignoring 0 passes).
    If none, returns (0, None).
    """
    max_bid = 0
    max_seat: int | None = None
    for seat, b in enumerate(state.bids_r1_by_seat):
        if b and b > max_bid:
            max_bid = b
            max_seat = seat
    return max_bid, max_seat


def _apply_r1_bid(state, *, seat: int, bid_value: int) -> None:
    if seat != state.turn_index:
        raise ValueError("Not this seat's turn to bid (R1).")

    first4_points_by_seat = [
        sum(c.points for c in state.players_cards[i]) for i in range(4)
    ]

    rules = compute_r1_turn_rules(
        bidding_order=state.bidding_order,
        step=state.bidding_r1_step,
        bids_by_pos=state.bidding_r1_bids_by_pos,
        passes_by_pos=state.bidding_r1_passes_by_pos,
        final_pos=state.bidding_r1_final_pos,
        first4_points_by_seat=first4_points_by_seat,
    )

    validate_r1_bid_value(rules=rules, bid_value=bid_value)

    if bid_value == -1:
        # Not implemented in your server flow
        raise ValueError("Redeal flow not implemented yet.")

    pos = state.bidding_r1_step
    state.bidding_r1_bids_by_pos[pos] = bid_value
    state.bids_r1_by_seat[seat] = bid_value

    if bid_value == 0:
        state.bidding_r1_passes_by_pos[pos] = True
        state.event_log.append(f"P{seat+1} passed.")
    else:
        state.bidding_r1_final_pos = pos
        state.event_log.append(f"P{seat+1} bid {bid_value}.")

    state.bidding_r1_step += 1

    if state.bidding_r1_step >= 4:
        winner_pos = state.bidding_r1_final_pos
        winner_seat = state.bidding_order[winner_pos]
        winner_bid = state.bidding_r1_bids_by_pos[winner_pos]

        state.round1_bidder_seat = winner_seat
        state.round1_bid_value = winner_bid
        state.final_bidder_seat = winner_seat
        state.final_bid_value = winner_bid

        state.phase = "TRUMP_SELECT_R1"
        state.event_log.append(
            f"R1 winner: P{winner_seat+1} with {winner_bid}. Select trump."
        )


def _apply_r2_bid(state, *, seat: int, bid_value: int) -> None:
    if seat != state.turn_index:
        raise ValueError("Not this seat's turn to bid (R2).")

    rules = compute_r2_turn_rules(
        bidding_order=state.bidding_order,
        step=state.bidding_r2_step,
        bids_so_far_by_pos=state.bidding_r2_bids_by_pos,
    )

    validate_r2_bid_value(rules=rules, bid_value=bid_value)

    pos = state.bidding_r2_step
    state.bidding_r2_bids_by_pos[pos] = bid_value
    state.bids_r2_by_seat[seat] = bid_value

    if bid_value == 0:
        state.event_log.append(f"P{seat+1} passed (R2).")
    else:
        state.event_log.append(f"P{seat+1} bid {bid_value} (R2).")

    state.bidding_r2_step += 1

    if state.bidding_r2_step >= 4:
        max_bid = max(state.bidding_r2_bids_by_pos)
        if max_bid == 0:
            # No further bids; final stays Round 1
            state.final_bidder_seat = state.round1_bidder_seat
            state.final_bid_value = state.round1_bid_value

            state.phase = "PLAY"
            init_play_state(state)
            state.event_log.append("No further bids in R2. Entering PLAY.")
        else:
            max_pos = state.bidding_r2_bids_by_pos.index(max_bid)
            new_bidder_seat = state.bidding_order[max_pos]

            # Return old concealed trump back to round1 bidder hand
            if state.player_trump is not None and state.round1_bidder_seat is not None:
                state.players_cards[state.round1_bidder_seat].append(state.player_trump)

            state.final_bidder_seat = new_bidder_seat
            state.final_bid_value = max_bid

            state.phase = "TRUMP_SELECT_R2"
            state.event_log.append(
                f"R2 winner: P{new_bidder_seat+1} with {max_bid}. Select new trump."
            )


def _apply_select_trump_card(state, *, seat: int, card_id: str) -> None:
    if state.phase not in ("TRUMP_SELECT_R1", "TRUMP_SELECT_R2"):
        raise ValueError("Not in trump selection phase.")

    if state.final_bidder_seat is None:
        raise ValueError("final_bidder_seat not set.")

    if seat != state.final_bidder_seat:
        raise ValueError("Not your trump selection turn.")

    chosen = from_card_id(card_id)

    hand = state.players_cards[seat]
    removed = False
    for i, c in enumerate(hand):
        if c.identity() == chosen.identity():
            state.player_trump = hand.pop(i)
            removed = True
            break

    if not removed:
        raise ValueError("Card not in hand.")

    state.event_log.append(f"P{seat+1} selected a concealed trump card.")

    if state.phase == "TRUMP_SELECT_R1":
        state.phase = "MANUAL_DEAL_REST"
        state.event_log.append(
            "Manual deal: assign the remaining 4 cards to each player."
        )
        return

    # TRUMP_SELECT_R2 -> proceed to play
    state.phase = "PLAY"
    init_play_state(state)
    state.event_log.append("Entering PLAY after R2 trump selection.")


async def _advance_bots_until_human_any_phase(state, pool, bot_sem) -> None:
    """
    Auto-advance bot seats (0 and 2) in:
      - BIDDING_R1: rules-based bid
      - TRUMP_SELECT_R1: rules-based trump pick
      - BIDDING_R2: bots always pass
      - PLAY: rollout bot plays (existing)
    Stops when the next actor is a human seat or phase requires human input.
    """
    while True:
        if state.phase == "BIDDING_R1":
            seat = state.turn_index
            if seat not in BOT_SEATS:
                return

            # Plan from first4
            first4 = [to_card_id(c) for c in state.players_cards[seat]]
            plan = plan_bid_and_trump_from_first4(first4)

            # Compute current rules for turn (for allowed range / pass allowed)
            first4_points_by_seat = [
                sum(c.points for c in state.players_cards[i]) for i in range(4)
            ]
            rules = compute_r1_turn_rules(
                bidding_order=state.bidding_order,
                step=state.bidding_r1_step,
                bids_by_pos=state.bidding_r1_bids_by_pos,
                passes_by_pos=state.bidding_r1_passes_by_pos,
                final_pos=state.bidding_r1_final_pos,
                first4_points_by_seat=first4_points_by_seat,
            )

            current_highest, highest_seat = _current_highest_r1(state)
            partner = _partner_seat(seat)

            # Do not overcall partner bot
            if highest_seat == partner and highest_seat in BOT_SEATS:
                bid_value = 0
            else:
                bid_value = plan.bid if plan.bid > current_highest else 0

            # Must fit allowed range; otherwise pass
            if bid_value != 0:
                if bid_value <= rules.min_bid_exclusive or bid_value > rules.max_bid_inclusive:
                    bid_value = 0

            # If pass is not allowed (first bidder), ensure we bid something legal.
            if bid_value == 0 and not rules.can_pass:
                bid_value = max(rules.min_bid_exclusive + 1, 14)

            _apply_r1_bid(state, seat=seat, bid_value=bid_value)
            continue

        if state.phase == "TRUMP_SELECT_R1":
            seat = state.final_bidder_seat
            if seat is None or seat not in BOT_SEATS:
                return

            first4 = [to_card_id(c) for c in state.players_cards[seat]]
            plan = plan_bid_and_trump_from_first4(first4)
            card_id = plan.trump_card_id

            # Safety: if mapping produced a card not in hand, fall back
            legal_ids = [to_card_id(c) for c in state.players_cards[seat]]
            if card_id not in legal_ids and legal_ids:
                card_id = legal_ids[0]

            _apply_select_trump_card(state, seat=seat, card_id=card_id)
            continue

        if state.phase == "MANUAL_DEAL_REST":
            # Humans must assign the remaining 16 cards
            return

        if state.phase == "BIDDING_R2":
            seat = state.turn_index
            if seat not in BOT_SEATS:
                return

            # Bots always pass in R2
            _apply_r2_bid(state, seat=seat, bid_value=0)
            continue

        if state.phase == "TRUMP_SELECT_R2":
            # Bots shouldn't reach here (they always pass in R2), but keep safe.
            seat = state.final_bidder_seat
            if seat is None or seat not in BOT_SEATS:
                return
            legal_ids = [to_card_id(c) for c in state.players_cards[seat]]
            if not legal_ids:
                return
            _apply_select_trump_card(state, seat=seat, card_id=legal_ids[0])
            continue

        if state.phase == "PLAY":
            await advance_bots_until_human(state, pool, bot_sem)
            return

        return


@router.websocket("/ws/games/{game_id}")
async def ws_game(websocket: WebSocket, game_id: str) -> None:
    await websocket.accept()

    state = game_manager.get_game(game_id)
    if not state:
        await websocket.send_json({"type": "ERROR", "message": "Game not found"})
        await websocket.close()
        return

    app = websocket.scope["app"]
    pool = app.state.process_pool
    bot_sem = app.state.bot_sem

    # Auto-advance bots before first state paint (if starting bidder is a bot)
    await _advance_bots_until_human_any_phase(state, pool, bot_sem)
    await _send_state(websocket, state)

    try:
        while True:
            msg = await websocket.receive_json()
            msg_type = msg.get("type")

            if msg_type == "GET_STATE":
                await _send_state(websocket, state)
                continue

            # -------------------
            # BIDDING: SUBMIT_BID
            # -------------------
            if msg_type == "SUBMIT_BID":
                seat = int(msg.get("seatIndex"))
                bid_value = int(msg.get("bidValue"))

                # Round 1
                if state.phase == "BIDDING_R1":
                    if seat != state.turn_index:
                        await websocket.send_json(
                            {"type": "ERROR", "message": f"Not P{seat+1}'s turn to bid."}
                        )
                        continue

                    first4_points_by_seat = [
                        sum(c.points for c in state.players_cards[i]) for i in range(4)
                    ]
                    rules = compute_r1_turn_rules(
                        bidding_order=state.bidding_order,
                        step=state.bidding_r1_step,
                        bids_by_pos=state.bidding_r1_bids_by_pos,
                        passes_by_pos=state.bidding_r1_passes_by_pos,
                        final_pos=state.bidding_r1_final_pos,
                        first4_points_by_seat=first4_points_by_seat,
                    )

                    try:
                        validate_r1_bid_value(rules=rules, bid_value=bid_value)
                    except ValueError as e:
                        await websocket.send_json({"type": "ERROR", "message": str(e)})
                        continue

                    if bid_value == -1:
                        state.event_log.append(
                            f"P{seat+1} requested redeal (not implemented)."
                        )
                        await websocket.send_json(
                            {
                                "type": "ERROR",
                                "message": "Redeal flow not implemented yet.",
                            }
                        )
                        continue

                    pos = state.bidding_r1_step
                    state.bidding_r1_bids_by_pos[pos] = bid_value
                    state.bids_r1_by_seat[seat] = bid_value

                    if bid_value == 0:
                        state.bidding_r1_passes_by_pos[pos] = True
                        state.event_log.append(f"P{seat+1} passed.")
                    else:
                        state.bidding_r1_final_pos = pos
                        state.event_log.append(f"P{seat+1} bid {bid_value}.")

                    state.bidding_r1_step += 1

                    if state.bidding_r1_step >= 4:
                        winner_pos = state.bidding_r1_final_pos
                        winner_seat = state.bidding_order[winner_pos]
                        winner_bid = state.bidding_r1_bids_by_pos[winner_pos]

                        state.round1_bidder_seat = winner_seat
                        state.round1_bid_value = winner_bid
                        state.final_bidder_seat = winner_seat
                        state.final_bid_value = winner_bid

                        state.phase = "TRUMP_SELECT_R1"
                        state.event_log.append(
                            f"R1 winner: P{winner_seat+1} with {winner_bid}. Select trump."
                        )

                    await _advance_bots_until_human_any_phase(state, pool, bot_sem)
                    await _send_state(websocket, state)
                    continue

                # Round 2
                if state.phase == "BIDDING_R2":
                    if seat != state.turn_index:
                        await websocket.send_json(
                            {"type": "ERROR", "message": f"Not P{seat+1}'s turn to bid."}
                        )
                        continue

                    rules = compute_r2_turn_rules(
                        bidding_order=state.bidding_order,
                        step=state.bidding_r2_step,
                        bids_so_far_by_pos=state.bidding_r2_bids_by_pos,
                    )

                    try:
                        validate_r2_bid_value(rules=rules, bid_value=bid_value)
                    except ValueError as e:
                        await websocket.send_json({"type": "ERROR", "message": str(e)})
                        continue

                    pos = state.bidding_r2_step
                    state.bidding_r2_bids_by_pos[pos] = bid_value
                    state.bids_r2_by_seat[seat] = bid_value

                    if bid_value == 0:
                        state.event_log.append(f"P{seat+1} passed (R2).")
                    else:
                        state.event_log.append(f"P{seat+1} bid {bid_value} (R2).")

                    state.bidding_r2_step += 1

                    if state.bidding_r2_step >= 4:
                        max_bid = max(state.bidding_r2_bids_by_pos)
                        if max_bid == 0:
                            state.final_bidder_seat = state.round1_bidder_seat
                            state.final_bid_value = state.round1_bid_value

                            state.phase = "PLAY"
                            init_play_state(state)

                            state.event_log.append("No further bids in R2. Entering PLAY.")
                        else:
                            max_pos = state.bidding_r2_bids_by_pos.index(max_bid)
                            new_bidder_seat = state.bidding_order[max_pos]

                            if (
                                state.player_trump is not None
                                and state.round1_bidder_seat is not None
                            ):
                                state.players_cards[state.round1_bidder_seat].append(
                                    state.player_trump
                                )

                            state.final_bidder_seat = new_bidder_seat
                            state.final_bid_value = max_bid

                            state.phase = "TRUMP_SELECT_R2"
                            state.event_log.append(
                                f"R2 winner: P{new_bidder_seat+1} with {max_bid}. Select new trump."
                            )

                    await _advance_bots_until_human_any_phase(state, pool, bot_sem)
                    await _send_state(websocket, state)
                    continue

                await websocket.send_json(
                    {"type": "ERROR", "message": "Not in a bidding phase."}
                )
                continue

            # -------------------------
            # TRUMP: SELECT_TRUMP_CARD
            # -------------------------
            if msg_type == "SELECT_TRUMP_CARD":
                seat = int(msg.get("seatIndex"))
                card_id = str(msg.get("cardId"))

                if state.phase not in ("TRUMP_SELECT_R1", "TRUMP_SELECT_R2"):
                    await websocket.send_json(
                        {"type": "ERROR", "message": "Not in trump selection phase."}
                    )
                    continue

                if state.final_bidder_seat is None:
                    await websocket.send_json(
                        {"type": "ERROR", "message": "final_bidder_seat not set."}
                    )
                    continue

                if seat != state.final_bidder_seat:
                    await websocket.send_json(
                        {"type": "ERROR", "message": "Not your trump selection turn."}
                    )
                    continue

                chosen = from_card_id(card_id)

                hand = state.players_cards[seat]
                removed = False
                for i, c in enumerate(hand):
                    if c.identity() == chosen.identity():
                        state.player_trump = hand.pop(i)
                        removed = True
                        break

                if not removed:
                    await websocket.send_json(
                        {"type": "ERROR", "message": "Card not in hand."}
                    )
                    continue

                state.event_log.append(f"P{seat+1} selected a concealed trump card.")

                if state.phase == "TRUMP_SELECT_R1":
                    state.phase = "MANUAL_DEAL_REST"
                    state.event_log.append(
                        "Manual deal: assign the remaining 4 cards to each player."
                    )
                else:
                    state.phase = "PLAY"
                    init_play_state(state)
                    state.event_log.append("Entering PLAY after R2 trump selection.")

                await _advance_bots_until_human_any_phase(state, pool, bot_sem)
                await _send_state(websocket, state)
                continue

            # -----------------------------
            # MANUAL DEAL REST (16 cards)
            # -----------------------------
            if msg_type == "SUBMIT_REST_DEAL":
                if state.phase != "MANUAL_DEAL_REST":
                    await websocket.send_json(
                        {"type": "ERROR", "message": "Not in MANUAL_DEAL_REST phase."}
                    )
                    continue

                rest_hands = msg.get("restHands")
                try:
                    if not isinstance(rest_hands, list):
                        raise ValueError("restHands must be a list.")
                    _validate_manual_rest_deal(state, rest_hands)

                    for seat in range(4):
                        for cid in rest_hands[seat]:
                            state.players_cards[seat].append(from_card_id(cid))

                    state.draw_pile.clear()

                    state.phase = "BIDDING_R2"
                    state.bidding_r2_step = 0
                    state.bidding_r2_bids_by_pos = [0, 0, 0, 0]
                    state.bids_r2_by_seat = [0, 0, 0, 0]
                    state.event_log.append("Manual deal complete. Bidding Round 2 starts.")

                    await _advance_bots_until_human_any_phase(state, pool, bot_sem)
                    await _send_state(websocket, state)
                except ValueError as e:
                    await websocket.send_json({"type": "ERROR", "message": str(e)})

                continue

            # -------------------
            # PLAY: REVEAL CHOICE
            # -------------------
            if msg_type == "CHOOSE_REVEAL_TRUMP":
                seat = int(msg.get("seatIndex"))
                reveal = bool(msg.get("reveal"))

                if state.phase != "PLAY":
                    await websocket.send_json(
                        {"type": "ERROR", "message": "Not in PLAY phase."}
                    )
                    continue

                try:
                    apply_reveal_choice(state, seat, reveal)
                    resolve_if_catch_complete(state)
                    await _advance_bots_until_human_any_phase(state, pool, bot_sem)
                except ValueError as e:
                    await websocket.send_json({"type": "ERROR", "message": str(e)})
                    continue

                await _send_state(websocket, state)
                continue

            # ----------------
            # PLAY: PLAY CARD
            # ----------------
            if msg_type == "PLAY_CARD":
                seat = int(msg.get("seatIndex"))
                card_id = str(msg.get("cardId"))

                if state.phase != "PLAY":
                    await websocket.send_json(
                        {"type": "ERROR", "message": "Not in PLAY phase."}
                    )
                    continue

                try:
                    apply_play_card(state, seat, card_id)
                    resolve_if_catch_complete(state)
                    await _advance_bots_until_human_any_phase(state, pool, bot_sem)
                except ValueError as e:
                    await websocket.send_json({"type": "ERROR", "message": str(e)})
                    continue

                await _send_state(websocket, state)
                continue

            await websocket.send_json(
                {"type": "ERROR", "message": f"Unknown message type: {msg_type}"}
            )

    except WebSocketDisconnect:
        return