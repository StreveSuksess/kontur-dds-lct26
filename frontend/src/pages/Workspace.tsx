import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeft,
  BookOpen,
  Check,
  ChevronDown,
  Clock3,
  FileCheck2,
  HelpCircle,
  Phone,
  RefreshCw,
  Save,
  Send,
  Wifi,
  WifiOff,
  X,
} from "lucide-react";
import { api, duration, errorText, formatDate } from "../api";
import { ApiError } from "../api";
import type { Session, User } from "../types";
import { STATUS_LABELS } from "../types";
import { EventQueue } from "../eventQueue";
import { firstStatusWithText } from "../reportState";
import PhonePanel from "../components/Phone";
import { Badge, ErrorNotice, Loading, Modal } from "../components/UI";
export default function Workspace({
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
  const [busy, setBusy] = useState(false);
  const [now, setNow] = useState(Date.now());
  const [online, setOnline] = useState(navigator.onLine);
  const [pending, setPending] = useState(0);
  const [callId, setCallId] = useState("");
  const [showSubmit, setShowSubmit] = useState(false);
  const [hint, setHint] = useState(false);
  const [syncText, setSyncText] = useState("");
  const [openedLocal, setOpenedLocal] = useState(false);
  const [notice, setNotice] = useState("");
  const [otherCards, setOtherCards] = useState<Session[]>([]);
  const [draft, setDraft] = useState({
    comment: "",
    selected_status: "accepted",
    phone: "",
    message: "",
  });
  const queue = useMemo(() => new EventQueue(user.id, id), [user.id, id]);
  const draftKey = `kontur:draft:${user.id}:${id}`;
  const offlineAt = useRef<number | null>(null);
  const initialized = useRef(false);
  const sessionRef = useRef<Session | null>(null);
  const draftRef = useRef(draft);
  const lastSavedDraft = useRef("");
  const savingDraft = useRef(false);
  draftRef.current = draft;
  sessionRef.current = session;
  async function saveDraft() {
    if (
      !initialized.current ||
      savingDraft.current ||
      sessionRef.current?.status !== "active" ||
      !navigator.onLine
    )
      return;
    const snapshot = draftRef.current;
    const serialized = JSON.stringify(snapshot);
    if (serialized === lastSavedDraft.current) return;
    savingDraft.current = true;
    try {
      await api(`/sessions/${id}/draft`, "PUT", { draft: snapshot });
      lastSavedDraft.current = serialized;
      setOnline(true);
      if (!queue.count) setSyncText("Все действия и черновик сохранены");
    } catch (error) {
      setSyncText("Черновик сохранён на устройстве. Ожидает синхронизации.");
      if (error instanceof ApiError && error.status === 0) setOnline(false);
    } finally {
      savingDraft.current = false;
    }
  }
  useEffect(() => {
    let live = true;
    api<Session>(`/sessions/${id}`)
      .then((s) => {
        if (!live) return;
        setSession(s);
        let local = {};
        try {
          local = JSON.parse(localStorage.getItem(draftKey) || "{}");
        } catch {
          /* A corrupt local draft never overrides the server. */
        }
        setDraft((d) => ({ ...d, ...s.draft, ...local }));
        initialized.current = true;
      })
      .catch((e) => {
        if (live) setError(errorText(e));
      });
    return () => {
      live = false;
    };
  }, [id, draftKey]);
  useEffect(() => {
    const last = session?.events
      .filter((e) => e.kind === "call_started" || e.kind === "call_ended")
      .at(-1);
    setCallId(
      session?.status === "active" &&
        last?.kind === "call_started" &&
        last.payload.connected !== false
        ? String(last.payload.call_id || "")
        : "",
    );
  }, [session]);
  useEffect(() => {
    queue.onChange = () => setPending(queue.count);
    queue.onResult = (r) => {
      setOnline(true);
      setSession((previous) =>
        previous && previous.events.length > r.session.events.length
          ? previous
          : r.session,
      );
      setSyncText("Все действия сохранены");
      setError("");
    };
    setPending(queue.count);
    return () => {
      queue.onChange = undefined;
      queue.onResult = undefined;
    };
  }, [queue]);
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    const off = () => {
      setOnline(false);
      offlineAt.current = Date.now();
      setSyncText("Нет сети. Действия сохраняются на этом устройстве.");
    };
    const on = () => {
      setOnline(true);
      if (offlineAt.current && sessionRef.current?.status === "active") {
        queue.enqueue("connection_restored", {
          offline_seconds: Math.round((Date.now() - offlineAt.current) / 1000),
        });
        offlineAt.current = null;
      }
      void sync();
    };
    async function sync() {
      if (sessionRef.current?.status !== "active") return;
      try {
        await queue.flush();
        await saveDraft();
        // Refresh terminal teacher actions without overwriting the local draft.
        const fresh = await api<Session>(`/sessions/${id}`);
        setOnline(true);
        setSession((previous) =>
          !previous || fresh.events.length >= previous.events.length
            ? fresh
            : previous,
        );
      } catch (e) {
        setSyncText(errorText(e));
        if (e instanceof ApiError && e.status === 0) setOnline(false);
        if (e instanceof ApiError && e.status !== 0) {
          setError(errorText(e));
          // A teacher may stop the attempt while a client action is queued.
          // Keep unsent evidence locally, but reflect the server's final state.
          try {
            setSession(await api<Session>(`/sessions/${id}`));
          } catch {
            /* retry later */
          }
        }
      }
    }
    const retry = setInterval(() => {
      if (navigator.onLine) void sync();
    }, 5000);
    window.addEventListener("offline", off);
    window.addEventListener("online", on);
    return () => {
      clearInterval(timer);
      clearInterval(retry);
      window.removeEventListener("offline", off);
      window.removeEventListener("online", on);
    };
  }, [queue]);
  useEffect(() => {
    if (!initialized.current || session?.status !== "active") return;
    try {
      localStorage.setItem(draftKey, JSON.stringify(draft));
    } catch {
      setError(
        "Не удалось сохранить черновик на устройстве. Проверьте свободное место перед продолжением.",
      );
    }
    const save = setTimeout(() => {
      void saveDraft();
    }, 900);
    return () => clearTimeout(save);
  }, [draft, id, draftKey, session?.status]);
  useEffect(() => {
    if (session?.status !== "active") return;
    let live = true;
    const refreshQueue = async () => {
      try {
        const cards = await api<Session[]>("/sessions");
        if (live) setOtherCards(cards.filter((card) => card.status === "active" && card.id !== id));
      } catch {
        // The current workspace remains usable during a queue refresh failure.
      }
    };
    void refreshQueue();
    const timer = setInterval(() => void refreshQueue(), 8000);
    return () => { live = false; clearInterval(timer); };
  }, [id, session?.status]);
  useEffect(() => {
    const guard = (e: BeforeUnloadEvent) => {
      if (queue.count) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", guard);
    return () => window.removeEventListener("beforeunload", guard);
  }, [queue]);
  const set = (key: keyof typeof draft, value: string) =>
    setDraft((d) => ({ ...d, [key]: value }));
  async function send(
    kind: string,
    payload: Record<string, unknown> = {},
    onQueued?: () => void,
  ) {
    setError("");
    setBusy(true);
    let queued = false;
    try {
      queue.enqueue(kind, payload);
      queued = true;
      onQueued?.();
      await queue.flush();
      return true;
    } catch (e) {
      setSyncText(
        queued
          ? "Действие в очереди. Повторная отправка сохранит его исходный идентификатор."
          : "Действие не сохранено. Текст остался в поле; проверьте доступность хранилища браузера.",
      );
      if (e instanceof ApiError && e.status === 0) setOnline(false);
      else setError(errorText(e));
      return false;
    } finally {
      setBusy(false);
    }
  }
  async function start() {
    setBusy(true);
    try {
      setSession(await api<Session>(`/sessions/${id}/start`, "POST", {}));
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  async function submit() {
    setBusy(true);
    setError("");
    try {
      await queue.flush();
      await api(`/sessions/${id}/draft`, "PUT", { draft });
      await api(`/sessions/${id}/submit`, "POST", {});
      localStorage.removeItem(draftKey);
      navigate(`report/${id}`);
    } catch (e) {
      setError(errorText(e));
      setShowSubmit(false);
    } finally {
      setBusy(false);
    }
  }
  if (!session)
    return (
      <div className="page-content">
        <ErrorNotice text={error} />
        {!error && <Loading />}
      </div>
    );
  const active = session.status === "active";
  const opened =
    openedLocal ||
    session.events.some((e) => e.kind === "card_opened") ||
    queue.events.some((e) => e.kind === "card_opened");
  const elapsed = session.started_at
    ? Math.max(0, (now - Date.parse(session.started_at)) / 1000)
    : 0;
  const openEvent = session.events.find((e) => e.kind === "card_opened");
  const statuses = session.events.filter((e) => e.kind === "status_changed");
  const firstUpdate = firstStatusWithText(session.events);
  if (session.status === "assigned")
    return (
      <div className="practice-intro">
        <button className="text-button" onClick={() => navigate("sessions")}>
          <ArrowLeft size={16} />К заданиям
        </button>
        <div className="practice-intro-card">
          <div className="intro-symbol">
            <FileCheck2 size={35} />
          </div>
          <Badge tone="blue">
            {session.mode === "practice"
              ? "Практика с подсказками"
              : "Контроль без подсказок"}
          </Badge>
          <h1>{session.scenario_title}</h1>
          <p>{session.objective}</p>
          <div className="intro-rules">
            <div>
              <Clock3 />
              <strong>{session.response_limit_seconds} сек</strong>
              <span>на открытие карточки</span>
            </div>
            <div>
              <BookOpen />
              <strong>{duration(session.completion_limit_seconds)}</strong>
              <span>до первого статуса с текстом</span>
            </div>
            <div>
              <Phone />
              <strong>Исходящий вызов</strong>
              <span>учебному должностному лицу</span>
            </div>
          </div>
          <div className="notice info">
            После начала задания в ленте появится готовая карточка. Время
            реакции начнёт отсчитываться сразу.
          </div>
          <ErrorNotice text={error} />
          <button
            className="button primary large"
            disabled={busy}
            onClick={() => void start()}
          >
            Начать занятие
            <ArrowRightIcon />
          </button>
          <small>Синтетический учебный случай · {session.service}</small>
        </div>
      </div>
    );
  return (
    <div className="arm">
      <div className="arm-training-toolbar">
        <button className="button small" onClick={() => navigate("sessions")}>
          <ArrowLeft size={16} />К заданиям
        </button>
        <div>
          <strong>АРМ ДДС</strong>
          <span>
            {session.mode === "practice" ? "Практика" : "Контроль"} ·{" "}
            {user.name}
          </span>
        </div>
        <div className="arm-time">
          <span>
            Реакция{" "}
            <b
              className={
                (openEvent?.elapsed_seconds ?? elapsed) >
                session.response_limit_seconds
                  ? "overdue"
                  : ""
              }
            >
              {duration(openEvent?.elapsed_seconds ?? elapsed)}
            </b>
            <small>/ {duration(session.response_limit_seconds)}</small>
          </span>
          <span>
            Первый статус + текст{" "}
            <b
              className={
                (firstUpdate?.elapsed_seconds ?? elapsed) > session.completion_limit_seconds ? "overdue" : ""
              }
            >
              {duration(firstUpdate?.elapsed_seconds ?? elapsed)}
            </b>
            <small>/ {duration(session.completion_limit_seconds)}</small>
          </span>
        </div>
        {active ? (
          <button
            className="button primary small"
            disabled={busy}
            onClick={() => setShowSubmit(true)}
          >
            <Send size={16} />
            Завершить задание
          </button>
        ) : (
          <button
            className="button primary small"
            onClick={() => navigate(`report/${id}`)}
          >
            Открыть разбор
          </button>
        )}
      </div>
      {active && otherCards.length > 0 && (
        <section className="arrival-queue workspace-queue" aria-label="Другие поступившие карточки">
          <strong>В очереди: {otherCards.length}</strong>
          <span>Время на других карточках продолжает идти.</span>
          {otherCards.map((card) => (
            <button className="button small" key={card.id} onClick={() => navigate(`workspace/${card.id}`)}>
              № {card.card.number} · {duration(Math.max(0, (now - Date.parse(card.started_at || card.assigned_at)) / 1000))}
            </button>
          ))}
        </section>
      )}
      <div className={`sync-strip ${pending || !online ? "pending" : ""}`}>
        {online ? <Wifi size={14} /> : <WifiOff size={14} />}
        <span>
          {pending
            ? `Ожидают отправки: ${pending}`
            : syncText || "Все действия сохранены"}
        </span>
        {pending > 0 && (
          <button
            className="text-button"
            onClick={() => queue.flush().catch((e) => setError(errorText(e)))}
          >
            <RefreshCw size={13} />
            Синхронизировать
          </button>
        )}
        <span className="sync-source">
          Учебная симуляция · исходные данные карточки не редактируются
        </span>
      </div>
      <ErrorNotice text={error} />
      {notice && (
        <div className="notice success">
          {notice}
          <button className="text-button" onClick={() => setNotice("")}>
            Закрыть
          </button>
        </div>
      )}
      {!active && (
        <div className="notice warning">
          Попытка завершена или остановлена преподавателем. Новые действия
          недоступны.
        </div>
      )}
      <div className="arm-incident-list">
        <div className="arm-list-heading">
          <strong>Список происшествий</strong>
          <span>Назначенная карточка · 1</span>
        </div>
        <div className="arm-table-wrap">
          <table>
            <thead>
              <tr>
                <th>Номер</th>
                <th>Поступила</th>
                <th>Тип происшествия</th>
                <th>Адрес</th>
                <th>Статус службы</th>
                <th />
              </tr>
            </thead>
            <tbody>
              <tr className={!opened ? "new-incident" : ""}>
                <td>{session.card.number}</td>
                <td>{formatDate(session.started_at)}</td>
                <td>{session.card.incident_type}</td>
                <td>{session.card.address}</td>
                <td>
                  {STATUS_LABELS[session.current_status || ""] ||
                    "Получена службой"}
                </td>
                <td>
                  <button
                    className="arm-open"
                    disabled={busy || !active}
                    onClick={() => {
                      setOpenedLocal(true);
                      if (!opened) void send("card_opened");
                    }}
                  >
                    {opened ? "Карточка открыта" : "Открыть карточку"}
                    <ChevronDown size={15} />
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div className="arm-description-line">
          <strong>Описание:</strong> {session.card.description}
        </div>
      </div>
      {opened ? (
        <div className="arm-layout">
          <div className="arm-card-area">
            <div className="arm-card-top">
              <div className="arm-fact">
                <small>АОН заявителя</small>
                <strong>{session.card.caller_phone || "Не указан"}</strong>
              </div>
              <div className="arm-fact">
                <small>Телефон на место</small>
                <strong>Нет сведений</strong>
              </div>
              <div className="arm-fact card-id">
                <strong>Происшествие {session.card.number}</strong>
                <small>
                  {formatDate(session.started_at)} · учебная карточка
                </small>
              </div>
            </div>
            <div className="arm-facts-grid">
              <section className="arm-original">
                <div className="arm-fact">
                  <small>ФИО заявителя</small>
                  <strong>{session.card.caller_name || "Не указан"}</strong>
                </div>
                <div className="arm-fact address">
                  <small>Адрес происшествия</small>
                  <strong>{session.card.address}</strong>
                </div>
                <div className="arm-narrative">
                  <small>Описание со слов заявителя</small>
                  <p>{session.card.description}</p>
                </div>
              </section>
              <section className="arm-classification">
                <div className="arm-fact">
                  <small>Пострадавшие</small>
                  <strong>
                    {
                      { unknown: "Нет сведений", yes: "Есть", no: "Нет" }[
                        session.card.casualties
                      ]
                    }
                  </strong>
                </div>
                <div className="arm-incident-type">
                  {session.card.incident_type}
                </div>
                <div className="arm-fact">
                  <small>Классификация</small>
                  <strong>
                    {session.card.incident_code || "По учебному сценарию"}
                  </strong>
                </div>
                <div className="arm-fact">
                  <small>Служба обучающегося</small>
                  <strong>{session.service}</strong>
                </div>
                <div className="arm-objective">
                  <BookOpen size={17} />
                  <div>
                    <strong>Учебная цель</strong>
                    <p>{session.objective}</p>
                  </div>
                </div>
              </section>
            </div>
            <div className="arm-status-section">
              <div className="arm-section-heading">
                <h2>Отработка службы</h2>
                {session.mode === "practice" && active && (
                  <button
                    className="arm-help"
                    onClick={() => {
                      setHint(true);
                      void send("hint_used", { hint: "workflow_guidance" });
                    }}
                  >
                    <HelpCircle size={16} />
                    Подсказка
                  </button>
                )}
              </div>
              <div className="arm-status-log">
                <div className="arm-log-row">
                  <span>{formatDate(session.started_at)}</span>
                  <strong>Получена службой</strong>
                  <p>Учебная карточка поступила на рабочее место.</p>
                </div>
                {statuses.map((e) => (
                  <div className="arm-log-row" key={e.id}>
                    <span>{formatDate(e.at)}</span>
                    <strong>
                      {STATUS_LABELS[String(e.payload.status)] ||
                        String(e.payload.status)}
                    </strong>
                    <p>{String(e.payload.comment || "")}</p>
                  </div>
                ))}
                {queue.events
                  .filter((e) => e.kind === "status_changed")
                  .map((e) => (
                    <div
                      className="arm-log-row pending-row"
                      key={e.client_event_id}
                    >
                      <span>Ожидает отправки</span>
                      <strong>{STATUS_LABELS[String(e.payload.status)]}</strong>
                      <p>{String(e.payload.comment || "")}</p>
                    </div>
                  ))}
              </div>
              <form
                className="arm-status-form"
                onSubmit={(e) => {
                  e.preventDefault();
                  if (busy || !draft.comment.trim()) return;
                  void send(
                    "status_changed",
                    {
                      status: draft.selected_status,
                      comment: draft.comment,
                    },
                    () => {
                      set("comment", "");
                      setNotice(
                        "Действие сохранено на устройстве. Оно появится в журнале после синхронизации.",
                      );
                    },
                  );
                }}
              >
                <label>
                  Новый статус
                  <select
                    value={draft.selected_status}
                    onChange={(e) => set("selected_status", e.target.value)}
                    disabled={!active}
                  >
                    {Object.entries(STATUS_LABELS).map(([key, label]) => (
                      <option key={key} value={key}>
                        {label}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Комментарий об отработке
                  <textarea
                    value={draft.comment}
                    onChange={(e) => set("comment", e.target.value)}
                    disabled={!active}
                    maxLength={1999}
                    rows={3}
                    placeholder="Зафиксируйте выполненные действия и полученные сведения своими словами"
                    required
                  />
                </label>
                <div className="row-between">
                  <span className="muted small-text">
                    {draft.comment.length} / 1999 · черновик сохраняется
                  </span>
                  <button
                    className="button arm-save"
                    disabled={!active || busy || !draft.comment.trim()}
                  >
                    <Save size={17} />
                    Сохранить статус
                  </button>
                </div>
              </form>
            </div>
            <div className="arm-services">
              <strong>Службы:</strong>
              {session.card.services.map((service, i) => (
                <div
                  className={service === session.service ? "selected" : ""}
                  key={`${service}-${i}`}
                >
                  <ChevronDown size={13} />
                  <strong>{service}</strong>
                  <small>
                    {service === session.service
                      ? STATUS_LABELS[session.current_status || ""] ||
                        "Получена"
                      : "Учебное назначение"}
                  </small>
                </div>
              ))}
            </div>
          </div>
          <PhonePanel
            sessionId={id}
            contacts={session.contacts}
            events={session.events}
            phone={draft.phone}
            setPhone={(v) => set("phone", v)}
            message={draft.message}
            setMessage={(v) => set("message", v)}
            callId={callId}
            busy={busy}
            disabled={!active || !online}
            onCall={() => void send("call_started", { phone: draft.phone })}
            onEnd={() => void send("call_ended", { call_id: callId })}
            onMessage={async () => {
              if (busy || !draft.message.trim()) return;
              await send(
                "trainee_message",
                {
                  text: draft.message,
                  call_id: callId,
                },
                () => set("message", ""),
              );
            }}
          />
        </div>
      ) : (
        <div className="arm-wait">
          <Clock3 size={35} />
          <h2>Поступила новая карточка</h2>
          <p>
            Откройте строку происшествия, чтобы изучить сведения и начать
            отработку.
          </p>
          <span>
            Время открытия учитывается отдельно от времени выполнения задания.
          </span>
        </div>
      )}
      {showSubmit && (
        <Modal
          title="Завершить учебное задание?"
          onClose={() => setShowSubmit(false)}
        >
          <div className="modal-body">
            <p>
              Проверьте, что все нужные статусы и комментарии записаны, а
              разговор завершён.
            </p>
            {draft.comment.trim() && (
              <div className="notice warning">
                В поле комментария есть несохранённый текст. Вернитесь в
                карточку и сохраните статус, чтобы текст учитывался как
                действие.
              </div>
            )}
            {callId && (
              <div className="notice warning">
                Учебный разговор ещё активен. Завершите его перед сдачей.
              </div>
            )}
            {pending > 0 && (
              <div className="notice info">
                Сначала будут отправлены {pending} сохранённых действий. Без
                синхронизации задание не будет сдано.
              </div>
            )}
            <p className="muted">
              После сдачи редактирование закроется. Вы получите разбор по
              критериям преподавателя.
            </p>
          </div>
          <div className="modal-footer">
            <button className="button" onClick={() => setShowSubmit(false)}>
              Вернуться к карточке
            </button>
            <button
              className="button primary"
              disabled={busy || !!callId || !!draft.comment.trim()}
              onClick={() => void submit()}
            >
              <Check size={17} />
              {busy ? "Сохраняем…" : "Сдать и открыть разбор"}
            </button>
          </div>
        </Modal>
      )}
      {hint && (
        <Modal title="Как работать с карточкой" onClose={() => setHint(false)}>
          <div className="modal-body">
            <ol className="help-steps">
              <li>
                Прочитайте тип, адрес и описание. Отделяйте известные факты от
                отсутствующих сведений.
              </li>
              <li>
                Выберите статус, который соответствует вашему действию и
                условиям ситуации.
              </li>
              <li>
                Найдите должностное лицо в учебном телефонном справочнике.
                Передайте сведения и изучите ответ.
              </li>
              <li>
                Зафиксируйте полученные факты вручную. Комментарий и изменение
                статуса — отдельные части отработки.
              </li>
              <li>Проверьте журнал и завершите задание.</li>
            </ol>
            <div className="source-note">
              Использование подсказки сохранено в журнале этой практики.
            </div>
          </div>
          <div className="modal-footer">
            <button className="button primary" onClick={() => setHint(false)}>
              <X size={17} />
              Понятно
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
function ArrowRightIcon() {
  return <Send size={18} />;
}
