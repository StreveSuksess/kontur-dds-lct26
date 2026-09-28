import { useEffect, useState } from "react";
import { BookOpen, ChevronDown, Search } from "lucide-react";
import { api, errorText } from "../api";
import type { ClassifierItem, KnowledgeItem } from "../types";
import { Badge, Empty, ErrorNotice, PageHeader } from "../components/UI";
export default function Knowledge() {
  const [articles, setArticles] = useState<KnowledgeItem[]>([]);
  const [query, setQuery] = useState("");
  const [data, setData] = useState<{
    total: number;
    version: string;
    items: ClassifierItem[];
    warnings: string[];
  } | null>(null);
  const [error, setError] = useState("");
  const [tab, setTab] = useState("guide");
  const [expanded, setExpanded] = useState("");
  useEffect(() => {
    api<KnowledgeItem[]>("/knowledge")
      .then(setArticles)
      .catch((e) => setError(errorText(e)));
  }, []);
  useEffect(() => {
    let live = true;
    const t = setTimeout(() => {
      api<typeof data>(`/classifier?q=${encodeURIComponent(query)}&limit=50`)
        .then((d) => {
          if (live) setData(d);
        })
        .catch((e) => {
          if (live) setError(errorText(e));
        });
    }, 250);
    return () => {
      live = false;
      clearTimeout(t);
    };
  }, [query]);
  return (
    <>
      <PageHeader
        eyebrow="МАТЕРИАЛЫ ДЛЯ УЧЕБНОЙ ПРАКТИКИ"
        title="База знаний"
        description="Памятки, рабочие процедуры и классификатор происшествий."
      />
      <ErrorNotice text={error} />
      <div className="toolbar">
        <div className="tabs">
          <button
            className={tab === "guide" ? "active" : ""}
            onClick={() => setTab("guide")}
          >
            Памятки и инструкции
          </button>
          <button
            className={tab === "classifier" ? "active" : ""}
            onClick={() => setTab("classifier")}
          >
            Классификатор
          </button>
        </div>
        {tab === "classifier" && (
          <label className="search-field">
            <Search size={18} />
            <input
              placeholder="Код или название происшествия"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
        )}
      </div>
      {tab === "guide" ? (
        <div className="knowledge-grid">
          {articles.map((a, i) => (
            <article className="panel knowledge-card" key={a.id}>
              <span className="knowledge-number">
                {String(i + 1).padStart(2, "0")}
              </span>
              <BookOpen size={22} />
              <h2>{a.title}</h2>
              <div className="knowledge-body">
                {a.body
                  .split("\n")
                  .filter(Boolean)
                  .map((p, j) => (
                    <p key={j}>{p.replace(/^#+\s*/, "")}</p>
                  ))}
              </div>
              <div className="source-note">{a.source}</div>
            </article>
          ))}
          {!articles.length && (
            <Empty title="Материалы пока не загружены">
              Учебные памятки появятся после загрузки на сервер.
            </Empty>
          )}
        </div>
      ) : (
        <>
          {data && (
            <div className="classifier-info">
              <p>
                <strong>{data.total.toLocaleString("ru-RU")}</strong> найдено ·{" "}
                {data.version}
              </p>
              <Badge>Официальный исходный классификатор</Badge>
            </div>
          )}
          {data?.warnings.map((w, i) => (
            <div className="notice warning" key={i}>
              {w}
            </div>
          ))}
          <div className="panel">
            {data?.items.map((item) => (
              <div className="classifier-row" key={item.code}>
                <button
                  onClick={() =>
                    setExpanded(expanded === item.code ? "" : item.code)
                  }
                >
                  <code>{item.code}</code>
                  <div>
                    <strong>{item.label}</strong>
                    <small>{item.group}</small>
                  </div>
                  <ChevronDown size={17} />
                </button>
                {expanded === item.code && (
                  <div className="classifier-details">
                    <p>
                      <strong>Признаки:</strong>{" "}
                      {item.features.join(" · ") || "Не указаны"}
                    </p>
                    <p>
                      <strong>Основная служба:</strong>{" "}
                      {item.primary_service ||
                        "Зависит от условий классификатора"}
                    </p>
                    <small>
                      Строка источника: {item.source_row}. Дополнительные службы
                      могут зависеть от признаков и территории.
                    </small>
                  </div>
                )}
              </div>
            ))}
            {data && !data.items.length && (
              <Empty title="Ничего не найдено">
                Попробуйте часть названия или другой код.
              </Empty>
            )}
          </div>
          {data && data.total > data.items.length && (
            <p className="muted">
              Показаны первые {data.items.length} совпадений. Уточните поиск.
            </p>
          )}
        </>
      )}
    </>
  );
}
