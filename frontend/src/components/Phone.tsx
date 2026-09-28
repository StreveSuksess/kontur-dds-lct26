import AudioInput from "./AudioInput";
import ReplyAudio from "./ReplyAudio";
import { useState } from "react";
import { Delete, PhoneCall, PhoneOff, Send, Volume2 } from "lucide-react";
import type { Contact, Event } from "../types";
export default function Phone({
  sessionId,
  contacts,
  events,
  phone,
  setPhone,
  message,
  setMessage,
  callId,
  onCall,
  onEnd,
  onMessage,
  busy,
  disabled,
}: {
  sessionId: string;
  contacts: Contact[];
  events: Event[];
  phone: string;
  setPhone: (v: string) => void;
  message: string;
  setMessage: (v: string) => void;
  callId: string;
  onCall: () => void;
  onEnd: () => void;
  onMessage: () => void;
  busy: boolean;
  disabled: boolean;
}) {
  const [tab, setTab] = useState<"phone" | "contacts">("phone");
  const messages = events.filter((e) =>
    ["trainee_message", "contact_message"].includes(e.kind),
  );
  const contact = contacts.find((c) => c.phone === phone);
  return (
    <section className="phone-panel">
      <div className="phone-heading">
        <div>
          <PhoneCall size={19} />
          <strong>Учебный телефон</strong>
        </div>
        <span className={callId ? "call-connected" : ""}>
          {callId ? "Соединение установлено" : "Программная симуляция"}
        </span>
      </div>
      <div className="phone-tabs">
        <button
          className={tab === "phone" ? "active" : ""}
          onClick={() => setTab("phone")}
        >
          Набор номера
        </button>
        <button
          className={tab === "contacts" ? "active" : ""}
          onClick={() => setTab("contacts")}
        >
          Справочник
        </button>
      </div>
      {tab === "contacts" ? (
        <div className="phone-contacts">
          {contacts.map((c) => (
            <button
              key={c.id}
              disabled={!!callId}
              onClick={() => {
                setPhone(c.phone);
                setTab("phone");
              }}
            >
              <div>
                <strong>{c.name}</strong>
                <small>{c.role}</small>
              </div>
              <b>{c.phone}</b>
            </button>
          ))}
        </div>
      ) : (
        <>
          <label className="phone-number">
            <span>Учебный номер · 3–4 цифры</span>
            <div>
              <input
                aria-label="Учебный номер телефона"
                inputMode="numeric"
                maxLength={4}
                value={phone}
                disabled={!!callId || disabled}
                onChange={(e) =>
                  setPhone(e.target.value.replace(/\D/g, "").slice(0, 4))
                }
                placeholder="— — — —"
              />
              <button
                className="icon-button"
                aria-label="Удалить цифру"
                disabled={!!callId || disabled}
                onClick={() => setPhone(phone.slice(0, -1))}
              >
                <Delete size={20} />
              </button>
            </div>
          </label>
          <div className="keypad">
            {["1", "2", "3", "4", "5", "6", "7", "8", "9", "*", "0", "#"].map(
              (n) => (
                <button
                  key={n}
                  disabled={disabled || !!callId || n === "*" || n === "#"}
                  onClick={() => setPhone((phone + n).slice(0, 4))}
                >
                  {n}
                </button>
              ),
            )}
          </div>
          {callId ? (
            <button
              className="button end-call full"
              disabled={busy || disabled}
              onClick={onEnd}
            >
              <PhoneOff size={17} />
              Завершить разговор
            </button>
          ) : (
            <button
              className="button call-button full"
              disabled={busy || disabled || !/^[0-9]{3,4}$/.test(phone)}
              onClick={onCall}
            >
              <PhoneCall size={17} />
              {busy ? "Соединяем…" : "Позвонить"}
            </button>
          )}
          {contact && (
            <p className="phone-contact-note">
              {contact.name} · {contact.role}
            </p>
          )}
        </>
      )}
      <div className="conversation">
        <div className="conversation-label">
          <Volume2 size={15} />
          Текстовый канал разговора
        </div>
        {!messages.length && (
          <p className="conversation-empty">
            Выберите учебный номер. Ответ собеседника появится после соединения.
          </p>
        )}
        {messages.map((e) => (
          <div
            key={e.id}
            className={`message ${e.kind === "trainee_message" ? "outgoing" : "incoming"}`}
          >
            <strong>
              {e.kind === "trainee_message" ? "Вы" : "Должностное лицо"}
            </strong>
            <p>{String(e.payload.text || e.payload.message || "")}</p>
            {e.kind === "contact_message" && (
              <ReplyAudio sessionId={sessionId} eventId={e.id} />
            )}
          </div>
        ))}
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onMessage();
        }}
        className="message-compose"
      >
        <label className="sr-only" htmlFor="phone-message">
          Сообщение собеседнику
        </label>
        <textarea
          id="phone-message"
          rows={3}
          maxLength={1999}
          placeholder={
            callId
              ? "Передайте сведения о происшествии…"
              : "Сначала установите соединение"
          }
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          disabled={!callId || disabled}
        />
        <button
          className="button small full"
          disabled={!callId || !message.trim() || busy || disabled}
        >
          <Send size={16} />
          Передать сообщение
        </button>
      </form>
      <AudioInput
        sessionId={sessionId}
        disabled={!callId || disabled || busy}
        onText={setMessage}
      />
      <p className="phone-footnote">Звонки проходят только внутри тренажёра.</p>
    </section>
  );
}
