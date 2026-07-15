from __future__ import annotations

from math import floor


def effective_tax_rate(person: dict, resident_rate: float, nonresident_rate: float) -> float:
    override = person.get("tax_rate")
    if override is not None:
        return float(override)
    if person.get("resident_type") == "nonresident":
        return float(nonresident_rate)
    return float(resident_rate)


def calc_from_gross(gross_amount: float, tax_rate: float) -> dict[str, float]:
    gross = max(float(gross_amount), 0.0)
    withholding = floor(gross * float(tax_rate))
    net = gross - withholding
    return {
        "gross_amount": gross,
        "withholding_amount": withholding,
        "net_amount": net,
    }


def calc_from_net(net_amount: float, tax_rate: float) -> dict[str, float]:
    net = max(float(net_amount), 0.0)
    if tax_rate >= 1:
        raise ValueError("tax_rate must be lower than 1")
    gross = floor(net / (1 - float(tax_rate)))
    withholding = gross - net
    return {
        "gross_amount": gross,
        "withholding_amount": withholding,
        "net_amount": net,
    }
