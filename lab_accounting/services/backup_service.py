from __future__ import annotations

import re
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Callable


REQUIRED_TABLES = {
    "persons",
    "accounting_records",
    "monthly_payments",
    "app_settings",
    "operation_logs",
}
AUTO_BACKUP_PATTERN = re.compile(r"^lab_accounting_auto_.+\.db$")


class BackupService:
    def __init__(
        self,
        database_path: str,
        backup_path: str,
        keep_count: int = 5,
        error_logger: Callable[[str], None] | None = None,
    ) -> None:
        self.database_path = Path(database_path)
        self.backup_path = Path(backup_path)
        self.keep_count = max(1, int(keep_count))
        self.error_logger = error_logger

    def create_backup(self, label: str = "auto") -> str:
        if not self.database_path.exists():
            raise FileNotFoundError("データベースが見つかりません。")
        self.backup_path.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = self._available_path(f"lab_accounting_{label}_{timestamp}")
        self._sqlite_backup(output_path)
        latest_path = self.backup_path / "lab_accounting_latest.db"
        shutil.copy2(output_path, latest_path)
        try:
            self._trim_auto_backups(self.keep_count)
        except OSError as exc:
            if self.error_logger:
                try:
                    self.error_logger(f"自動バックアップの整理に失敗しました: {exc}")
                except Exception:
                    pass
        return str(output_path)

    def restore_backup(self, backup_file: str, post_restore: Callable[[], None] | None = None) -> str:
        source = Path(backup_file)
        if not source.exists():
            raise FileNotFoundError("バックアップファイルが見つかりません。")
        self.validate_backup(source)
        before_restore = self.create_backup("before_restore")
        try:
            shutil.copy2(source, self.database_path)
            if post_restore:
                post_restore()
            self.validate_backup(self.database_path)
        except Exception:
            shutil.copy2(before_restore, self.database_path)
            if post_restore:
                post_restore()
            raise
        return before_restore

    def validate_backup(self, backup_file: Path) -> None:
        conn: sqlite3.Connection | None = None
        try:
            conn = sqlite3.connect(backup_file)
            rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
            integrity = conn.execute("PRAGMA integrity_check").fetchone()
            foreign_key_errors = conn.execute("PRAGMA foreign_key_check").fetchall()
        except sqlite3.DatabaseError as exc:
            raise ValueError("有効なSQLiteバックアップではありません。") from exc
        finally:
            if conn is not None:
                conn.close()
        tables = {row[0] for row in rows}
        missing = REQUIRED_TABLES - tables
        if missing:
            raise ValueError(f"必要なテーブルが不足しています: {', '.join(sorted(missing))}")
        if not integrity or str(integrity[0]).lower() != "ok":
            raise ValueError("バックアップの整合性チェックに失敗しました。")
        if foreign_key_errors:
            raise ValueError("バックアップの外部キー整合性チェックに失敗しました。")

    def _sqlite_backup(self, output_path: Path) -> None:
        source = sqlite3.connect(self.database_path)
        target = sqlite3.connect(output_path)
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()

    def _trim_auto_backups(self, keep: int) -> None:
        backups = [
            path
            for path in self.backup_path.iterdir()
            if path.is_file() and AUTO_BACKUP_PATTERN.fullmatch(path.name)
        ]
        backups.sort(key=lambda path: (path.stat().st_mtime_ns, path.name))
        for path in backups[:-keep]:
            path.unlink()

    def _available_path(self, stem: str) -> Path:
        candidate = self.backup_path / f"{stem}.db"
        suffix = 2
        while candidate.exists():
            candidate = self.backup_path / f"{stem}_{suffix}.db"
            suffix += 1
        return candidate
