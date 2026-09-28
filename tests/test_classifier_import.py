import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("import_classifier", ROOT / "scripts/import_classifier.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def write_fixture(path, overrides=None):
    """Small synthetic 046.11 layout; no customer workbook is needed by tests."""
    cells = {
        "M1": "Сценарий реагирования", "N1": "Главная служба",
        "AB1": "Классификатор МОСГАЗ", "AB3": "признак не выбран",
        "AC3": "газификация", "E4": "99", "F4": "Учебная группа",
        "A5": "99", "E5": "99010101", "K5": "Учебное происшествие",
        "M5": "synthetic-scenario", "N5": "MOSGAZ",
        "AB5": "Учебный маршрут без признака", "AC5": "Учебный маршрут с признаком",
    }
    for ref, value in (overrides or {}).items():
        if value is None:
            cells.pop(ref, None)
        else:
            cells[ref] = value
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    worksheet = ET.Element("worksheet", xmlns=ns)
    sheet = ET.SubElement(worksheet, "sheetData")
    for number in sorted({module.split_cell(ref)[1] for ref in cells}):
        row = ET.SubElement(sheet, "row", r=str(number))
        for ref, value in cells.items():
            if module.split_cell(ref)[1] == number:
                cell = ET.SubElement(row, "c", r=ref, t="inlineStr")
                ET.SubElement(ET.SubElement(cell, "is"), "t").text = value
    merged = ET.SubElement(worksheet, "mergeCells")
    for ref in ("M1:M3", "N1:N3", "AB1:AC1"):
        ET.SubElement(merged, "mergeCell", ref=ref)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("xl/worksheets/sheet1.xml", ET.tostring(worksheet))


class ClassifierImportTests(unittest.TestCase):
    def test_supported_schema_preserves_primary_service_and_conditional_routes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic_046_11.xlsx"
            write_fixture(path)
            data = module.import_classifier(path)
        item, = data["items"]
        self.assertEqual(item["primary_service"], "Служба 104")
        self.assertEqual(item["primary_service_code"], "MOSGAZ")
        self.assertEqual(item["scenario_code"], "synthetic-scenario")
        self.assertEqual(item["routing"]["AB"], {
            "service": "Классификатор МОСГАЗ", "condition": "признак не выбран",
            "value": "Учебный маршрут без признака", "source_cell": "AB5",
        })
        self.assertEqual(item["routing"]["AC"]["service"], "Классификатор МОСГАЗ")
        self.assertEqual(item["routing"]["AC"]["condition"], "газификация")

    def test_shifted_or_unknown_headers_are_rejected_regardless_of_filename(self):
        fixtures = (
            {"M1": "Главная служба", "N1": "Классификатор МЧС",
             "M5": "MOSGAZ", "N5": "Учебный тип службы 101"},
            {"M1": None},
            {"N1": None},
            {"N1": "Неизвестное поле"},
        )
        with tempfile.TemporaryDirectory() as directory:
            # A supported-looking name must not override incompatible content.
            path = Path(directory) / "synthetic_046_11.xlsx"
            for overrides in fixtures:
                with self.subTest(overrides=overrides):
                    write_fixture(path, overrides)
                    with self.assertRaisesRegex(ValueError, "Unsupported classifier schema"):
                        module.import_classifier(path)

    def test_nonempty_columns_after_supported_routing_range_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic_046_11.xlsx"
            for overrides in ({"CM5": "Новый маршрут"}, {"CU1": "Новая служба"}):
                with self.subTest(overrides=overrides):
                    write_fixture(path, overrides)
                    with self.assertRaisesRegex(ValueError, "beyond CL"):
                        module.import_classifier(path)
            # Formatting or an empty cell outside the range is not route data.
            write_fixture(path, {"CM5": "  "})
            self.assertEqual(module.import_classifier(path)["metadata"]["leaf_count"], 1)

    def test_cli_does_not_overwrite_output_or_create_directories_for_unsupported_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic_046_24.xlsx"
            write_fixture(path, {"M1": "Главная служба", "N1": "Классификатор МЧС"})
            output = Path(directory) / "classifier.json"
            original = b'{"existing": "keep exactly"}\n'
            output.write_bytes(original)
            for destination in (output, Path(directory) / "new" / "classifier.json"):
                with self.subTest(destination=destination.name):
                    result = subprocess.run(
                        [sys.executable, str(ROOT / "scripts/import_classifier.py"),
                         str(path), "--output", str(destination)],
                        capture_output=True, text=True, check=False,
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("Unsupported classifier schema", result.stderr)
                    self.assertNotIn("Traceback", result.stderr)
            self.assertEqual(output.read_bytes(), original)
            self.assertFalse((Path(directory) / "new").exists())

    def test_real_import_retains_source_provenance_and_conditions(self):
        data = json.loads((ROOT / "backend/data/classifier.json").read_text())
        if data.get('metadata', {}).get('redacted') is True:
            self.skipTest('Оригинальный классификатор не входит в публичный пакет; синтетические тесты импортёра остаются доступными')
        self.assertEqual(len(data["items"]), 1281)
        self.assertEqual(len({i["code"] for i in data["items"]}), 1281)
        self.assertEqual(data["metadata"]["fire_group_count"], 271)
        gas = next(i for i in data["items"] if i["code"] == "13010500")
        self.assertEqual(gas["primary_service"], "Служба 104")
        self.assertIn("AB", gas["routing"])
        self.assertTrue(gas["routing"]["AB"]["source_cell"].startswith("AB"))
        self.assertIn("не выбран", gas["routing"]["AB"]["condition"])

    def test_merge_fill_does_not_leak_to_following_unmerged_cells(self):
        ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
        xml = f'''<worksheet xmlns="{ns}"><sheetData>
          <row r="4"><c r="A4" t="inlineStr"><is><t>14</t></is></c></row>
          <row r="5"><c r="E5"><v>123</v></c></row>
          <row r="6"><c r="E6"><v>124</v></c></row>
          </sheetData><mergeCells><mergeCell ref="A4:A5"/></mergeCells></worksheet>'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.xlsx"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("xl/worksheets/sheet1.xml", xml)
            raw, resolved, _ = module.read_sheet(path)
        self.assertNotIn("A5", raw)
        self.assertEqual(resolved["A5"], "14")
        self.assertNotIn("A6", resolved)

    def test_excel_column_roundtrip(self):
        for number in [1, 26, 27, 52, 90, 100, 16384]:
            self.assertEqual(module.col_number(module.col_name(number)), number)


if __name__ == "__main__":
    unittest.main()
