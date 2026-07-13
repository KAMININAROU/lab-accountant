from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class AppConfig:
    app_name: str
    database_path: str
    fiscal_year: int
    fiscal_year_start_month: int
    resident_tax_rate: float
    nonresident_tax_rate: float
    default_daily_gross_amount: int
    default_daily_net_amount: int
    amount_decimal_places: int
    default_export_path: str
    backup_path: str
    auto_backup_interval_minutes: int
    app_version: str


def load_config() -> AppConfig:
    config_path = PROJECT_ROOT / "config" / "app_config.json"
    data = json.loads(config_path.read_text(encoding="utf-8"))
    database_path = Path(data["database_path"])
    if not database_path.is_absolute():
        data["database_path"] = str(PROJECT_ROOT / database_path)
    export_path = Path(data["default_export_path"])
    if not export_path.is_absolute():
        data["default_export_path"] = str(PROJECT_ROOT / export_path)
    backup_path = Path(data.get("backup_path", "backups"))
    if not backup_path.is_absolute():
        data["backup_path"] = str(PROJECT_ROOT / backup_path)
    data["auto_backup_interval_minutes"] = int(data.get("auto_backup_interval_minutes", 5))
    data["app_version"] = str(data.get("app_version", "1.0.1"))
    return AppConfig(**data)
