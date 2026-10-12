"""Create ephemeral, synthetic browser-test workbooks outside the repository."""
from pathlib import Path
from openpyxl import Workbook

root = Path("/tmp")
for name, row in (
    ("ledgerbridge-synthetic-valid.xlsx", ["SYNTHETIC BROWSER VENDOR", "2026-10-12", "12.34", "5100"]),
    ("ledgerbridge-synthetic-invalid.xlsx", ["SYNTHETIC FORMULA VENDOR", "2026-10-12", "=1+2", "5100"]),
):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["vendor", "date", "total", "account_code"])
    sheet.append(row)
    workbook.save(root / name)
