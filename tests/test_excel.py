import io
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


class ExcelPreviewTests(unittest.TestCase):
    def test_maps_synthetic_rows_with_exact_cents_without_persisting(self):
        rows = preview_xlsx(workbook([["vendor", "date", "total", "account_code"], ["ORBITAL CLOUD SERVICES", "2026-10-01", "321.00", "5100"]]), "synthetic.xlsx")
        self.assertEqual(rows[0]["fields"]["total_cents"], 32100)
        self.assertEqual(rows[0]["errors"], [])

    def test_reports_formula_and_fractional_cent_errors_per_row(self):
        rows = preview_xlsx(workbook([["vendor", "date", "total"], ["Example", "2026-10-01", "1.001"], ["Formula", "2026-10-01", "=1+1"]]), "synthetic.xlsx")
        self.assertIn("Invalid currency amount", rows[0]["errors"][0])
        self.assertIn("Formulas are not accepted", rows[1]["errors"][0])

    def test_rejects_unknown_headers_and_multiple_sheets(self):
        with self.assertRaises(WorkflowError):
            preview_xlsx(workbook([["vendor", "date", "total", "unknown"], ["Example", "2026-10-01", "1.00", "x"]]), "synthetic.xlsx")

