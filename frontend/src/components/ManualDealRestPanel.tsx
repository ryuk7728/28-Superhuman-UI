import { useMemo, useState } from "react";

type Props = {
  remainingCardIds: string[];
  neededPerSeat: number;
  onSubmit: (restHands: string[][]) => void;
};

export function ManualDealRestPanel({
  remainingCardIds,
  neededPerSeat,
  onSubmit,
}: Props) {
  const [activeSeat, setActiveSeat] = useState(0);
  const [hands, setHands] = useState<string[][]>([[], [], [], []]);

  const used = useMemo(() => new Set(hands.flat()), [hands]);

  const canSubmit = useMemo(() => {
    if (hands.some((h) => h.length !== neededPerSeat)) return false;

    const flat = hands.flat();
    if (flat.length !== 4 * neededPerSeat) return false;
    if (new Set(flat).size !== flat.length) return false;

    const a = new Set(flat);
    const b = new Set(remainingCardIds);
    if (a.size !== b.size) return false;
    for (const x of a) if (!b.has(x)) return false;

    return true;
  }, [hands, neededPerSeat, remainingCardIds]);

  function addCard(cid: string) {
    setHands((prev) => {
      const next = prev.map((h) => [...h]);

      if (used.has(cid)) return prev;
      if (next[activeSeat].length >= neededPerSeat) return prev;

      next[activeSeat].push(cid);
      return next;
    });
  }

  function removeCard(seat: number, cid: string) {
    setHands((prev) => {
      const next = prev.map((h) => h.filter((x) => x !== cid));
      return next;
    });
  }

  function clear() {
    setHands([[], [], [], []]);
  }

  return (
    <div className="rounded border border-gray-200 p-3">
      <div className="font-semibold">
        Manual Deal Remaining Cards (4 per player)
      </div>

      <div className="mt-1 text-sm text-gray-700">
        Assign these remaining cards: {remainingCardIds.length}
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <div className="text-sm font-semibold">Assign to:</div>

        <select
          className="rounded border border-gray-300 p-2 text-sm"
          value={activeSeat}
          onChange={(e) => setActiveSeat(Number(e.target.value))}
        >
          <option value={0}>Player 1</option>
          <option value={1}>Player 2</option>
          <option value={2}>Player 3</option>
          <option value={3}>Player 4</option>
        </select>

        <button
          className="rounded border border-gray-300 px-3 py-2 text-sm"
          type="button"
          onClick={clear}
        >
          Clear
        </button>

        <button
          className="rounded bg-black px-3 py-2 text-sm text-white disabled:bg-gray-400"
          type="button"
          disabled={!canSubmit}
          onClick={() => onSubmit(hands)}
        >
          Confirm Deal
        </button>
      </div>

      <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
        {hands.map((h, i) => (
          <div key={i} className="rounded border border-gray-100 p-2">
            <div className="text-sm font-semibold">
              Player {i + 1} ({h.length}/{neededPerSeat})
            </div>

            <div className="mt-2 flex flex-wrap gap-2">
              {h.map((cid) => (
                <button
                  key={cid}
                  type="button"
                  className="rounded border border-gray-300 px-2 py-1 text-xs"
                  onClick={() => removeCard(i, cid)}
                  title="Click to remove"
                >
                  {cid}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-4 rounded border border-gray-200 p-3">
        <div className="text-sm font-semibold">Remaining card picker</div>

        <div className="mt-2 text-xs text-gray-600">
          Click cards to assign to the selected player. A card can be assigned
          only once.
        </div>

        <div className="mt-3 flex flex-wrap gap-2">
          {remainingCardIds.map((cid) => {
            const disabled =
              used.has(cid) || hands[activeSeat].length >= neededPerSeat;

            return (
              <button
                key={cid}
                type="button"
                disabled={disabled}
                onClick={() => addCard(cid)}
                className={[
                  "rounded border px-2 py-1 text-xs",
                  disabled
                    ? "border-gray-200 bg-gray-100 text-gray-400"
                    : "border-gray-300 bg-white hover:bg-gray-50",
                ].join(" ")}
                title={
                  used.has(cid)
                    ? "Already assigned"
                    : hands[activeSeat].length >= neededPerSeat
                      ? "This player already has 4 cards"
                      : "Click to assign"
                }
              >
                {cid}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}