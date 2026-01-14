import { useMemo, useState } from "react";
import { http } from "../api/http";
import { CardButton } from "../components/CardButton";

const SUITS = ["Hearts", "Clubs", "Diamonds", "Spades"] as const;
const RANKS = [
  "Seven",
  "Eight",
  "Queen",
  "King",
  "Ten",
  "Ace",
  "Nine",
  "Jack",
] as const;

function cardId(suit: string, rank: string) {
  return `${suit}_${rank}`;
}

function cardLabel(suit: string, rank: string) {
  return `${rank} of ${suit}`;
}

type Props = {
  onGameCreated: (gameId: string) => void;
};

export function SetupPage({ onGameCreated }: Props) {
  const [startingBidderIndex, setStartingBidderIndex] = useState(0);
  const [activePlayer, setActivePlayer] = useState(0);
  const [hands, setHands] = useState<string[][]>([[], [], [], []]);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const allCards = useMemo(() => {
    const out: Array<{ id: string; label: string }> = [];
    for (const suit of SUITS) {
      for (const rank of RANKS) {
        out.push({ id: cardId(suit, rank), label: cardLabel(suit, rank) });
      }
    }
    return out;
  }, []);

  const used = useMemo(() => {
    return new Set(hands.flat());
  }, [hands]);

  function addCardToActive(cid: string) {
    setHands((prev) => {
      const next = prev.map((h) => [...h]);
      if (next[activePlayer].includes(cid)) return prev;
      if (next[activePlayer].length >= 4) return prev;
      if (used.has(cid)) return prev;
      next[activePlayer].push(cid);
      return next;
    });
  }

  function removeCard(cid: string) {
    setHands((prev) => {
      const next = prev.map((h) => h.filter((x) => x !== cid));
      return next;
    });
  }

  async function createGame() {
    setError(null);

    const ok = hands.every((h) => h.length === 4);
    if (!ok) {
      setError("Each player must have exactly 4 cards.");
      return;
    }

    setCreating(true);
    try {
      const res = await http.post("/games", {
        startingBidderIndex,
        first4Hands: hands,
      });
      onGameCreated(res.data.gameId as string);
    } catch (e: any) {
      const msg =
        e?.response?.data?.detail ??
        e?.message ??
        "Failed to create game";
      setError(String(msg));
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="mx-auto max-w-5xl p-4">
      <div className="text-xl font-bold">28 Setup (Manual first-4)</div>

      <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="rounded border border-gray-200 p-3">
          <div className="font-semibold">Starting bidder</div>
          <select
            className="mt-2 w-full rounded border border-gray-300 p-2"
            value={startingBidderIndex}
            onChange={(e) => setStartingBidderIndex(Number(e.target.value))}
          >
            <option value={0}>Player 1 (index 0)</option>
            <option value={1}>Player 2 (index 1)</option>
            <option value={2}>Player 3 (index 2)</option>
            <option value={3}>Player 4 (index 3)</option>
          </select>

          <div className="mt-4 font-semibold">Assign cards to</div>
          <select
            className="mt-2 w-full rounded border border-gray-300 p-2"
            value={activePlayer}
            onChange={(e) => setActivePlayer(Number(e.target.value))}
          >
            <option value={0}>Player 1</option>
            <option value={1}>Player 2</option>
            <option value={2}>Player 3</option>
            <option value={3}>Player 4</option>
          </select>

          <button
            className="mt-4 w-full rounded bg-black px-3 py-2 text-white disabled:bg-gray-400"
            onClick={createGame}
            disabled={creating}
            type="button"
          >
            {creating ? "Creating..." : "Create Game"}
          </button>

          {error && (
            <div className="mt-3 rounded border border-red-200 bg-red-50 p-2 text-sm text-red-800">
              {error}
            </div>
          )}
        </div>

        <div className="rounded border border-gray-200 p-3">
          <div className="font-semibold">Current first-4 hands</div>
          <div className="mt-2 grid grid-cols-1 gap-2 text-sm">
            {hands.map((h, i) => (
              <div key={i} className="rounded border border-gray-100 p-2">
                <div className="font-semibold">
                  Player {i + 1} ({h.length}/4)
                </div>
                <div className="mt-1 flex flex-wrap gap-2">
                  {h.map((cid) => (
                    <button
                      key={cid}
                      className="rounded border border-gray-300 px-2 py-1"
                      onClick={() => removeCard(cid)}
                      type="button"
                      title="Click to remove"
                    >
                      {cid}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
          <div className="mt-2 text-xs text-gray-500">
            Tip: click a cardId chip to remove it.
          </div>
        </div>
      </div>

      <div className="mt-6 rounded border border-gray-200 p-3">
        <div className="font-semibold">Card picker (32 cards)</div>
        <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-4">
          {allCards.map((c) => (
            <CardButton
              key={c.id}
              label={c.label}
              disabled={used.has(c.id)}
              selected={hands[activePlayer].includes(c.id)}
              onClick={() => addCardToActive(c.id)}
            />
          ))}
        </div>
      </div>
    </div>
  );
}