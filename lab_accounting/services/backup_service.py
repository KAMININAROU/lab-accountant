from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


REQUIRED_TABLES = {
    "persons",
    "accounting_records",
    "monthly_payments",
    "app_settings",
    "operation_logs",
}


class BackupService:
    def __init__(self, database_path: str, backup_path: str) -> None:
        self.database_path = Path(database_path)
        self.backup_path = Path(backup_path)

    def create_backup(self, label: str = "auto") -> str:
        if not self.database_path.exists():
            raise FileNotFoundError("データベースが見つかりません。")
        self.backup_path.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = self.backup_path / f"lab_accounting_{label}_{timestamp}.db"
        self._sqlite_backup(output_path)
        latest_path = self.backup_path / "lab_accounting_latest.db"
        shutil.copy2(output_path, latest_path)
        self._trim_auto_backups(keep=60)
        return str(output_path)

    def restore_backup(self, backup_file: str) -> str:
        source = Path(backup_file)
        if not source.exists():
            raise FileNotFoundError("バックアップファイルが見つかりません。")
        self.validate_backup(source)
        before_restore = self.create_backup("before_restore")
        shutil.copy2(source, self.database_path)
        return before_restore

    def validate_backup(self, backup_file: Path) -> None:
        try:
            with sqlite3.connect(backup_file) as conn:
                rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        except sqlite3.DatabaseError as exc:
            raise ValueError("有効なSQLiteバックアップではありません。") from exc
        tables = {row[0] for row in rows}
        missing = REQUIRED_TABLES - tables
        if missing:
            raise ValueError(f"必要なテーブルが不足しています: {', '.join(sorted(missing))}")

    def _sqlite_backup(self, output_path: Path) -> None:
        with sqlite3.connect(self.database_path) as source:
            with sqlite3.connect(output_path) as target:
                source.backup(target)

    def _trim_auto_backups(self, keep: int) -> None:
        backups = sorted(self.backup_path.glob("lab_accounting_auto_*.db"), key=lambda path: path.stat().st_mtime)
        for path in backups[:-keep]:
            path.unlink(missing_ok=True)
