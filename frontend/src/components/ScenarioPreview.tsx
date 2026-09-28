import type { Scenario } from "../types";
import { LEVEL_LABELS, STATUS_LABELS } from "../types";
import { Badge } from "./UI";

const CASUALTY_LABELS = {
  unknown: "Нет сведений",
  no: "Нет",
  yes: "Есть",
};

function text(value: string | undefined) {
  return value?.trim() ? value : "Не указано";
}

export default function ScenarioPreview({ scenario }: { scenario: Scenario }) {
  const card = scenario.card;
  return (
    <div className="scenario-preview">
      <header className="scenario-preview-heading">
        <div className="scenario-preview-meta">
          <Badge tone="blue">{text(scenario.service)}</Badge>
          <Badge>{LEVEL_LABELS[scenario.difficulty]}</Badge>
          <Badge>Версия {scenario.version}</Badge>
        </div>
        <h2>{text(scenario.title)}</h2>
        <p>{text(scenario.description)}</p>
        <dl>
          <dt>Учебная цель</dt>
          <dd>{text(scenario.objective)}</dd>
        </dl>
      </header>

      <section className="scenario-preview-section" aria-label="Лимиты задания">
        <h3>Лимиты задания</h3>
        <dl className="scenario-preview-limits">
          <div>
            <dt>Открыть карточку после начала попытки</dt>
            <dd>{scenario.response_limit_seconds} с</dd>
          </div>
          <div>
            <dt>Сохранить первый статус с текстом после начала попытки</dt>
            <dd>{scenario.completion_limit_seconds} с</dd>
          </div>
        </dl>
      </section>

      <section
        className="scenario-preview-section"
        aria-label="Карточка ученика"
      >
        <h3>Карточка ученика</h3>
        <dl className="scenario-preview-card">
          <div>
            <dt>Номер карточки</dt>
            <dd>{text(card.number)}</dd>
          </div>
          <div>
            <dt>Код происшествия</dt>
            <dd>{text(card.incident_code)}</dd>
          </div>
          <div className="scenario-preview-full">
            <dt>Тип происшествия</dt>
            <dd>{text(card.incident_type)}</dd>
          </div>
          <div className="scenario-preview-full">
            <dt>Адрес</dt>
            <dd>{text(card.address)}</dd>
          </div>
          <div className="scenario-preview-full">
            <dt>Описание происшествия</dt>
            <dd>{text(card.description)}</dd>
          </div>
          <div>
            <dt>Заявитель</dt>
            <dd>{text(card.caller_name)}</dd>
          </div>
          <div>
            <dt>Телефон заявителя</dt>
            <dd>{text(card.caller_phone)}</dd>
          </div>
          <div>
            <dt>Пострадавшие</dt>
            <dd>{CASUALTY_LABELS[card.casualties] ?? "Нет сведений"}</dd>
          </div>
          <div>
            <dt>Службы в карточке</dt>
            <dd>
              {card.services.length ? card.services.join(", ") : "Не указаны"}
            </dd>
          </div>
        </dl>
      </section>

      <section
        className="scenario-preview-section"
        aria-label="Учебные контакты и ответы"
      >
        <h3>Учебные контакты и ответы</h3>
        <p className="scenario-preview-note">
          Сопоставьте ответы собеседников с ожидаемыми фактами и эталоном.
          Согласованность содержания проверяет преподаватель.
        </p>
        {scenario.contacts.length ? (
          scenario.contacts.map((contact) => (
            <article className="scenario-preview-item" key={contact.id}>
              <h4>{text(contact.name)}</h4>
              <dl>
                <dt>Роль</dt>
                <dd>{text(contact.role)}</dd>
                <dt>Учебный номер</dt>
                <dd>{text(contact.phone)}</dd>
                <dt>Приветствие при соединении</dt>
                <dd>{text(contact.greeting)}</dd>
                <dt>Ответ после доклада учащегося</dt>
                <dd>{text(contact.reply)}</dd>
              </dl>
            </article>
          ))
        ) : (
          <p>Учебные контакты не указаны.</p>
        )}
      </section>

      <section
        className="scenario-preview-section"
        aria-label="Учебный эталон и действия"
      >
        <h3>Учебный эталон и действия</h3>
        <dl>
          <dt>Пример корректной отработки</dt>
          <dd>{text(scenario.reference_response)}</dd>
        </dl>
        <h4>Статусы в порядке выполнения</h4>
        {scenario.expected_statuses.length ? (
          <ol>
            {scenario.expected_statuses.map((status, index) => (
              <li key={`${status}-${index}`}>
                {STATUS_LABELS[status] || status}
              </li>
            ))}
          </ol>
        ) : (
          <p>Ожидаемые статусы не указаны.</p>
        )}
      </section>

      <section
        className="scenario-preview-section"
        aria-label="Проверяемые смысловые элементы"
      >
        <h3>Проверяемые смысловые элементы</h3>
        {scenario.required_facts.length ? (
          scenario.required_facts.map((fact) => (
            <article className="scenario-preview-item" key={fact.id}>
              <div className="scenario-preview-fact-heading">
                <h4>{text(fact.label)}</h4>
                {fact.critical && <Badge tone="red">Критично</Badge>}
              </div>
              <h5>Авторские варианты формулировок</h5>
              {fact.patterns.length ? (
                <ul>
                  {fact.patterns.map((pattern, index) => (
                    <li key={index}>{text(pattern)}</li>
                  ))}
                </ul>
              ) : (
                <p>Варианты формулировок не указаны.</p>
              )}
              {fact.confirmed_by_contact_ids?.length ? (
                <>
                  <h5>
                    До фиксации факта нужен подтверждающий ответ одного из
                    контактов
                  </h5>
                  <ul>
                    {fact.confirmed_by_contact_ids.map((id) => {
                      const contact = scenario.contacts.find(
                        (item) => item.id === id,
                      );
                      return (
                        <li key={id}>
                          {contact
                            ? `${text(contact.name)} · учебный номер ${text(contact.phone)}`
                            : `Связанный контакт не найден: ${id}`}
                        </li>
                      );
                    })}
                  </ul>
                  <p className="scenario-preview-note">
                    Приветствие при соединении не считается подтверждением
                    факта.
                  </p>
                </>
              ) : (
                <p className="scenario-preview-note">
                  Предварительное подтверждение контактом для этого факта не
                  задано.
                </p>
              )}
            </article>
          ))
        ) : (
          <p>Смысловые элементы не указаны.</p>
        )}
      </section>

      <div className="source-note">
        <strong>Источник сценария</strong>
        <p>{text(scenario.source_note)}</p>
      </div>
    </div>
  );
}
