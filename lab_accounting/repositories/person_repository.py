from __future__ import annotations

from lab_accounting.repositories.database import Database


class PersonRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def list(self, active_only: bool = False) -> list[dict]:
        sql = "SELECT * FROM persons"
        params: list[object] = []
        if active_only:
            sql += " WHERE active = 1"
        sql += " ORDER BY active DESC, name COLLATE NOCASE"
        return [dict(row) for row in self.db.query(sql, params)]

    def get(self, person_id: int) -> dict | None:
        rows = self.db.query("SELECT * FROM persons WHERE person_id = ?", (person_id,))
        return dict(rows[0]) if rows else None

    def create(self, values: dict) -> int:
        return self.db.execute(
            """
            INSERT INTO persons (
                name, display_name, name_kana, color, resident_type, tax_rate,
                daily_gross_amount, daily_net_amount, active
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                values["name"],
                values.get("display_name") or values["name"],
                values.get("name_kana") or "",
                values.get("color") or "#dbeafe",
                values.get("resident_type") or "resident",
                values.get("tax_rate"),
                int(values.get("daily_gross_amount") or 10000),
                int(values.get("daily_net_amount") or 8979),
                1 if values.get("active", True) else 0,
            ),
        )

    def update(self, person_id: int, values: dict) -> None:
        self.db.execute(
            """
            UPDATE persons
               SET name = ?, display_name = ?, name_kana = ?, color = ?,
                   resident_type = ?, tax_rate = ?, daily_gross_amount = ?,
                   daily_net_amount = ?, active = ?, updated_at = CURRENT_TIMESTAMP
             WHERE person_id = ?
            """,
            (
                values["name"],
                values.get("display_name") or values["name"],
                values.get("name_kana") or "",
                values.get("color") or "#dbeafe",
                values.get("resident_type") or "resident",
                values.get("tax_rate"),
                int(values.get("daily_gross_amount") or 10000),
                int(values.get("daily_net_amount") or 8979),
                1 if values.get("active", True) else 0,
                person_id,
            ),
        )

    def set_active(self, person_id: int, active: bool) -> None:
        self.db.execute(
            "UPDATE persons SET active = ?, updated_at = CURRENT_TIMESTAMP WHERE person_id = ?",
            (1 if active else 0, person_id),
        )

    def delete(self, person_id: int) -> None:
        with self.db.connect() as conn:
            conn.execute("DELETE FROM monthly_payments WHERE person_id = ?", (person_id,))
            conn.execute("DELETE FROM accounting_records WHERE person_id = ?", (person_id,))
            conn.execute("DELETE FROM persons WHERE person_id = ?", (person_id,))
