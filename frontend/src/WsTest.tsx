import { useEffect, useMemo, useState } from "react";

export function WsTest() {
  const [messages, setMessages] = useState<string[]>([]);
  const wsUrl = useMemo(() => {
    const base = import.meta.env.VITE_WS_BASE_URL ?? "ws://localhost:8000";
    return `${base}/ws`;
  }, []);

  useEffect(() => {
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (ev) => {
      setMessages((m) => [...m, ev.data]);
    };

    ws.onopen = () => {
      ws.send("ping");
    };

    ws.onerror = () => {
      setMessages((m) => [...m, "ws error"]);
    };

    return () => {
      ws.close();
    };
  }, [wsUrl]);

  return (
    <div className="p-4">
      <div className="font-semibold">WS URL: {wsUrl}</div>
      <div className="mt-3 space-y-2">
        {messages.map((msg, i) => (
          <pre key={i} className="rounded bg-gray-100 p-2 text-sm">
            {msg}
          </pre>
        ))}
      </div>
    </div>
  );
}