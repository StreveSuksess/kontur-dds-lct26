#!/usr/bin/env python3
"""Build the v3 companion PDF from docs/documentation-v3.md.

Run with the bundled Python runtime (reportlab required):
    python scripts/build_documentation_v3.py
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/documentation-v3.md"
OUTPUT = ROOT / "deliverables/kontur-dds-documentation-v3.pdf"
PAGE_W, PAGE_H = A4
MARGIN = 45
INK = colors.HexColor("#203538")
ACCENT = colors.HexColor("#3D6E61")
MUTED = colors.HexColor("#61736D")
LINE = colors.HexColor("#D7E0D8")
PALE = colors.HexColor("#F2F6F1")


def register_fonts() -> None:
    font_dir = Path("/System/Library/Fonts/Supplemental")
    pdfmetrics.registerFont(TTFont("DDS", str(font_dir / "Arial.ttf")))
    pdfmetrics.registerFont(TTFont("DDSBold", str(font_dir / "Arial Bold.ttf")))
    pdfmetrics.registerFontFamily("DDS", normal="DDS", bold="DDSBold")


def inline(value: str) -> str:
    """Render only the Markdown inline constructs used by the source."""
    value = value.replace("—", "-").replace("–", "-").replace("‑", "-")
    value = escape(value)
    value = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", value)
    value = re.sub(r"`([^`]+)`", r'<font name="DDSBold" color="#3D6E61">\1</font>', value)
    return value


def styles() -> dict[str, ParagraphStyle]:
    base = dict(alignment=TA_LEFT, allowWidows=0, allowOrphans=0)
    return {
        "title": ParagraphStyle("title", **base, fontName="DDSBold", fontSize=27, leading=33, textColor=INK, spaceAfter=13),
        "subtitle": ParagraphStyle("subtitle", **base, fontName="DDS", fontSize=9.2, leading=13, textColor=MUTED, spaceAfter=15),
        "section": ParagraphStyle("section", **base, fontName="DDSBold", fontSize=13, leading=17, textColor=ACCENT, spaceBefore=15, spaceAfter=8, keepWithNext=1),
        "body": ParagraphStyle("body", **base, fontName="DDS", fontSize=9.45, leading=14.2, textColor=INK, spaceAfter=8),
        "cell": ParagraphStyle("cell", **base, fontName="DDS", fontSize=8.1, leading=11.1, textColor=INK),
        "thead": ParagraphStyle("thead", **base, fontName="DDSBold", fontSize=8.1, leading=11.1, textColor=colors.white),
    }


def table(lines: list[str], style: dict[str, ParagraphStyle]) -> Table:
    rows = [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in lines]
    rows = [rows[0], *rows[2:]]  # remove Markdown alignment separator
    count = len(rows[0])
    if not all(len(row) == count for row in rows):
        raise ValueError("Inconsistent Markdown table column count")
    width = PAGE_W - MARGIN * 2
    proportions = {2: (0.32, 0.68), 3: (0.23, 0.43, 0.34)}.get(count)
    if proportions is None:
        raise ValueError(f"Unsupported Markdown table width: {count}")
    data = [
        [Paragraph(inline(cell), style["thead"] if index == 0 else style["cell"]) for cell in row]
        for index, row in enumerate(rows)
    ]
    item = Table(data, colWidths=[width * value for value in proportions], repeatRows=1, hAlign="LEFT")
    item.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), INK),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, LINE),
    ]))
    return item


def story_from_markdown(source: str) -> list:
    style = styles()
    lines = source.splitlines()
    story: list = []
    cursor = 0
    while cursor < len(lines):
        line = lines[cursor].strip()
        if not line:
            cursor += 1
            continue
        if line.startswith("| "):
            block = []
            while cursor < len(lines) and lines[cursor].strip().startswith("|"):
                block.append(lines[cursor])
                cursor += 1
            story.extend([table(block, style), Spacer(1, 9)])
            continue
        if line.startswith("# "):
            story.append(Paragraph(inline(line[2:]), style["title"]))
            cursor += 1
            continue
        if line.startswith("## "):
            story.append(Paragraph(inline(line[3:]), style["section"]))
            cursor += 1
            continue
        block = [line]
        cursor += 1
        while cursor < len(lines) and lines[cursor].strip() and not lines[cursor].startswith(("#", "|")):
            block.append(lines[cursor].strip())
            cursor += 1
        paragraph = " ".join(block)
        kind = "subtitle" if not story else "body"
        story.append(Paragraph(inline(paragraph), style[kind]))
    return story


def on_page(canvas, doc) -> None:
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.65)
    canvas.line(MARGIN, PAGE_H - 35, PAGE_W - MARGIN, PAGE_H - 35)
    canvas.setFillColor(ACCENT)
    canvas.setFont("DDSBold", 8)
    canvas.drawString(MARGIN, PAGE_H - 27, "КОНТУР ДДС / ДОКУМЕНТАЦИЯ V3")
    canvas.line(MARGIN, 43, PAGE_W - MARGIN, 43)
    canvas.setFillColor(MUTED)
    canvas.setFont("DDS", 7.5)
    canvas.drawString(MARGIN, 29, "Учебный прототип. Синтетические данные. 28.09.2026")
    canvas.drawRightString(PAGE_W - MARGIN, 29, str(doc.page))
    canvas.restoreState()


def build(output: Path) -> None:
    register_fonts()
    source = SOURCE.read_text(encoding="utf-8")
    required = ("28/48", "27/28", "30 секунд", "3 минуты", "112", "working", "started_at")
    missing = [phrase for phrase in required if phrase not in source]
    if missing:
        raise ValueError(f"Required v3 claims absent from source: {missing}")
    output.parent.mkdir(parents=True, exist_ok=True)
    document = BaseDocTemplate(
        str(output), pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=53, bottomMargin=55, title="Контур ДДС - сопроводительная документация v3",
        author="Команда Контур ДДС", subject="Учебный прототип, проверка и ограничения",
        pageCompression=1, invariant=1,
    )
    frame = Frame(MARGIN, 55, PAGE_W - MARGIN * 2, PAGE_H - 108, leftPadding=0,
                  bottomPadding=0, rightPadding=0, topPadding=0)
    document.addPageTemplates(PageTemplate(id="body", frames=[frame], onPage=on_page))
    document.build(story_from_markdown(source))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    build(args.output)
    print(args.output)


if __name__ == "__main__":
    main()
