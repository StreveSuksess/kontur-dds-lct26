import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import {
  ArrowRight,
  CheckCircle2,
  Clock3,
  Copy,
  FileText,
  Plus,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  Trash2,
} from "lucide-react";
import { api, errorText } from "../api";
import type { Meta, Scenario, User } from "../types";
import { LEVEL_LABELS, STATUS_LABELS } from "../types";
import ScenarioPreview from "../components/ScenarioPreview";
import {
  Badge,
  Empty,
  ErrorNotice,
  Loading,
  Modal,
  PageHeader,
} from "../components/UI";
const blank = (): Scenario => ({
  id: "",
  title: "",
  description: "",
  service: "",
  difficulty: "basic",
  objective: "",
  status: "draft",
  version: 1,
  owner_id: "",
  card: {
    number: `УЧ-${Date.now().toString().slice(-6)}`,
    address: "",
    description: "",
    incident_type: "",
    incident_code: "",
    caller_name: "Учебный заявитель",
    caller_phone: "",
    casualties: "unknown",
    services: [],
  },
  contacts: [
    {
      id: crypto.randomUUID(),
      name: "",
      role: "Дежурный руководитель",
      phone: "2001",
      greeting: "Слушаю вас.",
      reply: "",
    },
  ],
  expected_statuses: ["accepted", "responding", "completed"],
  required_facts: [],
  reference_response: "",
  response_limit_seconds: 30,
  completion_limit_seconds: 180,
  source_note: "Авторский учебный сценарий. Синтетические данные.",
  created_at: "",
  updated_at: "",
});
export default function Scenarios({ meta }: { meta: Meta | null }) {
  const [items, setItems] = useState<Scenario[]>([]);
  const [ownerId, setOwnerId] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [edit, setEdit] = useState<Scenario | null>(null);
  const [assign, setAssign] = useState<Scenario | null>(null);
  const [preview, setPreview] = useState<Scenario | null>(null);
  const [generate, setGenerate] = useState(false);
  const [notice, setNotice] = useState("");
  const refresh = async () => {
    try {
      const [list, me] = await Promise.all([
        api<Scenario[]>("/scenarios"),
        api<User>("/auth/me"),
      ]);
      setItems(list);
      setOwnerId(me.id);
      setError("");
    } catch (e) {
      setError(errorText(e));
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    void refresh();
  }, []);
  async function mutate(path: string) {
    try {
      const result = await api<Scenario>(path, "POST", {});
      await refresh();
      return result;
    } catch (e) {
      setError(errorText(e));
    }
  }
  async function openEditor(s: Scenario) {
    if (s.owner_id === ownerId) {
      setEdit(structuredClone(s));
      return;
    }
    const copy = await mutate(`/scenarios/${s.id}/duplicate`);
    if (copy) {
      setNotice(
        "Создана ваша копия библиотечного шаблона. Исходный сценарий сохранён.",
      );
      setEdit(copy);
    }
  }
  const filtered = items.filter(
    (s) =>
      (filter === "all" ? s.status !== "archived" : s.status === filter) &&
      `${s.title} ${s.service} ${s.card.incident_type}`
        .toLowerCase()
        .includes(search.toLowerCase()),
  );
  return (
    <>
      <PageHeader
        eyebrow="БИБЛИОТЕКА УЧЕБНЫХ СИТУАЦИЙ"
        title="Сценарии"
        description="Подготовьте карточку и критерии. Проверьте содержание перед назначением."
        actions={
          <>
            <button className="button" onClick={() => setGenerate(true)}>
              <Sparkles size={17} />
              Создать вариант
            </button>
            <button
              className="button primary"
              onClick={() =>
                setEdit({ ...blank(), service: meta?.services[0] || "" })
              }
            >
              <Plus size={18} />
              Новый сценарий
            </button>
          </>
        }
      />
      <ErrorNotice text={error} />
      {notice && (
        <div className="notice success">
          <CheckCircle2 size={18} />
          {notice}
          <button onClick={() => setNotice("")} className="text-button">
            Закрыть
          </button>
        </div>
      )}
      <div className="toolbar">
        <div className="tabs">
          {[
            ["all", "Все сценарии"],
            ["approved", "Утверждены"],
            ["draft", "Черновики"],
            ["archived", "Архив"],
          ].map(([key, label]) => (
            <button
              className={filter === key ? "active" : ""}
              key={key}
              onClick={() => setFilter(key)}
            >
              {label}
            </button>
          ))}
        </div>
        <label className="search-field">
          <Search size={18} />
          <input
            aria-label="Поиск сценариев"
            placeholder="Название или служба"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
      </div>
      {loading ? (
        <Loading />
      ) : filtered.length ? (
        <div className="scenario-grid">
          {filtered.map((s, i) => (
            <article className="scenario-card" key={s.id}>
              <div className="scenario-card-top">
                <span className={`scenario-icon variation-${i % 3}`}>
                  <FileText size={22} />
                </span>
                <Badge
                  tone={
                    s.status === "approved"
                      ? "mint"
                      : s.status === "draft"
                        ? "amber"
                        : "neutral"
                  }
                >
                  {s.status === "approved"
                    ? "Утверждён"
                    : s.status === "draft"
                      ? "Черновик"
                      : "Архив"}
                </Badge>
              </div>
              <div className="eyebrow">{s.service}</div>
              <h2>{s.title}</h2>
              <p className="scenario-description">
                {s.description || s.objective}
              </p>
              <div className="scenario-meta">
                <span>
                  <span className={`level-dots ${s.difficulty}`}>▮▮▮</span>
                  {LEVEL_LABELS[s.difficulty]}
                </span>
                <span>
                  <Clock3 size={15} />
                  Первый статус: {Math.round(s.completion_limit_seconds / 60)} мин
                </span>
                <span>v{s.version}</span>
              </div>
              <div className="scenario-card-actions">
                <button className="button small" onClick={() => setPreview(s)}>
                  Просмотреть
                  <ArrowRight size={15} />
                </button>
                <button
                  className="text-button"
                  onClick={() => void openEditor(s)}
                >
                  Изменить
                </button>
                <button
                  className="icon-button"
                  title="Создать копию"
                  aria-label={`Создать копию ${s.title}`}
                  onClick={async () => {
                    const result = await mutate(`/scenarios/${s.id}/duplicate`);
                    if (result) setEdit(result);
                  }}
                >
                  <Copy size={17} />
                </button>
              </div>
              {s.status === "approved" && (
                <button className="assign-strip" onClick={() => setAssign(s)}>
                  <Send size={16} />
                  Назначить учащимся
                  <ArrowRight size={15} />
                </button>
              )}
            </article>
          ))}
        </div>
      ) : (
        <Empty
          title={
            search ? "Сценарии не найдены" : "Здесь будут учебные сценарии"
          }
        >
          Создайте карточку, опишите ожидаемые действия и утвердите сценарий.
        </Empty>
      )}
      {edit && (
        <ScenarioEditor
          scenario={edit}
          services={meta?.services || []}
          onClose={() => setEdit(null)}
          onSaved={async () => {
            setEdit(null);
            setNotice(
              "Сценарий сохранён как черновик. Проверьте и утвердите его перед назначением.",
            );
            await refresh();
          }}
        />
      )}
      {assign && (
        <Assignment
          scenario={assign}
          onClose={() => setAssign(null)}
          onDone={() => {
            setAssign(null);
            setNotice(
              "Задания назначены. Их выполнение можно отслеживать в разделе «Занятия и назначения».",
            );
          }}
        />
      )}
      {generate && (
        <Generate
          services={meta?.services || []}
          onClose={() => setGenerate(false)}
          onDone={(s) => {
            setGenerate(false);
            setEdit(s);
            void refresh();
          }}
        />
      )}
      {preview && (
        <Modal
          title="Проверка учебного сценария"
          onClose={() => setPreview(null)}
          wide
        >
          <div className="modal-body">
            <ErrorNotice text={error} />
            <ScenarioPreview scenario={preview} />
          </div>
          <div className="modal-footer">
            <button
              className="button"
              onClick={() => {
                void openEditor(preview);
                setPreview(null);
              }}
            >
              Редактировать
            </button>
            {preview.status === "draft" ? (
              <button
                className="button primary"
                onClick={async () => {
                  const result = await mutate(
                    `/scenarios/${preview.id}/approve`,
                  );
                  if (result) {
                    setPreview(null);
                    setNotice("Сценарий утверждён и доступен для назначения.");
                  }
                }}
              >
                <ShieldCheck size={18} />
                Утвердить сценарий
              </button>
            ) : preview.status === "approved" ? (
              <button
                className="button primary"
                onClick={() => {
                  setAssign(preview);
                  setPreview(null);
                }}
              >
                Назначить учащимся
                <Send size={17} />
              </button>
            ) : null}
          </div>
        </Modal>
      )}
    </>
  );
}
function ScenarioEditor({
  scenario,
  services,
  onClose,
  onSaved,
}: {
  scenario: Scenario;
  services: string[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [s, setS] = useState(scenario);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const update = <K extends keyof Scenario>(key: K, value: Scenario[K]) =>
    setS((old) => ({ ...old, [key]: value }));
  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api(
        s.id ? `/scenarios/${s.id}` : "/scenarios",
        s.id ? "PUT" : "POST",
        s,
      );
      onSaved();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title={s.id ? "Редактировать сценарий" : "Новый учебный сценарий"}
      onClose={onClose}
      wide
    >
      <form onSubmit={save}>
        <div className="modal-body">
          <ErrorNotice text={error} />
          {s.status === "approved" && (
            <div className="notice warning">
              Изменения создадут новую версию и потребуют повторного
              утверждения. Назначенные попытки сохранят прежнюю версию.
            </div>
          )}
          <div className="editor-section">
            <h3>
              <span>01</span>Учебная цель
            </h3>
            <label>
              Название
              <input
                value={s.title}
                onChange={(e) => update("title", e.target.value)}
                required
                placeholder="Например: авария на водопроводе"
              />
            </label>
            <div className="form-grid">
              <label>
                Профиль ДДС
                <input
                  list="service-options"
                  value={s.service}
                  onChange={(e) => update("service", e.target.value)}
                  required
                />
                <datalist id="service-options">
                  {services.map((v) => (
                    <option key={v} value={v} />
                  ))}
                </datalist>
              </label>
              <label>
                Сложность
                <select
                  value={s.difficulty}
                  onChange={(e) =>
                    update(
                      "difficulty",
                      e.target.value as Scenario["difficulty"],
                    )
                  }
                >
                  {Object.entries(LEVEL_LABELS).map(([id, name]) => (
                    <option key={id} value={id}>
                      {name}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <label>
              Что должен отработать учащийся
              <textarea
                value={s.objective}
                onChange={(e) => update("objective", e.target.value)}
                required
                rows={2}
              />
            </label>
            <label>
              Краткое описание для библиотеки
              <textarea
                value={s.description}
                onChange={(e) => update("description", e.target.value)}
                rows={2}
              />
            </label>
            <div className="form-grid">
              <label>
                На открытие карточки, сек
                <input
                  type="number"
                  min={1}
                  max={3600}
                  value={s.response_limit_seconds}
                  onChange={(e) =>
                    update("response_limit_seconds", +e.target.value)
                  }
                  required
                />
              </label>
              <label>
                На первый статус с текстом, сек
                <input
                  type="number"
                  min={1}
                  max={7200}
                  value={s.completion_limit_seconds}
                  onChange={(e) =>
                    update("completion_limit_seconds", +e.target.value)
                  }
                  required
                />
              </label>
            </div>
          </div>
          <div className="editor-section">
            <h3>
              <span>02</span>Готовая карточка для учащегося
            </h3>
            <div className="form-grid">
              <label>
                Номер карточки
                <input
                  value={s.card.number}
                  onChange={(e) =>
                    update("card", { ...s.card, number: e.target.value })
                  }
                  required
                />
              </label>
              <label>
                Код происшествия
                <input
                  value={s.card.incident_code}
                  onChange={(e) =>
                    update("card", { ...s.card, incident_code: e.target.value })
                  }
                />
              </label>
            </div>
            <label>
              Тип происшествия
              <input
                value={s.card.incident_type}
                onChange={(e) =>
                  update("card", { ...s.card, incident_type: e.target.value })
                }
                required
              />
            </label>
            <label>
              Адрес
              <input
                value={s.card.address}
                onChange={(e) =>
                  update("card", { ...s.card, address: e.target.value })
                }
                required
                placeholder="Синтетический учебный адрес"
              />
            </label>
            <label>
              Описание происшествия
              <textarea
                value={s.card.description}
                onChange={(e) =>
                  update("card", { ...s.card, description: e.target.value })
                }
                required
                rows={3}
              />
            </label>
            <div className="form-grid">
              <label>
                Заявитель
                <input
                  value={s.card.caller_name}
                  onChange={(e) =>
                    update("card", { ...s.card, caller_name: e.target.value })
                  }
                />
              </label>
              <label>
                Учебный телефон заявителя
                <input
                  value={s.card.caller_phone}
                  onChange={(e) =>
                    update("card", { ...s.card, caller_phone: e.target.value })
                  }
                />
              </label>
              <label>
                Пострадавшие
                <select
                  value={s.card.casualties}
                  onChange={(e) =>
                    update("card", {
                      ...s.card,
                      casualties: e.target
                        .value as Scenario["card"]["casualties"],
                    })
                  }
                >
                  <option value="unknown">Нет сведений</option>
                  <option value="no">Нет</option>
                  <option value="yes">Есть</option>
                </select>
              </label>
              <label>
                Службы (через запятую)
                <input
                  value={s.card.services.join(", ")}
                  onChange={(e) =>
                    update("card", {
                      ...s.card,
                      services: e.target.value.split(",").map((x) => x.trim()),
                    })
                  }
                />
              </label>
            </div>
          </div>
          <div className="editor-section">
            <h3>
              <span>03</span>Учебные собеседники
            </h3>
            <p className="muted">
              Только короткие учебные номера. Ответ содержит факты, которые
              ученик узнает в разговоре.
            </p>
            {s.contacts.map((c, i) => (
              <div className="nested-form" key={c.id}>
                <div className="form-grid">
                  <label>
                    Имя
                    <input
                      value={c.name}
                      onChange={(e) =>
                        update(
                          "contacts",
                          s.contacts.map((v, j) =>
                            j === i ? { ...v, name: e.target.value } : v,
                          ),
                        )
                      }
                      required
                    />
                  </label>
                  <label>
                    Должность
                    <input
                      value={c.role}
                      onChange={(e) =>
                        update(
                          "contacts",
                          s.contacts.map((v, j) =>
                            j === i ? { ...v, role: e.target.value } : v,
                          ),
                        )
                      }
                      required
                    />
                  </label>
                  <label>
                    Учебный номер
                    <input
                      inputMode="numeric"
                      pattern="[0-9]{3,4}"
                      value={c.phone}
                      onChange={(e) =>
                        update(
                          "contacts",
                          s.contacts.map((v, j) =>
                            j === i ? { ...v, phone: e.target.value } : v,
                          ),
                        )
                      }
                      required
                    />
                  </label>
                  <label>
                    Приветствие
                    <input
                      value={c.greeting || ""}
                      onChange={(e) =>
                        update(
                          "contacts",
                          s.contacts.map((v, j) =>
                            j === i ? { ...v, greeting: e.target.value } : v,
                          ),
                        )
                      }
                      required
                    />
                  </label>
                </div>
                <label>
                  Ответ после сообщения учащегося
                  <textarea
                    rows={2}
                    value={c.reply || ""}
                    onChange={(e) =>
                      update(
                        "contacts",
                        s.contacts.map((v, j) =>
                          j === i ? { ...v, reply: e.target.value } : v,
                        ),
                      )
                    }
                    required
                  />
                </label>
                {s.contacts.length > 1 && (
                  <button
                    type="button"
                    className="text-button danger"
                    disabled={s.required_facts.some((f) =>
                      f.confirmed_by_contact_ids?.includes(c.id),
                    )}
                    title="Перед удалением снимите привязку контакта в смысловых критериях"
                    onClick={() =>
                      update(
                        "contacts",
                        s.contacts.filter((_, j) => j !== i),
                      )
                    }
                  >
                    <Trash2 size={15} />
                    Удалить контакт
                  </button>
                )}
              </div>
            ))}
            <button
              className="button small"
              type="button"
              onClick={() =>
                update("contacts", [
                  ...s.contacts,
                  {
                    id: crypto.randomUUID(),
                    name: "",
                    role: "",
                    phone: "",
                    greeting: "Слушаю вас.",
                    reply: "",
                  },
                ])
              }
            >
              <Plus size={16} />
              Добавить контакт
            </button>
          </div>
          <div className="editor-section">
            <h3>
              <span>04</span>Критерии и эталон
            </h3>
            <p className="muted">
              Выберите ожидаемые статусы в порядке выполнения. Это критерии
              данного упражнения.
            </p>
            <div className="status-options">
              {Object.entries(STATUS_LABELS).map(([id, name]) => (
                <button
                  type="button"
                  className={s.expected_statuses.includes(id) ? "selected" : ""}
                  key={id}
                  onClick={() =>
                    update(
                      "expected_statuses",
                      s.expected_statuses.includes(id)
                        ? s.expected_statuses.filter((v) => v !== id)
                        : [...s.expected_statuses, id],
                    )
                  }
                >
                  {s.expected_statuses.includes(id) && (
                    <span>{s.expected_statuses.indexOf(id) + 1}</span>
                  )}
                  {name}
                </button>
              ))}
            </div>
            <label>
              Пример корректной отработки
              <textarea
                rows={3}
                value={s.reference_response}
                onChange={(e) => update("reference_response", e.target.value)}
                required
              />
            </label>
            <h4>Смысловые элементы</h4>
            {s.required_facts.map((f, i) => (
              <div className="nested-form compact" key={f.id}>
                <label>
                  Что должно быть отражено
                  <input
                    value={f.label}
                    onChange={(e) =>
                      update(
                        "required_facts",
                        s.required_facts.map((v, j) =>
                          j === i ? { ...v, label: e.target.value } : v,
                        ),
                      )
                    }
                    required
                  />
                </label>
                <label>
                  Варианты формулировок (через ;)
                  <input
                    value={f.patterns.join("; ")}
                    onChange={(e) =>
                      update(
                        "required_facts",
                        s.required_facts.map((v, j) =>
                          j === i
                            ? {
                                ...v,
                                patterns: e.target.value
                                  .split(";")
                                  .map((x) => x.trim()),
                              }
                            : v,
                        ),
                      )
                    }
                    required
                  />
                </label>
                <fieldset className="fact-confirmation">
                  <legend>Сначала получить подтверждение в звонке</legend>
                  <p className="muted small-text">
                    Без выбора проверяется только содержание. При выборе нужен
                    ответ любого из указанных контактов, затем собственная
                    запись учащегося.
                  </p>
                  {s.contacts.map((c) => (
                    <label className="checkbox" key={c.id}>
                      <input
                        type="checkbox"
                        checked={(f.confirmed_by_contact_ids || []).includes(
                          c.id,
                        )}
                        onChange={(e) =>
                          update(
                            "required_facts",
                            s.required_facts.map((v, j) =>
                              j === i
                                ? {
                                    ...v,
                                    confirmed_by_contact_ids: e.target.checked
                                      ? [
                                          ...(v.confirmed_by_contact_ids || []),
                                          c.id,
                                        ]
                                      : (
                                          v.confirmed_by_contact_ids || []
                                        ).filter((id) => id !== c.id),
                                  }
                                : v,
                            ),
                          )
                        }
                      />
                      {c.name || "Контакт без имени"} ·{" "}
                      {c.phone || "номер не указан"}
                    </label>
                  ))}
                </fieldset>
                <div className="row-between">
                  <label className="checkbox">
                    <input
                      type="checkbox"
                      checked={f.critical}
                      onChange={(e) =>
                        update(
                          "required_facts",
                          s.required_facts.map((v, j) =>
                            j === i ? { ...v, critical: e.target.checked } : v,
                          ),
                        )
                      }
                    />
                    Критически важный факт
                  </label>
                  <button
                    type="button"
                    className="icon-button"
                    aria-label="Удалить критерий"
                    onClick={() =>
                      update(
                        "required_facts",
                        s.required_facts.filter((_, j) => j !== i),
                      )
                    }
                  >
                    <Trash2 size={17} />
                  </button>
                </div>
              </div>
            ))}
            <button
              type="button"
              className="button small"
              onClick={() =>
                update("required_facts", [
                  ...s.required_facts,
                  {
                    id: crypto.randomUUID(),
                    label: "",
                    patterns: [],
                    critical: false,
                  },
                ])
              }
            >
              <Plus size={16} />
              Добавить критерий
            </button>
            <label>
              Источник и ограничения
              <textarea
                rows={2}
                value={s.source_note}
                onChange={(e) => update("source_note", e.target.value)}
                required
              />
            </label>
          </div>
        </div>
        <div className="modal-footer">
          <button type="button" className="button" onClick={onClose}>
            Отмена
          </button>
          <button className="button primary" disabled={busy}>
            {busy ? "Сохраняем…" : "Сохранить черновик"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
function Assignment({
  scenario,
  onClose,
  onDone,
}: {
  scenario: Scenario;
  onClose: () => void;
  onDone: () => void;
}) {
  const [users, setUsers] = useState<User[]>([]);
  const [ids, setIds] = useState<string[]>([]);
  const [mode, setMode] = useState("practice");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    api<User[]>("/users")
      .then(setUsers)
      .catch((e) => setError(errorText(e)));
  }, []);
  return (
    <Modal title="Назначить учебный сценарий" onClose={onClose}>
      <div className="modal-body">
        <h3>{scenario.title}</h3>
        <p className="muted">
          {scenario.service} · версия {scenario.version}
        </p>
        <ErrorNotice text={error} />
        <label>
          Режим занятия
          <select value={mode} onChange={(e) => setMode(e.target.value)}>
            <option value="practice">
              Практика — с доступными подсказками
            </option>
            <option value="exam">Контроль — без подсказок</option>
          </select>
        </label>
        <h4>Выберите учащихся</h4>
        <p className="muted small-text">
          Показаны учащиеся с совместимым профилем службы и универсальной
          учебной ДДС.
        </p>
        {users
          .filter(
            (u) =>
              u.role === "student" &&
              u.active &&
              (u.service === scenario.service ||
                u.service === "Учебная ДДС" ||
                ["Учебная ДДС", "Все службы", "универсальная"].includes(
                  scenario.service,
                )),
          )
          .map((u) => (
            <label className="user-select" key={u.id}>
              <input
                type="checkbox"
                checked={ids.includes(u.id)}
                onChange={(e) =>
                  setIds(
                    e.target.checked
                      ? [...ids, u.id]
                      : ids.filter((id) => id !== u.id),
                  )
                }
              />
              <div>
                <strong>{u.name}</strong>
                <small>
                  {u.service} · {u.group_name}
                </small>
              </div>
            </label>
          ))}
        {!users.length && <p className="muted">Учащиеся пока не загружены.</p>}
      </div>
      <div className="modal-footer">
        <button className="button" onClick={onClose}>
          Отмена
        </button>
        <button
          className="button primary"
          disabled={!ids.length || busy}
          onClick={async () => {
            setBusy(true);
            try {
              await api("/sessions", "POST", {
                scenario_id: scenario.id,
                student_ids: ids,
                mode,
              });
              onDone();
            } catch (e) {
              setError(errorText(e));
            } finally {
              setBusy(false);
            }
          }}
        >
          <Send size={17} />
          {busy ? "Назначаем…" : `Назначить (${ids.length})`}
        </button>
      </div>
    </Modal>
  );
}
function Generate({
  services,
  onClose,
  onDone,
}: {
  services: string[];
  onClose: () => void;
  onDone: (s: Scenario) => void;
}) {
  const [code, setCode] = useState("");
  const [service, setService] = useState(services[0] || "");
  const [level, setLevel] = useState("basic");
  const [instructions, setInstructions] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  return (
    <Modal title="Создать вариант сценария" onClose={onClose}>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          try {
            onDone(
              await api<Scenario>("/scenarios/generate", "POST", {
                incident_code: code,
                service,
                difficulty: level,
                instructions,
              }),
            );
          } catch (e) {
            setError(errorText(e));
          } finally {
            setBusy(false);
          }
        }}
      >
        <div className="modal-body">
          <div className="notice info">
            <Sparkles size={19} />
            Система подготовит черновик. Проверьте факты, контакты и эталон
            перед утверждением. Режим генерации будет указан в источнике.
          </div>
          <ErrorNotice text={error} />
          <label>
            Код из классификатора
            <input
              value={code}
              onChange={(e) => setCode(e.target.value)}
              required
              placeholder="Найдите код в базе знаний"
            />
          </label>
          <label>
            Профиль службы
            <select
              value={service}
              onChange={(e) => setService(e.target.value)}
              required
            >
              <option value="">Выберите службу</option>
              {services.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
          <label>
            Сложность
            <select value={level} onChange={(e) => setLevel(e.target.value)}>
              {Object.entries(LEVEL_LABELS).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          <label>
            Учебная цель и дополнительные условия
            <textarea
              rows={4}
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              placeholder="Какой навык нужно отработать?"
            />
          </label>
        </div>
        <div className="modal-footer">
          <button className="button" type="button" onClick={onClose}>
            Отмена
          </button>
          <button className="button primary" disabled={busy}>
            {busy ? "Создаём вариант…" : "Создать черновик"}
            <Sparkles size={17} />
          </button>
        </div>
      </form>
    </Modal>
  );
}
