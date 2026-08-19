/**
 * GameOverModal - End of game overlay
 *
 * Features:
 * - Shows win/lose result
 * - Cumulative coolies and final deal points
 * - New game button
 */

import React from "react";
import "../../styles/panels.scss";

export interface GameOverModalProps {
  didWin: boolean;
  humanScore: number;
  botScore: number;
  humanPoints: number;
  botPoints: number;
  bidValue: number;
  biddingTeam: "humans" | "bots";
  onNewGame: () => void;
  newGameDisabled?: boolean;
  newGameLabel?: string;
  statusMessage?: string | null;
  replayUrl?: string | null;
}

export const GameOverModal: React.FC<GameOverModalProps> = ({
  didWin,
  humanScore,
  botScore,
  humanPoints,
  botPoints,
  bidValue,
  biddingTeam,
  onNewGame,
  newGameDisabled = false,
  newGameLabel = "New Game",
  statusMessage = null,
  replayUrl = null,
}) => {
  const bidderWon =
    (biddingTeam === "humans" && humanPoints >= bidValue) ||
    (biddingTeam === "bots" && botPoints >= bidValue);

  return (
    <div className="game-over-overlay">
      <div className="game-over-modal">
        <div className={`result-title ${didWin ? "win" : "lose"}`}>
          {didWin ? "You Win!" : "You Lose"}
        </div>

        <div className="result-details">
          <div className="score-line">
            <strong>Coolies:</strong> You {humanScore} - {botScore} Bots
          </div>
          <div className="score-line">
            <strong>Points:</strong> You {humanPoints} - {botPoints} Bots
          </div>
          <div className="score-line">
            <strong>Bid:</strong> {bidValue} by {biddingTeam === "humans" ? "You" : "Bots"}
            {" - "}
            {bidderWon ? "Made!" : "Failed!"}
          </div>
        </div>

        {statusMessage ? <div className="rematch-status">{statusMessage}</div> : null}

        <div className="game-over-actions">
          {replayUrl ? (
            <a className="replay-game-btn" href={replayUrl} target="_blank" rel="noreferrer">
              View full replay
            </a>
          ) : null}
          <button className="new-game-btn" onClick={onNewGame} disabled={newGameDisabled}>
            {newGameLabel}
          </button>
        </div>
      </div>
    </div>
  );
};

export default GameOverModal;
