import { useCallback, useEffect, useRef, useState } from "react";
import type { VoiceWsMessage } from "../api/types";

export type VoiceStatus =
  | "idle"
  | "preparing"
  | "waiting"
  | "connecting"
  | "connected"
  | "reconnecting"
  | "error";

type RoomVoiceState = {
  signalingConnected: boolean;
  joined: boolean;
  status: VoiceStatus;
  muted: boolean;
  error: string | null;
  remoteAudioRef: React.RefObject<HTMLAudioElement | null>;
  joinVoice: () => Promise<void>;
  leaveVoice: () => void;
  toggleMute: () => void;
};

const ICE_SERVERS: RTCIceServer[] = [
  {
    urls: [
      "stun:stun.l.google.com:19302",
      "stun:stun1.l.google.com:19302",
    ],
  },
];

function voiceWebSocketUrl(roomCode: string, playerToken: string): string {
  const configured = (import.meta.env.VITE_WS_BASE_URL as string | undefined)?.replace(
    /\/$/,
    ""
  );
  const base =
    configured ||
    `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.hostname}:8000`;
  return `${base}/ws/rooms/${encodeURIComponent(roomCode)}/voice?token=${encodeURIComponent(playerToken)}`;
}

function microphoneErrorMessage(error: unknown): string {
  const name = error instanceof DOMException ? error.name : "";
  if (name === "NotAllowedError" || name === "SecurityError") {
    return "Microphone permission was blocked. Allow it in your browser settings.";
  }
  if (name === "NotFoundError") return "No microphone was found on this device.";
  if (name === "NotReadableError") return "Your microphone is being used by another app.";
  return "Could not start voice chat on this device.";
}

export function useRoomVoice(
  roomCode: string,
  playerToken: string,
  localSeatIndex: number
): RoomVoiceState {
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef<number | null>(null);
  const peerRef = useRef<RTCPeerConnection | null>(null);
  const localStreamRef = useRef<MediaStream | null>(null);
  const remoteAudioRef = useRef<HTMLAudioElement | null>(null);
  const pendingIceRef = useRef<RTCIceCandidateInit[]>([]);
  const joinedRef = useRef(false);
  const [signalingConnected, setSignalingConnected] = useState(false);
  const [joined, setJoined] = useState(false);
  const [status, setStatus] = useState<VoiceStatus>("idle");
  const [muted, setMuted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sendSignal = useCallback((message: object): boolean => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return false;
    ws.send(JSON.stringify(message));
    return true;
  }, []);

  const closePeer = useCallback(() => {
    const peer = peerRef.current;
    if (peer) {
      peer.onicecandidate = null;
      peer.ontrack = null;
      peer.onconnectionstatechange = null;
      peer.close();
    }
    peerRef.current = null;
    pendingIceRef.current = [];
    if (remoteAudioRef.current) remoteAudioRef.current.srcObject = null;
  }, []);

  const createPeer = useCallback((preservePendingIce = false): RTCPeerConnection => {
    const queuedIce = pendingIceRef.current;
    closePeer();
    if (preservePendingIce) pendingIceRef.current = queuedIce;
    const peer = new RTCPeerConnection({ iceServers: ICE_SERVERS });
    peerRef.current = peer;
    for (const track of localStreamRef.current?.getTracks() ?? []) {
      peer.addTrack(track, localStreamRef.current as MediaStream);
    }
    peer.onicecandidate = (event) => {
      sendSignal({
        type: "VOICE_ICE",
        candidate: event.candidate?.toJSON() ?? null,
      });
    };
    peer.ontrack = (event) => {
      const stream = event.streams[0] ?? new MediaStream([event.track]);
      if (remoteAudioRef.current) {
        remoteAudioRef.current.srcObject = stream;
        void remoteAudioRef.current.play().catch(() => undefined);
      }
    };
    peer.onconnectionstatechange = () => {
      if (peer !== peerRef.current || !joinedRef.current) return;
      if (peer.connectionState === "connected") {
        setStatus("connected");
        setError(null);
      } else if (peer.connectionState === "connecting" || peer.connectionState === "new") {
        setStatus("connecting");
      } else if (peer.connectionState === "disconnected") {
        setStatus("reconnecting");
      } else if (peer.connectionState === "failed") {
        setStatus("error");
        setError("The direct voice connection failed. Leave and try again.");
      }
    };
    return peer;
  }, [closePeer, sendSignal]);

  const applyPendingIce = useCallback(async (peer: RTCPeerConnection) => {
    const pending = pendingIceRef.current.splice(0);
    for (const candidate of pending) await peer.addIceCandidate(candidate);
  }, []);

  useEffect(() => {
    let disposed = false;

    const handleMessage = async (message: VoiceWsMessage) => {
      if (message.type === "VOICE_STATE") {
        const partnerPresent = message.activeSeatIndices.some(
          (seat) => seat !== localSeatIndex
        );
        if (joinedRef.current && !partnerPresent) {
          closePeer();
          setStatus("waiting");
        } else if (
          joinedRef.current &&
          partnerPresent &&
          peerRef.current?.connectionState !== "connected"
        ) {
          setStatus("connecting");
        }
        return;
      }

      if (message.type === "VOICE_START" && joinedRef.current) {
        try {
          setStatus("connecting");
          const peer = createPeer();
          const offer = await peer.createOffer();
          await peer.setLocalDescription(offer);
          sendSignal({ type: "VOICE_OFFER", description: peer.localDescription });
        } catch {
          setStatus("error");
          setError("Could not start the voice connection.");
        }
        return;
      }

      if (message.type === "VOICE_OFFER" && joinedRef.current) {
        try {
          setStatus("connecting");
          const peer = createPeer(true);
          await peer.setRemoteDescription(message.description);
          await applyPendingIce(peer);
          const answer = await peer.createAnswer();
          await peer.setLocalDescription(answer);
          sendSignal({ type: "VOICE_ANSWER", description: peer.localDescription });
        } catch {
          setStatus("error");
          setError("Could not answer the voice connection.");
        }
        return;
      }

      if (message.type === "VOICE_ANSWER" && joinedRef.current) {
        try {
          const peer = peerRef.current;
          if (!peer) return;
          await peer.setRemoteDescription(message.description);
          await applyPendingIce(peer);
        } catch {
          setStatus("error");
          setError("The voice connection could not be completed.");
        }
        return;
      }

      if (message.type === "VOICE_ICE" && message.candidate && joinedRef.current) {
        const peer = peerRef.current;
        if (peer?.remoteDescription) {
          await peer.addIceCandidate(message.candidate).catch(() => undefined);
        } else {
          pendingIceRef.current.push(message.candidate);
        }
        return;
      }

      if (message.type === "VOICE_PEER_LEFT") {
        closePeer();
        if (joinedRef.current) setStatus("waiting");
        return;
      }

      if (message.type === "ERROR") {
        if (message.message.includes("not in voice")) {
          if (joinedRef.current) setStatus("waiting");
          return;
        }
        setError(message.message);
      }
    };

    const connect = () => {
      if (disposed) return;
      const ws = new WebSocket(voiceWebSocketUrl(roomCode, playerToken));
      wsRef.current = ws;
      ws.onopen = () => {
        setSignalingConnected(true);
        setError(null);
        if (joinedRef.current) {
          closePeer();
          setStatus("waiting");
          sendSignal({ type: "VOICE_JOIN" });
        }
      };
      ws.onmessage = (event) => {
        const message = JSON.parse(event.data) as VoiceWsMessage;
        void handleMessage(message);
      };
      ws.onerror = () => {
        if (joinedRef.current) setStatus("reconnecting");
      };
      ws.onclose = () => {
        setSignalingConnected(false);
        if (joinedRef.current) {
          closePeer();
          setStatus("reconnecting");
        }
        if (!disposed) retryRef.current = window.setTimeout(connect, 1500);
      };
    };

    connect();
    return () => {
      disposed = true;
      if (retryRef.current !== null) window.clearTimeout(retryRef.current);
      joinedRef.current = false;
      wsRef.current?.close();
      wsRef.current = null;
      closePeer();
      for (const track of localStreamRef.current?.getTracks() ?? []) track.stop();
      localStreamRef.current = null;
    };
  }, [applyPendingIce, closePeer, createPeer, localSeatIndex, playerToken, roomCode, sendSignal]);

  const joinVoice = useCallback(async () => {
    if (joinedRef.current || status === "preparing") return;
    if (!navigator.mediaDevices?.getUserMedia || !window.RTCPeerConnection) {
      setStatus("error");
      setError("Voice chat is not supported by this browser.");
      return;
    }
    setStatus("preparing");
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
        video: false,
      });
      localStreamRef.current = stream;
      joinedRef.current = true;
      setJoined(true);
      setMuted(false);
      setStatus("waiting");
      if (!sendSignal({ type: "VOICE_JOIN" })) {
        setStatus("reconnecting");
      }
    } catch (caught) {
      joinedRef.current = false;
      setJoined(false);
      setStatus("error");
      setError(microphoneErrorMessage(caught));
    }
  }, [sendSignal, status]);

  const leaveVoice = useCallback(() => {
    if (joinedRef.current) sendSignal({ type: "VOICE_LEAVE" });
    joinedRef.current = false;
    setJoined(false);
    closePeer();
    for (const track of localStreamRef.current?.getTracks() ?? []) track.stop();
    localStreamRef.current = null;
    setMuted(false);
    setError(null);
    setStatus("idle");
  }, [closePeer, sendSignal]);

  const toggleMute = useCallback(() => {
    const nextMuted = !muted;
    for (const track of localStreamRef.current?.getAudioTracks() ?? []) {
      track.enabled = !nextMuted;
    }
    setMuted(nextMuted);
  }, [muted]);

  return {
    signalingConnected,
    joined,
    status,
    muted,
    error,
    remoteAudioRef,
    joinVoice,
    leaveVoice,
    toggleMute,
  };
}
