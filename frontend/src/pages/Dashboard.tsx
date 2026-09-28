import Recommendations from "../components/Recommendations";
import { useEffect, useState } from "react";
import {
  ArrowRight,
  BookOpen,
  CheckCircle2,
  Clock3,
  FileCheck2,
  Play,
  Users,
} from "lucide-react";
import { api, duration, errorText, formatDate } from "../api";
import type { Analytics, User } from "../types";
import { displayScore, reportLabel, sessionLabel } from "../reportState";
import {
  Badge,
  Empty,
  ErrorNotice,
  Loading,
  PageHeader,
} from "../components/UI";
export default function Dashboard({
  user,
  navigate,
}: {
  user: User;
  navigate: (to: string) => void;
}) {
  const [data, setData] = useState<Analytics | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api<Analytics>("/analytics")
      .then(setData)
      .catch((e) => setError(errorText(e)));
  }, []);
  if (!data && !error) return <Loading />;
  const teacher = user.role === "teacher";
  const weakCriteria =
    data?.criteria
      .filter((criterion) => criterion.total > 0 && criterion.failed > 0)
      .sort(
        (left, right) =>
          right.failed - left.failed ||
          right.failed / right.total - left.failed / left.total ||
          left.title.localeCompare(right.title) ||
          left.id.localeCompare(right.id),
      )
      .slice(0, 5) ?? [];
  return (
    <>
      <PageHeader
        eyebrow={teacher ? "КАБИНЕТ ПРЕПОДАВАТЕЛЯ" : "ВАША УЧЕБНАЯ ПРАКТИКА"}
        title={teacher ? "Обзор обучения" : "Готовы к следующему шагу?"}
        description={
          teacher
            ? "Всё, что нужно для занятия: от сценария до разбора."
            : "Тренируйте действия диспетчера в знакомом рабочем интерфейсе."
        }
        actions={
          <button
            className="button primary"
            onClick={() => navigate(teacher ? "scenarios" : "sessions")}
          >
            {teacher ? "Подготовить занятие" : "Открыть задания"}
            <ArrowRight size={17} />
          </button>
        }
      />
      <ErrorNotice text={error} />
      <section className="welcome-banner">
        <div>
          <Badge tone="mint">
            {teacher
              ? "Обучение через практику"
              : "Ваши действия имеют значение"}
          </Badge>
          <h2>
            {teacher
              ? "От учебной карточки —\nк уверенному решению."
              : "Прочитайте. Действуйте.\nРазберите результат."}
          </h2>
          <p>
            {teacher
              ? "Утвердите сценарий, назначьте его группе и наблюдайте за выполнением в реальном времени."
              : "Принимайте карточки, связывайтесь с должностными лицами и фиксируйте каждый этап реагирования."}
          </p>
          <button
            className="text-button"
            onClick={() => navigate(teacher ? "sessions" : "knowledge")}
          >
            {teacher ? "Перейти к занятиям" : "Открыть памятку"}
            <ArrowRight size={17} />
          </button>
        </div>
        <div className="process-visual" aria-hidden="true">
          <div className="process-card">
            <span className="process-icon">
              <BookOpen />
            </span>
            <span>
              <small>01 / ПОДГОТОВКА</small>
              <strong>Учебный сценарий</strong>
            </span>
            <CheckCircle2 />
          </div>
          <div className="process-line" />
          <div className="process-card middle">
            <span className="process-icon">
              <Play />
            </span>
            <span>
              <small>02 / ПРАКТИКА</small>
              <strong>Рабочее место ДДС</strong>
            </span>
            <span className="process-pulse" />
          </div>
          <div className="process-line" />
          <div className="process-card">
            <span className="process-icon">
              <FileCheck2 />
            </span>
            <span>
              <small>03 / ОБРАТНАЯ СВЯЗЬ</small>
              <strong>Понятный разбор</strong>
            </span>
            <ArrowRight />
          </div>
        </div>
      </section>
      {data && (
        <>
          <div className="stats-grid">
            {[
              {
                label: "Назначено заданий",
                value: data.total_sessions,
                icon: BookOpen,
              },
              {
                label: "Сейчас в работе",
                value: data.active_sessions,
                icon: Users,
              },
              {
                label: "Завершено для анализа",
                value: data.completed_sessions,
                icon: CheckCircle2,
              },
              {
                label: "Среднее время реакции",
                value: duration(data.average_reaction_seconds),
                icon: Clock3,
              },
            ].map((stat) => (
              <div className="stat" key={stat.label}>
                <span>
                  {stat.label}
                  <stat.icon size={18} />
                </span>
                <strong>{stat.value}</strong>
                <small>
                  {stat.label.includes("реакции")
                    ? "От появления до открытия карточки"
                    : "По сохранённым учебным попыткам"}
                </small>
              </div>
            ))}
          </div>
          <div className="dashboard-grid">
            <section className="panel">
              <div className="section-heading">
                <div>
                  <h2>{teacher ? "Последние занятия" : "Последние задания"}</h2>
                  <p>Текущий статус учебных попыток</p>
                </div>
                <button
                  className="text-button"
                  onClick={() => navigate("sessions")}
                >
                  Все задания
                  <ArrowRight size={16} />
                </button>
              </div>
              {data.recent_sessions.length ? (
                <div className="session-list">
                  {data.recent_sessions.slice(0, 5).map((s) => (
                    <button
                      className="session-list-item"
                      key={s.id}
                      onClick={() =>
                        navigate(
                          s.report
                            ? `report/${s.id}`
                            : teacher
                              ? "sessions"
                              : `workspace/${s.id}`,
                        )
                      }
                    >
                      <span className="session-symbol">
                        <ClipboardIcon />
                      </span>
                      <div>
                        <strong>{s.scenario_title}</strong>
                        <small>
                          {teacher ? s.student_name : s.service} ·{" "}
                          {formatDate(s.assigned_at)}
                        </small>
                        {s.report && (
                          <small>
                            {displayScore(s.report)} / 100 ·{" "}
                            {reportLabel(s.report)}
                          </small>
                        )}
                      </div>
                      <Badge
                        tone={
                          s.events.some(
                            (event) => event.kind === "teacher_stopped",
                          )
                            ? "amber"
                            : s.status === "active"
                              ? "blue"
                              : s.status === "reviewed"
                                ? "mint"
                                : "neutral"
                        }
                      >
                        {sessionLabel(s)}
                      </Badge>
                      <ArrowRight size={17} />
                    </button>
                  ))}
                </div>
              ) : (
                <Empty title="Занятия ещё не начались">
                  {teacher
                    ? "Утвердите первый сценарий и назначьте его учащимся."
                    : "Назначенные преподавателем задания появятся здесь."}
                </Empty>
              )}
            </section>
            <section className="panel skill-panel">
              <div className="section-heading">
                <div>
                  <h2>На что обратить внимание</h2>
                  <p>Определённые исходы по критериям</p>
                </div>
              </div>
              {weakCriteria.length ? (
                weakCriteria.map((c) => (
                  <div
                    className="skill-row"
                    key={JSON.stringify([c.id, c.title])}
                  >
                    <div>
                      <strong>{c.title}</strong>
                      <span>
                        {c.failed} из {c.total}
                      </span>
                    </div>
                    <div className="bar">
                      <span
                        style={{
                          width: `${Math.min(100, (100 * c.failed) / c.total)}%`,
                        }}
                      />
                    </div>
                  </div>
                ))
              ) : (
                <div className="quiet-empty">
                  <FileCheck2 size={32} />
                  <h3>Сначала — практика</h3>
                  <p>
                    После завершения заданий здесь появятся навыки, которым
                    нужно уделить внимание.
                  </p>
                </div>
              )}
              <div className="source-note">
                Средняя оценка:{" "}
                {data.average_score === null
                  ? "пока нет"
                  : `${data.average_score} / 100`}
                . Всего назначено: {data.total_sessions}; завершено для анализа:{" "}
                {data.completed_sessions}; пригодны для расчёта:{" "}
                {data.scored_sessions}; ожидают подтверждения:{" "}
                {data.pending_review_sessions}; остановлено:{" "}
                {data.stopped_sessions}. Критерии показаны по пригодным
                исходам; «из» означает число таких исходов по конкретному
                критерию. Спорные критерии и неподтверждённые изменения не
                учитываются. Решение о подготовленности принимает преподаватель.
              </div>
            </section>
          </div>
        </>
      )}
      <Recommendations navigate={navigate} />
    </>
  );
}
function ClipboardIcon() {
  return <FileCheck2 size={20} />;
}
