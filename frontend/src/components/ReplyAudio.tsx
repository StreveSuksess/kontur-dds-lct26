import { useEffect, useRef, useState } from "react";
import { Volume2, Square } from "lucide-react";
import { errorText } from "../api";

export default function ReplyAudio({
  sessionId,
  eventId,
}: {
  sessionId: string;
  eventId: string;
}) {
  const [busy, setBusy] = useState(false),
    [playing, setPlaying] = useState(false),
    [error, setError] = useState("");
  const player = useRef<HTMLAudioElement | null>(null),
    url = useRef("");
  useEffect(
    () => () => {
      player.current?.pause();
      if (url.current) URL.revokeObjectURL(url.current);
    },
    [],
  );
  async function play() {
    if (playing) {
      player.current?.pause();
      setPlaying(false);
      return;
    }
    setBusy(true);
    setError("");
    try {
      if (!url.current) {
        const r = await fetch(
          `/api/sessions/${sessionId}/events/${eventId}/audio`,
          { credentials: "include" },
        );
        if (!r.ok) {
          const data = await r.json();
          throw new Error(data.detail || "Озвучка недоступна");
        }
        url.current = URL.createObjectURL(await r.blob());
      }
      player.current = new Audio(url.current);
      player.current.onended = () => setPlaying(false);
      await player.current.play();
      setPlaying(true);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <button
        type="button"
        className="text-button reply-audio"
        onClick={() => void play()}
        disabled={busy}
      >
        {playing ? <Square size={12} /> : <Volume2 size={13} />}{" "}
        {busy ? "Готовим голос…" : playing ? "Остановить" : "Прослушать ответ"}
      </button>
      {error && <small className="audio-error">{error}</small>}
    </>
  );
}
