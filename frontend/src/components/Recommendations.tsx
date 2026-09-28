import { useEffect, useState } from "react";
import { api, errorText } from "../api";
import { LEVEL_LABELS } from "../types";
type Recommendation = {
  student_id: string;
  student_name: string;
  status: string;
  sample_size: number;
  proposed_level: string | null;
  reason: string;
  evidence_session_ids: string[];
  weak_skills: {
    criterion_id: string;
    title: string;
    failed: number;
    total: number;
  }[];
  scenario_selection_reason: string;
  unmatched_criteria: { criterion_id: string; title: string }[];
  suggested_scenarios: {
    id: string;
    title: string;
    selection_basis: "rubric_match" | "profile_level";
    matched_criteria: { criterion_id: string; title: string }[];
  }[];
};
export default function Recommendations({
  navigate,
}: {
  navigate: (path: string) => void;
}) {
  const [items, setItems] = useState<Recommendation[] | null>(null),
    [error, setError] = useState("");
  useEffect(() => {
    api<{ items: Recommendation[] }>("/recommendations")
      .then((r) => setItems(r.items))
      .catch((e) => setError(errorText(e)));
  }, []);
  return (
    <section className="panel recommendations-panel">
      <div className="section-heading">
        <div>
          <h2>Следующая практика</h2>
          <p>
            Рекомендация по сохранённым попыткам. Уровень и назначение
            определяет преподаватель.
          </p>
        </div>
      </div>
      {error && <p className="audio-error">{error}</p>}
      {items?.length === 0 && (
        <p className="muted">
          После назначения и выполнения упражнений здесь появятся основания для
          следующего занятия.
        </p>
      )}
      {items?.map((item) => (
        <div className="recommendation-row" key={item.student_id}>
          <div className="row-between">
            <h3>{item.student_name}</h3>
            <span className="badge">
              {item.proposed_level
                ? LEVEL_LABELS[item.proposed_level]
                : "Недостаточно данных"}
            </span>
          </div>
          <p>{item.reason}</p>
          {!!item.weak_skills.length && (
            <ul>
              {item.weak_skills.map((s) => (
                <li key={`${s.criterion_id}:${s.title}`}>
                  {s.title}: {s.failed} замечаний в {s.total} попытках
                </li>
              ))}
            </ul>
          )}
          {item.status === "recommendation" && (
            <div>
              <h4>Варианты следующего упражнения</h4>
              <p>{item.scenario_selection_reason}</p>
              {!!item.suggested_scenarios.length && (
                <ul>
                  {item.suggested_scenarios.map((scenario) => (
                    <li key={scenario.id}>
                      <strong>{scenario.title}</strong>
                      <p>
                        {scenario.selection_basis === "rubric_match"
                          ? `Совпадают критерии: ${scenario.matched_criteria.map((criterion) => criterion.title).join("; ")}.`
                          : "Подбор по профилю службы и уровню сложности."}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
              {!!item.unmatched_criteria.length && (
                <p>
                  <strong>В показанной подборке не покрыты критерии: </strong>
                  {item.unmatched_criteria
                    .map((criterion) => criterion.title)
                    .join("; ")}
                  . Преподаватель может проверить другие упражнения в библиотеке
                  или подготовить отдельный вариант с этими критериями.
                </p>
              )}
            </div>
          )}
          <div className="recommendation-evidence">
            {item.evidence_session_ids.slice(0, 3).map((id, i) => (
              <button
                className="text-button"
                key={id}
                onClick={() => navigate(`report/${id}`)}
              >
                Основание {i + 1}
              </button>
            ))}
            <small>Попыток в расчёте: {item.sample_size}</small>
          </div>
        </div>
      ))}
    </section>
  );
}
