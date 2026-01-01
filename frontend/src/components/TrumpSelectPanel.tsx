import type { LegalActions } from "../api/types";

type Props = {
  actions: LegalActions;
  onSelect: (seatIndex: number, cardId: string) => void;
};

export function TrumpSelectPanel({ actions, onSelect }: Props) {
  const isR1 = actions.type === "SELECT_TRUMP_R1";
  const isR2 = actions.type === "SELECT_TRUMP_R2";

  if (!(isR1 || isR2)) return null;

  return (
    <div className="rounded border border-gray-200 p-3">
      <div className="font-semibold">
        {isR1 ? "Select Trump Card (R1 Winner)" : "Select Trump Card (R2 Winner)"}
        {" — "}
        Player {actions.seatIndex + 1}
      </div>

      <div className="mt-2 flex flex-wrap gap-2">
        {actions.cardIds.map((cid) => (
          <button
            key={cid}
            className="rounded border border-gray-300 px-2 py-1 text-sm"
            type="button"
            onClick={() => onSelect(actions.seatIndex, cid)}
          >
            {cid}
          </button>
        ))}
      </div>

      <div className="mt-2 text-xs text-gray-500">
        This card is kept concealed and removed from the bidder’s hand (matches
        your engine model).
      </div>
    </div>
  );
}