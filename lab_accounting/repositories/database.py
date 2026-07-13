from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from typing import Iterable


class Database:
    def __init__(self, path: str) -> None:
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            self._seed_settings(conn)

    def query(self, sql: str, params: Iterable[object] = ()) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(sql, tuple(params)).fetchall()

    def execute(self, sql: str, params: Iterable[object] = ()) -> int:
        with self.connect() as conn:
            cur = conn.execute(sql, tuple(params))
            return int(cur.lastrowid or 0)

    def executescript(self, sql: str) -> None:
        with self.connect() as conn:
            conn.executescript(sql)

    def _seed_settings(self, conn: sqlite3.Connection) -> None:
        defaults = {
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


SCHEMA = """
CREATE TABLE IF NOT EXISTS persons (
    person_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    display_name TEXT,
    name_kana TEXT,
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
    FOREIGN KEY (person_id) REFERENCES persons(person_id)
);

CREATE TABLE IF NOT EXISTS monthly_payments (
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
    FOREIGN KEY (person_id) REFERENCES persons(person_id),
    UNIQUE (person_id, fiscal_year, target_month)
);

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
