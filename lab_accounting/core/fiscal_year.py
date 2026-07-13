from __future__ import annotations

from datetime import date


def fiscal_year_for_date(value: date, start_month: int = 4) -> int:
    return value.year if value.month >= start_month else value.year - 1


def target_month_for_date(value: date) -> str:
    return f"{value.year:04d}-{value.month:02d}"


def fiscal_months(fiscal_year: int, start_month: int = 4) -> list[str]:
    months: list[str] = []
    year = fiscal_year
    month = start_month
    for _ in range(12):
        months.append(f"{year:04d}-{month:02d}")
        month += 1
        if month == 13:
            month = 1
            year += 1
    return months


def month_label(target_month: str) -> str:
    month = int(target_month.split("-")[1])
    return f"{month}月"
