from __future__ import annotations

from lab_accounting.repositories.database import Database


class RecordRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create(self, values: dict) -> int:
        return self.db.execute(
            """
            INSERT INTO accounting_records (
                record_date, person_id, item_name, amount, record_type,
                fiscal_year, target_month, memo
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                values["record_date"],
                values["person_id"],
                values["item_name"],
                float(values["amount"]),
                values["record_type"],
                values["fiscal_year"],
                values["target_month"],
                values.get("memo") or "",
            ),
        )

    def list(self, filters: dict | None = None) -> list[dict]:
        filters = filters or {}
        sql = """
            SELECT r.*, p.name AS person_name, p.display_name, p.color
              FROM accounting_records r
              JOIN persons p ON p.person_id = r.person_id
             WHERE 1 = 1
        """
        params: list[object] = []
        if filters.get("fiscal_year"):
            sql += " AND r.fiscal_year = ?"
            params.append(filters["fiscal_year"])
        if filters.get("target_month"):
            sql += " AND r.target_month = ?"
            params.append(filters["target_month"])
        if filters.get("person_id"):
            sql += " AND r.person_id = ?"
            params.append(filters["person_id"])
        if filters.get("record_type"):
            sql += " AND r.record_type = ?"
            params.append(filters["record_type"])
        if filters.get("keyword"):
            sql += " AND (r.item_name LIKE ? OR r.memo LIKE ?)"
            keyword = f"%{filters['keyword']}%"
            params.extend([keyword, keyword])
        sql += " ORDER BY r.record_date, r.record_id"
        return [dict(row) for row in self.db.query(sql, params)]

    def get(self, record_id: int) -> dict | None:
        rows = self.db.query(
            """
            SELECT r.*, p.name AS person_name
              FROM accounting_records r
              JOIN persons p ON p.person_id = r.person_id
             WHERE r.record_id = ?
            """,
            (record_id,),
        )
        return dict(rows[0]) if rows else None

    def delete(self, record_id: int) -> None:
        self.db.execute("DELETE FROM accounting_records WHERE record_id = ?", (record_id,))

    def monthly_added(self, person_id: int, fiscal_year: int, target_month: str) -> float:
        rows = self.db.query(
            """
            SELECT COALESCE(SUM(amount), 0) AS total
              FROM accounting_records
             WHERE person_id = ?
               AND fiscal_year = ?
               AND target_month = ?
               AND record_type NOT IN ('payment', '支給')
            """,
            (person_id, fiscal_year, target_month),
        )
        return float(rows[0]["total"] or 0)

    def total_added_until(self, person_id: int, fiscal_year: int, target_month: str) -> float:
        rows = self.db.query(
            """
            SELECT COALESCE(SUM(amount), 0) AS total
              FROM accounting_records
             WHERE person_id = ?
               AND fiscal_year = ?
               AND target_month <= ?
               AND record_type NOT IN ('payment', '支給')
            """,
            (person_id, fiscal_year, target_month),
        )
        return float(rows[0]["total"] or 0)

    def person_total_added(self, person_id: int, fiscal_year: int) -> float:
        rows = self.db.query(
            """
            SELECT COALESCE(SUM(amount), 0) AS total
              FROM accounting_records
             WHERE person_id = ?
               AND fiscal_year = ?
               AND record_type NOT IN ('payment', '支給')
            """,
            (person_id, fiscal_year),
        )
        return float(rows[0]["total"] or 0)

    def manual_payment_total(self, person_id: int, fiscal_year: int) -> float:
        rows = self.db.query(
            """
            SELECT COALESCE(SUM(amount), 0) AS total
              FROM accounting_records
             WHERE person_id = ?
               AND fiscal_year = ?
               AND record_type IN ('payment', '支給')
            """,
            (person_id, fiscal_year),
        )
        return float(rows[0]["total"] or 0)

    def manual_payment_before(self, person_id: int, fiscal_year: int, target_month: str) -> float:
        rows = self.db.query(
            """
            SELECT COALESCE(SUM(amount), 0) AS total
              FROM accounting_records
             WHERE person_id = ?
               AND fiscal_year = ?
               AND target_month < ?
               AND record_type IN ('payment', '支給')
            """,
            (person_id, fiscal_year, target_month),
        )
        return float(rows[0]["total"] or 0)
