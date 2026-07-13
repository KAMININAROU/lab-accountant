from __future__ import annotations

from lab_accounting.repositories.database import Database


class PaymentRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def upsert(self, values: dict, status: str = "draft") -> None:
        self.db.execute(
            """
            INSERT INTO monthly_payments (
                person_id, fiscal_year, target_month, calculation_mode, payment_days,
                distribution_ratio, previous_balance, monthly_added_amount,
                before_payment_balance, gross_amount, withholding_amount, net_amount,
                after_balance, status, memo
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(person_id, fiscal_year, target_month) DO UPDATE SET
                calculation_mode = excluded.calculation_mode,
                payment_days = excluded.payment_days,
                distribution_ratio = excluded.distribution_ratio,
                previous_balance = excluded.previous_balance,
                monthly_added_amount = excluded.monthly_added_amount,
                before_payment_balance = excluded.before_payment_balance,
                gross_amount = excluded.gross_amount,
                withholding_amount = excluded.withholding_amount,
                net_amount = excluded.net_amount,
                after_balance = excluded.after_balance,
                status = excluded.status,
                memo = excluded.memo,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                values["person_id"],
                values["fiscal_year"],
                values["target_month"],
                values["calculation_mode"],
                values.get("payment_days", 0),
                values.get("distribution_ratio", 1),
                values["previous_balance"],
                values["monthly_added_amount"],
                values["before_payment_balance"],
                values["gross_amount"],
                values["withholding_amount"],
                values["net_amount"],
                values["after_balance"],
                status,
                values.get("memo") or "",
            ),
        )

    def set_status(self, person_id: int, fiscal_year: int, target_month: str, status: str) -> None:
        self.db.execute(
            """
            UPDATE monthly_payments
               SET status = ?, updated_at = CURRENT_TIMESTAMP
             WHERE person_id = ? AND fiscal_year = ? AND target_month = ?
            """,
            (status, person_id, fiscal_year, target_month),
        )

    def delete(self, person_id: int, fiscal_year: int, target_month: str) -> None:
        self.db.execute(
            """
            DELETE FROM monthly_payments
             WHERE person_id = ? AND fiscal_year = ? AND target_month = ?
            """,
            (person_id, fiscal_year, target_month),
        )

    def get(self, person_id: int, fiscal_year: int, target_month: str) -> dict | None:
        rows = self.db.query(
            """
            SELECT mp.*, p.name AS person_name, p.display_name
              FROM monthly_payments mp
              JOIN persons p ON p.person_id = mp.person_id
             WHERE mp.person_id = ? AND mp.fiscal_year = ? AND mp.target_month = ?
            """,
            (person_id, fiscal_year, target_month),
        )
        return dict(rows[0]) if rows else None

    def list(self, filters: dict | None = None) -> list[dict]:
        filters = filters or {}
        sql = """
            SELECT mp.*, p.name AS person_name, p.display_name, p.color
              FROM monthly_payments mp
              JOIN persons p ON p.person_id = mp.person_id
             WHERE 1 = 1
        """
        params: list[object] = []
        if filters.get("fiscal_year"):
            sql += " AND mp.fiscal_year = ?"
            params.append(filters["fiscal_year"])
        if filters.get("target_month"):
            sql += " AND mp.target_month = ?"
            params.append(filters["target_month"])
        if filters.get("person_id"):
            sql += " AND mp.person_id = ?"
            params.append(filters["person_id"])
        sql += " ORDER BY mp.target_month, p.name"
        return [dict(row) for row in self.db.query(sql, params)]

    def latest_before(self, person_id: int, fiscal_year: int, target_month: str) -> dict | None:
        rows = self.db.query(
            """
            SELECT *
              FROM monthly_payments
             WHERE person_id = ?
               AND fiscal_year = ?
               AND target_month < ?
             ORDER BY target_month DESC
             LIMIT 1
            """,
            (person_id, fiscal_year, target_month),
        )
        return dict(rows[0]) if rows else None

    def total_net_before(self, person_id: int, fiscal_year: int, target_month: str) -> float:
        rows = self.db.query(
            """
            SELECT COALESCE(SUM(net_amount), 0) AS total
              FROM monthly_payments
             WHERE person_id = ?
               AND fiscal_year = ?
               AND target_month < ?
            """,
            (person_id, fiscal_year, target_month),
        )
        return float(rows[0]["total"] or 0)

    def totals_by_person(self, fiscal_year: int) -> dict[int, dict]:
        rows = self.db.query(
            """
            SELECT person_id,
                   COALESCE(SUM(payment_days), 0) AS payment_days,
                   COALESCE(SUM(net_amount), 0) AS net_amount
              FROM monthly_payments
             WHERE fiscal_year = ?
             GROUP BY person_id
            """,
            (fiscal_year,),
        )
        return {int(row["person_id"]): dict(row) for row in rows}
