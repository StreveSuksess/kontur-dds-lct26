import { useState } from "react";
import { Sparkles } from "lucide-react";
import { api, errorText } from "../api";
type Advice = {
  model: string;
  latency_seconds: number;
  suggestions: { criterion_id: string; observation: string; quote: string }[];
  discarded_unsupported: number;
  message?: string;
};
export default function AiReview({ sessionId }: { sessionId: string }) {
  const [result, setResult] = useState<Advice | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  return (
    <section className="panel teacher-review ai-review">
      <div className="section-heading">
        <div>
          <h2>Экспериментальная проверка спорного текста</h2>
          <p>
            Малая локальная модель может ошибаться даже при точной цитате. Она
            рассматривает только спорные смысловые критерии; баллы не изменяет.
          </p>
        </div>
        <button
          className="button"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            setError("");
            try {
              setResult(
                await api<Advice>(
                  `/sessions/${sessionId}/ai-review`,
                  "POST",
                  {},
                ),
              );
            } catch (e) {
              setError(errorText(e));
            } finally {
              setBusy(false);
            }
          }}
        >
          <Sparkles size={17} />
          {busy ? "Проверяем текст…" : "Запросить замечания"}
        </button>
      </div>
      {error && (
        <div className="notice warning" role="alert">
          {error}
        </div>
      )}
      {result && (
        <>
          <small>
            {result.model} · {result.latency_seconds} с · требуется экспертная
            проверка
          </small>
          {result.suggestions.length ? (
            result.suggestions.map((s, i) => (
              <div className="ai-suggestion" key={i}>
                <blockquote>{s.quote}</blockquote>
                <p>{s.observation}</p>
                <small>Критерий: {s.criterion_id}</small>
              </div>
            ))
          ) : (
            <p>
              {result.message ||
                "Модель не вернула замечаний с проверяемыми цитатами."}{" "}
              Это не подтверждает отсутствие ошибок.
            </p>
          )}
          {result.discarded_unsupported > 0 && (
            <small>
              Исключены предложения без подтверждённой цитаты:{" "}
              {result.discarded_unsupported}.
            </small>
          )}
        </>
      )}
    </section>
  );
}
