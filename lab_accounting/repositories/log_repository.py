from __future__ import annotations

from datetime import datetime, timezone, timedelta

from lab_accounting.repositories.database import Database


JST = timezone(timedelta(hours=9))


class LogRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, level: str, event_type: str, message: str) -> None:
        self.db.execute(
            """
            INSERT INTO operation_logs (event_time, event_level, event_type, message)
            VALUES (?, ?, ?, ?)
            """,
            (datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S JST"), level, event_type, message),
        )

    def list(self, level: str = "", keyword: str = "") -> list[dict]:
        sql = "SELECT * FROM operation_logs WHERE 1 = 1"
        params: list[object] = []
        if level:
            sql += " AND event_level = ?"
            params.append(level)
        if keyword:
            sql += " AND (event_type LIKE ? OR message LIKE ?)"
            params.extend([f"%{keyword}%", f"%{keyword}%"])
        sql += " ORDER BY log_id DESC LIMIT 500"
        return [dict(row) for row in self.db.query(sql, params)]
