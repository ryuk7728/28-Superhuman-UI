from __future__ import annotations

import asyncio
import secrets

from fastapi import APIRouter, Header, HTTPException, Query, WebSocket

from app.engine.replay_store import replay_store
from app.settings import settings

router = APIRouter()


def _require_password(value: str | None) -> None:
    if value is None or not secrets.compare_digest(value, settings.replay_password):
        raise HTTPException(status_code=401, detail="Incorrect replay password.")


@router.post("/replays/auth")
def authenticate_replays(
    x_replay_password: str | None = Header(default=None),
) -> dict[str, bool]:
    _require_password(x_replay_password)
    return {"ok": True}


@router.get("/replays")
def list_replays(
    limit: int = Query(default=50, ge=1, le=200),
    room_code: str | None = Query(default=None, alias="roomCode"),
    x_replay_password: str | None = Header(default=None),
) -> dict[str, object]:
    _require_password(x_replay_password)
    return {"replays": replay_store.list_replays(limit=limit, room_code=room_code)}


@router.get("/replays/{room_code}")
def get_latest_replay(
    room_code: str,
    x_replay_password: str | None = Header(default=None),
) -> dict[str, object]:
    _require_password(x_replay_password)
    replay = replay_store.get_replay(room_code)
    if replay is None:
        raise HTTPException(status_code=404, detail="Replay not found.")
    return replay


@router.get("/replays/{room_code}/{deal_number}")
def get_replay(
    room_code: str,
    deal_number: int,
    x_replay_password: str | None = Header(default=None),
) -> dict[str, object]:
    _require_password(x_replay_password)
    replay = replay_store.get_replay(room_code, deal_number)
    if replay is None:
        raise HTTPException(status_code=404, detail="Replay not found.")
    return replay


@router.websocket("/ws/replays/{room_code}")
async def replay_live(websocket: WebSocket, room_code: str) -> None:
    supplied = websocket.query_params.get("password")
    if supplied is None or not secrets.compare_digest(supplied, settings.replay_password):
        await websocket.close(code=4401, reason="Incorrect replay password")
        return
    raw_deal = websocket.query_params.get("deal")
    deal_number = int(raw_deal) if raw_deal and raw_deal.isdigit() else None
    await websocket.accept()

    last_marker: tuple[object, object] | None = None
    try:
        while True:
            replay = await asyncio.to_thread(
                lambda: replay_store.get_replay(room_code, deal_number)
            )
            if replay is not None:
                marker = (replay.get("revision"), replay.get("updatedAtEpochMs"))
                if marker != last_marker:
                    await websocket.send_json({"type": "REPLAY_UPDATE", "replay": replay})
                    last_marker = marker
            elif last_marker is None:
                await websocket.send_json(
                    {"type": "WAITING", "message": "Waiting for the first saved game state."}
                )
                last_marker = ("waiting", None)
            await asyncio.sleep(0.75)
    except Exception:
        return
