import { useState } from "react";
import { SetupPage } from "./pages/SetupPage";
import { RoomPage } from "./pages/RoomPage";

export default function App() {
  const [gameId, setGameId] = useState<string | null>(null);

  if (!gameId) {
    return <SetupPage onGameCreated={setGameId} />;
  }

  return <RoomPage gameId={gameId} />;
}