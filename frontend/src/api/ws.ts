export function connectGameWs(gameId: string): WebSocket {
  const base = import.meta.env.VITE_WS_BASE_URL ?? "ws://localhost:8000";
  return new WebSocket(`${base}/ws/games/${gameId}`);
}