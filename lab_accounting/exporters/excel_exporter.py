from __future__ import annotations

from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from lab_accounting.core.fiscal_year import fiscal_months, month_label


HEADER_FILL = PatternFill("solid", fgColor="D9EAF7")
NEGATIVE_FILL = PatternFill("solid", fgColor="F4CCCC")
CONFIRMED_FILL = PatternFill("solid", fgColor="D9EAD3")


class ExcelExporter:
    def export(
        self,
        output_path: str,
        fiscal_year: int,
        records: list[dict],
        overview: list[dict],
        payments: list[dict],
        include_records: bool = True,
        include_summary: bool = True,
        include_payments: bool = True,
        include_items: bool = True,
        include_tax_sheet: bool = True,
    ) -> str:
        wb = Workbook()
        wb.remove(wb.active)
        self._write_updated(wb)
        if include_records:
            self._write_records(wb, records)
        if include_summary:
            self._write_summary(wb, overview, fiscal_year)
        if include_payments:
            self._write_payments(wb, payments, fiscal_year)
        if include_items:
            self._write_items(wb, records)
        if include_tax_sheet:
            self._write_tax(wb)

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        wb.save(path)
        return str(path)

    def _write_updated(self, wb: Workbook) -> None:
        ws = wb.create_sheet("最終更新日")
        ws.append(["最終更新日"])
        ws.append([datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
        ws.append([])
        ws.append(["更新者"])
        ws.append(["LabAccounting"])
        self._fit(ws)

    def _write_records(self, wb: Workbook, rows: list[dict]) -> None:
        ws = wb.create_sheet("案件入力")
        headers = ["日付", "人", "名目", "金額", "種類", "年度", "対象月", "備考"]
        ws.append(headers)
        for row in rows:
            ws.append(
                [
                    row["record_date"],
                    row["person_name"],
                    row["item_name"],
                    row["amount"],
                    row["record_type"],
                    row["fiscal_year"],
                    row["target_month"],
                    row.get("memo") or "",
                ]
            )
        self._style_table(ws, money_cols=[4])

    def _write_summary(self, wb: Workbook, rows: list[dict], fiscal_year: int) -> None:
        ws = wb.create_sheet("Summary")
        ws.append([f"{fiscal_year}年度 集計"])
        ws.append(["人", "累積利用額", "累積支給日数", "累積支給額", "残額", "状態"])
        for row in rows:
            ws.append(
                [
                    row["person_name"],
                    row["total_added"],
                    row["payment_days"],
                    row["net_amount"],
                    row["balance"],
                    "有効" if row["active"] else "停止",
                ]
            )
            if row["balance"] < 0:
                for cell in ws[ws.max_row]:
                    cell.fill = NEGATIVE_FILL
        self._style_table(ws, header_row=2, money_cols=[2, 4, 5])
        ws["A1"].font = Font(bold=True, size=14)

    def _write_payments(self, wb: Workbook, rows: list[dict], fiscal_year: int) -> None:
        ws = wb.create_sheet("個人別支給額")
        months = fiscal_months(fiscal_year)
        by_person: dict[str, dict[str, dict]] = {}
        for row in rows:
            by_person.setdefault(row["person_name"], {})[row["target_month"]] = row

        ws.append([f"{fiscal_year}年度 業務委託報酬"])
        ws.append(["日数"])
        ws.append(["人"] + [month_label(m) for m in months] + ["合計"])
        for person_name, monthly in by_person.items():
            values = [float(monthly.get(m, {}).get("payment_days", 0) or 0) for m in months]
            ws.append([person_name] + values + [sum(values)])
        ws.append([])
        ws.append(["金額"])
        ws.append(["人"] + [month_label(m) for m in months] + ["合計"])
        for person_name, monthly in by_person.items():
            values = [float(monthly.get(m, {}).get("net_amount", 0) or 0) for m in months]
            ws.append([person_name] + values + [sum(values)])
        self._style_headers(ws, [3, 6 + len(by_person)])
        for row in ws.iter_rows(min_row=7 + len(by_person), min_col=2):
            for cell in row:
                if isinstance(cell.value, (int, float)):
                    cell.number_format = '#,##0'
        self._fit(ws)
        ws.freeze_panes = "B4"

    def _write_items(self, wb: Workbook, rows: list[dict]) -> None:
        ws = wb.create_sheet("使用費目一覧")
        ws.append(["年度", "対象月", "人", "日付", "名目", "金額", "種類", "備考"])
        for row in rows:
            ws.append(
                [
                    row["fiscal_year"],
                    row["target_month"],
                    row["person_name"],
                    row["record_date"],
                    row["item_name"],
                    row["amount"],
                    row["record_type"],
                    row.get("memo") or "",
                ]
            )
        self._style_table(ws, money_cols=[6])

    def _write_tax(self, wb: Workbook) -> None:
        ws = wb.create_sheet("税額計算表")
        ws.append(["税額計算参考"])
        ws.append([])
        ws.append(["区分", "税率", "支払総額", "源泉徴収額", "手取額"])
        for label, rate, gross in [("居住者", 0.1021, 10000), ("非居住者", 0.2042, 10000)]:
            withholding = int(gross * rate)
            ws.append([label, rate, gross, withholding, gross - withholding])
        self._style_table(ws, header_row=3, money_cols=[3, 4, 5])
        for cell in ws["B"]:
            if isinstance(cell.value, float):
                cell.number_format = "0.00%"

    def _style_table(self, ws, header_row: int = 1, money_cols: list[int] | None = None) -> None:
        self._style_headers(ws, [header_row])
        money_cols = money_cols or []
        for col in money_cols:
            for row in range(header_row + 1, ws.max_row + 1):
                ws.cell(row, col).number_format = '#,##0'
        ws.freeze_panes = f"A{header_row + 1}"
        ws.auto_filter.ref = ws.dimensions
        self._fit(ws)

    def _style_headers(self, ws, rows: list[int]) -> None:
        for row in rows:
            for cell in ws[row]:
                cell.font = Font(bold=True)
                cell.fill = HEADER_FILL

    def _fit(self, ws) -> None:
        for column in ws.columns:
            max_len = 10
            col_letter = get_column_letter(column[0].column)
            for cell in column:
                value = "" if cell.value is None else str(cell.value)
                max_len = max(max_len, min(len(value) + 2, 36))
            ws.column_dimensions[col_letter].width = max_len
