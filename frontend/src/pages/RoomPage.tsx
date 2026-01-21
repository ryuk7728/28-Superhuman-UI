import { useEffect, useRef, useState } from "react";
import type { GameState, LegalActions, WsMessage } from "../api/types";
import { connectGameWs } from "../api/ws";
import { BiddingPanel } from "../components/BiddingPanel";
import { ManualDealRestPanel } from "../components/ManualDealRestPanel";
import { PlayPanel } from "../components/PlayPanel";
import { PlayerHandPanel } from "../components/PlayerHandPanel";
import { TrumpSelectPanel } from "../components/TrumpSelectPanel";

type Props = {
  gameId: string;
};

export function RoomPage({ gameId }: Props) {
  const wsRef = useRef<WebSocket | null>(null);

  const [state, setState] = useState<GameState | null>(null);
  const [legal, setLegal] = useState<LegalActions | null>(null);

  const [error, setError] = useState<string | null>(null);
  const [warning, setWarning] = useState<string | null>(null);
  const [status, setStatus] = useState<"connecting" | "open" | "closed">(
    "connecting"
  );

  useEffect(() => {
    setError(null);
    setWarning(null);
    setStatus("connecting");
    setState(null);
    setLegal(null);

    const ws = connectGameWs(gameId);
    wsRef.current = ws;

    let gotState = false;
    let disposed = false;

    const stateTimeout = window.setTimeout(() => {
      if (!disposed && !gotState) {
        setError("Timed out waiting for game state over WebSocket.");
      }
    }, 2000);

    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data) as WsMessage;

        if (msg.type === "STATE_UPDATE") {
          gotState = true;
          setState(msg.state);
          setWarning(null);
          return;
        }

        if (msg.type === "LEGAL_ACTIONS") {
          setLegal(msg.actions);
          return;
        }

        if (msg.type === "ERROR") {
          setError(msg.message);
          return;
        }

        if (msg.type === "GAME_ABORTED") {
          setError(`Game aborted: ${msg.reason}. Returning to setup...`);
          // Hard redirect to setup/home (simplest, no router assumptions)
          window.setTimeout(() => {
            window.location.href = "/";
          }, 200);
          return;
        }

        setWarning("Received unknown WS message type.");
      } catch {
        setWarning("Received non-JSON WS message.");
      }
    };

    ws.onopen = () => {
      setStatus("open");
      ws.send(JSON.stringify({ type: "GET_STATE" }));
    };

    ws.onerror = () => {
      if (!disposed) {
        setWarning("WebSocket reported an error (may be transient in dev).");
      }
    };

    ws.onclose = () => {
      setStatus("closed");
      if (disposed) return;

      if (gotState) {
        setWarning("WebSocket closed (state was received).");
        return;
      }

      setWarning("WebSocket closed before receiving state (may retry in dev).");
    };

    return () => {
      disposed = true;
      window.clearTimeout(stateTimeout);

      if (wsRef.current === ws) {
        wsRef.current = null;
      }

      ws.close();
    };
  }, [gameId]);

  function sendWs(payload: unknown) {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      setWarning("WebSocket not connected yet.");
      return;
    }
    ws.send(JSON.stringify(payload));
  }

  // Bidding actions
  function onSubmitBid(seatIndex: number, bidValue: number) {
    sendWs({ type: "SUBMIT_BID", seatIndex, bidValue });
  }

  // Trump selection action
  function onSelectTrump(seatIndex: number, cardId: string) {
    sendWs({ type: "SELECT_TRUMP_CARD", seatIndex, cardId });
  }

  // Manual deal rest (16 cards total: 4 per player)
  function onSubmitRestDeal(restHands: string[][]) {
    sendWs({ type: "SUBMIT_REST_DEAL", restHands });
  }

  // Play actions
  function onRevealChoice(seatIndex: number, reveal: boolean) {
    sendWs({ type: "CHOOSE_REVEAL_TRUMP", seatIndex, reveal });
  }

  function onPlayCard(seatIndex: number, cardId: string) {
    sendWs({ type: "PLAY_CARD", seatIndex, cardId });
  }

  if (error) {
    return (
      <div className="p-4">
        <div className="rounded border border-red-200 bg-red-50 p-3">
          {error}
        </div>
      </div>
    );
  }

  if (!state) {
    return (
      <div className="p-4">
        Connecting to game {gameId}... ({status})
        {warning && (
          <div className="mt-2 rounded border border-yellow-200 bg-yellow-50 p-2 text-sm">
            {warning}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl p-4">
      <div className="text-xl font-bold">Game Room</div>

      {warning && (
        <div className="mt-3 rounded border border-yellow-200 bg-yellow-50 p-2 text-sm">
          {warning}
        </div>
      )}

      <div className="mt-2 text-sm text-gray-700">GameId: {state.gameId}</div>
      <div className="mt-1 text-sm text-gray-700">Phase: {state.phase}</div>
      <div className="mt-1 text-sm text-gray-700">
        StartingBidderIndex: {state.startingBidderIndex}
      </div>
      <div className="mt-1 text-sm text-gray-700">TurnIndex: {state.turnIndex}</div>
      <div className="mt-1 text-sm text-gray-700">
        DrawPileCount: {state.drawPileCount}
      </div>

      <div className="mt-4 space-y-3">
        {legal && (legal.type === "BID_R1" || legal.type === "BID_R2") && (
          <BiddingPanel
            actions={legal}
            seatTypes={state.seatTypes}
            onSubmitBid={onSubmitBid}
          />
        )}

        {legal &&
          (legal.type === "SELECT_TRUMP_R1" ||
            legal.type === "SELECT_TRUMP_R2") && (
            <TrumpSelectPanel
              actions={legal}
              seatTypes={state.seatTypes}
              onSelect={onSelectTrump}
            />
          )}

        {legal && legal.type === "MANUAL_DEAL_REST" && (
          <ManualDealRestPanel
            remainingCardIds={legal.remainingCardIds}
            neededPerSeat={legal.neededPerSeat}
            onSubmit={onSubmitRestDeal}
          />
        )}

        <PlayPanel
          state={state}
          actions={legal}
          onRevealChoice={onRevealChoice}
          onPlayCard={onPlayCard}
        />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
        {state.players.map((p) => (
          <PlayerHandPanel
            key={p.seatIndex}
            title={`Player ${p.seatIndex + 1} (Team ${p.team})${
              p.isBidder ? " — Bidder" : ""
            }`}
            cards={p.cards}
          />
        ))}
      </div>

      <div className="mt-6 rounded border border-gray-200 p-3">
        <div className="font-semibold">Event log</div>
        <ul className="mt-2 list-disc pl-5 text-sm">
          {state.eventLog.map((e, i) => (
            <li key={i}>{e}</li>
          ))}
        </ul>
      </div>

      <div className="mt-6 rounded border border-gray-200 p-3">
        <div className="font-semibold">Raw state</div>
        <pre className="mt-2 overflow-auto rounded bg-gray-100 p-2 text-xs">
          {JSON.stringify({ state, legal }, null, 2)}
        </pre>
      </div>
    </div>
  );
}