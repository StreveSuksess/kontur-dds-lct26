import { useEffect, useState } from "react";
import {
  Activity,
  ArrowUpRight,
  BookOpen,
  ChevronRight,
  ClipboardList,
  GraduationCap,
  LayoutDashboard,
  LogOut,
  Menu,
  Radio,
  Settings,
  ShieldCheck,
  Users,
  X,
} from "lucide-react";
import { api } from "./api";
import type { Meta, User } from "./types";
import { Loading } from "./components/UI";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Scenarios from "./pages/Scenarios";
import Sessions from "./pages/Sessions";
import Workspace from "./pages/Workspace";
import ReportPage from "./pages/Report";
import Knowledge from "./pages/Knowledge";
import Admin from "./pages/Admin";
import Intake112 from "./pages/Intake112";
export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [loading, setLoading] = useState(true);
  const [route, setRoute] = useState(location.hash.slice(1) || "overview");
  const [mobile, setMobile] = useState(false);
  useEffect(() => {
    const handle = () => {
      setRoute(location.hash.slice(1) || "overview");
      setMobile(false);
    };
    window.addEventListener("hashchange", handle);
    Promise.all([
      api<User>("/auth/me")
        .then(setUser)
        .catch(() => null),
      api<Meta>("/meta")
        .then(setMeta)
        .catch(() => null),
    ]).finally(() => setLoading(false));
    return () => window.removeEventListener("hashchange", handle);
  }, []);
  const navigate = (to: string) => {
    location.hash = to;
    setRoute(to);
    setMobile(false);
  };
  if (loading) return <Loading />;
  if (!user)
    return (
      <Login
        demo={meta?.demo_mode ?? false}
        onLogin={(u) => {
          setUser(u);
          navigate(u.role === "admin" ? "admin" : "overview");
        }}
      />
    );
  const nav =
    user.role === "admin"
      ? [
          { key: "admin", label: "Управление системой", icon: Settings },
          { key: "knowledge", label: "База знаний", icon: BookOpen },
        ]
      : [
          {
            key: "overview",
            label: user.role === "teacher" ? "Обзор обучения" : "Моя практика",
            icon: LayoutDashboard,
          },
          ...(user.role === "teacher"
            ? [{ key: "scenarios", label: "Сценарии", icon: ClipboardList }]
            : []),
          {
            key: "sessions",
            label:
              user.role === "teacher" ? "Занятия и назначения" : "Мои задания",
            icon: Users,
          },
          { key: "intake112", label: "Первичный приём 112", icon: ClipboardList },
          {
            key: "results",
            label: user.role === "teacher" ? "Результаты" : "История обучения",
            icon: Activity,
          },
          { key: "knowledge", label: "База знаний", icon: BookOpen },
        ];
  const isWorkspace = route.startsWith("workspace/");
  const roleLabel = {
    teacher: "Преподаватель",
    student: "Обучающийся",
    admin: "Администратор",
  }[user.role];
  return (
    <div className={`app-shell ${isWorkspace ? "workspace-shell" : ""}`}>
      <aside className={`sidebar ${mobile ? "open" : ""}`}>
        <a className="brand" href="#overview">
          <span className="brand-mark">
            <Radio size={23} />
          </span>
          <span>
            Контур<span className="brand-dds">ДДС</span>
            <small>УЧЕБНАЯ СРЕДА</small>
          </span>
        </a>
        <button
          className="mobile-close icon-button"
          onClick={() => setMobile(false)}
          aria-label="Закрыть меню"
        >
          <X />
        </button>
        <div className="nav-caption">{roleLabel}</div>
        <nav>
          {nav.map((item) => (
            <button
              key={item.key}
              className={route === item.key ? "active" : ""}
              onClick={() => navigate(item.key)}
            >
              <item.icon size={19} />
              {item.label}
              {route === item.key && <ChevronRight size={15} />}
            </button>
          ))}
        </nav>
        <div className="sidebar-note">
          <ShieldCheck size={22} />
          <strong>Практика в безопасной среде</strong>
          <p>
            Учебные карточки и звонки.
            <br />
            Без связи с экстренными службами.
          </p>
          <span>
            <i /> Локальный контур
          </span>
        </div>
        <div className="sidebar-user">
          <div className="avatar">
            {user.name
              .split(" ")
              .slice(0, 2)
              .map((n) => n[0])
              .join("")}
          </div>
          <div>
            <strong>{user.name}</strong>
            <small>{user.group_name || roleLabel}</small>
          </div>
          <button
            className="icon-button"
            title="Выйти"
            aria-label="Выйти из учётной записи"
            onClick={async () => {
              try {
                await api("/auth/logout", "POST", {});
                setUser(null);
              } catch {
                alert("Не удалось завершить сеанс. Повторите выход.");
              }
            }}
          >
            <LogOut size={18} />
          </button>
        </div>
      </aside>
      <div className="main-shell">
        <div className="topbar">
          <div className="breadcrumb">
            <button
              className="mobile-menu icon-button"
              onClick={() => setMobile(true)}
              aria-label="Открыть меню"
            >
              <Menu />
            </button>
            <GraduationCap size={18} />
            <span>Учебный центр</span>
            <ChevronRight size={14} />
            <strong>
              {isWorkspace
                ? "Рабочее место ДДС"
                : nav.find((n) => n.key === route)?.label || "Разбор задания"}
            </strong>
          </div>
          <div className="topbar-right">
            {meta?.demo_mode && (
              <span className="demo-chip">Демонстрационные данные</span>
            )}
            <span className="online-dot" /> Учебная среда
          </div>
        </div>
        <main className={isWorkspace ? "workspace-main" : "page-content"}>
          {route.startsWith("workspace/") ? (
            <Workspace
              key={route}
              id={route.split("/")[1]}
              user={user}
              navigate={navigate}
            />
          ) : route.startsWith("report/") ? (
            <ReportPage
              key={route}
              id={route.split("/")[1]}
              user={user}
              navigate={navigate}
            />
          ) : route === "scenarios" && user.role === "teacher" ? (
            <Scenarios meta={meta} />
          ) : route === "intake112" && user.role !== "admin" ? (
            <Intake112 user={user} />
          ) : route === "sessions" || route === "results" ? (
            <Sessions
              user={user}
              results={route === "results"}
              navigate={navigate}
            />
          ) : route === "knowledge" ? (
            <Knowledge />
          ) : user.role === "admin" ? (
            <Admin user={user} />
          ) : (
            <Dashboard user={user} navigate={navigate} />
          )}
        </main>
        <footer className="app-footer">
          <span>Контур ДДС · Подготовка к уверенным действиям</span>
          <a href="#knowledge">
            Материалы и источники <ArrowUpRight size={13} />
          </a>
        </footer>
      </div>
    </div>
  );
}
