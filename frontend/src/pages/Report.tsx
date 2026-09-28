import AiReview from "../components/AiReview";
import CriterionReview from "../components/CriterionReview";
import {
  CRITERION_LABELS,
  displayScore,
  firstCardDecision,
  firstStatusWithText,
  isReviewFinal,
  needsReview,
  reportLabel,
} from "../reportState";
import { useEffect, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  ChevronDown,
  Clock3,
  Download,
  FileCheck2,
  RefreshCw,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";
import { api, duration, errorText, formatDate } from "../api";
import type { Criterion, Event, Session, User } from "../types";
import { STATUS_LABELS } from "../types";
import {
  Badge,
  Empty,
  ErrorNotice,
  Loading,
  PageHeader,
} from "../components/UI";
const eventLabels: Record<string, string> = {
  session_started: "Задание начато",
  card_opened: "Карточка открыта",
  status_changed: "Изменён статус",
  call_started: "Исходящий вызов",
  call_ended: "Разговор завершён",
  trainee_message: "Сообщение учащегося",
  contact_message: "Ответ должностного лица",
  hint_used: "Использована подсказка",
  connection_restored: "Связь восстановлена",
  session_submitted: "Задание сдано",
  teacher_stopped: "Остановлено преподавателем",
  review_saved: "Экспертная оценка",
  criterion_review_saved: "Решение по критерию",
  draft_saved: "Черновик сохранён",
};
function traceDescription(event: Event, criteria: Criterion[]): string {
  const payload = event.payload;
  if (event.kind === "criterion_review_saved") {
    const current = payload.current as Record<string, unknown> | undefined;
    const previous = payload.previous as Record<string, unknown> | undefined;
    const title =
      criteria.find((c) => c.id === payload.criterion_id)?.title ?? "Критерий";
    const status = (value: unknown) =>
      value === "pass" || value === "fail" || value === "review"
        ? CRITERION_LABELS[value]
        : "неизвестно";
    return `${title}: ${previous ? `${status(previous.status)} → ` : ""}${status(current?.status)}. ${typeof current?.comment === "string" ? current.comment : ""}`;
  }
  if (event.kind === "review_saved") {
    const review = payload.review as Record<string, unknown> | undefined;
    return `Общий итог: ${typeof review?.score === "number" ? `${review.score} / 100` : "не указан"}. ${typeof review?.comment === "string" ? review.comment : ""}`;
  }
  if (event.kind === "status_changed")
    return `${STATUS_LABELS[String(payload.status)] || payload.status}: ${payload.comment || ""}`;
  if (event.kind === "call_started")
    return `Номер ${payload.phone} · ${payload.connected === false ? "соединение не установлено" : "учебный вызов"}`;
  return String(payload.text || payload.comment || payload.hint || "");
}
export default function ReportPage({
  id,
  user,
  navigate,
}: {
  id: string;
  user: User;
  navigate: (path: string) => void;
}) {
  const [session, setSession] = useState<Session | null>(null);
  const [error, setError] = useState("");
  const [score, setScore] = useState(0);
  const [comment, setComment] = useState("");
  const [scoreDirty, setScoreDirty] = useState(false);
  const [commentDirty, setCommentDirty] = useState(false);
  const [needsRecheck, setNeedsRecheck] = useState(false);
  const [rechecked, setRechecked] = useState(false);
  const [unsavedCriteria, setUnsavedCriteria] = useState<
    Record<string, boolean>
  >({});
  const [busy, setBusy] = useState(false);
  const [criterionBusy, setCriterionBusy] = useState(false);
  const [localSave, setLocalSave] = useState<{
    criterionId: string;
    revision: number;
  } | null>(null);
  const [expanded, setExpanded] = useState<string[]>([]);
  const [evidence, setEvidence] = useState<string[]>([]);
  useEffect(() => {
    let current = true;
    api<Session>(`/sessions/${id}`)
      .then((s) => {
        if (!current || s.id !== id) return;
        setSession(s);
        setScore(s.report ? displayScore(s.report) : 0);
        setComment(s.report?.teacher_review?.comment || "");
      })
      .catch((e) => {
        if (current) setError(errorText(e));
      });
    return () => {
      current = false;
    };
  }, [id]);
  if (!session)
    return (
      <>
        <ErrorNotice text={error} />
        {!error && <Loading />}
      </>
    );
  const r = session.report;
  if (!r)
    return (
      <Empty title="Разбор пока недоступен">
        Он появится после завершения задания.
      </Empty>
    );
  const hasDecisions = Object.keys(r.criterion_reviews ?? {}).length > 0;
  const cardDecision = firstCardDecision(session.events);
  const firstUpdate = firstStatusWithText(session.events);
  const remaining = r.criteria.filter(
    (c) => (r.criterion_reviews?.[c.id]?.status ?? c.status) === "review",
  ).length;
  const criticalErrors =
    r.expert_assessment?.critical_errors ?? r.critical_errors;
  const mutationBusy = busy || criterionBusy;
  const hasUnsavedCriteria = Object.values(unsavedCriteria).some(Boolean);
  const onCriterionSaved = (updated: Session, criterionId: string) => {
    setSession(updated);
    setLocalSave({
      criterionId,
      revision: updated.report?.criterion_review_revision ?? 0,
    });
    if (!scoreDirty)
      setScore(
        updated.report?.expert_assessment?.score ?? updated.report?.score ?? 0,
      );
    if (scoreDirty || commentDirty) {
      setNeedsRecheck(true);
      setRechecked(false);
    }
    setError("");
  };
  return (
    <>
      <button
        className="text-button back-link"
        onClick={() => navigate("results")}
      >
        <ArrowLeft size={16} />К результатам
      </button>
      <PageHeader
        eyebrow="РАЗБОР УЧЕБНОЙ ПОПЫТКИ"
        title={session.scenario_title}
        description={`${session.student_name} · ${session.service} · ${formatDate(session.finished_at)}`}
        actions={
          <>
            <button
              className="button"
              disabled={mutationBusy}
              onClick={async () => {
                setBusy(true);
                try {
                  const updated = await api<Session>(`/sessions/${id}`);
                  setSession(updated);
                  if (!scoreDirty)
                    setScore(updated.report ? displayScore(updated.report) : 0);
                  if (!commentDirty)
                    setComment(updated.report?.teacher_review?.comment ?? "");
                  if (scoreDirty || commentDirty) {
                    setNeedsRecheck(true);
                    setRechecked(false);
                  }
                  setError("");
                } catch (e) {
                  setError(errorText(e));
                } finally {
                  setBusy(false);
                }
              }}
            >
              <RefreshCw size={17} />
              Обновить разбор
            </button>
            <a
              className="button"
              href={`/api/sessions/${id}/export.csv`}
              download
            >
              <Download size={17} />
              Отчёт CSV
            </a>
            {(user.role === "teacher" || session.mode === "practice") && (
              <button
                className="button primary"
                disabled={mutationBusy}
                onClick={async () => {
                  setBusy(true);
                  try {
                    const next = await api<Session>(
                      `/sessions/${id}/repeat`,
                      "POST",
                      {},
                    );
                    navigate(
                      user.role === "student"
                        ? `workspace/${next.id}`
                        : "sessions",
                    );
                  } catch (e) {
                    setError(errorText(e));
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                <RefreshCw size={17} />
                Назначить повтор
              </button>
            )}
          </>
        }
      />
      <ErrorNotice text={error} />
      {(session.status === "stopped" ||
        session.events.some((e) => e.kind === "teacher_stopped")) && (
        <div className="notice warning">
          Попытка остановлена преподавателем. Результат отражает только
          выполненную часть.
        </div>
      )}
      <div className="report-summary">
        <div
          className="score-circle"
          style={
            {
              "--score": `${displayScore(r) * 3.6}deg`,
            } as React.CSSProperties
          }
        >
          <div>
            <strong>{displayScore(r)}</strong>
            <span>
              {isReviewFinal(r) ? "итог / 100" : "предварительно / 100"}
            </span>
          </div>
        </div>
        <div className="report-summary-text">
          <Badge
            tone={
              isReviewFinal(r) && remaining === 0
                ? "mint"
                : needsReview(r) || remaining > 0
                  ? "amber"
                  : "blue"
            }
          >
            {reportLabel(r)}
          </Badge>
          <h2>
            {isReviewFinal(r)
              ? "Общий итог подтверждён"
              : hasDecisions
                ? "Покритериальный разбор"
                : "От действий — к пониманию"}
          </h2>
          {hasDecisions ? (
            <p>
              Исходная оценка: {r.score} / 100. После решений по критериям:{" "}
              {r.expert_assessment?.score ?? r.score} / 100.
            </p>
          ) : (
            <p>{r.summary}</p>
          )}
          {remaining > 0 && (
            <p className="unresolved-criteria">
              Требуют отдельного разбора: {remaining} критерия. Подтверждение
              общего балла не разрешает их автоматически.
            </p>
          )}
          <small>
            {r.mode === "hybrid"
              ? "Правила и локальный нейросетевой анализ"
              : "Проверка по учебным правилам"}{" "}
            · версия сценария {session.scenario_version}
          </small>
        </div>
        <div className="report-timing">
          <div>
            <Clock3 size={17} />
            <span>Открытие карточки</span>
            <strong>{duration(r.reaction_seconds)}</strong>
            <small>лимит {duration(session.response_limit_seconds)}</small>
          </div>
          <div>
            <FileCheck2 size={17} />
            <span>Первый статус с текстом</span>
            <strong>{duration(r.first_update_seconds ?? firstUpdate?.elapsed_seconds ?? null)}</strong>
            <small>лимит {duration(session.completion_limit_seconds)}</small>
          </div>
        </div>
        <p className="muted">Полная длительность учебной попытки: {duration(r.duration_seconds)}. Завершение работ этим лимитом не ограничено.</p>
      </div>
      <div className="notice" aria-label="Первое решение по карточке">
        <Clock3 size={20} />
        <div>
          <strong>Первое решение по карточке</strong>
          {cardDecision ? (
            <p>
              {STATUS_LABELS[String(cardDecision.payload.status)]}
              {" · "}
              {duration(cardDecision.elapsed_seconds)}
              {" от начала учебной попытки."}
            </p>
          ) : (
            <p>
              Не зафиксировано: в журнале нет действия «Принята» или «Не
              принята».
            </p>
          )}
          <p>
            Это отдельное наблюдение по журналу, оно не меняет оценку открытия
            карточки.
            {session.events.some(
              (event) => event.kind === "connection_restored",
            ) &&
              " Был разрыв связи: время серверной записи может отличаться от времени действия."}
          </p>
        </div>
      </div>
      {r.teacher_review_stale && (
        <div className="notice warning" role="status">
          <TriangleAlert size={20} />
          <div>
            <strong>Предыдущий итог устарел</strong>
            <p>
              После его подтверждения изменились решения по критериям. Проверьте
              разбор и подтвердите общий итог повторно. До этого попытка не
              участвует в рекомендациях.
            </p>
          </div>
        </div>
      )}
      {hasDecisions && !r.teacher_review && (
        <div className="notice info">
          Решения по критериям сохранены. Общий итог ещё не подтверждён
          преподавателем; попытка пока не участвует в рекомендациях.
        </div>
      )}
      {criticalErrors > 0 && (
        <div className="notice error">
          <TriangleAlert size={20} />
          <div>
            <strong>Есть критические замечания: {criticalErrors}</strong>
            <p>Они требуют отдельного разбора независимо от общего балла.</p>
          </div>
        </div>
      )}
      <details className="original-feedback" open={!hasDecisions}>
        <summary>
          {hasDecisions
            ? "Исходный автоматический разбор · до решений преподавателя"
            : "Первичная обратная связь по учебным правилам"}
        </summary>
        {hasDecisions && (
          <p className="muted">
            {r.summary} Эти исходные выводы сохранены для сравнения. Актуальные
            решения показаны в критериях ниже.
          </p>
        )}
        <div className="report-two-columns">
          <section className="panel feedback-panel">
            <h3>
              <CheckCircle2 size={20} />
              Что получилось
            </h3>
            {r.strengths.length ? (
              <ul>
                {r.strengths.map((v, i) => (
                  <li key={i}>{v}</li>
                ))}
              </ul>
            ) : (
              <p className="muted">
                Пока недостаточно выполненных действий для выделения сильных
                сторон.
              </p>
            )}
          </section>
          <section className="panel feedback-panel">
            <h3>
              <ArrowRight size={20} />
              Что отработать дальше
            </h3>
            {r.recommendations.length ? (
              <ul>
                {r.recommendations.map((v, i) => (
                  <li key={i}>{v}</li>
                ))}
              </ul>
            ) : (
              <p className="muted">
                Дополнительных рекомендаций по этой попытке нет.
              </p>
            )}
          </section>
        </div>
      </details>
      <section className="panel criteria-panel">
        <div className="section-heading">
          <div>
            <h2>Проверка по критериям</h2>
            <p>Откройте пункт, чтобы увидеть основание и связанные действия.</p>
          </div>
          <Badge>{r.criteria.length} критериев</Badge>
        </div>
        {r.criteria.map((c) => {
          const decision = r.criterion_reviews?.[c.id];
          const status = decision?.status ?? c.status;
          const evidenceIds = decision?.evidence_ids ?? c.evidence_ids;
          const selectedByTeacher =
            !!decision &&
            JSON.stringify(decision.evidence_ids) !==
              JSON.stringify(c.evidence_ids);
          return (
            <div className={`criterion ${status}`} key={c.id}>
              <button
                className="criterion-toggle"
                aria-expanded={expanded.includes(c.id)}
                onClick={() =>
                  setExpanded(
                    expanded.includes(c.id)
                      ? expanded.filter((v) => v !== c.id)
                      : [...expanded, c.id],
                  )
                }
              >
                <span className="criterion-icon">
                  {status === "pass" ? (
                    <CheckCircle2 size={20} />
                  ) : (
                    <TriangleAlert size={20} />
                  )}
                </span>
                <strong>{c.title}</strong>
                {unsavedCriteria[c.id] && (
                  <Badge tone="amber">Не сохранено</Badge>
                )}
                {c.critical && (
                  <Badge tone={status === "fail" ? "red" : "neutral"}>
                    {status === "fail" ? "Критично" : "Критический критерий"}
                  </Badge>
                )}
                <Badge
                  tone={
                    status === "pass"
                      ? "mint"
                      : status === "review"
                        ? "amber"
                        : "red"
                  }
                >
                  {CRITERION_LABELS[status]}
                  {decision ? " · преподаватель" : ""}
                </Badge>
                <span className="criterion-points">
                  {decision ? (status === "pass" ? c.max_points : 0) : c.points}{" "}
                  / {c.max_points}
                </span>
                <ChevronDown size={17} />
              </button>
              <div
                className="criterion-detail"
                hidden={!expanded.includes(c.id)}
              >
                {decision && (
                  <p className="original-criterion">
                    Исходный вывод системы: {CRITERION_LABELS[c.status]} ·{" "}
                    {c.points} / {c.max_points}. Ниже сохранены исходные данные
                    проверки.
                  </p>
                )}
                <div className="form-grid">
                  <div>
                    <span className="eyebrow">ФАКТИЧЕСКИ</span>
                    <p>{c.actual || "Нет данных"}</p>
                  </div>
                  <div>
                    <span className="eyebrow">ОЖИДАЛОСЬ</span>
                    <p>{c.expected}</p>
                  </div>
                </div>
                <p>{c.explanation}</p>
                <div className="row-between">
                  <small className="muted">Основание: {c.source}</small>
                  {evidenceIds.length > 0 && (
                    <button
                      className="text-button"
                      onClick={() => {
                        setEvidence(evidenceIds);
                        document
                          .getElementById("event-trace")
                          ?.scrollIntoView({ behavior: "smooth" });
                      }}
                    >
                      {selectedByTeacher
                        ? "События решения преподавателя"
                        : "События исходной проверки"}
                      <ArrowRight size={15} />
                    </button>
                  )}
                </div>
                {evidenceIds.length === 0 && (
                  <small className="muted">
                    Связанных событий нет. Полный журнал доступен ниже.
                  </small>
                )}
                <CriterionReview
                  sessionId={id}
                  criterion={c}
                  decision={decision}
                  revision={r.criterion_review_revision ?? 0}
                  localSave={localSave}
                  editable={user.role === "teacher"}
                  locked={mutationBusy}
                  onBusyChange={setCriterionBusy}
                  onDirtyChange={(criterionId, dirty) =>
                    setUnsavedCriteria((previous) => ({
                      ...previous,
                      [criterionId]: dirty,
                    }))
                  }
                  onSaved={(updated) => onCriterionSaved(updated, c.id)}
                />
              </div>
            </div>
          );
        })}
      </section>
      {user.role === "teacher" && (
        <details className="experimental-ai">
          <summary>Экспериментальный AI-помощник · требует проверки</summary>
          <AiReview key={r.criterion_review_revision ?? 0} sessionId={id} />
        </details>
      )}
      {user.role === "teacher" && (
        <section className="panel teacher-review">
          <div className="section-heading">
            <div>
              <h2>
                <ShieldCheck size={22} />
                Подтверждение общего итога
              </h2>
              <p>
                Решения по критериям не подтверждают общий итог автоматически.
                Проверьте балл и поясните вывод. Исходная оценка сохраняется.
              </p>
            </div>
          </div>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              if (
                mutationBusy ||
                hasUnsavedCriteria ||
                (needsRecheck && !rechecked)
              )
                return;
              setBusy(true);
              try {
                setSession(
                  await api<Session>(`/sessions/${id}/review`, "POST", {
                    score,
                    comment,
                    expected_criterion_revision:
                      r.criterion_review_revision ?? 0,
                  }),
                );
                setScoreDirty(false);
                setCommentDirty(false);
                setNeedsRecheck(false);
                setRechecked(false);
                setError("");
              } catch (e) {
                setError(errorText(e));
              } finally {
                setBusy(false);
              }
            }}
          >
            {hasUnsavedCriteria && (
              <div className="notice warning" role="status">
                Есть несохранённые решения по критериям. Сохраните их до
                подтверждения общего итога.
              </div>
            )}
            {needsRecheck && (
              <div className="notice warning">
                Ваши несохранённые балл или комментарий сохранены в этой форме
                после обновления разбора.
                <label className="review-recheck">
                  <input
                    type="checkbox"
                    checked={rechecked}
                    onChange={(event) => setRechecked(event.target.checked)}
                  />
                  Я проверил балл и комментарий с учётом текущих решений по
                  критериям
                </label>
                <button
                  type="button"
                  className="text-button"
                  onClick={() => {
                    setScore(displayScore(r));
                    setComment(r.teacher_review?.comment ?? "");
                    setScoreDirty(false);
                    setCommentDirty(false);
                    setNeedsRecheck(false);
                    setRechecked(false);
                  }}
                >
                  Сбросить мои несохранённые поля
                </button>
              </div>
            )}
            <div className="review-fields">
              <label>
                Итоговый балл
                <input
                  type="number"
                  min={0}
                  max={100}
                  value={score}
                  onChange={(e) => {
                    setScore(+e.target.value);
                    setScoreDirty(true);
                  }}
                  required
                />
              </label>
              <label>
                Комментарий и основание оценки
                <textarea
                  rows={3}
                  value={comment}
                  onChange={(e) => {
                    setComment(e.target.value);
                    setCommentDirty(true);
                  }}
                  required
                  minLength={3}
                  maxLength={1999}
                  placeholder="Подтвердите выводы или поясните причину коррекции"
                />
              </label>
            </div>
            <button
              className="button primary"
              disabled={
                mutationBusy ||
                hasUnsavedCriteria ||
                (needsRecheck && !rechecked) ||
                comment.trim().length < 3
              }
            >
              <ShieldCheck size={17} />
              {busy
                ? "Сохраняем…"
                : r.teacher_review_stale
                  ? "Подтвердить общий итог повторно"
                  : "Подтвердить общий итог"}
            </button>
          </form>
        </section>
      )}
      {r.teacher_review && (
        <div
          className={`notice ${r.teacher_review_stale ? "warning" : "success"}`}
        >
          <ShieldCheck size={20} />
          <div>
            <strong>
              {r.teacher_review_stale
                ? "Предыдущее подтверждение: "
                : "Общий итог: "}
              {r.teacher_review.reviewer_name} ·{" "}
              {formatDate(r.teacher_review.reviewed_at)}
            </strong>
            <p>{r.teacher_review.comment}</p>
            <small>
              Первичная оценка: {r.score}.{" "}
              {r.teacher_review_stale ? "Прежний итог" : "Подтверждённый итог"}:{" "}
              {r.teacher_review.score}.
            </small>
          </div>
        </div>
      )}
      <section className="panel trace-panel" id="event-trace">
        <div className="section-heading">
          <div>
            <h2>Журнал действий</h2>
            <p>Сохранённая последовательность этой учебной попытки</p>
          </div>
          {evidence.length > 0 && (
            <button className="text-button" onClick={() => setEvidence([])}>
              Снять выделение
            </button>
          )}
        </div>
        <div className="timeline">
          {session.events
            .filter((e) => e.kind !== "draft_saved")
            .map((e) => (
              <div
                className={`timeline-event ${evidence.includes(e.id) ? "highlighted" : ""}`}
                key={e.id}
              >
                <span className="timeline-time">
                  {duration(e.elapsed_seconds)}
                </span>
                <span className="timeline-dot" />
                <div>
                  <strong>{eventLabels[e.kind] || e.kind}</strong>
                  <p>{traceDescription(e, r.criteria)}</p>
                </div>
              </div>
            ))}
        </div>
      </section>
      <div className="source-note">
        Это учебная оценка по утверждённым критериям сценария. Она не является
        официальной аттестацией и не доказывает готовность к реальным
        чрезвычайным ситуациям.
      </div>
    </>
  );
}
