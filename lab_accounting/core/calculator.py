from __future__ import annotations

from math import floor

from lab_accounting.core.tax import calc_from_gross, calc_from_net


def calculate_monthly_payment(
    previous_balance: float,
    monthly_added_amount: float,
    tax_rate: float,
    daily_gross_amount: float,
    calculation_mode: str,
    payment_days: float = 0.0,
    distribution_ratio: float = 1.0,
    manual_net_amount: float = 0.0,
) -> dict[str, float]:
    before_payment_balance = float(previous_balance) + float(monthly_added_amount)

    if calculation_mode == "days":
        gross_amount = float(payment_days) * float(daily_gross_amount)
        tax_result = calc_from_gross(gross_amount, tax_rate)
        net_amount = tax_result["net_amount"]
    elif calculation_mode == "ratio":
        net_amount = floor(before_payment_balance * float(distribution_ratio))
        net_amount = max(net_amount, 0.0)
        tax_result = calc_from_net(net_amount, tax_rate)
    elif calculation_mode == "manual":
        net_amount = max(float(manual_net_amount), 0.0)
        tax_result = calc_from_net(net_amount, tax_rate)
    else:
        raise ValueError("Invalid calculation mode")

    after_balance = before_payment_balance - net_amount
    return {
        "previous_balance": previous_balance,
        "monthly_added_amount": monthly_added_amount,
        "before_payment_balance": before_payment_balance,
        "gross_amount": tax_result["gross_amount"],
        "withholding_amount": tax_result["withholding_amount"],
        "net_amount": net_amount,
        "after_balance": after_balance,
    }
