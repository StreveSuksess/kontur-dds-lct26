#!/usr/bin/env python3
"""Build the submission guide with selectable Cyrillic text (ReportLab)."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image, KeepTogether, Preformatted
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4

ROOT = Path(__file__).resolve().parents[1]
GREEN = colors.HexColor('#28695b')
DARK = colors.HexColor('#1b3235')
INK = colors.HexColor('#263b35')
MUTED = colors.HexColor('#54685e')
LINE = colors.HexColor('#dbe4dc')
PALE = colors.HexColor('#f1f5ef')
AMBER = colors.HexColor('#fff5df')
PAGE_W, PAGE_H = A4
WIDTH = PAGE_W - 96


def fonts():
    custom = os.getenv('LCT_GUIDE_FONT_DIR')
    candidates = [Path(custom)] if custom else []
    candidates += [Path('/System/Library/Fonts/Supplemental'), Path('/usr/share/fonts/truetype/dejavu')]
    for folder in candidates:
        for names in [('Arial.ttf', 'Arial Bold.ttf', 'Arial Italic.ttf'), ('DejaVuSans.ttf', 'DejaVuSans-Bold.ttf', 'DejaVuSans-Oblique.ttf')]:
            if all((folder / name).exists() for name in names):
                for alias, name in zip(['Guide', 'GuideBold', 'GuideItalic'], names):
                    pdfmetrics.registerFont(TTFont(alias, str(folder / name)))
                pdfmetrics.registerFontFamily('Guide', normal='Guide', bold='GuideBold', italic='GuideItalic', boldItalic='GuideBold')
                return
    raise RuntimeError('Set LCT_GUIDE_FONT_DIR to Arial or DejaVuSans TTF directory.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT / 'deliverables/kontur-dds-guide.pdf')
    args = parser.parse_args()
    fonts()
    styles = {
        'body': ParagraphStyle('body', fontName='Guide', fontSize=10.6, leading=15.7, textColor=INK, spaceAfter=9),
        'small': ParagraphStyle('small', fontName='Guide', fontSize=9, leading=13, textColor=MUTED, spaceAfter=7),
        'h1': ParagraphStyle('h1', fontName='GuideBold', fontSize=24, leading=29, textColor=DARK, spaceAfter=15),
        'h2': ParagraphStyle('h2', fontName='GuideBold', fontSize=13.5, leading=18, textColor=GREEN, spaceBefore=12, spaceAfter=7),
        'cell': ParagraphStyle('cell', fontName='Guide', fontSize=9.3, leading=13.1, textColor=INK),
        'head': ParagraphStyle('head', fontName='GuideBold', fontSize=9.2, leading=13, textColor=colors.white),
        'eyebrow': ParagraphStyle('eyebrow', fontName='GuideBold', fontSize=8.6, leading=12, textColor=GREEN, spaceAfter=9),
        'code': ParagraphStyle('code', fontName='Guide', fontSize=8.8, leading=12.3, textColor=DARK, backColor=PALE, borderPadding=10, spaceBefore=5, spaceAfter=12),
    }
    story = []
    def p(text, kind='body'):
        return Paragraph(text.replace('Q&A', 'Q&amp;A'), styles[kind])
    def add(text, kind='body'):
        story.append(p(text, kind))
    def title(number, text, subtitle=None):
        add(f'РУКОВОДСТВО / {number:02d}', 'eyebrow')
        add(text, 'h1')
        if subtitle: add(subtitle)
    def h(text): add(text, 'h2')
    def code(text): story.append(Preformatted(text, styles['code']))
    def note(text, amber=False):
        table = Table([[p(text)]], colWidths=[WIDTH])
        table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), AMBER if amber else PALE), ('BOX', (0, 0), (-1, -1), .6, LINE), ('LEFTPADDING',(0,0),(-1,-1),13),('RIGHTPADDING',(0,0),(-1,-1),13),('TOPPADDING',(0,0),(-1,-1),11),('BOTTOMPADDING',(0,0),(-1,-1),3)]))
        story.extend([table, Spacer(1, 10)])
    def table(headers, rows, widths):
        data=[[p(x, 'head') for x in headers]]+[[p(x, 'cell') for x in row] for row in rows]
        t=Table(data, colWidths=[WIDTH*x for x in widths], repeatRows=1, hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),DARK),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),10),('RIGHTPADDING',(0,0),(-1,-1),10),('TOPPADDING',(0,0),(-1,-1),9),('BOTTOMPADDING',(0,0),(-1,-1),9),('LINEBELOW',(0,1),(-1,-1),.4,LINE),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,PALE])]))
        story.extend([t,Spacer(1,11)])
    def screenshot(name, caption):
        path=ROOT/'deliverables/assets'/name
        from PIL import Image as PILImage
        with PILImage.open(path) as im: w,h=im.size
        image_h=min(275, WIDTH*h/w)
        story.append(Image(str(path),width=image_h*w/h,height=image_h))
        story.append(Spacer(1,7));add(caption,'small')
    def end(): story.append(PageBreak())
    def foot(c, doc):
        c.saveState()
        if doc.page>1:
            c.setStrokeColor(LINE);c.line(48,PAGE_H-36,PAGE_W-48,PAGE_H-36)
            c.setFont('GuideBold',8);c.setFillColor(GREEN);c.drawString(48,PAGE_H-27,'КОНТУР ДДС')
            c.setFont('Guide',8);c.setFillColor(MUTED);c.drawRightString(PAGE_W-48,PAGE_H-27,'Сопроводительная документация / 19.09.2026')
        c.setStrokeColor(LINE);c.line(48,39,PAGE_W-48,39)
        c.setFillColor(MUTED);c.setFont('Guide',8);c.drawString(48,25,'Учебный прототип. Синтетические данные. Не действующая система-112.')
        c.drawRightString(PAGE_W-48,25,str(doc.page))
        c.restoreState()
    def cover(c,doc):
        c.saveState();c.setFillColor(DARK);c.rect(0,330,PAGE_W,PAGE_H-330,fill=1,stroke=0)
        c.setFillColor(colors.HexColor('#c8dfcf'));c.setFont('GuideBold',10);c.drawString(48,754,'ЛЦТ / УЧЕБНЫЙ КОНТУР / ВЕРСИЯ 0.1.0')
        c.setFillColor(colors.white);c.setFont('GuideBold',43);c.drawString(46,676,'Контур ДДС')
        cs=ParagraphStyle('cover',fontName='Guide',fontSize=20,leading=28,textColor=colors.white)
        q=Paragraph('Практика на готовой карточке.<br/>Разбор по реальным действиям.',cs);q.wrap(WIDTH,120);q.drawOn(c,48,574)
        cs2=ParagraphStyle('cover2',fontName='Guide',fontSize=11.4,leading=17,textColor=colors.HexColor('#d3e0d7'))
        q=Paragraph('Руководство для преподавателя, учащегося<br/>и технического специалиста. Продуктовая логика,<br/>запуск, проверенные свойства и границы применения.',cs2);q.wrap(WIDTH,120);q.drawOn(c,48,445)
        c.setFillColor(colors.HexColor('#93bba6'));c.rect(48,385,54,4,fill=1,stroke=0)
        c.setFillColor(GREEN);c.setFont('GuideBold',12);c.drawString(48,293,'ОТ КАРТОЧКИ К ПОДТВЕРЖДЁННОМУ НАВЫКУ')
        q=Paragraph('Преподаватель утверждает сценарий и критерии. Диспетчер получает готовую карточку, передаёт исходящий доклад, фиксирует реагирование и получает объяснимый разбор. Спорный смысл проверяет человек.',styles['body']);q.wrap(WIDTH,120);q.drawOn(c,48,207)
        c.setFillColor(INK);c.setFont('GuideBold',11);c.drawString(48,158,'Локальный прототип / 3 роли / программный телефон')
        q=Paragraph('Подготовлено 19 сентября 2026. Документ фиксирует состояние реализованного прототипа. Пользовательского пилота и официальной аттестации не было.',styles['small']);q.wrap(WIDTH,70);q.drawOn(c,48,99)
        c.restoreState();foot(c,doc)
    story.append(Spacer(1,690));end()

    title(1,'Задача и продуктовая логика','Основной пользователь - сотрудник профильной ДДС, который получает готовую карточку от системы-112 и организует дальнейшее реагирование.')
    table(['Основание','Что принято в прототипе'],[
      ['Q&A 17:42-18:51;<br/>21:41-23:38','Один поток ДДС. Первичный приём гражданина и второй прототип оператора-112 не требуются на этом этапе.'],
      ['Q&A 10:32-11:10;<br/>39:31-40:18','Программный исходящий звонок по учебному номеру. Реальный телефон и SIP не выдаются за реализованную интеграцию.'],
      ['Q&A 25:10-27:47','Рабочие поля и серо-синяя схема АРМ узнаваемы. Кабинет преподавателя проектируется отдельно.'],
      ['Q&A 31:53-35:27','Утверждённой универсальной шкалы нет. 30 с на открытие и около 3 мин на обработку - настраиваемые учебные ориентиры.'],
    ],[.28,.72])
    h('Работа, которую помогает выполнить продукт')
    add('<b>Преподавателю:</b> подготовить и утвердить случай, назначить его группе, наблюдать действия, быстро проверить разбор и выбрать следующее упражнение.')
    add('<b>Учащемуся:</b> отработать последовательность и смысл доклада в знакомом интерфейсе, затем понять, какое именно действие или формулировка требует исправления.')
    note('<b>Главная гипотеза пилота:</b> сократить время на корректно проверенный разбор без ухудшения обнаружения критических ошибок. Балл и скорость сами по себе не являются доказательством обучения.')
    add('Кабинетный ресёрч: 10 аналогов и 12 продуктовых гипотез; изучены материалы задания, инструкция, скриншоты, классификатор и запись Q&A. Интервью и педагогического пилота не было. Расшифровка Q&A машинная; спорные фразы не используются как точные цитаты.','small')
    add('Источники: <link href="https://i.moscow/hackaton/lct/9852d41aacad40178aaa2c90c627b09a" color="#28695b">официальная страница задачи</link>; <link href="https://drive.google.com/file/d/1qpYkmGuSVKPBrBQgC_WB5luTcDzr0ZW9/view" color="#28695b">запись Q&A</link>. Подробная traceability: docs/product-research.md и docs/coverage.md.','small')
    end()

    title(2,'Преподаватель: подготовить и проверить','Сценарий и критерии утверждает преподаватель. Изменения сценария не переписывают снимки уже назначенных попыток.')
    screenshot('teacher-overview.png','Рис. 1. Реальный экран кабинета на демонстрационной базе. Числа относятся к сохранённым синтетическим попыткам, а не результатам пилота.')
    table(['Шаг','Действие'],[
      ['1. Подготовить','Скопировать библиотечный пример или создать черновик. Проверить карточку, профиль службы, контакты, факты, статусы и время.'],
      ['2. Утвердить','Предпросмотр и approve обязательны перед назначением. Генерация AI создаёт только черновик.'],
      ['3. Наблюдать','Назначить практику или контроль. Смотреть карточку, текущий статус, таймеры, серверный черновик и журнал; обновление каждые 8 с.'],
      ['4. Проверить','Открыть доказательства замечаний. Подтвердить или скорректировать общий балл с причиной; исходный результат сохраняется.'],
    ],[.23,.77])
    add('Сохранённый черновик явно отделён от выполненного действия. Наблюдение не показывает текст, который остался только в браузере учащегося без синхронизации.','small')
    end()

    title(3,'Учащийся: полный цикл ДДС','В исходной карточке поля доступны для чтения. Действия выполняются вручную; ответ собеседника не засчитывается как собственный доклад.')
    screenshot('workspace-viewport.png','Рис. 2. Реальный АРМ: входящая строка, готовая карточка, программный телефон. Нижний журнал продолжает экран при прокрутке.')
    add('<b>1.</b> Открыть назначение и нажать «Начать». Отсчёт первой реакции заканчивается отдельным действием открытия карточки.')
    add('<b>2.</b> Изучить сведения, выбрать статус и написать содержательный комментарий. Статус и текст сохраняются раздельно.')
    add('<b>3.</b> Набрать учебный номер из 3-4 цифр, передать доклад и получить ответ. Проверить распознанный текст перед отправкой, если включён голос.')
    add('<b>4.</b> Зафиксировать предусмотренные сценарием действия и завершить разговор. Перед сдачей дождаться синхронизации всех событий.')
    note('В практике доступны учитываемые подсказки. В контроле они скрыты. Несколько назначений представлены отдельными попытками; это не заявляется полноценным тренингом одновременной диспетчерской нагрузки.')
    end()

    title(4,'Запуск и демонстрационные роли')
    add('Обычный запуск требует Node.js 22/npm, совместимого Python 3.12 или 3.13 и uv. Первый запуск устанавливает зависимости из lock-файлов и собирает интерфейс, поэтому нужен доступ к пакетным репозиториям.')
    code('./scripts/start.sh\n# После подготовки зависимостей и сборки:\n./scripts/start.sh --offline')
    add('Открыть <b>http://127.0.0.1:8000</b>. Конфигурация берётся из окружения либо backend/.env. В деморежиме создаются синтетические пользователи:')
    table(['Роль','Логин','Пароль'],[['Преподаватель','teacher','Demo112!'],['Учащийся','student','Demo112!'],['Администратор','admin','Demo112!']],[.44,.28,.28])
    add('Дополнительные профили: student_water, student_bridge, student_lift; тот же демопароль. Для параллельной демонстрации разных ролей используйте отдельные профили браузера: cookie одной роли действует на все вкладки профиля.')
    h('Что означает офлайн')
    add('start.sh --offline не устанавливает зависимости: backend/.venv и frontend/dist уже должны существовать. Отдельный wheelhouse для текущей платформы описан на следующей странице. Голос и LLM - необязательные процессы; текстовый цикл от них не зависит.')
    h('Доступ в классе и Docker')
    add('По умолчанию сервер опубликован только на loopback. Доступ из LAN включается явно. Для реального внедрения нужны отдельная БД без демопаролей, DEMO_MODE=false, уникальный bootstrap-пароль и HTTPS reverse proxy. Встроенного TLS нет.')
    code('docker compose build\ndocker compose up -d\n# Для уже собранного локального образа:\ndocker compose up -d --no-build --pull never')
    add('Docker-конфигурация проверена командой compose config. Build/run не выполнены: daemon в среде отсутствовал. Контейнер по умолчанию работает в rules/text режиме, без macOS AI-сервисов.','small')
    end()

    title(5,'Отдельный комплект для офлайн-установки')
    offline_path=ROOT/'runtime/offline-validation/result.json'
    add('Подготовлен native-platform wheelhouse для <b>CPython 3.12.13 / macOS arm64</b>: 31 wheel, 15 685 114 байт (около 15 МиБ). В него входят точные зависимости из backend/uv.lock с хешами и готовый frontend-dist.')
    note('Это не установщик на пустую ОС. Python 3.12 с venv и ensurepip должен быть установлен заранее. Исходники приложения передаются отдельно. Python runtime, AI-веса, .env и рабочая БД в wheelhouse не входят.',amber=True)
    h('Подготовка с интернетом')
    code('python3.12 scripts/prepare_offline.py \\\n  --python python3.12 \\\n  --destination runtime/offline-wheelhouse')
    h('Первая установка без пакетного индекса')
    code('python3.12 scripts/install_offline.py \\\n  --bundle runtime/offline-wheelhouse \\\n  --venv backend/.venv --smoke')
    add('Назначение venv должно быть новым. Установщик проверяет платформу и хеши, использует --no-index, --find-links и --require-hashes. Подробные параметры и запуск со статикой из wheelhouse: <b>docs/offline-install.md</b>.')
    h('Статус проверки')
    # Verified fresh-venv result supplied by the offline packaging agent.
    add('Свежий venv установлен с --no-index и блокировкой исходящих Python-соединений. pip check чистый. Smoke прошёл: 0 сетевых попыток, временная БД без .env, 8 сценариев, index и 2 статических ресурса, вход, назначение, телефон, сдача на 100 баллов, проверка и рекомендации.')
    add('Протокол: runtime/offline-validation/result.json. Это ASGI TestClient на текущем Mac, не браузерный тест и не отключение сети на уровне ОС.', 'small')
    h('Граница переносимости')
    add('Комплект привязан к семейству ОС, архитектуре и версии Python. Linux x86_64, Windows и целевой компьютер i5/16 ГБ здесь не проверены. Копия macOS venv не считается переносимым Linux-дистрибутивом.')
    add('Каталог runtime исключён из Git и source ZIP. Wheelhouse передаётся явно как дополнительный артефакт; наличие исходников и рецепта Docker не заменяет готовый проверенный комплект.','small')
    end()

    title(6,'Архитектура, права и сохранность')
    note('<b>Браузер React/TypeScript</b> → same-origin /api → <b>FastAPI</b> → SQLAlchemy → <b>SQLite WAL</b>.<br/>Один Uvicorn worker; ASGI admission ограничивает одновременно обслуживаемые API-запросы до 24.')
    table(['Контур','Ответственность'],[
      ['Преподаватель','Свои сценарии, назначения, наблюдение, утверждение и коррекция результата. Чужие материалы не редактирует.'],
      ['Учащийся','Только собственные назначения и история. До сдачи не получает скрытую рубрику и эталон.'],
      ['Администратор','Пользователи, диагностика, аудит. Не подменяет методическую роль преподавателя.'],
      ['События и снимки','Снимок версии сценария; серверное время, UUID события, уникальность внутри попытки. Повтор запроса не создаёт дубль.'],
      ['Черновик и сеть','Браузерный localStorage и серверный черновик. Последовательная очередь; сдача после синхронизации. Разрыв делает тайминг спорным.'],
    ],[.27,.73])
    h('Доступ и конфигурация')
    add('Пароли хешируются scrypt; cookies HttpOnly/SameSite, настраиваемый Secure. Проверяются роль и владелец, Origin изменяющих запросов, размеры тела и активность пользователя. Есть аудит. Это меры MVP и регрессионные тесты, не независимый security-аудит.')
    h('Резервная копия и восстановление')
    code('python3 scripts/backup.py --source backend/var/dds.db \\\n  --destination backups/dds-copy-01.sqlite3\npython3 scripts/restore.py --source backups/dds-copy-01.sqlite3 \\\n  --destination backups/dds-restored-01.sqlite3')
    add('Каталог назначения создаётся заранее, файл должен быть новым. SQLite online backup учитывает WAL. Restore проверяет схему и целостность, удаляет токены входа и не переключает работающий сервер. Модели, конфигурация и справочники вне БД сохраняются отдельно.','small')
    add('PostgreSQL URL предусмотрен кодом, но развёртывание и восстановление PostgreSQL не испытаны. Подробности: docs/architecture.md, docs/backup-restore.md.','small')
    end()

    title(7,'AI помогает, преподаватель решает')
    table(['Компонент','Роль','Граница'],[
      ['Qwen3 1.7B<br/>:11434','Черновые формулировки; экспериментальные советы по спорным критериям','Не выставляет балл. Советы только по review content/grammar; при их отсутствии модель не вызывается.'],
      ['Whisper small<br/>:11435','Запись или аудиофайл → проверяемый текст доклада','Учащийся исправляет и отправляет отдельно. Raw аудио не сохраняется прокси в БД.'],
      ['Milena / macOS say<br/>:11436','Полная озвучка сохранённой реплики контакта','Только установленный macOS-голос; 1999 символов, один слот, тайм-аут 20 с.'],
    ],[.23,.35,.42])
    h('Как устроена оценка')
    add('Правила проверяют время, номера и последовательность; ограниченные смысловые признаки различают факт, отрицание, вопрос и будущее. Неизвестный смысл получает «Нужна проверка». Статус нельзя заменить правильной фразой. Для двух полных демосценариев подтверждение контакта должно предшествовать собственной записи учащегося.')
    add('Критерии и ссылки на события видны в разборе. Общая коррекция преподавателя сохраняется отдельно от первичной оценки. AI-совет принимается только с существующим критерием и дословной цитатой; это не доказывает правильность интерпретации.')
    note('<b>Почему нет автономной AI-оценки:</b> диагностический набор небольшой модели дал 3 из 6 смысловых проверок. В браузере модель дала два ложных замечания к корректному докладу; цитаты были настоящими, выводы неверными. Раздел свёрнут и помечен экспериментальным. Полезность оставшихся советов не валидирована.',amber=True)
    h('Следующее упражнение')
    add('Прозрачная эвристика рассматривает до 10 подходящих попыток; при менее 3 данных не хватает. Рекомендации содержат основание и ссылки на попытки. Спорные неподтверждённые и остановленные работы исключаются; назначение остаётся решением преподавателя.')
    add('Локальные модели проверены на Mac arm64 / 48 ГБ, CPU. Это не замер на целевом i5. Установка и веса не включены в source ZIP; отдельные команды, хеши и ограничения: docs/local-ai.md, docs/local-tts.md, docs/adaptation.md.','small')
    end()

    title(8,'Что проверено технически')
    table(['Проверка','Результат','Что это не доказывает'],[
      ['Backend pytest','97 passed','Не заменяет пользовательскую и методистскую приёмку.'],
      ['Stdlib tests','20 passed','Импорт, backup и упаковка; не полная приёмка поставки.'],
      ['Клиентская очередь','Отдельные проверки UUID и повторов','Не гарантирует сохранность при очистке профиля или отказе диска.'],
      ['Frontend','TypeScript + Vite build прошли','Build не является аудитом доступности.'],
      ['Зависимости','npm 121 entries / Python 26: 0 известных advisory','Не аудит OS-образов, весов AI и всех платформенных пакетов.'],
    ],[.28,.25,.47])
    h('Синтетический benchmark')
    add('40 кейсов содержат 48 утверждений. Адаптер поддерживает 28; точное совпадение для 27 из них. 20 помечены unsupported, четыре результата отправлены на ручную проверку. Нет независимой слепой разметки методистом; это не «точность 96%» на реальной работе.')
    h('Нагрузка: короткий API-прогон')
    add('100 различных авторизованных пользователей: 300 чтений, p95 417 мс. 20 активных попыток: 200 записей, 529 запросов/с; все 200 событий сохранены. 20 отчётов: p95 69 мс. Ошибок HTTP в этом прогоне нет.')
    add('Платформа: Mac arm64, 48 ГБ, SQLite WAL, один worker. Не измерены длительная нагрузка, браузерный рендеринг, школьная сеть и 20 параллельных голосовых занятий. HTTP commits не равны отдельным SQL INSERT.','small')
    h('Интеграционные наблюдения')
    add('В браузере пройден цикл назначения, неверного/верного номера и сдачи. Проверен WebM → редактируемая расшифровка; ответ озвучивается через TTS. Контролируемый разрыв backend более 30 с дал однократное сохранение ожидавшего события; факт разрыва отражён в журнале.')
    add('Доказательства: docs/benchmark-results.json, docs/load-test-results.json, docs/dependency-audit.json и тесты в backend/tests, tests. Свежий повтор: scripts/check.sh.','small')
    end()

    title(9,'Пилот: проверить пользу, а не обещать её','План ниже предложен командой. Участники, сроки и критерии ещё не согласованы с заказчиком; результатов пилота нет.')
    table(['Этап','Метод и результат'],[
      ['1. Методистская сверка','2-3 преподавателя: согласовать 20-30 учебных ситуаций, критические ошибки, эталонные факты и допустимые перефразы. Уточнить границы таймеров.'],
      ['2. Проверка интерфейса','6-8 учащихся разного опыта, включая старшую аудиторию: наблюдение без подсказок разработчика. Пройти вход, карточку, звонок, статус, сдачу и разбор.'],
      ['3. Сравнительный пилот','Предложено 12-20 учащихся и минимум два преподавателя. Сопоставимые случаи: обычный разбор и разбор с тренажёром; порядок чередовать.'],
    ],[.28,.72])
    h('Что измерять')
    add('<b>Время преподавателя:</b> медиана минут на один корректно проверенный разбор, отдельно от времени автора сценария. Сравнивать одинаковый состав и сложность задач.')
    add('<b>Качество:</b> слепое экспертное обнаружение критических ошибок, ложные подтверждения и неопределённые случаи. Отдельно считать расхождения преподавателей и исправленные AI-советы.')
    add('<b>Самостоятельность:</b> доля успешно завершённых попыток без помощи разработчика, число подсказок и причины прерывания. Скорость интерфейса не смешивать со скоростью навыка.')
    add('<b>Сохранность:</b> ожидаемые и фактически сохранённые события, черновики и отчёт после обрыва связи и перезапуска.')
    note('<b>Предложенные условия перехода:</b> все критические ошибки контрольного набора замечены либо явно отправлены на проверку; не менее 95% назначенных попыток заканчиваются сохранённым разбором; медианное время преподавателя уменьшается хотя бы на 20% без ухудшения согласованной точности. Это цели для обсуждения, не полученные результаты.')
    add('Перенос навыков проверяется отдельной последующей отработкой в штатной учебной среде. Самооценка удобства и высокий балл в тренажёре не заменяют эту проверку.','small')
    end()

    title(10,'Покрытие, ограничения и комплект сдачи')
    table(['Область','Текущий статус'],[
      ['Полный поток ДДС','Реализован и технически проверен: сценарий → approve → назначение → доклад/статусы → разбор → преподаватель.'],
      ['Классификатор','046.11 / 15.11.2024: 1281 тип с происхождением. В источнике 271 тип пожара/задымления; предупреждение сохранено. 046.24 и дополнительные билеты не импортированы.'],
      ['Наблюдение и карточки','Polling 8 с; контекст, черновик, все события. Карточка - отдельная попытка; одновременная нагрузка не валидирована.'],
      ['Не включено','Первичный приём 112, настоящие SIP/РТУ, SMS/связанные карточки, тепловые карты, полноценный Excel/PDF-экспорт индивидуального отчёта. CSV есть.'],
      ['Не подтверждено','Педагогический эффект, целевой Linux/i5, Docker runtime, PostgreSQL, шумная живая речь, длительная нагрузка класса.'],
    ],[.28,.72])
    h('Карта файлов')
    table(['Артефакт','Назначение'],[
      ['kontur-dds-guide.pdf','Это руководство: продукт, роли, запуск, доказательства и ограничения.'],
      ['kontur-dds-defense-v1.pptx / .pdf','Редактируемая презентация и PDF защиты.'],
      ['kontur-dds-source.zip','Исходники, готовый frontend, тесты и документы. Без .env, рабочих БД, документов заказчика и AI-весов.'],
      ['runtime/offline-wheelhouse/','Отдельно передаваемые wheels и frontend для текущей платформы.'],
      ['README.md / docs/','Запуск, API, покрытие, AI, backup/restore, протоколы и сценарий демонстрации.'],
    ],[.40,.60])
    add('ТЗ требует ссылки на репозиторий, презентацию, прототип и документацию. Локальные файлы сами по себе не создают публичные ссылки. Q&A дополнительно просит запись экрана со звуком до 5 минут; сценарий видео не равен готовой записи.','small')
    

    args.output.parent.mkdir(parents=True,exist_ok=True)
    doc=SimpleDocTemplate(str(args.output),pagesize=A4,rightMargin=48,leftMargin=48,topMargin=57,bottomMargin=52,title='Контур ДДС - сопроводительная документация',author='Контур ДДС',subject='Учебный прототип, руководство и границы проверок',pageCompression=1)
    doc.build(story,onFirstPage=cover,onLaterPages=foot)
    print(args.output)


if __name__=='__main__': main()
