import { useCallback, useEffect, useState } from "react";
import { http } from "./api/http";
import { PLAYER_NAMES } from "./config/constants";
import { GameRoomPage } from "./pages/GameRoomPage";
import { RoomPage } from "./pages/RoomPage";
import { StartGamePage } from "./pages/StartGamePage";
import { TestPage } from "./pages/TestPage";
import { TestArenaPage } from "./pages/TestArenaPage";
import { GamePage } from "./pages/GamePage";

// Set to true to show the Phase 1 test page, false for normal app
const SHOW_TEST_PAGE = false;
// Set to true to show the new Arena test page (Step 2)
const SHOW_ARENA_TEST = false;
// Set to true to use the old debug RoomPage, false for new visual GameRoomPage
const USE_OLD_ROOM_PAGE = false;
// Set to true to use the NEW integrated GamePage (Step 5)
const USE_NEW_GAME_PAGE = true;

export default function App() {
  const [hasStarted, setHasStarted] = useState(false);
  const [gameId, setGameId] = useState<string | null>(null);
  const [startingBidderIndex, setStartingBidderIndex] = useState(0);
  const [creatingGame, setCreatingGame] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const createGame = useCallback(async (starterSeat: number) => {
    setCreateError(null);
    setCreatingGame(true);

    try {
      const res = await http.post("/games/auto", {
        startingBidderIndex: starterSeat,
      });
      setGameId(res.data.gameId as string);
    } catch (e: unknown) {
      const err = e as {
        response?: { data?: { detail?: string } };
        message?: string;
      };
      const msg = err?.response?.data?.detail ?? err?.message ?? "Failed to create game";
      setCreateError(String(msg));
    } finally {
      setCreatingGame(false);
    }
  }, []);

  useEffect(() => {
    if (SHOW_TEST_PAGE || SHOW_ARENA_TEST || !hasStarted || gameId || creatingGame) {
      return;
    }
    void createGame(startingBidderIndex);
  }, [hasStarted, gameId, creatingGame, startingBidderIndex, createGame]);

  const handleGameEnd = useCallback(() => {
    setGameId(null);
    setStartingBidderIndex((prev) => (prev + 1) % 4);
  }, []);

  // For testing Phase 1 components
  if (SHOW_TEST_PAGE) {
    return <TestPage />;
  }

  // For testing new Arena components (Step 2)
  if (SHOW_ARENA_TEST) {
    return <TestArenaPage />;
  }

  if (!hasStarted) {
    return <StartGamePage onStart={() => setHasStarted(true)} />;
  }

  if (!gameId) {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          minHeight: "100vh",
          background: "#0d3d17",
          color: "white",
          flexDirection: "column",
          gap: 12,
          padding: 24,
          textAlign: "center",
        }}
      >
        <div style={{ fontSize: 24, fontWeight: 700 }}>
          {creatingGame ? "Creating game..." : "Preparing next game..."}
        </div>
        <div style={{ opacity: 0.8 }}>
          Starter: {PLAYER_NAMES[startingBidderIndex]}
        </div>
        {createError && (
          <>
            <div style={{ color: "#fca5a5", maxWidth: 640 }}>{createError}</div>
            <button
              onClick={() => void createGame(startingBidderIndex)}
              style={{
                border: 0,
                borderRadius: 10,
                padding: "10px 18px",
                fontWeight: 700,
                cursor: "pointer",
              }}
            >
              Retry
            </button>
          </>
        )}
      </div>
    );
  }

  // Use the new integrated GamePage (Step 5)
  if (USE_NEW_GAME_PAGE) {
    return <GamePage gameId={gameId} onGameEnd={handleGameEnd} />;
  }

  // Use new visual game room or old debug room
  if (USE_OLD_ROOM_PAGE) {
    return <RoomPage gameId={gameId} />;
  }

  return <GameRoomPage gameId={gameId} onGameEnd={handleGameEnd} />;
}
