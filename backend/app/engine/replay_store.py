from __future__ import annotations

import json
import logging
import threading
from typing import Any

from app.settings import settings

logger = logging.getLogger(__name__)


class ReplayStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._memory_replays: dict[str, dict[str, Any]] = {}
        self._memory_sessions: dict[str, dict[str, Any]] = {}
        self._firestore_client = None

    @property
    def backend(self) -> str:
        return settings.replay_store

    def _client(self):
        if self._firestore_client is None:
            from google.cloud import firestore

            self._firestore_client = firestore.Client(project=settings.gcp_project_id)
        return self._firestore_client

    def save(
        self,
        *,
        session: dict[str, Any],
        replay: dict[str, Any],
        state_storage: dict[str, Any],
    ) -> None:
        room_code = str(session["roomCode"]).upper()
        replay_id = str(replay["replayId"])
        session_doc = dict(session)
        session_doc["currentReplayId"] = replay_id
        replay_doc = {
            "replayId": replay_id,
            "roomCode": room_code,
            "dealNumber": replay["dealNumber"],
            "status": replay["status"],
            "phase": replay["phase"],
            "revision": replay["revision"],
            "startedAtEpochMs": replay["startedAtEpochMs"],
            "updatedAtEpochMs": replay["updatedAtEpochMs"],
            "completedAtEpochMs": replay["completedAtEpochMs"],
            "playerNames": replay["playerNames"],
            "finalBidderSeat": replay["finalBidderSeat"],
            "finalBidValue": replay["finalBidValue"],
            "winnerTeam": replay["winnerTeam"],
            "team1Points": replay["team1Points"],
            "team2Points": replay["team2Points"],
            "team1Coolies": replay["team1Coolies"],
            "team2Coolies": replay["team2Coolies"],
            "replayJson": json.dumps(replay, separators=(",", ":")),
            "stateJson": json.dumps(state_storage, separators=(",", ":")),
        }

        if self.backend == "memory":
            with self._lock:
                self._memory_sessions[room_code] = session_doc
                self._memory_replays[replay_id] = replay_doc
            return
        if self.backend != "firestore":
            raise RuntimeError(f"Unsupported replay store: {self.backend!r}")

        client = self._client()
        batch = client.batch()
        batch.set(
            client.collection(settings.session_firestore_collection).document(room_code),
            session_doc,
        )
        batch.set(
            client.collection(settings.replay_firestore_collection).document(replay_id),
            replay_doc,
        )
        batch.commit()

    def save_session(self, session: dict[str, Any]) -> None:
        room_code = str(session["roomCode"]).upper()
        if self.backend == "memory":
            with self._lock:
                previous = self._memory_sessions.get(room_code, {})
                self._memory_sessions[room_code] = {**previous, **session}
            return
        self._client().collection(settings.session_firestore_collection).document(
            room_code
        ).set(session, merge=True)

    def load_session(self, room_code: str) -> dict[str, Any] | None:
        code = room_code.strip().upper()
        if self.backend == "memory":
            with self._lock:
                session = self._memory_sessions.get(code)
                if session is None:
                    return None
                result = dict(session)
                replay_id = result.get("currentReplayId")
                replay = self._memory_replays.get(str(replay_id)) if replay_id else None
                if replay:
                    result["stateStorage"] = json.loads(replay["stateJson"])
                return result

        snapshot = self._client().collection(
            settings.session_firestore_collection
        ).document(code).get()
        if not snapshot.exists:
            return None
        result = snapshot.to_dict() or {}
        replay_id = result.get("currentReplayId")
        if replay_id:
            replay_snapshot = self._client().collection(
                settings.replay_firestore_collection
            ).document(str(replay_id)).get()
            if replay_snapshot.exists:
                replay_doc = replay_snapshot.to_dict() or {}
                if replay_doc.get("stateJson"):
                    result["stateStorage"] = json.loads(replay_doc["stateJson"])
        return result

    def get_replay(self, room_code: str, deal_number: int | None = None) -> dict[str, Any] | None:
        code = room_code.strip().upper()
        replay_id = f"{code}-{deal_number:04d}" if deal_number is not None else None
        if self.backend == "memory":
            with self._lock:
                if replay_id is None:
                    session = self._memory_sessions.get(code) or {}
                    replay_id = session.get("currentReplayId")
                doc = self._memory_replays.get(str(replay_id)) if replay_id else None
                return json.loads(doc["replayJson"]) if doc else None

        client = self._client()
        if replay_id is None:
            session = client.collection(settings.session_firestore_collection).document(code).get()
            if not session.exists:
                return None
            replay_id = (session.to_dict() or {}).get("currentReplayId")
        if not replay_id:
            return None
        snapshot = client.collection(settings.replay_firestore_collection).document(
            str(replay_id)
        ).get()
        if not snapshot.exists:
            return None
        doc = snapshot.to_dict() or {}
        return json.loads(doc["replayJson"]) if doc.get("replayJson") else None

    def list_replays(self, *, limit: int = 50, room_code: str | None = None) -> list[dict[str, Any]]:
        normalized = room_code.strip().upper() if room_code else None
        excluded = {"replayJson", "stateJson"}
        if self.backend == "memory":
            with self._lock:
                docs = list(self._memory_replays.values())
            if normalized:
                docs = [doc for doc in docs if doc.get("roomCode") == normalized]
            docs.sort(key=lambda item: int(item.get("updatedAtEpochMs", 0)), reverse=True)
            return [{key: value for key, value in doc.items() if key not in excluded} for doc in docs[:limit]]

        from google.cloud import firestore

        query = self._client().collection(settings.replay_firestore_collection)
        if normalized:
            query = query.where("roomCode", "==", normalized)
            snapshots = list(query.stream())
            snapshots.sort(
                key=lambda item: int((item.to_dict() or {}).get("updatedAtEpochMs", 0)),
                reverse=True,
            )
            snapshots = snapshots[:limit]
        else:
            snapshots = list(
                query.order_by(
                    "updatedAtEpochMs", direction=firestore.Query.DESCENDING
                ).limit(limit).stream()
            )
        return [
            {key: value for key, value in (snapshot.to_dict() or {}).items() if key not in excluded}
            for snapshot in snapshots
        ]

    def clear_memory(self) -> None:
        with self._lock:
            self._memory_replays.clear()
            self._memory_sessions.clear()


replay_store = ReplayStore()
