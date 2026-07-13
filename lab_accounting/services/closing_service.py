from __future__ import annotations

from lab_accounting.core.calculator import calculate_monthly_payment
from lab_accounting.repositories.log_repository import LogRepository
from lab_accounting.repositories.payment_repository import PaymentRepository
from lab_accounting.repositories.person_repository import PersonRepository
from lab_accounting.repositories.record_repository import RecordRepository


class ClosingService:
    def __init__(
        self,
        persons: PersonRepository,
        records: RecordRepository,
        payments: PaymentRepository,
        logs: LogRepository,
        default_resident_tax_rate: float,
        default_nonresident_tax_rate: float,
    ) -> None:
        self.persons = persons
        self.records = records
        self.payments = payments
        self.logs = logs
        self.default_resident_tax_rate = default_resident_tax_rate
        self.default_nonresident_tax_rate = default_nonresident_tax_rate

    def preview(
        self,
        fiscal_year: int,
        target_month: str,
        person_ids: list[int] | None,
        calculation_mode: str,
        payment_days: float,
        distribution_ratio: float,
        manual_net_amount: float,
    ) -> list[dict]:
        people = self.persons.list(active_only=True)
        if person_ids:
            people = [p for p in people if int(p["person_id"]) in person_ids]
        result: list[dict] = []
        for person in people:
            pid = int(person["person_id"])
            monthly_added = self.records.monthly_added(pid, fiscal_year, target_month)
            cumulative_added = self.records.total_added_until(pid, fiscal_year, target_month)
            cumulative_paid_before = (
                self.payments.total_net_before(pid, fiscal_year, target_month)
                + self.records.manual_payment_before(pid, fiscal_year, target_month)
            )
            before_payment_balance = cumulative_added - cumulative_paid_before
            previous_balance = before_payment_balance - monthly_added
            tax_rate = self._tax_rate(person)
            calculated = calculate_monthly_payment(
                previous_balance=previous_balance,
                monthly_added_amount=monthly_added,
                tax_rate=tax_rate,
                daily_gross_amount=float(person["daily_gross_amount"]),
                calculation_mode=calculation_mode,
                payment_days=payment_days,
                distribution_ratio=distribution_ratio,
                manual_net_amount=manual_net_amount,
            )
            existing = self.payments.get(pid, fiscal_year, target_month)
            result.append(
                {
                    **calculated,
                    "person_id": pid,
                    "person_name": person["name"],
                    "display_name": person.get("display_name") or person["name"],
                    "fiscal_year": fiscal_year,
                    "target_month": target_month,
                    "calculation_mode": calculation_mode,
                    "payment_days": payment_days if calculation_mode == "days" else 0,
                    "distribution_ratio": distribution_ratio if calculation_mode == "ratio" else 1,
                    "status": existing["status"] if existing else "preview",
                    "memo": "",
                }
            )
            result[-1]["before_payment_balance"] = before_payment_balance
            result[-1]["after_balance"] = before_payment_balance - result[-1]["net_amount"]
        self.logs.add("INFO", "CLOSING_PREVIEW", f"Monthly preview generated: {target_month}")
        return result

    def save_rows(self, rows: list[dict], status: str = "draft") -> None:
        for row in rows:
            self.payments.upsert(row, status)
        self.logs.add("INFO", "CLOSING_SAVED", f"Monthly payments saved: {len(rows)} rows")

    def set_status_for_month(self, fiscal_year: int, target_month: str, status: str) -> None:
        rows = self.payments.list({"fiscal_year": fiscal_year, "target_month": target_month})
        for row in rows:
            self.payments.set_status(int(row["person_id"]), fiscal_year, target_month, status)
        self.logs.add("INFO", "CLOSING_STATUS_CHANGED", f"Monthly status changed: {target_month} {status}")

    def delete_rows(self, rows: list[dict]) -> None:
        for row in rows:
            self.payments.delete(int(row["person_id"]), int(row["fiscal_year"]), row["target_month"])
        self.logs.add("INFO", "CLOSING_DELETED", f"Monthly payments deleted: {len(rows)} rows")

    def recalculate_saved_rows(self, rows: list[dict]) -> list[dict]:
        recalculated: list[dict] = []
        for row in rows:
            current = dict(row)
            pid = int(current["person_id"])
            fiscal_year = int(current["fiscal_year"])
            target_month = current["target_month"]
            monthly_added = self.records.monthly_added(pid, fiscal_year, target_month)
            cumulative_added = self.records.total_added_until(pid, fiscal_year, target_month)
            cumulative_paid_before = (
                self.payments.total_net_before(pid, fiscal_year, target_month)
                + self.records.manual_payment_before(pid, fiscal_year, target_month)
            )
            before_payment_balance = cumulative_added - cumulative_paid_before
            current["monthly_added_amount"] = monthly_added
            current["previous_balance"] = before_payment_balance - monthly_added
            current["before_payment_balance"] = before_payment_balance
            current["after_balance"] = before_payment_balance - float(current.get("net_amount") or 0)
            recalculated.append(current)
        return recalculated

    def _tax_rate(self, person: dict) -> float:
        if person.get("resident_type") == "nonresident":
            return self.default_nonresident_tax_rate
        return self.default_resident_tax_rate
