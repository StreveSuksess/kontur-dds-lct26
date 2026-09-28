# Проверка зависимостей и контраста

Дата: 19 сентября 2026. Проверка без изменения зависимостей, lock-файлов или frontend. Машиночитаемый [сводный протокол](dependency-audit.json) содержит время, SHA-256 входов и точные коэффициенты. Это поиск известных advisory и выборочный расчёт CSS, не security-сертификация и не полный accessibility-аудит.

## Зависимости

| Проверка | Объём | Результат |
|---|---|---|
| npm audit, официальный registry.npmjs.org | Metadata npm:121 entries; prod5,dev117,optional53 — категории пересекаются | 0 известных уязвимостей:info/low/moderate/high/critical0;exit0 |
| pip-audit2.10.1, PyPI | 26 runtime-пакетов из frozen uv.lock, маркеры текущего macOS;skipped0 | 0 известных уязвимостей;exit0 |

npm audit повторён после добавления root инструмента Prettier3.6.2: результат остаётся0, total121по metadata lock. Это число не равно числу физически установленных пакетов на одной платформе.

Сырые результаты: [npm JSON](dependency-audit-npm.json), [Python JSON](dependency-audit-python.json). В package-lock фактически четыре внешних production-пакета: React19.2.8,React DOM19.2.8,Scheduler0.27.0,lucide-react0.468.0; значение prod5 из npm metadata включает собственный проект. Python:FastAPI0.141.1,Starlette1.6.0,SQLAlchemy2.0.54 и остальные версии перечислены в JSON.

Первый npm audit через настроенный корпоративный registry вернул403 «method is not implemented». Отдельный запрос к официальному npm сначала встретил недоверенный сертификат; успешно повторён с системным хранилищем CA (`NODE_OPTIONS=--use-system-ca`). Проверка TLS не отключалась. Python-инструмент установлен через `uvx` в изолированный tool cache, не в backend/.venv; PyPI доступен с `--system-certs`, Python HTTP использовал `truststore`. Первый запуск без системных CA завершился ошибкой, не учитывается как успешный аудит.

Воспроизведение из корня:

```sh
(cd frontend && NODE_OPTIONS=--use-system-ca npm audit --json --registry=https://registry.npmjs.org)
uv export --project backend --frozen --no-dev --no-hashes --no-emit-project \
  --format requirements-txt --output-file /tmp/lcthack-backend-audit-requirements.txt
uvx --system-certs --index-url https://pypi.org/simple --from pip-audit --with truststore \
  python -c "import truststore,runpy; truststore.inject_into_ssl(); runpy.run_module('pip_audit',run_name='__main__')" \
  -r /tmp/lcthack-backend-audit-requirements.txt --no-deps --disable-pip --format json
```

Export включает полные закреплённые транзитивные версии; pip-audit не устанавливал и не разрешал зависимости заново. Хеши убраны только из временного входа аудитора. Сам uv.lock не менялся. Dev-пакеты Python, исключённые платформенными маркерами пакеты (например greenlet для Linux/x86), Docker OS-образы, AI runtime и веса этим прогоном не проверялись. Нулевой результат означает отсутствие совпавших известных advisory на дату запроса, а не отсутствие любых дефектов.

## Контраст: конкретные находки

Для обычного текста WCAG2.2 AA задаёт4,5:1; для крупного3:1. Неактивные элементы исключены из этого требования. Это различие учитывается ниже. [W3C SC1.4.3](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html). Для значимых границ/индикаторов UI применим порог3:1; оценка конкретного focus-индикатора также зависит от соседних цветов и отображения. [W3C SC1.4.11](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html).

Расчёт использует записанные CSS-цвета и предполагаемые однотонные фоны. Это не computed styles браузера, не axe и не проверка всех экранов. Значения округлены только для чтения; точные числа сохранены в JSON.

| CSS / пара | Контраст | Вывод / предложенная замена |
|---|---:|---|
| Body `#263b35` / `#f4f6f3` | 10,98 | Хороший запас |
| `--muted:#748478` / page `#f4f6f3` | 3,64 | Ниже4,5; `#5e6e62` даёт4,98 |
| `--muted` / panel `#fdfefb` | 3,90 | Ниже4,5; `#55665c` даёт6,03 |
| `.page-header p:#7a8871` / page | 3,46 | 12px; использовать тот же более тёмный muted |
| `.badge:#727f63` / `#edf0e7` | 3,69 | 10px; `#5e6d52` даёт4,81 |
| `.badge.blue:#447b97` / `#e9f1f7` | 4,06 | `#376981` даёт5,25 |
| `.badge.amber:#967732` / `#faf0d9` | 3,72 | `#7a5e24` даёт5,36 |
| `.arm-fact small:#697983` / `#f0f0f0` | 3,95 | Подписи11px; темнее `#536875`, плюс полезно увеличить размер |
| ARM body `#26384a` / `#f0f0f0` | 10,55 | Хороший запас |
| Status log white / `#167db8` | 4,507 | Формально выше4,5, но почти без запаса; фон `#126b9e` даёт5,80 |
| `.phone-footnote:#7b9bb1` / `#eff2f3` | 2,61 | 9px desktop/11px mobile; `#536875` даёт5,18 |
| `.recommendation-evidence small:#788880` / panel | 3,68 | Важное доказательство рекомендации; затемнить до общего muted |
| Primary white / `#28695b` | 6,44 | Достаточно |
| Focus outline `#69a78d` / white | 2,80 | Ниже3 на белом; `#47745d` даёт5,35 |

`button:disabled{opacity:.5}` делает primary примерно `#93b4ad` на белом; белая подпись имеет2,24:1. Это **не заявляется нарушением SC1.4.3**, поскольку элемент действительно неактивен. Для старшей аудитории полезнее явный серый фон/тёмная подпись и текст причины недоступности, чем исчезающая кнопка. Нельзя применять это исключение к работающим кнопкам или readonly-тексту карточки.

Приоритет: подписи АРМ и телефонии → muted/бейджи кабинета → focus-outline. Сохранение серо-синей схемы не требует сохранять низкий контраст. CSS не изменялся в рамках этого аудита; последующие правки root требуют повторного расчёта и браузерной проверки.

## Лицензии и состав поставки: наблюдаемые факты

- В корне проекта собственного `LICENSE` нет. Выбор лицензии авторского кода не сделан этим аудитом.
- Все четыре production-пакета frontend содержат LICENSE. React/React DOM/Scheduler — MIT;lucide-react — ISC с указанием заимствований Feather. В dist JS сохраняются короткие license-комментарии, но отдельного полного файла notices раньше не было. Добавлен [third-party-notices.md](third-party-notices.md) с фактическими текстами из установленных пакетов.
- Backend wheel-дистрибутивы содержат файлы `dist-info/licenses`; выборочно проверены FastAPI,psycopg_binary,Click. Полный SBOM/лицензионный анализ всех транзитивных компонентов не проводился.
- Рядом с локальным llama runtime есть11файлов LICENSE и XGRAMMAR_NOTICE. Каталог runtime исключён из Git. При отдельной упаковке runtime эти файлы должны оставаться в его составе; публичный репозиторий сам по себе не содержит бинарную AI-поставку.
- Скачанный Qwen README указывает `apache-2.0` и ссылку на upstream LICENSE, но отдельного LICENSE рядом с весами нет. Полный комплект notices для поставки моделей ещё не собран.
- В первоначальном срезе Dockerfile копировал venv и dist, а `.dockerignore` исключал docs. После отдельного поручения root добавлено точечное исключение для `docs/third-party-notices.md` и COPY в `/app/licenses/frontend-third-party-notices.md`. Compose config проходит; наличие файла в собранном образе пока не проверено, поскольку Docker daemon отсутствует.

Это инвентаризация наличия и содержимого файлов, не заключение о юридической совместимости или сертификации поставки.
