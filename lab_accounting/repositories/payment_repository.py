from __future__ import annotations

import sqlite3

from lab_accounting.repositories.database import Database


class PaymentRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create(self, values: dict, status: str = "draft") -> int:
        with self.db.transaction() as conn:
            return self._insert(conn, values, status)

    def create_many(self, rows: list[dict], status: str = "draft") -> list[int]:
        ids: list[int] = []
        with self.db.transaction() as conn:
            for row in rows:
                ids.append(self._insert(conn, row, status))
        return ids

    def update(self, payment_id: int, values: dict, status: str | None = None) -> None:
        current = self.get(payment_id)
        if not current:
            raise ValueError("更新する月次精算が見つかりません。")
        merged = {**current, **values}
        self.db.execute(
            """
            UPDATE monthly_payments
               SET person_id = ?, fiscal_year = ?, target_month = ?, calculation_mode = ?,
                   payment_days = ?, distribution_ratio = ?, previous_balance = ?,
                   monthly_added_amount = ?, before_payment_balance = ?, gross_amount = ?,
                   withholding_amount = ?, net_amount = ?, after_balance = ?, status = ?,
                   memo = ?, updated_at = CURRENT_TIMESTAMP
             WHERE payment_id = ?
            """,
            self._values(merged, status or str(current["status"])) + (payment_id,),
        )

    def set_status(self, payment_id: int, status: str) -> None:
        self.db.execute(
            "UPDATE monthly_payments SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE payment_id = ?",
            (status, payment_id),
        )

    def set_status_many(self, payment_ids: list[int], status: str) -> None:
        if not payment_ids:
            return
        placeholders = ",".join("?" for _ in payment_ids)
        with self.db.transaction() as conn:
            conn.execute(
                f"UPDATE monthly_payments SET status = ?, updated_at = CURRENT_TIMESTAMP "
                f"WHERE payment_id IN ({placeholders})",
                (status, *payment_ids),
            )

    def delete(self, payment_id: int) -> None:
        self.delete_many([payment_id])

    def delete_many(self, payment_ids: list[int]) -> None:
        if not payment_ids:
            return
        placeholders = ",".join("?" for _ in payment_ids)
        with self.db.transaction() as conn:
            conn.execute(
                f"DELETE FROM monthly_payments WHERE payment_id IN ({placeholders})",
                tuple(payment_ids),
            )

    def get(self, payment_id: int) -> dict | None:
        rows = self.db.query(
            """
            SELECT mp.*, p.name AS person_name, p.display_name, p.color
              FROM monthly_payments mp
              JOIN persons p ON p.person_id = mp.person_id
             WHERE mp.payment_id = ?
            """,
            (payment_id,),
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
        sql += " ORDER BY mp.target_month, p.name COLLATE NOCASE, mp.created_at, mp.payment_id"
        return [dict(row) for row in self.db.query(sql, params)]

    def total_net_before(self, person_id: int, fiscal_year: int, target_month: str) -> float:
        return self._total_net(person_id, fiscal_year, target_month, "<")

    def total_net_until(self, person_id: int, fiscal_year: int, target_month: str) -> float:
        return self._total_net(person_id, fiscal_year, target_month, "<=")

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

    def _total_net(self, person_id: int, fiscal_year: int, target_month: str, operator: str) -> float:
        if operator not in {"<", "<="}:
            raise ValueError("Invalid comparison operator")
        rows = self.db.query(
            f"""
            SELECT COALESCE(SUM(net_amount), 0) AS total
              FROM monthly_payments
             WHERE person_id = ?
               AND fiscal_year = ?
               AND target_month {operator} ?
            """,
            (person_id, fiscal_year, target_month),
        )
        return float(rows[0]["total"] or 0)

    def _insert(self, conn: sqlite3.Connection, values: dict, status: str) -> int:
        cursor = conn.execute(
            """
            INSERT INTO monthly_payments (
                person_id, fiscal_year, target_month, calculation_mode, payment_days,
                distribution_ratio, previous_balance, monthly_added_amount,
                before_payment_balance, gross_amount, withholding_amount, net_amount,
                after_balance, status, memo
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            self._values(values, status),
        )
        return int(cursor.lastrowid)

    @staticmethod
    def _values(values: dict, status: str) -> tuple:
        return (
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
        )
