import { useEffect, useState } from "react";
import { ArrowRight, Clock3, RefreshCw, Search, Square } from "lucide-react";
import { api, duration, errorText, formatDate } from "../api";
import type { Event, Session, User } from "../types";
import { SESSION_LABELS, STATUS_LABELS } from "../types";
import {
  CRITERION_LABELS,
  displayScore,
  firstStatusWithText,
  reportLabel,
  sessionLabel,
} from "../reportState";
import {
  Badge,
  Empty,
  ErrorNotice,
  Loading,
  Modal,
  PageHeader,
} from "../components/UI";

const EVENT_LABELS: Record<string, string> = {
  session_started: "Начало занятия",
  card_opened: "Карточка открыта",
  status_changed: "Сохранён статус",
  call_started: "Исходящий вызов",
  call_ended: "Разговор завершён",
  trainee_message: "Доклад учащегося",
  contact_message: "Ответ учебного собеседника",
  hint_used: "Открыта подсказка",
  connection_restored: "Соединение восстановлено",
  draft_saved: "Черновик сохранён на сервере",
  session_submitted: "Работа сдана",
  teacher_stopped: "Занятие остановлено преподавателем",
  review_saved: "Проверка преподавателя сохранена",
  criterion_review_saved: "Решение по критерию сохранено",
};
const DRAFT_LABELS: Record<string, string> = {
  comment: "Комментарий",
  selected_status: "Выбранный статус",
  phone: "Набранный номер",
  message: "Текст доклада",
};

function eventDescription(event: Event): string {
  const p = event.payload;
  const text = (key: string) =>
    typeof p[key] === "string" ? (p[key] as string) : "";
  switch (event.kind) {
    case "status_changed":
      return [
        STATUS_LABELS[text("status")] || "Статус не указан",
        text("comment"),
      ]
        .filter(Boolean)
        .join(". ");
    case "call_started":
      return `Учебный номер ${text("phone") || "не указан"}. ${p.connected === true ? "Соединение установлено" : "Соединение не установлено"}`;
    case "trainee_message":
    case "contact_message":
      return text("text");
    case "session_started":
      return p.mode === "exam" ? "Режим контроля" : "Режим практики";
    case "draft_saved":
      return Array.isArray(p.fields)
        ? `Поля: ${p.fields
            .map((field) => DRAFT_LABELS[String(field)])
            .filter(Boolean)
            .join(", ")}. Это не выполненное действие.`
        : "Промежуточный ввод, ещё не выполненное действие.";
    case "connection_restored":
      return typeof p.offline_seconds === "number"
        ? `Связь отсутствовала около ${Math.round(p.offline_seconds)} с. Тайминг требует проверки.`
        : "Доставка событий возобновлена.";
    case "review_saved":
      if (p.review && typeof p.review === "object") {
        const review = p.review as Record<string, unknown>;
        return [
          typeof review.score === "number" ? `Итог: ${review.score} / 100` : "",
          typeof review.comment === "string" ? review.comment : "",
        ]
          .filter(Boolean)
          .join(". ");
      }
      return "Экспертный результат сохранён в разборе.";
    case "criterion_review_saved": {
      const current = p.current as Record<string, unknown> | undefined;
      const title =
        typeof p.criterion_id === "string" ? p.criterion_id : "Критерий";
      const status = current?.status;
      const label =
        status === "pass" || status === "fail" || status === "review"
          ? CRITERION_LABELS[status]
          : "неизвестно";
      return `${title}: ${label}. ${typeof current?.comment === "string" ? current.comment : ""}`;
    }
    case "hint_used":
      return "Учащийся воспользовался учебной подсказкой; это учитывается при разборе.";
    default:
      return text("comment") || text("text");
  }
}

function Observation({
  session,
  updatedAt,
  clock,
}: {
  session: Session;
  updatedAt: number | null;
  clock: number;
}) {
  const opened = session.events.find((event) => event.kind === "card_opened");
  const firstUpdate = firstStatusWithText(session.events);
  const saved = [...session.events]
    .reverse()
    .find((event) => event.kind === "draft_saved");
  const elapsed = session.started_at
    ? Math.max(
        0,
        ((session.finished_at ? Date.parse(session.finished_at) : clock) -
          Date.parse(session.started_at)) /
          1000,
      )
    : null;
  const draft = Object.entries(session.draft).filter(
    ([key, value]) => key in DRAFT_LABELS && value.trim(),
  );
  const hasOutage = session.events.some(
    (event) => event.kind === "connection_restored",
  );
  return (
    <div className="observation">
      <h3>
        {session.student_name} · {session.scenario_title}
      </h3>
      <div className="notice info">
        <Clock3 size={18} />
        <span>
          Статус: {SESSION_LABELS[session.status]}. Обновление каждые 8 секунд.
          <br />
          Последнее получение данных:{" "}
          {updatedAt
            ? formatDate(new Date(updatedAt).toISOString())
            : "ожидается"}
          .
        </span>
      </div>
      <section
        className="observation-card"
        aria-label="Контекст учебной карточки"
      >
        <div className="row-between">
          <strong>Карточка № {session.card.number}</strong>
          <Badge tone="blue">{session.service}</Badge>
        </div>
        <h4>{session.card.incident_type}</h4>
        <p className="observation-address">{session.card.address}</p>
        <p>{session.card.description}</p>
        <dl className="observation-facts">
          <div>
            <dt>Зафиксированный статус</dt>
            <dd>
              {session.current_status
                ? STATUS_LABELS[session.current_status] || "Неизвестный статус"
                : "Статус ещё не сохранён"}
            </dd>
          </div>
          <div>
            <dt>Открытие карточки / лимит</dt>
            <dd>
              {opened ? duration(opened.elapsed_seconds) : "Ещё не открыта"} /{" "}
              {duration(session.response_limit_seconds)}
            </dd>
          </div>
          <div>
            <dt>Первый статус с текстом / лимит</dt>
            <dd>
              {firstUpdate ? duration(firstUpdate.elapsed_seconds) : elapsed === null ? "Ещё не начато" : duration(elapsed)} /{" "}
              {duration(session.completion_limit_seconds)}
            </dd>
          </div>
        </dl>
        <small className="muted">
          {hasOutage
            ? "Зафиксирован разрыв связи: время требует проверки преподавателя."
            : "Текущий отсчёт ориентировочный. Итоговое серверное время — в разборе; это не срок реального реагирования."}
        </small>
      </section>
      <section
        className="observation-draft"
        aria-label="Сохранённый черновик учащегося"
      >
        <h4>Последний сохранённый черновик</h4>
        <p>
          Промежуточный ввод на сервере — ещё не отправленный доклад и не
          сохранённый статус. Он не оценивается как действие.
        </p>
        {saved && (
          <small className="muted">Сохранён: {formatDate(saved.at)}</small>
        )}
        {draft.length ? (
          <dl>
            {draft.map(([key, value]) => (
              <div key={key}>
                <dt>{DRAFT_LABELS[key]}</dt>
                <dd>
                  {key === "selected_status"
                    ? STATUS_LABELS[value] || "Неизвестный статус"
                    : value}
                </dd>
              </div>
            ))}
          </dl>
        ) : (
          <p className="muted">
            Сохранённый ввод пока отсутствует. Текст, оставшийся только в
            браузере учащегося, здесь не виден.
          </p>
        )}
      </section>
      <section aria-label="Журнал всех событий">
        <h4>Журнал действий · {session.events.length}</h4>
        <p className="muted">
          Собственные доклады, ответы собеседника и промежуточные сохранения
          показаны отдельно. Все события сохранены.
        </p>
        <div className="observation-events">
          {session.events.map((event) => (
            <article key={event.id}>
              <time dateTime={event.at} title={formatDate(event.at)}>
                {duration(event.elapsed_seconds)}
              </time>
              <div>
                <strong>{EVENT_LABELS[event.kind] || "Событие журнала"}</strong>
                {eventDescription(event) && <p>{eventDescription(event)}</p>}
              </div>
            </article>
          ))}
        </div>
        {session.events.length === 0 && (
          <Empty title="Учащийся ещё не начал">
            Действия появятся после начала попытки.
          </Empty>
        )}
      </section>
    </div>
  );
}

export default function Sessions({
  user,
  results,
  navigate,
}: {
  user: User;
  results: boolean;
  navigate: (path: string) => void;
}) {
  const [items, setItems] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [stop, setStop] = useState<Session | null>(null);
  const [inspect, setInspect] = useState<Session | null>(null);
  const [updatedAt, setUpdatedAt] = useState<number | null>(null);
  const [clock, setClock] = useState(Date.now());
  const [selected, setSelected] = useState<string[]>([]);
  const [delivering, setDelivering] = useState(false);
  const refresh = async () => {
    try {
      setItems(await api<Session[]>("/sessions"));
      setUpdatedAt(Date.now());
      setError("");
    } catch (e) {
      setError(errorText(e));
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    void refresh();
    const id = setInterval(() => {
      void refresh();
    }, 8000);
    return () => clearInterval(id);
  }, []);
  useEffect(() => {
    setClock(Date.now());
    const timer = setInterval(() => setClock(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  const deliver = async () => {
    setDelivering(true);
    try {
      await api<Session[]>("/sessions/arrive", "POST", { session_ids: selected });
      setSelected([]);
      await refresh();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setDelivering(false);
    }
  };
  const activeQueue = items.filter((s) => s.status === "active");
  const filtered = items.filter(
    (s) =>
      (results ? !!s.report : true) &&
      (filter === "all" || s.status === filter) &&
      `${s.scenario_title} ${s.student_name}`
        .toLowerCase()
        .includes(search.toLowerCase()),
  );
  return (
    <>
      <PageHeader
        eyebrow={
          results ? "РЕЗУЛЬТАТЫ ПРАКТИКИ" : "УПРАВЛЕНИЕ УЧЕБНЫМ ПРОЦЕССОМ"
        }
        title={
          results
            ? "Разборы и результаты"
            : user.role === "teacher"
              ? "Занятия и назначения"
              : "Мои задания"
        }
        description={
          results
            ? "Каждая оценка связана с действиями и критериями задания."
            : "Задания, текущий прогресс и история назначений."
        }
        actions={
          <button className="button" onClick={() => void refresh()}>
            <RefreshCw size={17} />
            Обновить
          </button>
        }
      />
      <ErrorNotice text={error} />
      {!results && user.role === "student" && activeQueue.length > 0 && (
        <section className="panel arrival-queue" aria-label="Очередь поступивших карточек">
          <h2>Поступившие карточки · {activeQueue.length}</h2>
          <p className="muted">Время по каждой карточке идёт с момента поступления, даже пока вы работаете с другой.</p>
          <div className="arrival-queue-list">
            {activeQueue.map((s) => {
              const opened = s.events.some((event) => event.kind === "card_opened");
              const elapsed = Math.max(0, (clock - Date.parse(s.started_at || s.assigned_at)) / 1000);
              return (
                <div className="arrival-queue-item" key={s.id}>
                  <div><strong>№ {s.card.number} · {s.card.incident_type}</strong><small>{s.card.address}</small></div>
                  <span>{opened ? "Открыта" : "Ожидает открытия"} · {duration(elapsed)} / {duration(s.response_limit_seconds)}</span>
                  <button className="button small primary" onClick={() => navigate(`workspace/${s.id}`)}>Открыть <ArrowRight size={15} /></button>
                </div>
              );
            })}
          </div>
        </section>
      )}
      {!results && user.role === "teacher" && selected.length > 0 && (
        <div className="panel arrival-actions">
          <span>Выбрано назначений: {selected.length}</span>
          <button className="button primary" disabled={delivering} onClick={() => void deliver()}>
            Доставить карточки одновременно
          </button>
        </div>
      )}
      <div className="toolbar">
        <div className="tabs">
          {[
            ["all", "Все"],
            ...(results
              ? [
                  ["submitted", "На проверке"],
                  ["reviewed", "Проверены"],
                ]
              : [
                  ["assigned", "Назначены"],
                  ["active", "В работе"],
                  ["submitted", "Завершены"],
                ]),
          ].map(([id, name]) => (
            <button
              key={id}
              className={filter === id ? "active" : ""}
              onClick={() => setFilter(id)}
            >
              {name}
            </button>
          ))}
        </div>
        <label className="search-field">
          <Search size={18} />
          <input
            placeholder="Сценарий или учащийся"
            aria-label="Поиск заданий"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
      </div>
      {loading ? (
        <Loading />
      ) : filtered.length ? (
        <div className="panel table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                {!results && user.role === "teacher" && <th aria-label="Выбрать для доставки" />}
                <th>Учебный сценарий</th>
                {user.role === "teacher" && <th>Учащийся</th>}
                <th>Режим</th>
                <th>Статус</th>
                <th>{results ? "Результат" : "Назначено"}</th>
                <th aria-label="Действие" />
              </tr>
            </thead>
            <tbody>
              {filtered.map((s) => (
                <tr key={s.id}>
                  {!results && user.role === "teacher" && (
                    <td>
                      {s.status === "assigned" && (
                        <input type="checkbox" aria-label={`Доставить карточку ${s.card.number} учащемуся ${s.student_name}`}
                          checked={selected.includes(s.id)}
                          onChange={(e) => setSelected((current) => e.target.checked ? [...current, s.id] : current.filter((id) => id !== s.id))} />
                      )}
                    </td>
                  )}
                  <td>
                    <strong>{s.scenario_title}</strong>
                    <small>
                      {s.service} · версия {s.scenario_version}
                    </small>
                  </td>
                  {user.role === "teacher" && <td>{s.student_name}</td>}
                  <td>
                    <Badge>
                      {s.mode === "practice" ? "Практика" : "Контроль"}
                    </Badge>
                  </td>
                  <td>
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
                              : s.status === "submitted"
                                ? "amber"
                                : "neutral"
                      }
                    >
                      {sessionLabel(s)}
                    </Badge>
                  </td>
                  <td>
                    {results ? (
                      <div className="session-score">
                        <strong>
                          {s.report ? displayScore(s.report) : "—"} / 100
                        </strong>
                        <small>
                          {s.report ? reportLabel(s.report) : "Нет оценки"}
                        </small>
                      </div>
                    ) : (
                      formatDate(s.assigned_at)
                    )}
                  </td>
                  <td>
                    <div className="table-actions">
                      {s.report ? (
                        <button
                          className="text-button"
                          onClick={() => navigate(`report/${s.id}`)}
                        >
                          Разбор
                          <ArrowRight size={16} />
                        </button>
                      ) : user.role === "student" && s.status !== "stopped" ? (
                        <button
                          className="button small primary"
                          onClick={() => navigate(`workspace/${s.id}`)}
                        >
                          {s.status === "active" ? "Открыть" : "Начать"}
                          <ArrowRight size={15} />
                        </button>
                      ) : (
                        <button
                          className="text-button"
                          onClick={() => setInspect(s)}
                        >
                          Наблюдать
                          <ArrowRight size={16} />
                        </button>
                      )}
                      {user.role === "teacher" &&
                        ["active", "assigned"].includes(s.status) && (
                          <button
                            className="icon-button danger"
                            aria-label="Остановить задание"
                            onClick={() => setStop(s)}
                          >
                            <Square size={16} />
                          </button>
                        )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <Empty
          title={results ? "Результатов пока нет" : "Нет заданий в этом списке"}
        >
          {results
            ? "Завершите первую попытку, чтобы увидеть разбор."
            : user.role === "teacher"
              ? "Назначьте утверждённый сценарий из библиотеки."
              : "Здесь появятся задания вашего преподавателя."}
        </Empty>
      )}
      {stop && (
        <Modal
          title="Остановить учебное задание?"
          onClose={() => setStop(null)}
        >
          <div className="modal-body">
            <p>
              {stop.student_name}: {stop.scenario_title}
            </p>
            <p className="muted">
              Попытка будет отмечена как прерванная. Выполненные действия
              останутся в журнале.
            </p>
          </div>
          <div className="modal-footer">
            <button className="button" onClick={() => setStop(null)}>
              Продолжить занятие
            </button>
            <button
              className="button danger-button"
              onClick={async () => {
                try {
                  await api(`/sessions/${stop.id}/stop`, "POST", {});
                  setStop(null);
                  await refresh();
                } catch (e) {
                  setError(errorText(e));
                  setStop(null);
                }
              }}
            >
              Остановить
            </button>
          </div>
        </Modal>
      )}
      {inspect && user.role === "teacher" && (
        <Modal
          title="Наблюдение за попыткой"
          onClose={() => setInspect(null)}
          wide
        >
          <div className="modal-body">
            <ErrorNotice
              text={
                error
                  ? `Не удалось обновить наблюдение. Показаны последние полученные данные. ${error}`
                  : ""
              }
            />
            <Observation
              session={
                items.find((value) => value.id === inspect.id) || inspect
              }
              updatedAt={updatedAt}
              clock={clock}
            />
          </div>
        </Modal>
      )}
    </>
  );
}
