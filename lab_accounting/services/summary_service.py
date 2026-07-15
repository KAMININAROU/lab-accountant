from __future__ import annotations

from lab_accounting.core.fiscal_year import fiscal_months
from lab_accounting.repositories.payment_repository import PaymentRepository
from lab_accounting.repositories.person_repository import PersonRepository
from lab_accounting.repositories.record_repository import RecordRepository


class SummaryService:
    def __init__(self, persons: PersonRepository, records: RecordRepository, payments: PaymentRepository) -> None:
        self.persons = persons
        self.records = records
        self.payments = payments

    def annual_overview(self, fiscal_year: int) -> list[dict]:
        people = self.persons.list(active_only=False)
        payment_totals = self.payments.totals_by_person(fiscal_year)
        result: list[dict] = []
        for person in people:
            pid = int(person["person_id"])
            added = self.records.person_total_added(pid, fiscal_year)
            totals = payment_totals.get(pid, {"payment_days": 0, "net_amount": 0})
            paid_amount = float(totals["net_amount"] or 0) + self.records.manual_payment_total(pid, fiscal_year)
            balance = added - paid_amount
            result.append(
                {
                    "person_id": pid,
                    "person_name": person["name"],
                    "color": person.get("color") or "",
                    "active": int(person["active"]),
                    "total_added": added,
                    "payment_days": float(totals["payment_days"] or 0),
                    "net_amount": paid_amount,
                    "balance": balance,
                }
            )
        return result

    def monthly_matrix(self, fiscal_year: int, value_field: str) -> tuple[list[str], list[dict]]:
        months = fiscal_months(fiscal_year)
        people = self.persons.list(active_only=False)
        payments = self.payments.list({"fiscal_year": fiscal_year})
        by_key: dict[tuple[int, str], float] = {}
        for payment in payments:
            key = (int(payment["person_id"]), payment["target_month"])
            by_key[key] = by_key.get(key, 0.0) + float(payment.get(value_field, 0) or 0)
        rows: list[dict] = []
        for person in people:
            pid = int(person["person_id"])
            row = {
                "person_id": pid,
                "person_name": person["name"],
                "color": person.get("color") or "",
                "total": 0.0,
            }
            for month in months:
                value = by_key.get((pid, month), 0.0)
                row[month] = value
                row["total"] += value
            rows.append(row)
        return months, rows
