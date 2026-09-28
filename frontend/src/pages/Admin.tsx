import { useEffect, useState } from "react";
import {
  Database,
  Download,
  Plus,
  RefreshCw,
  ShieldCheck,
  Users,
} from "lucide-react";
import { api, errorText, formatDate } from "../api";
import type { User } from "../types";
import { Badge, ErrorNotice, Modal, PageHeader } from "../components/UI";
interface Status {
  users_count: number;
  sessions_count: number;
  audit_count: number;
  database_backend: string;
  ai_mode: string;
  backup_files: unknown[];
  uptime_seconds: number;
}
interface Audit {
  id: string;
  actor_name: string;
  action: string;
  entity_type: string;
  entity_id: string;
  at: string;
  details: unknown;
}
export default function Admin({ user }: { user: User }) {
  const [status, setStatus] = useState<Status | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [audit, setAudit] = useState<Audit[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [show, setShow] = useState(false);
  const [tab, setTab] = useState("users");
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    username: "",
    name: "",
    password: "",
    role: "student",
    service: "",
    group_name: "",
  });
  async function refresh() {
    try {
      const [s, u, a] = await Promise.all([
        api<Status>("/admin/status"),
        api<User[]>("/users"),
        api<Audit[]>("/admin/audit"),
      ]);
      setStatus(s);
      setUsers(u);
      setAudit(a);
      setError("");
    } catch (e) {
      setError(errorText(e));
    }
  }
  useEffect(() => {
    void refresh();
  }, []);
  return (
    <>
      <PageHeader
        eyebrow="АДМИНИСТРИРОВАНИЕ ЛОКАЛЬНОГО КОНТУРА"
        title="Система и пользователи"
        description="Техническое состояние, доступ и журнал изменений."
        actions={
          <button className="button" onClick={() => void refresh()}>
            <RefreshCw size={17} />
            Обновить
          </button>
        }
      />
      <ErrorNotice text={error} />
      {notice && (
        <div className="notice success">
          <ShieldCheck size={19} />
          {notice}
        </div>
      )}
      {status && (
        <div className="stats-grid">
          <div className="stat">
            <span>
              Пользователей
              <Users size={18} />
            </span>
            <strong>{status.users_count}</strong>
            <small>Учётные записи системы</small>
          </div>
          <div className="stat">
            <span>
              База данных
              <Database size={18} />
            </span>
            <strong className="text-stat">{status.database_backend}</strong>
            <small>{status.sessions_count} учебных попыток</small>
          </div>
          <div className="stat">
            <span>
              Режим оценки
              <ShieldCheck size={18} />
            </span>
            <strong className="text-stat">{status.ai_mode}</strong>
            <small>Фактическая конфигурация сервера</small>
          </div>
          <div className="stat">
            <span>
              Резервные копии
              <Download size={18} />
            </span>
            <strong>{status.backup_files.length}</strong>
            <button
              className="text-button"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  const r = await api<{
                    filename: string;
                    created_at: string;
                    bytes: number;
                  }>("/admin/backup", "POST", {});
                  setNotice(
                    `Копия создана на сервере: ${r.filename} (${Math.ceil(r.bytes / 1024)} КБ).`,
                  );
                  await refresh();
                } catch (e) {
                  setError(errorText(e));
                } finally {
                  setBusy(false);
                }
              }}
            >
              {busy ? "Создаём…" : "Создать копию"}
            </button>
          </div>
        </div>
      )}
      <div className="toolbar">
        <div className="tabs">
          <button
            className={tab === "users" ? "active" : ""}
            onClick={() => setTab("users")}
          >
            Пользователи
          </button>
          <button
            className={tab === "audit" ? "active" : ""}
            onClick={() => setTab("audit")}
          >
            Журнал аудита
          </button>
        </div>
        {tab === "users" && (
          <button className="button primary" onClick={() => setShow(true)}>
            <Plus size={17} />
            Новый пользователь
          </button>
        )}
      </div>
      <section className="panel table-wrap">
        {tab === "users" ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>Пользователь</th>
                <th>Роль</th>
                <th>Служба / группа</th>
                <th>Доступ</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>
                    <strong>{u.name}</strong>
                    <small>{u.username}</small>
                  </td>
                  <td>
                    {
                      {
                        student: "Обучающийся",
                        teacher: "Преподаватель",
                        admin: "Администратор",
                      }[u.role]
                    }
                  </td>
                  <td>
                    {u.service || "—"}
                    <small>{u.group_name}</small>
                  </td>
                  <td>
                    <Badge tone={u.active ? "mint" : "red"}>
                      {u.active ? "Активен" : "Заблокирован"}
                    </Badge>
                  </td>
                  <td>
                    {u.id !== user.id && (
                      <button
                        className="text-button"
                        onClick={async () => {
                          try {
                            await api(`/admin/users/${u.id}`, "PATCH", {
                              active: !u.active,
                            });
                            await refresh();
                          } catch (e) {
                            setError(errorText(e));
                          }
                        }}
                      >
                        {u.active ? "Заблокировать" : "Разблокировать"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Время</th>
                <th>Пользователь</th>
                <th>Действие</th>
                <th>Объект</th>
              </tr>
            </thead>
            <tbody>
              {audit.map((a) => (
                <tr key={a.id}>
                  <td>{formatDate(a.at)}</td>
                  <td>{a.actor_name || "Система"}</td>
                  <td>{a.action}</td>
                  <td>
                    {a.entity_type}
                    <small>{a.entity_id}</small>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
      <div className="source-note">
        Администратор управляет техническим контуром. Оценки и содержание
        активных занятий остаются в ведении преподавателя.
      </div>
      {show && (
        <Modal title="Создать пользователя" onClose={() => setShow(false)}>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(true);
              try {
                await api("/admin/users", "POST", form);
                setShow(false);
                setForm({
                  username: "",
                  name: "",
                  password: "",
                  role: "student",
                  service: "",
                  group_name: "",
                });
                await refresh();
              } catch (e) {
                setError(errorText(e));
              } finally {
                setBusy(false);
              }
            }}
          >
            <div className="modal-body">
              <ErrorNotice text={error} />
              <label>
                Имя
                <input
                  required
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                />
              </label>
              <div className="form-grid">
                <label>
                  Логин
                  <input
                    required
                    autoComplete="off"
                    value={form.username}
                    onChange={(e) =>
                      setForm({ ...form, username: e.target.value })
                    }
                  />
                </label>
                <label>
                  Пароль
                  <input
                    required
                    type="password"
                    minLength={8}
                    autoComplete="new-password"
                    value={form.password}
                    onChange={(e) =>
                      setForm({ ...form, password: e.target.value })
                    }
                  />
                </label>
              </div>
              <label>
                Роль
                <select
                  value={form.role}
                  onChange={(e) => setForm({ ...form, role: e.target.value })}
                >
                  <option value="student">Обучающийся</option>
                  <option value="teacher">Преподаватель</option>
                  <option value="admin">Администратор</option>
                </select>
              </label>
              <div className="form-grid">
                <label>
                  Служба
                  <input
                    value={form.service}
                    onChange={(e) =>
                      setForm({ ...form, service: e.target.value })
                    }
                  />
                </label>
                <label>
                  Группа / АРМ
                  <input
                    value={form.group_name}
                    onChange={(e) =>
                      setForm({ ...form, group_name: e.target.value })
                    }
                  />
                </label>
              </div>
            </div>
            <div className="modal-footer">
              <button
                type="button"
                className="button"
                onClick={() => setShow(false)}
              >
                Отмена
              </button>
              <button className="button primary" disabled={busy}>
                Создать пользователя
              </button>
            </div>
          </form>
        </Modal>
      )}
    </>
  );
}
