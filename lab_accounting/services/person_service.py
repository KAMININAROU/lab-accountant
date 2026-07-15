from __future__ import annotations

from lab_accounting.repositories.log_repository import LogRepository
from lab_accounting.repositories.person_repository import PersonRepository


class PersonService:
    def __init__(self, repo: PersonRepository, logs: LogRepository) -> None:
        self.repo = repo
        self.logs = logs

    def list(self, active_only: bool = False, group_by_color: bool = False) -> list[dict]:
        return self.repo.list(active_only, group_by_color)

    def save(self, values: dict, person_id: int | None = None) -> int | None:
        if not values.get("name"):
            raise ValueError("氏名を入力してください。")
        if values.get("daily_gross_amount", 0) < 0:
            raise ValueError("日額(支払総額)は0以上で入力してください。")
        if values.get("daily_net_amount", 0) < 0:
            raise ValueError("日額(手取額)は0以上で入力してください。")
        if person_id:
            self.repo.update(person_id, values)
            self.logs.add("INFO", "PERSON_UPDATED", f"Person updated: {values['name']}")
            return person_id
        new_id = self.repo.create(values)
        self.logs.add("INFO", "PERSON_CREATED", f"Person created: {values['name']}")
        return new_id

    def set_active(self, person_id: int, active: bool) -> None:
        self.repo.set_active(person_id, active)
        self.logs.add("INFO", "PERSON_ACTIVE_CHANGED", f"Person active changed: {person_id}")

    def delete(self, person_id: int) -> None:
        self.delete_many([person_id])

    def delete_many(self, person_ids: list[int]) -> None:
        people = [self.repo.get(person_id) for person_id in person_ids]
        names = [person["name"] if person else str(person_id) for person_id, person in zip(person_ids, people)]
        self.repo.delete_many(person_ids)
        self.logs.add(
            "INFO",
            "PERSON_DELETED",
            f"People deleted with related records/payments: {len(person_ids)}; " + " | ".join(names),
        )
