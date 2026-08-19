from __future__ import annotations

from dataclasses import dataclass, field
from collections import deque
import secrets
import string
import threading
import time
import logging

from app.bots.bid_policy import BidPolicyConfig, BidThresholds
from app.engine.game_manager import game_manager
from app.engine.k_policy import KPolicyConfig
from app.engine.replay_payload import build_replay_payload
from app.engine.replay_store import replay_store
from app.engine.state_storage import game_state_from_storage_dict, game_state_to_storage_dict
from app.settings import settings

HUMAN_ROOM_SEATS: tuple[int, int] = (1, 3)
ROOM_CODE_CHARS = string.ascii_uppercase + string.digits
ROOM_CODE_LENGTH = 6
DEFAULT_BOT_THINK_SECONDS = 30.0
MIN_BOT_THINK_SECONDS = 1.0
MAX_BOT_THINK_SECONDS = 120.0
MAX_CHAT_MESSAGE_LENGTH = 280
MAX_CHAT_HISTORY = 100
CHAT_RATE_WINDOW_SECONDS = 10.0
CHAT_RATE_MAX_MESSAGES = 5
logger = logging.getLogger(__name__)


class RoomError(Exception):
    pass


class RoomNotFoundError(RoomError):
    pass


class RoomFullError(RoomError):
    pass


class RoomTokenError(RoomError):
    pass


@dataclass
class Room:
    code: str
    created_at: float
    updated_at: float
    starting_bidder_index: int
    bot_bidding_policy: BidPolicyConfig = field(default_factory=BidPolicyConfig.aggressive)
    bot_k_policy: KPolicyConfig = field(default_factory=KPolicyConfig)
    bot_think_timeout_seconds: float = DEFAULT_BOT_THINK_SECONDS
    game_id: str | None = None
    seat_tokens: dict[int, str] = field(default_factory=dict)
    seat_names: dict[int, str] = field(default_factory=dict)
    rematch_ready_seats: set[int] = field(default_factory=set)
    chat_messages: deque[dict[str, object]] = field(
        default_factory=lambda: deque(maxlen=MAX_CHAT_HISTORY)
    )
    chat_sent_at: dict[int, deque[float]] = field(default_factory=dict)

    @property
    def players_joined(self) -> int:
        return len(self.seat_tokens)

    @property
    def waiting_for_player(self) -> bool:
        return self.players_joined < len(HUMAN_ROOM_SEATS)


@dataclass(frozen=True)
class RoomAssignment:
    room_code: str
    seat_index: int
    player_token: str
    game_id: str | None
    seat_name: str
    waiting_for_player: bool
    players_joined: int


@dataclass(frozen=True)
class RematchRequestResult:
    started: bool
    waiting_for_seat: int | None
    ready_seats: tuple[int, ...]
    starting_bidder_index: int | None


class RoomManager:
    def __init__(self) -> None:
        self._rooms: dict[str, Room] = {}
        self._lock = threading.Lock()

    def _cleanup_expired_locked(self) -> None:
        now = time.time()
        ttl = max(60, settings.room_ttl_seconds)
        expired_codes: list[str] = []
        for code, room in self._rooms.items():
            if now - room.updated_at <= ttl:
                continue
            expired_codes.append(code)
            if room.game_id:
                game_manager.delete_game(room.game_id)
        for code in expired_codes:
            self._rooms.pop(code, None)

    def _generate_code_locked(self) -> str:
        for _ in range(1000):
            code = "".join(secrets.choice(ROOM_CODE_CHARS) for _ in range(ROOM_CODE_LENGTH))
            if code not in self._rooms:
                return code
        raise RuntimeError("Unable to allocate unique room code")

    def _lookup_room_locked(self, room_code: str) -> Room:
        code = room_code.strip().upper()
        room = self._rooms.get(code)
        if room is None:
            stored = replay_store.load_session(code)
            if stored is not None:
                room = self._room_from_storage_locked(stored)
                self._rooms[code] = room
        if room is None:
            raise RoomNotFoundError("Room not found.")
        return room

    def _room_from_storage_locked(self, payload: dict[str, object]) -> Room:
        policy_data = payload.get("botBiddingPolicy") or {}
        thresholds_data = policy_data.get("thresholds") or {}
        mode = str(policy_data.get("mode", "aggressive"))
        position_aware = bool(policy_data.get("positionAware", False))
        if mode == "optimal":
            policy = BidPolicyConfig.optimal(position_aware=position_aware)
        elif mode == "custom":
            policy = BidPolicyConfig.custom(
                BidThresholds(
                    opening_15=int(thresholds_data["opening15"]),
                    opening_16=int(thresholds_data["opening16"]),
                    later_bid=int(thresholds_data["laterBid"]),
                    jump_to_16=int(thresholds_data["jumpTo16"]),
                ),
                position_aware=position_aware,
            )
        else:
            policy = BidPolicyConfig.aggressive(position_aware=position_aware)

        room = Room(
            code=str(payload["roomCode"]),
            created_at=float(payload.get("createdAt", time.time())),
            updated_at=float(payload.get("updatedAt", time.time())),
            starting_bidder_index=int(payload.get("startingBidderIndex", 0)),
            bot_bidding_policy=policy,
            bot_k_policy=KPolicyConfig(mode=str(payload.get("botKPolicyMode", "regular"))),
            bot_think_timeout_seconds=float(payload.get("botThinkTimeSeconds", 30.0)),
            game_id=str(payload["gameId"]) if payload.get("gameId") else None,
            seat_tokens={
                int(key): str(value)
                for key, value in (payload.get("seatTokens") or {}).items()
            },
            seat_names={
                int(key): str(value)
                for key, value in (payload.get("seatNames") or {}).items()
            },
            rematch_ready_seats={
                int(value) for value in (payload.get("rematchReadySeats") or [])
            },
            chat_messages=deque(
                payload.get("chatMessages") or [], maxlen=MAX_CHAT_HISTORY
            ),
        )
        state_storage = payload.get("stateStorage")
        if room.game_id and isinstance(state_storage, dict):
            state = game_state_from_storage_dict(state_storage)
            state.room_code = room.code
            game_manager.restore_game(state)
        return room

    def _room_storage_payload(self, room: Room) -> dict[str, object]:
        return {
            "roomCode": room.code,
            "createdAt": room.created_at,
            "updatedAt": room.updated_at,
            "startingBidderIndex": room.starting_bidder_index,
            "gameId": room.game_id,
            "seatTokens": {str(key): value for key, value in room.seat_tokens.items()},
            "seatNames": {str(key): value for key, value in room.seat_names.items()},
            "rematchReadySeats": sorted(room.rematch_ready_seats),
            "chatMessages": list(room.chat_messages),
            "botBiddingPolicy": room.bot_bidding_policy.to_public_dict(),
            "botKPolicyMode": room.bot_k_policy.mode,
            "botThinkTimeSeconds": room.bot_think_timeout_seconds,
        }

    def _persist_session_locked(self, room: Room) -> None:
        try:
            replay_store.save_session(self._room_storage_payload(room))
        except Exception:
            logger.exception("Unable to persist room session %s", room.code)

    def _find_seat_for_token_locked(self, room: Room, player_token: str) -> int | None:
        for seat_index, token in room.seat_tokens.items():
            if token == player_token:
                return seat_index
        return None

    def _normalize_player_name(self, player_name: str | None) -> str:
        cleaned = (player_name or "").strip()
        if not cleaned:
            raise RoomError("playerName is required.")
        if len(cleaned) > 24:
            raise RoomError("playerName must be at most 24 characters.")
        return cleaned

    def _ensure_game_created_locked(self, room: Room) -> None:
        if room.game_id is not None:
            return
        if room.players_joined < len(HUMAN_ROOM_SEATS):
            return
        state = game_manager.create_game_auto_deal(
            starting_bidder_index=room.starting_bidder_index,
            bot_bidding_policy=room.bot_bidding_policy,
            bot_k_policy=room.bot_k_policy,
            bot_think_timeout_seconds=room.bot_think_timeout_seconds,
        )
        state.player_names = [
            "T-1000",
            room.seat_names.get(1, "Player 1"),
            "Skynet",
            room.seat_names.get(3, "Player 2"),
        ]
        state.room_code = room.code
        room.game_id = state.game_id
        room.rematch_ready_seats.clear()

    def create_room(
        self,
        *,
        player_name: str,
        starting_bidder_index: int | None = None,
        bot_bidding_policy: BidPolicyConfig | None = None,
        bot_k_policy: KPolicyConfig | None = None,
        bot_think_timeout_seconds: float = DEFAULT_BOT_THINK_SECONDS,
    ) -> RoomAssignment:
        with self._lock:
            self._cleanup_expired_locked()
            code = self._generate_code_locked()
            room = Room(
                code=code,
                created_at=time.time(),
                updated_at=time.time(),
                starting_bidder_index=(
                    secrets.randbelow(4)
                    if starting_bidder_index is None
                    else starting_bidder_index
                ),
                bot_bidding_policy=bot_bidding_policy or BidPolicyConfig.aggressive(),
                bot_k_policy=bot_k_policy or KPolicyConfig(),
                bot_think_timeout_seconds=self._validate_bot_think_seconds(
                    bot_think_timeout_seconds
                ),
            )
            seat_index = HUMAN_ROOM_SEATS[0]
            player_token = secrets.token_urlsafe(24)
            normalized_name = self._normalize_player_name(player_name)
            room.seat_tokens[seat_index] = player_token
            room.seat_names[seat_index] = normalized_name
            self._rooms[code] = room
            self._persist_session_locked(room)
            return RoomAssignment(
                room_code=room.code,
                seat_index=seat_index,
                player_token=player_token,
                game_id=room.game_id,
                seat_name=normalized_name,
                waiting_for_player=room.waiting_for_player,
                players_joined=room.players_joined,
            )

    def join_room(
        self,
        *,
        room_code: str,
        player_token: str | None = None,
        player_name: str | None = None,
    ) -> RoomAssignment:
        with self._lock:
            self._cleanup_expired_locked()
            room = self._lookup_room_locked(room_code)

            seat_index: int | None = None
            token = (player_token or "").strip()
            if token:
                seat_index = self._find_seat_for_token_locked(room, token)
                if seat_index is not None and player_name:
                    room.seat_names[seat_index] = self._normalize_player_name(player_name)

            if seat_index is None:
                normalized_name = self._normalize_player_name(player_name)
                # A room code plus the original display name can recover a seat
                # on a new browser after both human seats have already been
                # allocated. The stronger token path remains preferred.
                if room.players_joined >= len(HUMAN_ROOM_SEATS):
                    matching_seats = [
                        existing_seat
                        for existing_seat, existing_name in room.seat_names.items()
                        if existing_name.casefold() == normalized_name.casefold()
                    ]
                    if len(matching_seats) == 1:
                        seat_index = matching_seats[0]
                        token = room.seat_tokens[seat_index]

            if seat_index is None:
                normalized_name = self._normalize_player_name(player_name)
                for candidate in HUMAN_ROOM_SEATS:
                    if candidate not in room.seat_tokens:
                        seat_index = candidate
                        token = secrets.token_urlsafe(24)
                        room.seat_tokens[seat_index] = token
                        room.seat_names[seat_index] = normalized_name
                        break

            if seat_index is None:
                raise RoomFullError("Room is full.")

            self._ensure_game_created_locked(room)
            room.updated_at = time.time()
            self._persist_session_locked(room)

            return RoomAssignment(
                room_code=room.code,
                seat_index=seat_index,
                player_token=token,
                game_id=room.game_id,
                seat_name=room.seat_names.get(seat_index, f"P{seat_index+1}"),
                waiting_for_player=room.waiting_for_player,
                players_joined=room.players_joined,
            )

    def get_room_status(
        self, *, room_code: str, player_token: str | None = None
    ) -> dict[str, object]:
        with self._lock:
            self._cleanup_expired_locked()
            room = self._lookup_room_locked(room_code)

            seat_index: int | None = None
            token = (player_token or "").strip()
            if token:
                seat_index = self._find_seat_for_token_locked(room, token)

            return {
                "roomCode": room.code,
                "gameId": room.game_id,
                "seatIndex": seat_index,
                "seatName": room.seat_names.get(seat_index) if seat_index is not None else None,
                "waitingForPlayer": room.waiting_for_player,
                "playersJoined": room.players_joined,
                "biddingPolicy": room.bot_bidding_policy.to_public_dict(),
                "kPolicy": room.bot_k_policy.to_public_dict(),
                "botThinkTimeSeconds": room.bot_think_timeout_seconds,
            }

    def _validate_bot_think_seconds(self, value: float) -> float:
        seconds = float(value)
        if not MIN_BOT_THINK_SECONDS <= seconds <= MAX_BOT_THINK_SECONDS:
            raise RoomError(
                f"botThinkTimeSeconds must be between {MIN_BOT_THINK_SECONDS:g} "
                f"and {MAX_BOT_THINK_SECONDS:g}."
            )
        return seconds

    def get_chat_history(self, *, room_code: str) -> list[dict[str, object]]:
        with self._lock:
            self._cleanup_expired_locked()
            room = self._lookup_room_locked(room_code)
            return [dict(message) for message in room.chat_messages]

    def add_chat_message(
        self, *, room_code: str, player_token: str, text: str
    ) -> dict[str, object]:
        with self._lock:
            self._cleanup_expired_locked()
            room = self._lookup_room_locked(room_code)
            seat_index = self._find_seat_for_token_locked(
                room, player_token.strip()
            )
            if seat_index is None:
                raise RoomTokenError("Invalid room token.")

            cleaned = str(text).strip()
            if not cleaned:
                raise RoomError("Chat message cannot be empty.")
            if len(cleaned) > MAX_CHAT_MESSAGE_LENGTH:
                raise RoomError(
                    f"Chat messages must be at most {MAX_CHAT_MESSAGE_LENGTH} characters."
                )

            now = time.time()
            recent = room.chat_sent_at.setdefault(seat_index, deque())
            while recent and now - recent[0] >= CHAT_RATE_WINDOW_SECONDS:
                recent.popleft()
            if len(recent) >= CHAT_RATE_MAX_MESSAGES:
                raise RoomError("You are sending messages too quickly. Please wait.")
            recent.append(now)

            message = {
                "id": secrets.token_urlsafe(9),
                "seatIndex": seat_index,
                "senderName": room.seat_names.get(seat_index, f"P{seat_index + 1}"),
                "text": cleaned,
                "sentAtEpochMs": int(now * 1000),
            }
            room.chat_messages.append(message)
            room.updated_at = now
            self._persist_session_locked(room)
            return dict(message)

    def validate_player(self, *, room_code: str, player_token: str) -> tuple[Room, int]:
        with self._lock:
            self._cleanup_expired_locked()
            room = self._lookup_room_locked(room_code)
            seat_index = self._find_seat_for_token_locked(room, player_token.strip())
            if seat_index is None:
                raise RoomTokenError("Invalid room token.")
            room.updated_at = time.time()
            self._persist_session_locked(room)
            return room, seat_index

    def request_rematch(
        self, *, room_code: str, player_token: str
    ) -> RematchRequestResult:
        """
        Mark one human player as ready for rematch.
        Starts the next game in-place only after both human seats are ready.
        """
        with self._lock:
            self._cleanup_expired_locked()
            room = self._lookup_room_locked(room_code)
            seat_index = self._find_seat_for_token_locked(room, player_token.strip())
            if seat_index is None:
                raise RoomTokenError("Invalid room token.")
            if seat_index not in HUMAN_ROOM_SEATS:
                raise RoomError("Only human room seats can request rematch.")
            if room.game_id is None:
                raise RoomError("Game is not ready yet.")

            state = game_manager.get_game(room.game_id)
            if state is None:
                raise RoomError("Game not found.")
            if state.phase != "GAME_OVER":
                raise RoomError("Rematch is available only after game over.")

            room.rematch_ready_seats.add(seat_index)
            room.updated_at = time.time()
            ready = tuple(sorted(room.rematch_ready_seats))

            all_ready = all(seat in room.rematch_ready_seats for seat in HUMAN_ROOM_SEATS)
            if not all_ready:
                self._persist_session_locked(room)
                waiting_for = next(
                    seat for seat in HUMAN_ROOM_SEATS if seat not in room.rematch_ready_seats
                )
                return RematchRequestResult(
                    started=False,
                    waiting_for_seat=waiting_for,
                    ready_seats=ready,
                    starting_bidder_index=None,
                )

            next_starting_bidder = (state.starting_bidder_index + 1) % 4
            game_manager.restart_game_in_place(
                state, starting_bidder_index=next_starting_bidder
            )
            room.starting_bidder_index = next_starting_bidder
            room.rematch_ready_seats.clear()
            self._persist_session_locked(room)

            return RematchRequestResult(
                started=True,
                waiting_for_seat=None,
                ready_seats=(),
                starting_bidder_index=next_starting_bidder,
            )

    def persist_state(self, *, room_code: str, state) -> None:
        with self._lock:
            room = self._lookup_room_locked(room_code)
            if room.game_id != state.game_id:
                raise RoomError("Room game changed while persisting replay.")
            room.updated_at = time.time()
            replay_store.save(
                session=self._room_storage_payload(room),
                replay=build_replay_payload(state, room_code=room.code),
                state_storage=game_state_to_storage_dict(state),
            )


room_manager = RoomManager()
