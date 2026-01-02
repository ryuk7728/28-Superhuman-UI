from __future__ import annotations

import json
import sys

from app.engine.cards_adapter import from_card_id
from app.legacy import minimax as legacy


def main():
    if len(sys.argv) != 2:
        print("Usage: python -m app.scripts.replay_rollout_crash_dump <dump.json>")
        raise SystemExit(2)

    path = sys.argv[1]
    dump = json.loads(open(path, "r", encoding="utf-8").read())

    mm = dump["minimaxCall"]
    sim = dump["simulated"]

    s_cards = [from_card_id(cid) for cid in mm["sCardIds"]]

    players = []
    players_cards = sim["playersCardsCardIds"]
    for i in range(4):
        hand = [from_card_id(cid) for cid in players_cards[i] if cid is not None]
        players.append(
            {
                "cards": hand,
                "isTrump": i == (mm["finalBid"] - 1),
                "team": 1 if i % 2 == 0 else 2,
                "trump": None,
            }
        )

    playerTrump = (
        from_card_id(mm["playerTrumpCardId"]) if mm["playerTrumpCardId"] else None
    )
    if playerTrump is not None:
        players[mm["finalBid"] - 1]["trump"] = playerTrump

    reward_distribution = []

    print("Replaying dump:", path)
    print("Original exception:", dump["exception"]["type"], dump["exception"]["message"])
    print("\nSet breakpoints in app/legacy/minimax.py (actions/result/undo_result)")
    print("Then step into minimax_extended below.\n")

    legacy.minimax_extended(
        s_cards,
        True,
        True,
        mm["trumpPlayed"],
        s_cards,
        mm["trumpIndice"],
        mm["leaderIndex_playerChance"],
        players,
        mm["currentSuit"],
        mm["trumpReveal"],
        mm["trumpSuit"],
        mm["chose"],
        mm["finalBid"],
        playerTrump,
        -1,
        reward_distribution,
        0,
        0,
        mm["k"],
    )


if __name__ == "__main__":
    main()
