import { useState } from "react";
import type { FormEvent } from "react";
import { ArrowRight, Check, Radio, ShieldCheck } from "lucide-react";
import { api, errorText } from "../api";
import type { User } from "../types";
import { ErrorNotice } from "../components/UI";
export default function Login({
  onLogin,
  demo,
}: {
  onLogin: (user: User) => void;
  demo: boolean;
}) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      onLogin(await api<User>("/auth/login", "POST", { username, password }));
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="login-page">
      <section className="login-story">
        <div className="brand">
          <span className="brand-mark">
            <Radio />
          </span>
          <span>
            Контур<span className="brand-dds">ДДС</span>
            <small>УЧЕБНАЯ СРЕДА</small>
          </span>
        </div>
        <div className="login-story-main">
          <span className="eyebrow">ПОДГОТОВКА ДИСПЕТЧЕРОВ</span>
          <h1>
            Уверенные действия
            <br />
            начинаются
            <br />с практики.
          </h1>
          <p>
            Рабочие ситуации, знакомый интерфейс
            <br />и понятный разбор каждого решения.
          </p>
          <div className="login-workflow">
            <span>
              <Check /> Принять карточку
            </span>
            <span>
              <Check /> Организовать реагирование
            </span>
            <span>
              <Check /> Разобрать результат
            </span>
          </div>
        </div>
        <div className="login-foot">
          <ShieldCheck size={18} /> Изолированный учебный контур
        </div>
      </section>
      <section className="login-form-area">
        <form className="login-form" onSubmit={submit}>
          <span className="eyebrow">ДОБРО ПОЖАЛОВАТЬ</span>
          <h2>Вход в учебный центр</h2>
          <p>
            Продолжите практику или подготовьте
            <br />
            следующее занятие для вашей группы.
          </p>
          <ErrorNotice text={error} />
          <label>
            Логин
            <input
              autoFocus
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              placeholder="Ваш логин"
            />
          </label>
          <label>
            Пароль
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              placeholder="Введите пароль"
            />
          </label>
          <button className="button primary full" disabled={busy}>
            {busy ? "Входим…" : "Войти"}
            <ArrowRight size={19} />
          </button>
          {demo && (
            <div className="demo-access">
              <strong>Попробовать учебный контур</strong>
              <p>Выберите роль. Все пользователи и происшествия вымышлены.</p>
              <div className="demo-roles">
                {[
                  ["teacher", "Преподаватель"],
                  ["student", "Обучающийся"],
                  ["admin", "Администратор"],
                ].map(([id, label]) => (
                  <button
                    key={id}
                    type="button"
                    onClick={() => {
                      setUsername(id);
                      setPassword("Demo112!");
                    }}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <small>Пароль демодоступа: Demo112!</small>
            </div>
          )}
          <p className="login-help">
            Если нет учётной записи, обратитесь
            <br />к администратору учебного центра.
          </p>
        </form>
      </section>
    </div>
  );
}
