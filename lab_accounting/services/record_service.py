from __future__ import annotations

from datetime import date

from lab_accounting.core.fiscal_year import fiscal_year_for_date, target_month_for_date
from lab_accounting.repositories.log_repository import LogRepository
from lab_accounting.repositories.record_repository import RecordRepository


class RecordService:
    def __init__(self, repo: RecordRepository, logs: LogRepository, fiscal_start_month: int = 4) -> None:
        self.repo = repo
        self.logs = logs
        self.fiscal_start_month = fiscal_start_month

    def list(self, filters: dict | None = None) -> list[dict]:
        return self.repo.list(filters)

    def create(self, values: dict) -> int:
        record_date = values["record_date"]
        if isinstance(record_date, date):
            record_date_text = record_date.isoformat()
            fiscal_year = fiscal_year_for_date(record_date, self.fiscal_start_month)
            target_month = target_month_for_date(record_date)
        else:
            parsed = date.fromisoformat(str(record_date))
            record_date_text = parsed.isoformat()
            fiscal_year = fiscal_year_for_date(parsed, self.fiscal_start_month)
            target_month = target_month_for_date(parsed)

        amount = float(values["amount"])
        if amount < 0 and not values.get("memo"):
            raise ValueError("マイナス金額には備考が必要です。")
        if not values.get("item_name"):
            raise ValueError("名目を入力してください。")

        saved = dict(values)
        saved.update(
            {
                "record_date": record_date_text,
                "amount": amount,
                "fiscal_year": fiscal_year,
                "target_month": target_month,
            }
        )
        new_id = self.repo.create(saved)
        self.logs.add("INFO", "RECORD_CREATED", f"Record added: {saved['item_name']} {amount:.0f}")
        return new_id

    def delete_many(self, record_ids: list[int]) -> None:
        deleted: list[str] = []
        existing_ids: list[int] = []
        for record_id in record_ids:
            record = self.repo.get(record_id)
            if not record:
                continue
            existing_ids.append(record_id)
            deleted.append(f"{record['person_name']} {record['record_date']} {record['item_name']}")
        self.repo.delete_many(existing_ids)
        if deleted:
            self.logs.add("INFO", "RECORDS_DELETED", f"Records deleted: {len(deleted)}; " + " | ".join(deleted))
