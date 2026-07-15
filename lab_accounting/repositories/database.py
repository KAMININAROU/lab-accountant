from __future__ import annotations

import hashlib
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Iterator


SCHEMA_VERSION = 2


class Database:
    def __init__(self, path: str) -> None:
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        conn = self.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        conn = self.connect()
        try:
            conn.executescript(SCHEMA)
            conn.commit()
            self._migrate(conn)
            self._seed_settings(conn)
            self._check_integrity(conn)
            conn.commit()
        finally:
            conn.close()

    def query(self, sql: str, params: Iterable[object] = ()) -> list[sqlite3.Row]:
        conn = self.connect()
        try:
            return conn.execute(sql, tuple(params)).fetchall()
        finally:
            conn.close()

    def execute(self, sql: str, params: Iterable[object] = ()) -> int:
        conn = self.connect()
        try:
            cur = conn.execute(sql, tuple(params))
            conn.commit()
            return int(cur.lastrowid or 0)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def executescript(self, sql: str) -> None:
        conn = self.connect()
        try:
            conn.executescript(sql)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def integrity_check(self) -> None:
        conn = self.connect()
        try:
            self._check_integrity(conn)
        finally:
            conn.close()

    def _migrate(self, conn: sqlite3.Connection) -> None:
        version_row = conn.execute(
            "SELECT setting_value FROM app_settings WHERE setting_key = 'schema_version'"
        ).fetchone()
        try:
            old_version = int(version_row[0]) if version_row else 1
        except (TypeError, ValueError):
            old_version = 1
        person_columns = self._table_columns(conn, "persons")
        needs_memo = "memo" not in person_columns
        needs_payment_rebuild = self._has_payment_natural_key_unique(conn)

        conn.commit()
        conn.execute("PRAGMA foreign_keys = OFF")
        try:
            conn.execute("BEGIN IMMEDIATE")
            if needs_memo:
                conn.execute("ALTER TABLE persons ADD COLUMN memo TEXT")
            if needs_memo or old_version < 2:
                conn.execute(
                    """
                    UPDATE persons
                       SET memo = name_kana
                     WHERE (memo IS NULL OR TRIM(memo) = '')
                       AND name_kana IS NOT NULL
                       AND TRIM(name_kana) <> ''
                    """
                )
            if needs_payment_rebuild:
                self._rebuild_monthly_payments(conn)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_monthly_payments_person_year_month "
                "ON monthly_payments(person_id, fiscal_year, target_month)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_accounting_records_person_year_month "
                "ON accounting_records(person_id, fiscal_year, target_month)"
            )
            conn.execute(
                """
                INSERT INTO app_settings(setting_key, setting_value, updated_at)
                VALUES ('schema_version', ?, CURRENT_TIMESTAMP)
                ON CONFLICT(setting_key) DO UPDATE SET
                    setting_value = excluded.setting_value,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (str(SCHEMA_VERSION),),
            )
            foreign_key_errors = conn.execute("PRAGMA foreign_key_check").fetchall()
            if foreign_key_errors:
                raise sqlite3.IntegrityError("データベースの外部キー整合性チェックに失敗しました。")
            self._check_integrity(conn)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.execute("PRAGMA foreign_keys = ON")

    def _rebuild_monthly_payments(self, conn: sqlite3.Connection) -> None:
        before_count = int(conn.execute("SELECT COUNT(*) FROM monthly_payments").fetchone()[0])
        conn.execute("DROP TABLE IF EXISTS monthly_payments_new")
        conn.execute(MONTHLY_PAYMENTS_TABLE.replace("monthly_payments", "monthly_payments_new", 1))
        columns = (
            "payment_id, person_id, fiscal_year, target_month, calculation_mode, payment_days, "
            "distribution_ratio, previous_balance, monthly_added_amount, before_payment_balance, "
            "gross_amount, withholding_amount, net_amount, after_balance, status, memo, created_at, updated_at"
        )
        conn.execute(
            f"INSERT INTO monthly_payments_new ({columns}) SELECT {columns} FROM monthly_payments"
        )
        after_count = int(conn.execute("SELECT COUNT(*) FROM monthly_payments_new").fetchone()[0])
        if before_count != after_count:
            raise sqlite3.IntegrityError("月次精算データの移行件数が一致しません。")
        conn.execute("DROP TABLE monthly_payments")
        conn.execute("ALTER TABLE monthly_payments_new RENAME TO monthly_payments")

    def _has_payment_natural_key_unique(self, conn: sqlite3.Connection) -> bool:
        for index in conn.execute("PRAGMA index_list(monthly_payments)").fetchall():
            if not int(index[2]):
                continue
            columns = [row[2] for row in conn.execute(f"PRAGMA index_info('{index[1]}')").fetchall()]
            if columns == ["person_id", "fiscal_year", "target_month"]:
                return True
        return False

    @staticmethod
    def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
        return {str(row[1]) for row in conn.execute(f"PRAGMA table_info('{table}')").fetchall()}

    @staticmethod
    def _check_integrity(conn: sqlite3.Connection) -> None:
        result = conn.execute("PRAGMA integrity_check").fetchone()
        if not result or str(result[0]).lower() != "ok":
            detail = result[0] if result else "unknown error"
            raise sqlite3.DatabaseError(f"データベース整合性チェックに失敗しました: {detail}")

    def _seed_settings(self, conn: sqlite3.Connection) -> None:
        defaults = {
            "schema_version": str(SCHEMA_VERSION),
            "fiscal_year": "2026",
            "fiscal_year_start_month": "4",
            "resident_tax_rate": "0.1021",
            "nonresident_tax_rate": "0.2042",
            "default_daily_gross_amount": "10000",
            "default_daily_net_amount": "8979",
            "amount_decimal_places": "0",
            "delete_password_hash": hashlib.sha256("Coast2404".encode("utf-8")).hexdigest(),
        }
        for key, value in defaults.items():
            conn.execute(
                """
                INSERT OR IGNORE INTO app_settings (setting_key, setting_value)
                VALUES (?, ?)
                """,
                (key, value),
            )


MONTHLY_PAYMENTS_TABLE = """
CREATE TABLE monthly_payments (
    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER NOT NULL,
    fiscal_year INTEGER NOT NULL,
    target_month TEXT NOT NULL,
    calculation_mode TEXT NOT NULL DEFAULT 'days',
    payment_days REAL DEFAULT 0,
    distribution_ratio REAL DEFAULT 1.0,
    previous_balance REAL NOT NULL DEFAULT 0,
    monthly_added_amount REAL NOT NULL DEFAULT 0,
    before_payment_balance REAL NOT NULL DEFAULT 0,
    gross_amount REAL NOT NULL DEFAULT 0,
    withholding_amount REAL NOT NULL DEFAULT 0,
    net_amount REAL NOT NULL DEFAULT 0,
    after_balance REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'draft',
    memo TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (person_id) REFERENCES persons(person_id) ON DELETE CASCADE
)
"""


SCHEMA = f"""
CREATE TABLE IF NOT EXISTS persons (
    person_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    display_name TEXT,
    name_kana TEXT,
    memo TEXT,
    color TEXT,
    resident_type TEXT NOT NULL DEFAULT 'resident',
    tax_rate REAL,
    daily_gross_amount INTEGER NOT NULL DEFAULT 10000,
    daily_net_amount INTEGER NOT NULL DEFAULT 8979,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS accounting_records (
    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_date TEXT NOT NULL,
    person_id INTEGER NOT NULL,
    item_name TEXT NOT NULL,
    amount REAL NOT NULL DEFAULT 0,
    record_type TEXT NOT NULL DEFAULT 'income',
    fiscal_year INTEGER NOT NULL,
    target_month TEXT NOT NULL,
    memo TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (person_id) REFERENCES persons(person_id) ON DELETE CASCADE
);

{MONTHLY_PAYMENTS_TABLE.replace('CREATE TABLE monthly_payments', 'CREATE TABLE IF NOT EXISTS monthly_payments', 1)};

CREATE TABLE IF NOT EXISTS app_settings (
    setting_key TEXT PRIMARY KEY,
    setting_value TEXT NOT NULL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS operation_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_time TEXT DEFAULT CURRENT_TIMESTAMP,
    event_level TEXT NOT NULL DEFAULT 'INFO',
    event_type TEXT NOT NULL,
    message TEXT NOT NULL
);
"""
