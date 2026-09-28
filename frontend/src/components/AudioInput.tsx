import { useEffect, useRef, useState } from "react";
import { Mic, Square, Upload, Check } from "lucide-react";
import { errorText } from "../api";

/** Recording and transcription are drafts. Only the learner can send a report. */
export default function AudioInput({
  sessionId,
  disabled,
  onText,
}: {
  sessionId: string;
  disabled: boolean;
  onText: (text: string) => void;
}) {
  const [recording, setRecording] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [candidate, setCandidate] = useState("");
  const [info, setInfo] = useState("");
  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const timeout = useRef<number | undefined>(undefined);
  const upload = useRef<HTMLInputElement>(null);
  const live = useRef(true);
  const unavailable = useRef(disabled);
  const request = useRef<AbortController | null>(null);
  unavailable.current = disabled;
  useEffect(() => {
    live.current = true;
    return () => {
      live.current = false;
      request.current?.abort();
      window.clearTimeout(timeout.current);
      if (recorder.current?.state === "recording") recorder.current.stop();
      stream.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);
  useEffect(() => {
    if (!disabled) return;
    window.clearTimeout(timeout.current);
    request.current?.abort();
    if (recorder.current?.state === "recording") recorder.current.stop();
    stream.current?.getTracks().forEach((track) => track.stop());
    setRecording(false);
    setBusy(false);
  }, [disabled]);

  async function transcribe(blob: Blob) {
    if (unavailable.current || !live.current) return;
    if (blob.size > 10 * 1024 * 1024) {
      setError("Запись должна быть меньше 10 МБ.");
      return;
    }
    setBusy(true);
    setError("");
    setCandidate("");
    const controller = new AbortController();
    request.current?.abort();
    request.current = controller;
    try {
      // Browsers often label audio-only WebM/MP4 files as video containers.
      const mime =
        blob.type.replace(/^video\/(webm|mp4)/, "audio/$1") || "audio/wav";
      const response = await fetch(`/api/sessions/${sessionId}/transcribe`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": mime },
        body: blob,
        signal: controller.signal,
      });
      const result = await response.json();
      if (!response.ok)
        throw new Error(result.detail || "Не удалось распознать запись");
      if (!live.current || unavailable.current || controller.signal.aborted)
        return;
      setCandidate(result.text || "");
      setInfo(
        result.text
          ? `${result.model} · ${result.latency_seconds} с · локально`
          : "Речь не распознана. Повторите запись или введите текст.",
      );
    } catch (e) {
      if (live.current && !controller.signal.aborted) setError(errorText(e));
    } finally {
      if (live.current) setBusy(false);
    }
  }

  async function begin() {
    if (disabled || busy || recording) return;
    setError("");
    setInfo("");
    if (
      !navigator.mediaDevices?.getUserMedia ||
      typeof MediaRecorder === "undefined"
    ) {
      setError(
        "Браузер не поддерживает запись. Можно загрузить аудиофайл или ввести текст.",
      );
      return;
    }
    try {
      setBusy(true);
      stream.current = await navigator.mediaDevices.getUserMedia({
        audio: true,
      });
      if (!live.current || unavailable.current) {
        stream.current.getTracks().forEach((t) => t.stop());
        return;
      }
      const mime = [
        "audio/webm;codecs=opus",
        "audio/webm",
        "audio/mp4",
        "audio/ogg",
      ].find((t) => MediaRecorder.isTypeSupported(t));
      const next = new MediaRecorder(
        stream.current,
        mime ? { mimeType: mime } : undefined,
      );
      const chunks: Blob[] = [];
      next.ondataavailable = (e) => {
        if (e.data.size) chunks.push(e.data);
      };
      next.onstop = () => {
        window.clearTimeout(timeout.current);
        stream.current?.getTracks().forEach((t) => t.stop());
        if (live.current) {
          setRecording(false);
          if (!unavailable.current)
            void transcribe(new Blob(chunks, { type: next.mimeType }));
        }
      };
      next.start();
      recorder.current = next;
      setRecording(true);
      timeout.current = window.setTimeout(() => {
        if (next.state === "recording") next.stop();
      }, 90000);
    } catch (e) {
      stream.current?.getTracks().forEach((t) => t.stop());
      setError(
        "Нет доступа к микрофону. Разрешите его в браузере или введите доклад текстом.",
      );
    } finally {
      if (live.current) setBusy(false);
    }
  }

  return (
    <div className="audio-input">
      <div className="audio-actions">
        {recording ? (
          <button
            type="button"
            className="button small"
            onClick={() => recorder.current?.stop()}
          >
            <Square size={14} />
            Завершить запись
          </button>
        ) : (
          <button
            type="button"
            className="button small"
            disabled={disabled || busy}
            onClick={() => void begin()}
          >
            <Mic size={15} />
            {busy ? "Распознаём…" : "Записать доклад"}
          </button>
        )}
        <button
          type="button"
          className="icon-button"
          aria-label="Загрузить аудиозапись доклада"
          disabled={disabled || busy || recording}
          onClick={() => upload.current?.click()}
        >
          <Upload size={16} />
        </button>
        <input
          ref={upload}
          className="sr-only"
          type="file"
          disabled={disabled || busy || recording}
          accept="audio/wav,audio/webm,audio/ogg,audio/mp4,video/webm,video/mp4"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) void transcribe(file);
            e.target.value = "";
          }}
        />
      </div>
      {recording && (
        <small role="status">Идёт запись. Максимум 90 секунд.</small>
      )}
      {error && (
        <p className="audio-error" role="alert">
          {error}
        </p>
      )}
      {info && <small role="status">{info}</small>}
      {candidate && (
        <div className="transcript-review">
          <label>
            Проверьте адрес, числа и отрицания
            <textarea
              aria-label="Распознанный текст доклада"
              rows={4}
              maxLength={1999}
              value={candidate}
              onChange={(e) => setCandidate(e.target.value)}
            />
          </label>
          <button
            type="button"
            className="button small"
            disabled={disabled || candidate.length > 1999}
            onClick={() => {
              onText(candidate);
              setCandidate("");
              setInfo(
                "Текст добавлен в черновик. Передайте его отдельной кнопкой.",
              );
            }}
          >
            <Check size={14} />
            Вставить в доклад
          </button>
        </div>
      )}
      <small>Распознавание на локальном сервере. Аудио не сохраняется.</small>
    </div>
  );
}
