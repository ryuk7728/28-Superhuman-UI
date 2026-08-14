import { useRoomVoice, type VoiceStatus } from "../hooks/useRoomVoice";

type Props = {
  roomCode: string;
  playerToken: string;
  localSeatIndex: number;
};

const STATUS_LABELS: Record<VoiceStatus, string> = {
  idle: "Voice",
  preparing: "Opening mic",
  waiting: "Waiting for partner",
  connecting: "Connecting",
  connected: "Voice connected",
  reconnecting: "Reconnecting",
  error: "Voice issue",
};

function MicIcon({ muted = false }: { muted?: boolean }) {
  return muted ? (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m4 4 16 16M9 9v3a3 3 0 0 0 4.5 2.6M15 10V7a3 3 0 0 0-5.6-1.5M5 11v1a7 7 0 0 0 11.2 5.6M19 11v1a7 7 0 0 1-.4 2.3M12 19v3M8 22h8" />
    </svg>
  ) : (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="9" y="3" width="6" height="12" rx="3" />
      <path d="M5 11v1a7 7 0 0 0 14 0v-1M12 19v3M8 22h8" />
    </svg>
  );
}

function HangUpIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5.2 15.4c4.5-3.2 9.1-3.2 13.6 0M7.4 14l-1.8-3M16.6 14l1.8-3" />
    </svg>
  );
}

export function RoomVoice({ roomCode, playerToken, localSeatIndex }: Props) {
  const {
    signalingConnected,
    joined,
    status,
    muted,
    error,
    remoteAudioRef,
    joinVoice,
    leaveVoice,
    toggleMute,
  } = useRoomVoice(roomCode, playerToken, localSeatIndex);
  const label = STATUS_LABELS[status];

  return (
    <aside className={`room-voice ${joined ? "joined" : ""}`}>
      <audio ref={remoteAudioRef} autoPlay playsInline />

      {!joined ? (
        <>
          {error ? (
            <div className="room-voice-notice" role="alert" title={error}>
              {error}
            </div>
          ) : null}
          <button
            type="button"
            className="room-voice-join"
            onClick={() => void joinVoice()}
            disabled={!signalingConnected || status === "preparing"}
            aria-label={status === "preparing" ? "Opening microphone" : "Join voice chat"}
            title={signalingConnected ? "Join voice chat" : "Voice service reconnecting"}
          >
            <MicIcon />
            <span>{status === "preparing" ? label : "Voice"}</span>
          </button>
        </>
      ) : (
        <div className="room-voice-bar" role="group" aria-label="Voice chat controls">
          <div className="room-voice-status" title={error ?? label} aria-live="polite">
            <i className={status} />
            <span>{label}</span>
          </div>
          <button
            type="button"
            className={muted ? "muted" : ""}
            onClick={toggleMute}
            aria-label={muted ? "Unmute microphone" : "Mute microphone"}
            title={muted ? "Unmute" : "Mute"}
          >
            <MicIcon muted={muted} />
          </button>
          <button
            type="button"
            className="leave"
            onClick={leaveVoice}
            aria-label="Leave voice chat"
            title="Leave voice"
          >
            <HangUpIcon />
          </button>
        </div>
      )}
    </aside>
  );
}
