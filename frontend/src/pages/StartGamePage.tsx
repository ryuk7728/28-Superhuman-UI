import type { CSSProperties } from "react";
import "../styles/start-game.scss";

type Props = {
  onStart: () => void;
};

type DecoCard = {
  rank: string;
  suit: string;
  tone: "red" | "black";
  rotation: string;
};

const DECO_CARDS: DecoCard[] = [
  { rank: "J", suit: "♥", tone: "red", rotation: "-18deg" },
  { rank: "A", suit: "♠", tone: "black", rotation: "-8deg" },
  { rank: "Q", suit: "♦", tone: "red", rotation: "14deg" },
  { rank: "K", suit: "♣", tone: "black", rotation: "22deg" },
  { rank: "9", suit: "♣", tone: "black", rotation: "12deg" },
  { rank: "10", suit: "♥", tone: "red", rotation: "-5deg" },
  { rank: "8", suit: "♦", tone: "red", rotation: "-16deg" },
  { rank: "7", suit: "♠", tone: "black", rotation: "8deg" },
];

export function StartGamePage({ onStart }: Props) {
  return (
    <div className="start-game-page">
      <div className="felt-bg" />
      <div className="table-ring" />

      <div className="floating-cards" aria-hidden>
        {DECO_CARDS.map((card, idx) => (
          <div
            key={`${card.rank}-${card.suit}-${idx}`}
            className={`card-deco ${card.tone}`}
            data-suit={card.suit}
            style={{ "--r": card.rotation } as CSSProperties}
          >
            {card.rank}
          </div>
        ))}
      </div>

      <div className="stage">
        <div className="ornament">
          <div className="ornament-line" />
          <span className="ornament-suit">♠</span>
          <div className="ornament-diamond" />
          <span className="ornament-suit">♥</span>
          <div className="ornament-line right" />
        </div>

        <div className="title-wrap">
          <div className="number-badge">28</div>
          <span className="title-card-game">The Classic</span>
          <h1>
            <span>28</span> Card
            <br />
            Game
          </h1>
        </div>

        <div className="suits-row" aria-hidden>
          <span className="suit-icon black">♠</span>
          <span className="suit-icon red">♥</span>
          <span className="suit-icon red">♦</span>
          <span className="suit-icon black">♣</span>
        </div>

        <div className="btn-wrap">
          <button className="btn-start" onClick={onStart}>
            Start Game
          </button>
        </div>
      </div>
    </div>
  );
}

