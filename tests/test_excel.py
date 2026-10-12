import io
import zipfile
import unittest

from openpyxl import Workbook

from ledgerbridge.excel import preview_xlsx
from ledgerbridge.core import WorkflowError


def workbook(rows):
    book = Workbook()
    sheet = book.active
    for row in rows:
        sheet.append(row)
    output = io.BytesIO()
    book.save(output)
    return output.getvalue()


def workbook_with_member(content, name, value):
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(content)) as source, zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as target:
        for item in source.infolist():
            target.writestr(item.filename, source.read(item))
        target.writestr(name, value)
    return output.getvalue()


class ExcelPreviewTests(unittest.TestCase):
    def test_maps_synthetic_rows_with_exact_cents_without_persisting(self):
        rows = preview_xlsx(workbook([["vendor", "date", "total", "account_code"], ["ORBITAL CLOUD SERVICES", "2026-10-01", "321.00", "5100"]]), "synthetic.xlsx")
        self.assertEqual(rows[0]["fields"]["total_cents"], 32100)
        self.assertEqual(rows[0]["errors"], [])

    def test_reports_formula_and_fractional_cent_errors_per_row(self):
        rows = preview_xlsx(workbook([["vendor", "date", "total"], ["Example", "2026-10-01", "1.001"], ["Formula", "2026-10-01", "=1+1"]]), "synthetic.xlsx")
        self.assertIn("Invalid currency amount", rows[0]["errors"][0])
        self.assertIn("Formulas are not accepted", rows[1]["errors"][0])

    def test_blank_required_values_are_preview_errors(self):
        rows = preview_xlsx(workbook([["vendor", "date", "total"], ["", "", None]]), "synthetic.xlsx")
        self.assertEqual(len(rows[0]["errors"]), 3)

    def test_rejects_unknown_headers_and_multiple_sheets(self):
        with self.assertRaises(WorkflowError):
            preview_xlsx(workbook([["vendor", "date", "total", "unknown"], ["Example", "2026-10-01", "1.00", "x"]]), "synthetic.xlsx")

    def test_rejects_malformed_and_oversized_workbooks(self):
        with self.assertRaises(WorkflowError): preview_xlsx(b"not a workbook", "synthetic.xlsx")
        with self.assertRaises(WorkflowError): preview_xlsx(b"x" * 1_000_001, "synthetic.xlsx")

    def test_rejects_zip_paths_external_relationships_and_compression_bombs(self):
        clean = workbook([["vendor", "date", "total"], ["SYNTHETIC", "2026-10-01", "1.00"]])
        for path in ("../outside.xml", r"xl\..\outside.xml", r"C:\outside.xml"):
            with self.subTest(path=path), self.assertRaises(WorkflowError):
                preview_xlsx(workbook_with_member(clean, path, b"synthetic"), "synthetic.xlsx")
        alias_collision=workbook_with_member(workbook_with_member(clean,"custom/alias.xml",b"one"),r"custom\alias.xml",b"two")
        with self.assertRaises(WorkflowError):
            preview_xlsx(alias_collision,"synthetic.xlsx")
        rels = b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship TargetMode="External" Target="https://example.invalid/book.xlsx" Type="urn:synthetic" Id="rId1"/></Relationships>'
        with self.assertRaises(WorkflowError):
            preview_xlsx(workbook_with_member(clean, "custom/_rels/workbook.xml.rels", rels), "synthetic.xlsx")
        compressed_bomb = workbook_with_member(clean, "custom/expanded.bin", b"x" * 5_100_000)
        self.assertLess(len(compressed_bomb), 1_000_000)
        with self.assertRaises(WorkflowError):
            preview_xlsx(compressed_bomb, "synthetic.xlsx")

    def test_rejects_more_than_five_hundred_data_rows(self):
        rows = [["vendor", "date", "total"]] + [[f"SYNTHETIC {i}", "2026-10-01", "1.00"] for i in range(501)]
        with self.assertRaises(WorkflowError):
            preview_xlsx(workbook(rows), "synthetic.xlsx")

