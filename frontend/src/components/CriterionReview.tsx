import { useEffect, useId, useState } from "react";
import { ShieldCheck } from "lucide-react";
import { api, errorText, formatDate } from "../api";
import type { Criterion, CriterionDecision, Session } from "../types";
import { CRITERION_LABELS } from "../reportState";
import { ErrorNotice } from "./UI";

export default function CriterionReview({
  sessionId,
  criterion,
  decision,
  revision,
  localSave,
  editable,
  locked,
  onBusyChange,
  onDirtyChange,
  onSaved,
}: {
  sessionId: string;
  criterion: Criterion;
  decision?: CriterionDecision;
  revision: number;
  localSave: { criterionId: string; revision: number } | null;
  editable: boolean;
  locked: boolean;
  onBusyChange: (busy: boolean) => void;
  onDirtyChange: (criterionId: string, dirty: boolean) => void;
  onSaved: (session: Session) => void;
}) {
  const fieldId = useId();
  const [status, setStatus] = useState<Criterion["status"]>(
    decision?.status ?? criterion.status,
  );
  const [comment, setComment] = useState(decision?.comment ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [editRevision, setEditRevision] = useState<number | null>(null);
  const revisionChangedWhileEditing =
    editRevision !== null && editRevision !== revision;
  useEffect(() => {
    if (
      dirty &&
      editRevision !== null &&
      localSave?.criterionId !== criterion.id &&
      localSave?.revision === revision &&
      revision === editRevision + 1
    ) {
      // A sibling criterion was saved by this page. Its server response is the
      // new revision, so the untouched draft can safely be based on it.
      setEditRevision(revision);
    }
  }, [criterion.id, dirty, editRevision, localSave, revision]);
  const sourceEvidence = decision?.evidence_ids ?? criterion.evidence_ids;
  const selectedEvidence = [...new Set(sourceEvidence)].slice(0, 50);
  useEffect(() => {
    if (!dirty) {
      setStatus(decision?.status ?? criterion.status);
      setComment(decision?.comment ?? "");
    }
  }, [decision?.revision, criterion.status, dirty]);
  const markDirty = () => {
    if (!dirty) setEditRevision(revision);
    setDirty(true);
    onDirtyChange(criterion.id, true);
    setSaved(false);
  };
  const resetDraft = () => {
    setStatus(decision?.status ?? criterion.status);
    setComment(decision?.comment ?? "");
    setEditRevision(null);
    setDirty(false);
    setError("");
    setSaved(false);
    onDirtyChange(criterion.id, false);
  };
  if (!editable && !decision) return null;
  return (
    <section
      className="criterion-review"
      aria-label={`Решение преподавателя: ${criterion.title}`}
    >
      <h4>
        <ShieldCheck size={18} /> Решение преподавателя
      </h4>
      {decision && (
        <div className="criterion-decision">
          <strong>{CRITERION_LABELS[decision.status]}</strong>
          <p>{decision.comment}</p>
          <small>
            {decision.reviewer_name} · {formatDate(decision.reviewed_at)} ·
            решение № {decision.revision}
          </small>
        </div>
      )}
      {editable && (
        <form
          onSubmit={async (event) => {
            event.preventDefault();
            if (
              busy ||
              locked ||
              !dirty ||
              revisionChangedWhileEditing ||
              comment.trim().length < 3
            )
              return;
            setBusy(true);
            onBusyChange(true);
            setError("");
            setSaved(false);
            try {
              const updated = await api<Session>(
                `/sessions/${sessionId}/criterion-reviews`,
                "POST",
                {
                  criterion_id: criterion.id,
                  status,
                  comment: comment.trim(),
                  expected_criterion_revision: editRevision ?? revision,
                  evidence_ids: selectedEvidence,
                },
              );
              setDirty(false);
              setEditRevision(null);
              onDirtyChange(criterion.id, false);
              onSaved(updated);
              setSaved(true);
            } catch (e) {
              setError(errorText(e));
            } finally {
              setBusy(false);
              onBusyChange(false);
            }
          }}
        >
          {sourceEvidence.length > selectedEvidence.length && (
            <p className="notice warning">
              Правила связали критерий с {sourceEvidence.length} событиями. В
              решение попадут первые {selectedEvidence.length} уникальных
              ссылок; полный журнал остаётся ниже.
            </p>
          )}
          {revisionChangedWhileEditing && (
            <div className="notice warning" role="alert">
              Разбор критериев изменился, пока вы редактировали этот вывод.
              Сохраните свой текст отдельно или загрузите актуальное решение.
              <button
                type="button"
                className="text-button"
                onClick={resetDraft}
              >
                Загрузить актуальное решение
              </button>
            </div>
          )}
          <div className="criterion-review-fields">
            <label htmlFor={`${fieldId}-status`}>
              Вывод по критерию
              <select
                id={`${fieldId}-status`}
                value={status}
                disabled={busy || locked}
                onChange={(e) => {
                  setStatus(e.target.value as Criterion["status"]);
                  markDirty();
                }}
              >
                <option value="pass">Выполнено</option>
                <option value="fail">Не выполнено</option>
                <option value="review">Оставить на проверке</option>
              </select>
            </label>
            <label htmlFor={`${fieldId}-reason`}>
              Основание решения
              <textarea
                id={`${fieldId}-reason`}
                value={comment}
                rows={3}
                required
                minLength={3}
                maxLength={1999}
                disabled={busy || locked}
                placeholder="Укажите действие или цитату и поясните свой вывод"
                onChange={(e) => {
                  setComment(e.target.value);
                  markDirty();
                }}
              />
            </label>
          </div>
          <ErrorNotice text={error} />
          <div className="criterion-review-actions">
            <button
              className="button"
              disabled={
                busy ||
                locked ||
                !dirty ||
                revisionChangedWhileEditing ||
                comment.trim().length < 3
              }
            >
              <ShieldCheck size={16} />
              {busy ? "Сохраняем…" : "Сохранить решение по критерию"}
            </button>
            {dirty && !revisionChangedWhileEditing && (
              <button
                type="button"
                className="text-button"
                disabled={busy || locked}
                onClick={resetDraft}
              >
                Сбросить черновик
              </button>
            )}
            <span role="status">
              {saved
                ? "Решение сохранено. Подтвердите общий итог ниже."
                : "Исходная проверка и история решений сохраняются."}
            </span>
          </div>
        </form>
      )}
    </section>
  );
}
