import { useEffect, useMemo, useRef } from "react";
import { Card } from "./card/Card";
import type { CompletedCatch } from "../api/types";

type Props = {
  catches: CompletedCatch[];
  playerNames: string[] | Record<number, string>;
  onClose: () => void;
};

function playerName(
  names: string[] | Record<number, string>,
  seatIndex: number
): string {
  return names[seatIndex] || `Player ${seatIndex + 1}`;
}

function HistoryIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M3 12a9 9 0 1 0 3-6.7" />
      <path d="M3 4v5h5M12 7v5l3 2" />
    </svg>
  );
}

export function CatchHistoryModal({ catches, playerNames, onClose }: Props) {
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const newestFirst = useMemo(() => [...catches].reverse(), [catches]);

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeButtonRef.current?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [onClose]);

  return (
    <div className="catch-history-overlay" onMouseDown={onClose}>
      <section
        className="catch-history-sheet"
        role="dialog"
        aria-modal="true"
        aria-labelledby="catch-history-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="catch-history-header">
          <button
            ref={closeButtonRef}
            type="button"
            className="catch-history-close"
            onClick={onClose}
            aria-label="Close previous catch"
          >
            <span aria-hidden>×</span>
            <small>Close</small>
          </button>
          <div className="catch-history-heading">
            <span className="catch-history-heading-icon">
              <HistoryIcon />
            </span>
            <div>
              <p>Last completed</p>
              <h2 id="catch-history-title">Previous catch</h2>
            </div>
          </div>
        </header>

        <div className="catch-history-content">
          {newestFirst.map((completedCatch, catchIndex) => (
            <article
              className="catch-history-item"
              key={completedCatch.catchNumber}
              data-latest={catchIndex === 0 ? "true" : undefined}
            >
              <div className="catch-history-summary">
                <div>
                  <span className="catch-history-number">
                    Catch {completedCatch.catchNumber}
                  </span>
                  {catchIndex === 0 ? (
                    <span className="catch-history-latest">Latest</span>
                  ) : null}
                </div>
                <p>
                  <strong>{playerName(playerNames, completedCatch.winnerSeatIndex)}</strong>
                  <span> won for {completedCatch.points} points</span>
                </p>
                <span className={`catch-history-team team-${completedCatch.winnerTeam}`}>
                  Team {completedCatch.winnerTeam}
                </span>
              </div>

              <div className="catch-history-plays">
                {completedCatch.plays.map((play, playIndex) => {
                  const isWinner = play.seatIndex === completedCatch.winnerSeatIndex;
                  const isLeader = play.seatIndex === completedCatch.leaderSeatIndex;
                  return (
                    <div
                      className={`catch-history-play ${isWinner ? "winner" : ""}`}
                      key={`${completedCatch.catchNumber}-${playIndex}`}
                    >
                      <div className="catch-history-player">
                        <span className="catch-history-order">{playIndex + 1}</span>
                        <div>
                          <strong>{playerName(playerNames, play.seatIndex)}</strong>
                          <small>P{play.seatIndex + 1}</small>
                        </div>
                        {isLeader ? <em>Led</em> : null}
                      </div>

                      <div className="catch-history-card-wrap">
                        <Card cardId={play.card.cardId} width={82} height={115} />
                        {isWinner ? <span className="winning-card-label">Winner</span> : null}
                        {play.wasTrump ? <span className="trump-card-label">Trump</span> : null}
                      </div>

                      <span className="catch-history-card-name">
                        {play.card.rank} of {play.card.suit}
                      </span>
                    </div>
                  );
                })}
              </div>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

export function CatchHistoryTrigger({
  count,
  onOpen,
}: {
  count: number;
  onOpen: () => void;
}) {
  if (count < 1) return null;

  return (
    <button
      type="button"
      className="catch-history-trigger"
      onClick={onOpen}
      aria-haspopup="dialog"
    >
      <HistoryIcon />
      <span>Previous catch</span>
    </button>
  );
}
