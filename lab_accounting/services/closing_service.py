from __future__ import annotations

from lab_accounting.core.calculator import calculate_monthly_payment
from lab_accounting.core.tax import effective_tax_rate
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
    ) -> list[dict]:
        people = self.persons.list(active_only=True)
        if person_ids:
            selected = set(person_ids)
            people = [person for person in people if int(person["person_id"]) in selected]
        result: list[dict] = []
        for person in people:
            pid = int(person["person_id"])
            monthly_added = self.records.monthly_added(pid, fiscal_year, target_month)
            previous_balance = (
                self.records.total_added_before(pid, fiscal_year, target_month)
                - self.records.manual_payment_before(pid, fiscal_year, target_month)
                - self.payments.total_net_before(pid, fiscal_year, target_month)
            )
            before_payment_balance = (
                self.records.total_added_until(pid, fiscal_year, target_month)
                - self.records.manual_payment_until(pid, fiscal_year, target_month)
                - self.payments.total_net_until(pid, fiscal_year, target_month)
            )
            tax_rate = self._tax_rate(person)
            calculated = calculate_monthly_payment(
                previous_balance=before_payment_balance - monthly_added,
                monthly_added_amount=monthly_added,
                tax_rate=tax_rate,
                daily_gross_amount=float(person["daily_gross_amount"]),
                calculation_mode=calculation_mode,
                payment_days=payment_days,
                distribution_ratio=distribution_ratio,
            )
            calculated.update(
                {
                    "previous_balance": previous_balance,
                    "before_payment_balance": before_payment_balance,
                    "after_balance": before_payment_balance - calculated["net_amount"],
                    "person_id": pid,
                    "person_name": person["name"],
                    "display_name": person.get("display_name") or person["name"],
                    "fiscal_year": fiscal_year,
                    "target_month": target_month,
                    "calculation_mode": calculation_mode,
                    "payment_days": payment_days if calculation_mode == "days" else 0,
                    "distribution_ratio": distribution_ratio if calculation_mode == "ratio" else 1,
                    "effective_tax_rate": tax_rate,
                    "status": "preview",
                    "memo": "",
                }
            )
            result.append(calculated)
        self.logs.add("INFO", "CLOSING_PREVIEW", f"Monthly preview generated: {target_month}")
        return result

    def save_rows(self, rows: list[dict], status: str = "draft") -> list[int]:
        if not rows:
            return []
        payment_ids = self.payments.create_many(rows, status)
        self.logs.add(
            "INFO",
            "CLOSING_SAVED",
            f"Monthly payments inserted: {len(rows)} rows; IDs: {','.join(map(str, payment_ids))}",
        )
        return payment_ids

    def set_status(self, payment_ids: list[int], status: str) -> None:
        self.payments.set_status_many(payment_ids, status)
        if payment_ids:
            self.logs.add(
                "INFO",
                "CLOSING_STATUS_CHANGED",
                f"Monthly status changed: {status}; IDs: {','.join(map(str, payment_ids))}",
            )

    def delete_rows(self, rows: list[dict]) -> None:
        payment_ids = sorted({int(row["payment_id"]) for row in rows if row.get("payment_id") is not None})
        if not payment_ids:
            return
        self.payments.delete_many(payment_ids)
        self.logs.add(
            "INFO",
            "CLOSING_DELETED",
            f"Monthly payments deleted: {len(payment_ids)} rows; IDs: {','.join(map(str, payment_ids))}",
        )

    def recalculate_saved_rows(self, rows: list[dict]) -> list[dict]:
        balance_by_payment_id: dict[int, tuple[float, float, float, float]] = {}
        keys = {(int(row["person_id"]), int(row["fiscal_year"]), row["target_month"]) for row in rows}
        for person_id, fiscal_year, target_month in keys:
            previous_balance = (
                self.records.total_added_before(person_id, fiscal_year, target_month)
                - self.records.manual_payment_before(person_id, fiscal_year, target_month)
                - self.payments.total_net_before(person_id, fiscal_year, target_month)
            )
            monthly_added = self.records.monthly_added(person_id, fiscal_year, target_month)
            running_balance = (
                self.records.total_added_until(person_id, fiscal_year, target_month)
                - self.records.manual_payment_until(person_id, fiscal_year, target_month)
                - self.payments.total_net_before(person_id, fiscal_year, target_month)
            )
            month_rows = self.payments.list(
                {"person_id": person_id, "fiscal_year": fiscal_year, "target_month": target_month}
            )
            for month_row in month_rows:
                before_balance = running_balance
                after_balance = before_balance - float(month_row.get("net_amount") or 0)
                balance_by_payment_id[int(month_row["payment_id"])] = (
                    previous_balance,
                    monthly_added,
                    before_balance,
                    after_balance,
                )
                running_balance = after_balance

        recalculated: list[dict] = []
        for row in rows:
            current = dict(row)
            values = balance_by_payment_id.get(int(current["payment_id"]))
            if values:
                current["previous_balance"] = values[0]
                current["monthly_added_amount"] = values[1]
                current["before_payment_balance"] = values[2]
                current["after_balance"] = values[3]
            recalculated.append(current)
        return recalculated

    def _tax_rate(self, person: dict) -> float:
        return effective_tax_rate(
            person,
            self.default_resident_tax_rate,
            self.default_nonresident_tax_rate,
        )
