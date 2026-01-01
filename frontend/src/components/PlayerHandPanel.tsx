import { useMemo, useState } from "react";
import type { Card } from "../api/types";

type Props = {
  title: string;
  cards: Card[];
};

export function PlayerHandPanel({ title, cards }: Props) {
  const [show, setShow] = useState(false);

  const eyeLabel = useMemo(() => (show ? "Hide" : "Show"), [show]);

  return (
    <div className="rounded border border-gray-200 p-3">
      <div className="flex items-center justify-between">
        <div className="font-semibold">{title}</div>
        <button
          className="rounded border border-gray-300 px-2 py-1 text-sm"
          onClick={() => setShow((s) => !s)}
          type="button"
        >
          {eyeLabel}
        </button>
      </div>

      <div className="mt-2 text-sm text-gray-600">
        Cards: {cards.length}
      </div>

      {show && (
        <ul className="mt-2 list-disc pl-5 text-sm">
          {cards.map((c) => (
            <li key={c.cardId}>{c.label}</li>
          ))}
        </ul>
      )}
    </div>
  );
}