import { useEffect, useState } from "react";
import { api, errorText, formatDate } from "../api";
import { ErrorNotice, Loading, PageHeader } from "../components/UI";
import type { User } from "../types";

type Case = { id: string; title: string; statement: string };
type Card = { incident_type: string; address: string; description: string; caller_name: string; caller_phone: string; services: string[] };
type Compared = { label: string; entered?: string; expected?: string; name?: string; selected?: boolean; matched: boolean };
type Attempt = { id: string; case_title: string; statement: string; student_name: string; submitted_at: string; card: Card; comparison: { fields: Compared[]; services: Compared[]; matched: number; total: number; rule: string }; review_comment: string | null; reviewed_at: string | null };
const emptyCard = (): Card => ({ incident_type: "", address: "", description: "", caller_name: "", caller_phone: "", services: [] });
const fields: { key: keyof Omit<Card, "services">; label: string }[] = [
  { key: "incident_type", label: "Тип происшествия" },
  { key: "address", label: "Адрес" },
  { key: "description", label: "Что произошло" },
  { key: "caller_name", label: "Имя заявителя" },
  { key: "caller_phone", label: "Телефон заявителя" },
];

export default function Intake112({ user }: { user: User }) {
  const [cases, setCases] = useState<Case[]>([]);
  const [services, setServices] = useState<string[]>([]);
  const [caseId, setCaseId] = useState("");
  const [card, setCard] = useState<Card>(emptyCard);
  const [attempts, setAttempts] = useState<Attempt[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [comment, setComment] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const student = user.role === "student";
  useEffect(() => {
    Promise.all([api<{ cases: Case[]; services: string[] }>("/intake112/cases"), api<Attempt[]>("/intake112/attempts")])
      .then(([catalog, rows]) => { setCases(catalog.cases); setServices(catalog.services); setCaseId(catalog.cases[0]?.id || ""); setAttempts(rows); })
      .catch((e) => setError(errorText(e)))
      .finally(() => setLoaded(true));
  }, []);
  const current = cases.find((item) => item.id === caseId);
  const selected = attempts.find((item) => item.id === selectedId);
  async function submit() {
    setBusy(true); setError("");
    try {
      const row = await api<Attempt>("/intake112/attempts", "POST", { case_id: caseId, card });
      setAttempts((old) => [row, ...old]); setSelectedId(row.id); setCard(emptyCard());
    } catch (e) { setError(errorText(e)); }
    finally { setBusy(false); }
  }
  async function review() {
    if (!selected) return;
    setBusy(true); setError("");
    try {
      const row = await api<Attempt>(`/intake112/attempts/${selected.id}/review`, "POST", { comment });
      setAttempts((old) => old.map((item) => item.id === row.id ? row : item)); setComment("");
    } catch (e) { setError(errorText(e)); }
    finally { setBusy(false); }
  }
  if (!loaded) return <Loading />;
  return <>
    <PageHeader eyebrow="УЧЕБНЫЙ МАРШРУТ 112" title="Первичный приём обращения" description="Прочитайте синтетическую вводную, заполните карточку и выберите службы. После сдачи появится проверка полей; окончательное заключение оставляет преподаватель." />
    <ErrorNotice text={error} />
    {student && <section className="panel intake-panel">
      <h2>Вводная заявителя</h2>
      <label>Учебная ситуация<select value={caseId} onChange={(e) => { setCaseId(e.target.value); setCard(emptyCard()); }}>{cases.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label>
      <blockquote className="intake-statement">{current?.statement}</blockquote>
      <h2>Карточка происшествия</h2>
      <div className="intake-grid">{fields.map(({ key, label }) => <label key={key}>{label}{key === "description" ? <textarea value={card[key]} maxLength={500} rows={3} onChange={(e) => setCard({ ...card, [key]: e.target.value })} /> : <input value={card[key]} maxLength={key === "address" ? 240 : 120} onChange={(e) => setCard({ ...card, [key]: e.target.value })} />}</label>)}</div>
      <fieldset className="intake-services"><legend>Службы-получатели</legend>{services.map((service) => <label key={service}><input type="checkbox" checked={card.services.includes(service)} onChange={(e) => setCard({ ...card, services: e.target.checked ? [...card.services, service] : card.services.filter((name) => name !== service) })} /> {service}</label>)}</fieldset>
      <button className="button primary" disabled={busy || !caseId} onClick={submit}>Сдать карточку на проверку</button>
    </section>}
    <section className="panel intake-panel">
      <h2>{student ? "Мои сданные карточки" : "Карточки учащихся группы"}</h2>
      {attempts.length === 0 ? <p>Сданных карточек пока нет.</p> : <div className="intake-list">{attempts.map((item) => <button className={selectedId === item.id ? "intake-list-item selected" : "intake-list-item"} key={item.id} onClick={() => { setSelectedId(item.id); setComment(item.review_comment || ""); }}><strong>{item.case_title}</strong><span>{student ? formatDate(item.submitted_at) : `${item.student_name} · ${formatDate(item.submitted_at)}`}</span><span>{item.comparison.matched} / {item.comparison.total} совпадений{item.reviewed_at ? " · Разобрано" : " · Ждёт разбора"}</span></button>)}</div>}
    </section>
    {selected && <section className="panel intake-panel" aria-live="polite">
      <h2>Разбор: {selected.case_title}</h2>
      <p>Вводная: {selected.statement}</p>
      <p><strong>{selected.comparison.matched} из {selected.comparison.total}</strong> проверок совпали. {selected.comparison.rule}</p>
      <div className="intake-comparison">{selected.comparison.fields.map((field) => <div key={field.label} className={field.matched ? "match" : "mismatch"}><strong>{field.label} — {field.matched ? "совпало" : "требует проверки"}</strong><span>Ученик: {field.entered || "не указано"}</span><span>Эталон: {field.expected}</span></div>)}</div>
      <h3>Службы-получатели</h3>
      <div className="intake-comparison">{selected.comparison.services.map((service) => <div key={service.name} className={service.matched ? "match" : "mismatch"}><strong>{service.name} — {service.matched ? "совпало" : "расхождение"}</strong><span>Выбрана: {service.selected ? "да" : "нет"}; ожидается: {service.expected ? "да" : "нет"}</span></div>)}</div>
      {selected.review_comment && <p className="intake-review"><strong>Заключение преподавателя:</strong> {selected.review_comment}</p>}
      {!student && <div className="intake-review-form"><label>Заключение преподавателя<textarea rows={3} maxLength={2000} value={comment} onChange={(e) => setComment(e.target.value)} /></label><button className="button primary" disabled={busy || !comment.trim()} onClick={review}>Сохранить заключение</button></div>}
    </section>}
  </>;
}
