"""Read the supplied OOXML classifier without executing macros or formulas.

Merged-cell values are resolved only inside their actual ranges. Routing columns
remain explicitly conditional source data: they are NOT an operational routing
engine or a claim that all listed services should respond simultaneously.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
SERVICE_NAMES = {
    "MCHS": "Служба 101", "Police": "Служба 102", "AMBULANCE": "Служба 103",
    "MOSGAZ": "Служба 104", "MOSLIFT": "Мослифт", "MOSVODOCANAL": "Мосводоканал",
    "MOSVODOSTOK": "Мосводосток", "GORMOST": "Гормост", "MOSCOLLECTOR": "Москоллектор",
    "AUTOROADS": "Автомобильные дороги", "MOEK": "МОЭК", "OEK": "ОЭК",
    "MOESK": "Россети Московский регион", "MOSGORTRANS": "Мосгортранс",
    "METRO": "Метрополитен", "MZD": "Московская железная дорога", "MGTS": "МГТС",
    "GKH": "Городское хозяйство", "ZODD": "ЦОДД", "ZEMP": "ЦЭМП",
    "MSPPN": "Московская служба психологической помощи", "Dep.tszn": "Департамент ТСЗН",
    "DepEco": "Департамент природопользования",
}


def col_number(value: str) -> int:
    n = 0
    for c in value.upper():
        n = n * 26 + ord(c) - 64
    return n


def col_name(value: int) -> str:
    result = ""
    while value:
        value, rem = divmod(value - 1, 26)
        result = chr(65 + rem) + result
    return result


def split_cell(ref: str) -> tuple[int, int]:
    match = re.fullmatch(r"([A-Z]+)(\d+)", ref)
    if not match:
        raise ValueError(f"Invalid cell reference: {ref}")
    return col_number(match[1]), int(match[2])


def read_sheet(path: Path) -> tuple[dict[str, str], dict[str, str], list[int]]:
    with zipfile.ZipFile(path) as archive:
        # A read-only import should not let a malicious OOXML archive consume
        # unbounded memory. The genuine input is less than one megabyte zipped.
        if sum(i.file_size for i in archive.infolist()) > 100_000_000:
            raise ValueError("Workbook uncompressed size exceeds 100 MB")
        strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            strings = ["".join(e.itertext()) for e in ET.fromstring(archive.read("xl/sharedStrings.xml"))]
        root = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        cells: dict[str, str] = {}
        hidden = []
        for row in root.findall("s:sheetData/s:row", NS):
            if row.get("hidden") == "1":
                hidden.append(int(row.attrib["r"]))
            for cell in row.findall("s:c", NS):
                value = cell.find("s:v", NS)
                text = value.text or "" if value is not None else ""
                if cell.get("t") == "s" and text:
                    text = strings[int(text)]
                elif cell.get("t") == "inlineStr":
                    inline = cell.find("s:is", NS)
                    text = "".join(inline.itertext()) if inline is not None else ""
                if text.strip():
                    cells[cell.attrib["r"]] = text.strip()
        resolved = dict(cells)
        for merge in root.findall("s:mergeCells/s:mergeCell", NS):
            first, last = merge.attrib["ref"].split(":")
            x1, y1 = split_cell(first)
            x2, y2 = split_cell(last)
            if (x2 - x1 + 1) * (y2 - y1 + 1) > 100_000:
                raise ValueError("Merged range is too large")
            value = cells.get(first, "")
            if value:
                for y in range(y1, y2 + 1):
                    for x in range(x1, x2 + 1):
                        resolved.setdefault(f"{col_name(x)}{y}", value)
        return cells, resolved, hidden


def validate_supported_schema(cells: dict[str, str]) -> None:
    """Reject layouts that this positional 046.11 importer cannot read safely.

    In 046.24 the main service moved from N to M and routing extends past CL.
    A filename is not evidence of compatibility; do not guess shifted columns.
    """
    expected_headers = {"M1": "Сценарий реагирования", "N1": "Главная служба"}
    if any(" ".join(cells.get(ref, "").split()) != label
           for ref, label in expected_headers.items()):
        raise ValueError(
            "Unsupported classifier schema: expected the 046.11 headers "
            "M1='Сценарий реагирования' and N1='Главная служба'. "
            "Adapt the importer before importing another layout."
        )
    for ref, value in cells.items():
        if split_cell(ref)[0] > col_number("CL") and value.strip():
            raise ValueError(
                f"Unsupported classifier schema: nonempty cell {ref} beyond CL "
                "would be omitted from the supported routing range. "
                "Adapt the importer before importing this workbook."
            )


def import_classifier(path: Path) -> dict:
    raw, cells, hidden = read_sheet(path)
    validate_supported_schema(cells)
    rows = sorted({split_cell(c)[1] for c in raw})
    groups = {}
    for row in rows:
        code = cells.get(f"E{row}", "")
        if code.isdigit() and int(code) < 100 and cells.get(f"F{row}"):
            groups[code] = cells[f"F{row}"]
    items, seen = [], set()
    for row in rows:
        if row <= 3 or not raw.get(f"K{row}"):
            continue
        code = cells.get(f"E{row}", "")
        if not code or code in seen:
            raise ValueError(f"Missing or duplicate incident code at row {row}: {code}")
        seen.add(code)
        main = cells.get(f"N{row}", "")
        primary = ", ".join(SERVICE_NAMES.get(x.strip(), x.strip()) for x in main.split(",")) or None
        group_id = cells.get(f"A{row}", "")
        routing = {}
        # O..CL contain service-specific labels, including conditional columns.
        for col in range(col_number("O"), col_number("CL") + 1):
            name = col_name(col)
            value = raw.get(f"{name}{row}")
            if value:
                labels = list(dict.fromkeys(cells.get(f"{name}{r}", "") for r in [2, 3]))
                routing[name] = {
                    "service": cells.get(f"{name}1", ""),
                    "condition": "; ".join(x for x in labels if x),
                    "value": value, "source_cell": f"{name}{row}",
                }
        items.append({
            "code": code, "label": raw[f"K{row}"],
            "group": groups.get(group_id, f"Группа {group_id}"), "group_id": group_id,
            "features": [cells[f"{col}{row}"] for col in ["G", "H", "I"] if cells.get(f"{col}{row}")],
            "additional_features": cells.get(f"J{row}", ""),
            "primary_service": primary, "primary_service_code": main or None,
            "scenario_code": cells.get(f"M{row}", ""),
            "source_row": row, "source_file": path.name,
            "operator_visible": "не отображается" not in cells.get(f"G{row}", "").lower(),
            "routing": routing,
        })
    fire_count = sum(item["group_id"] == "1" for item in items)
    warnings = [
        "Маршруты — исходные условные столбцы классификатора, а не действующий механизм диспетчеризации.",
        "Для учебного эталона преподаватель проверяет применимость маршрута и признаков.",
    ]
    if "искл" in path.name.lower() and fire_count:
        warnings.append(f"Вопреки слову 'искл' в имени файла сохранено {fire_count} типов группы пожаров и задымлений.")
    if hidden:
        warnings.append(f"Источник содержит скрытые строки: {len(hidden)}; они не исключены из импорта.")
    version = "046.11 / 15.11.2024" if "046_11" in path.name else path.stem
    return {
        "version": version, "warnings": warnings, "items": items,
        "metadata": {
            "source_file": path.name, "source_sheet": "Лист1",
            "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "leaf_count": len(items), "group_count": len({i["group_id"] for i in items}),
            "hidden_row_count": len(hidden), "fire_group_count": fire_count,
            "method": "OOXML read-only, cached values, exact merged ranges, routing conditions preserved",
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, default=Path("backend/data/classifier.json"))
    args = parser.parse_args()
    try:
        data = import_classifier(args.source)
    except ValueError as error:
        parser.error(str(error))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(json.dumps(data["metadata"], ensure_ascii=False, indent=2))
