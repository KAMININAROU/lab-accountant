from __future__ import annotations


def money(value: object) -> str:
    try:
        return f"{float(value):,.0f}"
    except (TypeError, ValueError):
        return ""


def decimal_text(value: object, digits: int = 2) -> str:
    try:
        text = f"{float(value):,.{digits}f}"
        return text.rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return ""
