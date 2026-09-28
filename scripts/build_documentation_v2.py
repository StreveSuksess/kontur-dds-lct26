#!/usr/bin/env python3
"""Six-page RC2 jury companion, generated from reviewed project facts.

This deliberately does not alter the frozen RC1 guide. The PDF contains no
source/offline ZIP digest because those archives are repackaged after this file.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "deliverables/kontur-dds-documentation-v2.pdf"
PAGE_W, PAGE_H = A4
MARGIN = 48
WIDTH = PAGE_W - 2 * MARGIN
DARK = colors.HexColor("#203538")
GREEN = colors.HexColor("#3D6E61")
MUTED = colors.HexColor("#61736D")
LINE = colors.HexColor("#D7E0D8")
PALE = colors.HexColor("#F2F6F1")
PAPER = colors.HexColor("#FAFBF9")
LIGHT = colors.HexColor("#BED3C4")
AMBER = colors.HexColor("#FFF3DC")


def fonts() -> None:
    root = Path("/System/Library/Fonts/Supplemental")
    pdfmetrics.registerFont(TTFont("DDS", str(root / "Arial.ttf")))
    pdfmetrics.registerFont(TTFont("DDSBold", str(root / "Arial Bold.ttf")))
    pdfmetrics.registerFontFamily("DDS", normal="DDS", bold="DDSBold", italic="DDS", boldItalic="DDSBold")


def styles() -> dict[str, ParagraphStyle]:
    return {
        "body": ParagraphStyle("body", fontName="DDS", fontSize=10.5, leading=15.2, textColor=DARK),
        "small": ParagraphStyle("small", fontName="DDS", fontSize=8.7, leading=12.5, textColor=MUTED),
        "lead": ParagraphStyle("lead", fontName="DDS", fontSize=12.4, leading=18, textColor=MUTED),
        "h2": ParagraphStyle("h2", fontName="DDSBold", fontSize=13.1, leading=18, textColor=GREEN),
        "cell": ParagraphStyle("cell", fontName="DDS", fontSize=9.2, leading=13.2, textColor=DARK),
        "thead": ParagraphStyle("thead", fontName="DDSBold", fontSize=9.1, leading=12.8, textColor=colors.white),
        "cover": ParagraphStyle("cover", fontName="DDS", fontSize=19.5, leading=27.5, textColor=colors.white),
        "coverbody": ParagraphStyle("coverbody", fontName="DDS", fontSize=11.2, leading=16.5, textColor=DARK),
    }


def para(c: canvas.Canvas, text: str, x: float, top: float, width: float,
         style: ParagraphStyle, gap: float = 0) -> float:
    item = Paragraph(text, style)
    _, height = item.wrap(width, PAGE_H)
    item.drawOn(c, x, top - height)
    return top - height - gap


def footer(c: canvas.Canvas, page: int) -> None:
    c.setStrokeColor(LINE)
    c.setLineWidth(.6)
    c.line(MARGIN, 43, PAGE_W - MARGIN, 43)
    c.setFont("DDS", 8.1)
    c.setFillColor(MUTED)
    c.drawString(MARGIN, 27, "Учебный прототип. Синтетические данные. Не действующая система-112.")
    c.drawRightString(PAGE_W - MARGIN, 27, f"{page} / 6")


def page_header(c: canvas.Canvas, page: int, title: str, subtitle: str) -> float:
    c.setFillColor(PAPER)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    c.setFillColor(GREEN)
    c.setFont("DDSBold", 8.7)
    c.drawString(MARGIN, PAGE_H - 31, "КОНТУР ДДС  /  RC2")
    c.setStrokeColor(LINE)
    c.line(MARGIN, PAGE_H - 39, PAGE_W - MARGIN, PAGE_H - 39)
    c.setFillColor(DARK)
    c.setFont("DDSBold", 23)
    c.drawString(MARGIN, PAGE_H - 82, title)
    y = para(c, subtitle, MARGIN, PAGE_H - 101, WIDTH, STYLES["lead"], 11)
    footer(c, page)
    c.bookmarkPage(f"page-{page}")
    c.addOutlineEntry(title, f"page-{page}", level=0)
    return y


def callout(c: canvas.Canvas, title: str, body: str, x: float, top: float,
            width: float, height: float, amber: bool = False) -> None:
    c.setFillColor(AMBER if amber else PALE)
    c.setStrokeColor(LINE)
    c.roundRect(x, top - height, width, height, 7, fill=1, stroke=1)
    c.setFillColor(GREEN if not amber else DARK)
    c.setFont("DDSBold", 11.3)
    c.drawString(x + 14, top - 24, title)
    end = para(c, body, x + 14, top - 38, width - 28, STYLES["small"])
    if end < top - height + 9:
        raise ValueError(f"Callout overflow: {title}")


def section(c: canvas.Canvas, label: str, top: float) -> float:
    c.setFillColor(GREEN)
    c.setFont("DDSBold", 13.1)
    c.drawString(MARGIN, top - 14, label)
    return top - 26


def row(c: canvas.Canvas, number: str, title: str, body: str, top: float) -> float:
    c.setFillColor(GREEN)
    c.setFont("DDSBold", 15)
    c.drawString(MARGIN, top - 17, number)
    c.setFillColor(DARK)
    c.setFont("DDSBold", 10.8)
    c.drawString(MARGIN + 38, top - 17, title)
    para(c, body, MARGIN + 171, top - 4, WIDTH - 171, STYLES["body"])
    c.setStrokeColor(LINE)
    c.line(MARGIN + 38, top - 44, PAGE_W - MARGIN, top - 44)
    return top - 52


def grid(c: canvas.Canvas, headers: list[str], rows: list[list[str]],
         widths: list[float], top: float, size: str = "cell") -> float:
    entries = [[Paragraph(text, STYLES["thead"]) for text in headers]]
    entries.extend([[Paragraph(text, STYLES[size]) for text in line] for line in rows])
    table = Table(entries, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LINEBELOW", (0, 1), (-1, -1), .4, LINE),
    ]))
    _, height = table.wrapOn(c, WIDTH, PAGE_H)
    table.drawOn(c, MARGIN, top - height)
    return top - height


def code(c: canvas.Canvas, lines: list[str], top: float, *, x: float = MARGIN,
         width: float = WIDTH, font_size: float = 8.6) -> float:
    line_height = 14
    height = 18 + line_height * len(lines)
    c.setFillColor(PALE)
    c.setStrokeColor(LINE)
    c.roundRect(x, top - height, width, height, 6, fill=1, stroke=1)
    c.setFillColor(DARK)
    c.setFont("Courier", font_size)
    for index, line in enumerate(lines):
        c.drawString(x + 11, top - 18 - index * line_height, line)
    return top - height - 12


def cover(c: canvas.Canvas) -> None:
    c.setFillColor(PAPER)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    c.setFillColor(DARK)
    c.rect(0, 306, PAGE_W, PAGE_H - 306, fill=1, stroke=0)
    c.setFillColor(LIGHT)
    c.setFont("DDSBold", 10)
    c.drawString(MARGIN, PAGE_H - 75, "ЛЦТ  /  СОПРОВОДИТЕЛЬНАЯ ДОКУМЕНТАЦИЯ  /  RC2")
    c.setFillColor(colors.white)
    c.setFont("DDSBold", 43)
    c.drawString(MARGIN - 2, 655, "Контур ДДС")
    para(c, "Тренажёр работы по готовой карточке.<br/>Проверяемый разбор преподавателя.",
         MARGIN, 620, WIDTH, STYLES["cover"])
    c.setFillColor(LIGHT)
    c.rect(MARGIN, 364, 56, 4, fill=1, stroke=0)
    c.setFillColor(GREEN)
    c.setFont("DDSBold", 12)
    c.drawString(MARGIN, 263, "ЧТО В КОМПЛЕКТЕ")
    para(c, "Рабочий учебный цикл, отдельное решение по спорному критерию, инструкция по локальному запуску и карта технических доказательств.",
         MARGIN, 247, WIDTH, STYLES["coverbody"], 8)
    para(c, "Проверки выполнены на синтетических данных. Методистского пилота и измеренного эффекта обучения пока нет.",
         MARGIN, 183, WIDTH, STYLES["coverbody"])
    c.setFillColor(MUTED)
    c.setFont("DDS", 9)
    c.drawString(MARGIN, 92, "26 сентября 2026  /  отдельное руководство к RC2")
    footer(c, 1)
    c.bookmarkPage("page-1")
    c.addOutlineEntry("Контур ДДС", "page-1", level=0)
    c.showPage()


def page_cycle(c: canvas.Canvas) -> None:
    top = page_header(c, 2, "Один учебный цикл", "Готовая карточка ДДС, исходящий доклад и итоговый разбор в двух ролях.")
    screenshot = ROOT / "deliverables/assets/workspace-viewport.png"
    with PILImage.open(screenshot) as image:
        image_w, image_h = image.size
    width = WIDTH
    height = width * image_h / image_w
    c.drawImage(str(screenshot), MARGIN, top - height, width=width, height=height,
                preserveAspectRatio=True, mask="auto")
    y = top - height - 8
    y = para(c, "Фактический экран прототипа с синтетической карточкой. Поля и цвета основаны на материалах заказчика; применимость к рабочему АРМ не проверена методистом.",
             MARGIN, y, WIDTH, STYLES["small"], 12)
    for number, title, body in [
        ("01", "Преподаватель", "Проверяет сценарий и критерии, утверждает версию, назначает ученику."),
        ("02", "Учащийся", "Открывает готовую карточку, фиксирует статусы и комментарии."),
        ("03", "Исходящий звонок", "Набирает учебный номер, докладывает и сохраняет ответ контакта."),
        ("04", "Сдача и разбор", "Видит оценку с событиями; преподаватель подтверждает спорное."),
    ]:
        y = row(c, number, title, body, y)
    if y < 63:
        raise ValueError("Page 2 content overlaps footer")
    c.showPage()


def page_review(c: canvas.Canvas) -> None:
    y = page_header(c, 3, "Как работает разбор RC2", "Преподаватель исправляет конкретный вывод и оставляет основание, исходный результат правил сохраняется.")
    y = grid(c, ["Слой результата", "Что сохраняется", "Что видит участник"], [
        ["Исходный отчёт", "Баллы, статусы критериев и ссылки на исходные события остаются неизменными.", "Почему правила поставили оценку или отправили случай на проверку."],
        ["Решение по критерию", "Преподаватель выбирает «выполнено», «не выполнено» или «проверить», добавляет основание и события.", "Решение, автора, время и доказательства в разборе завершённой попытки."],
        ["Общий итог", "Отдельное подтверждение балла с номером ревизии. Новая правка делает прежний итог устаревшим.", "Какая оценка подтверждена преподавателем и требуется ли повторная проверка."],
    ], [116, 192, WIDTH - 308], y)
    y -= 22
    y = section(c, "Защита от потери смысла и правок", y)
    y = para(c, "Каждое изменённое решение попадает в журнал с прежним и новым значением. Повтор без изменений не создаёт новую ревизию. Вторая вкладка не может молча перезаписать решение по устаревшей ревизии: сервер возвращает конфликт.",
             MARGIN, y, WIDTH, STYLES["body"], 14)
    callout(c, "Данные для рекомендаций", "Незавершённое покритериальное решение и устаревший общий итог не входят в анализ. Остановленные занятия исключаются. Подтверждение одного факта не удостоверяет остальные критерии.",
            MARGIN, y, WIDTH, 91)
    y -= 107
    y = para(c, "Проверенный путь: преподаватель исправил ошибочный зачёт отсутствующего адреса, повторно подтвердил итог и увидел решение глазами ученика. Это технический браузерный тест синтетической попытки; экономия труда преподавателя не измерялась.",
             MARGIN, y, WIDTH, STYLES["small"])
    if y < 65:
        raise ValueError("Page 3 content overlaps footer")
    c.showPage()


def page_install(c: canvas.Canvas) -> None:
    y = page_header(c, 4, "Как получить локальный прототип", "Два архива RC2 решают разные задачи. Оба открываются в каталоге kontur-dds/.")
    callout(c, "Исходники RC2", "kontur-dds-source-rc2.zip содержит код, готовый интерфейс и документацию. Для установки серверных пакетов нужен интернет, Python 3.12/3.13 и uv. Node.js 22 с npm нужны только для пересборки интерфейса.",
            MARGIN, y, WIDTH, 89)
    y -= 101
    y = code(c, ["cd kontur-dds", "uv sync --project backend --frozen --no-dev", "./scripts/start.sh --offline"], y)
    y = para(c, "Здесь --offline означает запуск без установки. Первоначальная синхронизация пакетов уже должна пройти.",
             MARGIN, y, WIDTH, STYLES["small"], 13)
    callout(c, "Офлайн-комплект macOS arm64", "kontur-dds-macos-arm64-offline-rc2.zip содержит те же исходники, готовый интерфейс и 31 закреплённый wheel. Нужен заранее установленный CPython 3.12 с venv и ensurepip. Node.js, npm и uv на целевой машине для этого пути не нужны.",
            MARGIN, y, WIDTH, 101)
    y -= 113
    y = code(c, ["cd kontur-dds", "python3.12 scripts/install_offline.py --python python3.12 \\",
                 "  --bundle runtime/offline-wheelhouse --venv backend/.venv --smoke"], y, font_size=8)
    y = para(c, "Дальнейший запуск описан в OFFLINE-INSTALL-README.md внутри архива. Откройте http://127.0.0.1:8000. Учебные логины teacher, student, admin имеют публичный демопароль Demo112! только при DEMO_MODE=true.",
             MARGIN, y, WIDTH, STYLES["body"], 12)
    y = para(c, "Модели AI, Python runtime, рабочая база и реальные документы заказчика в архивы не входят. На Linux/Windows этот macOS-комплект не проверен.",
             MARGIN, y, WIDTH, STYLES["small"])
    if y < 63:
        raise ValueError("Page 4 content overlaps footer")
    c.showPage()


def page_evidence(c: canvas.Canvas) -> None:
    y = page_header(c, 5, "Где проверить утверждения", "Исходный код, тесты и измерения лежат рядом с прототипом; человеческая валидация выделена отдельно.")
    y = grid(c, ["Вопрос жюри", "Проверяемое свидетельство"], [
        ["Работает ли RC2", "128 backend-, 28 системных и 13 клиентских тестов, Vite build, браузерный путь преподаватель - ученик. docs/release-readiness.md, docs/ui-validation.md"],
        ["Можно ли установить без сети", "Распакованный RC2 офлайн-архив: свежий Python venv, 31 wheel, pip check, ASGI smoke и 0 сетевых попыток. OFFLINE-INSTALL-README.md; deliverables/offline-release-rc2-smoke.json"],
        ["Что проверяет оценка", "Исходные события и критерии: docs/api-contract.md, docs/adaptation.md. Синтетический benchmark: docs/benchmark-results.json"],
        ["Откуда взят продуктовый фокус", "Материалы заказчика и Q&amp;A, десять аналогов, гипотезы и ограничения: docs/product-research.md, docs/coverage.md"],
        ["Есть ли педагогический эффект", "Пока нет измерения на людях. Протокол и пустые формы: docs/pilot-protocol.md, docs/pilot-templates/"],
    ], [153, WIDTH - 153], y)
    y -= 20
    y = section(c, "Проверка конкретного архива", y)
    y = para(c, "Рядом с каждым ZIP лежит файл *.validation.json; внутри есть манифест точных путей и хешей. Перед демонстрацией проверяйте именно выбранную версию архива. В этом PDF хеши ZIP намеренно не указаны: упаковка после добавления документа меняет их.",
             MARGIN, y, WIDTH, STYLES["body"], 16)
    callout(c, "Разделение доказательств", "Тесты и локальный smoke подтверждают поведение кода и конкретного пакета. Синтетические benchmark и нагрузка не доказывают точность на операторах или пользу обучения.",
            MARGIN, y, WIDTH, 79)
    y -= 94
    y = para(c, "Для первичного просмотра: README.md. Для архитектуры: docs/architecture.md. Для подробной воспроизводимости офлайн-поставки: docs/offline-install.md и docs/offline-distribution.md.",
             MARGIN, y, WIDTH, STYLES["small"])
    if y < 63:
        raise ValueError("Page 5 content overlaps footer")
    c.showPage()


def page_limits(c: canvas.Canvas) -> None:
    y = page_header(c, 6, "Границы и следующий шаг", "Прототип готов к локальной демонстрации. Методистская полезность и работа на целевой инфраструктуре остаются проверяемыми вопросами.")
    y = grid(c, ["Сейчас подтверждено", "Что ещё требует проверки"], [
        ["Локальный текстовый цикл и исправление критерия на синтетических заданиях.", "Два преподавателя и 6-8 учащихся в пилоте, наблюдение интерфейса, согласованность экспертных решений и перенос на новый случай."],
        ["Короткий API-прогон на Mac arm64 / 48 ГБ.", "Длительное занятие на целевых i5/16 ГБ, Linux/Docker и PostgreSQL. Живой микрофон тоже не проверен."],
        ["Классификатор 046.11 с предупреждением о 271 пожарном типе.", "Версия 046.24 и действующие правила маршрутизации не подтверждены; реальная SIP/РТУ и первичный приём 112 отсутствуют."],
    ], [WIDTH * .46, WIDTH * .54], y)
    y -= 22
    callout(c, "Модель 4B не допущена к оцениванию", "На 48 авторских синтетических примерах Qwen3-4B дала 32 верных ответа и 4 ложных подтверждения. Заранее заданный порог требовал 44/48 и ноль ложных подтверждений. Итог определяют правила и преподаватель.",
            MARGIN, y, WIDTH, 91, amber=True)
    y -= 109
    y = section(c, "Пилот, который может проверить пользу", y)
    y = para(c, "До наблюдений согласовать рубрику и сопоставимые задания. В ручном и продуктовом условиях симметрично замерять подготовку, проверку, исправления и обратную связь. Предварительная гипотеза - не менее 20% экономии активного времени у обоих преподавателей без ухудшения критических ошибок. Пилот пока не проводился.",
             MARGIN, y, WIDTH, STYLES["body"], 12)
    y = para(c, "Комплект для жюри: презентация deliverables/kontur-dds-defense-v2.pdf, это руководство и локальные RC2 архивы. Для сдачи по правилам хакатона ещё нужны реальные ссылки на репозиторий, прототип и материалы; этот PDF ссылки не публикует.",
             MARGIN, y, WIDTH, STYLES["small"])
    if y < 63:
        raise ValueError("Page 6 content overlaps footer")
    c.showPage()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    fonts()
    global STYLES
    STYLES = styles()
    required = [ROOT / "docs/release-readiness.md", ROOT / "docs/pilot-protocol.md",
                ROOT / "docs/model-comparison.md", ROOT / "deliverables/assets/workspace-viewport.png"]
    if not all(item.exists() for item in required):
        raise FileNotFoundError("RC2 research or screenshot is missing")
    readiness = required[0].read_text(encoding="utf-8")
    if not all(phrase in readiness for phrase in ("128 backend-тестов", "28 системных", "13 клиентских")):
        raise ValueError("RC2 evidence changed: review the PDF claims before rebuilding")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    document = canvas.Canvas(str(args.output), pagesize=A4, pageCompression=1,
                             invariant=1, bottomup=1)
    document.setTitle("Контур ДДС - сопроводительная документация RC2")
    document.setSubject("Учебный цикл, экспертный разбор, установка и границы доказательств")
    document.setAuthor("Команда Контур ДДС")
    cover(document)
    page_cycle(document)
    page_review(document)
    page_install(document)
    page_evidence(document)
    page_limits(document)
    document.save()
    print(args.output)


if __name__ == "__main__":
    main()
