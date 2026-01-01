import { useMemo, useState } from "react";
import type { LegalActions } from "../api/types";

type Props = {
  actions: LegalActions;
  onSubmitBid: (seatIndex: number, bidValue: number) => void;
};

export function BiddingPanel({ actions, onSubmitBid }: Props) {
  const [bid, setBid] = useState<string>("");

  const isR1 = actions.type === "BID_R1";
  const isR2 = actions.type === "BID_R2";

  const seat = useMemo(() => {
    if (isR1 || isR2) return actions.seatIndex;
    return null;
  }, [actions, isR1, isR2]);

  if (!(isR1 || isR2) || seat === null) return null;

  return (
    <div className="rounded border border-gray-200 p-3">
      <div className="font-semibold">
        {isR1 ? "Bidding Round 1" : "Bidding Round 2"} — Player {seat + 1}
      </div>

      <div className="mt-1 text-sm text-gray-700">
        Enter bid &gt; {actions.minBidExclusive} and ≤ {actions.maxBidInclusive}
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <input
          className="w-40 rounded border border-gray-300 p-2"
          value={bid}
          onChange={(e) => setBid(e.target.value)}
          placeholder="e.g. 16"
        />
        <button
          className="rounded bg-black px-3 py-2 text-white"
          type="button"
          onClick={() => {
            const n = Number(bid);
            onSubmitBid(seat, n);
            setBid("");
          }}
        >
          Submit Bid
        </button>

        {actions.canPass && (
          <button
            className="rounded border border-gray-300 px-3 py-2"
            type="button"
            onClick={() => onSubmitBid(seat, 0)}
          >
            Pass
          </button>
        )}

        {isR1 && actions.canRedeal && (
          <button
            className="rounded border border-gray-300 px-3 py-2"
            type="button"
            onClick={() => onSubmitBid(seat, -1)}
            title="Redeal request (not implemented yet)"
          >
            Redeal (-1)
          </button>
        )}
      </div>
    </div>
  );
}