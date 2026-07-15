from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path


def _default_project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


PROJECT_ROOT = _default_project_root()


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
    auto_backup_keep_count: int
    app_version: str
    app_description: str


def load_config(config_path: str | Path | None = None) -> AppConfig:
    path = Path(config_path) if config_path else PROJECT_ROOT / "config" / "app_config.json"
    loaded = json.loads(path.read_text(encoding="utf-8"))
    defaults = {
        "fiscal_year_start_month": 4,
        "resident_tax_rate": 0.1021,
        "nonresident_tax_rate": 0.2042,
        "default_daily_gross_amount": 10000,
        "default_daily_net_amount": 8979,
        "amount_decimal_places": 0,
        "default_export_path": "exports",
        "backup_path": "backups",
        "auto_backup_interval_minutes": 5,
        "auto_backup_keep_count": 5,
        "app_version": "1.1.0",
        "app_description": "研究室の業務委託報酬・使用費目を管理します。",
    }
    data = {**defaults, **loaded}
    base_root = path.parent.parent if path.parent.name == "config" else path.parent
    database_path = Path(data["database_path"])
    if not database_path.is_absolute():
        data["database_path"] = str(base_root / database_path)
    export_path = Path(data["default_export_path"])
    if not export_path.is_absolute():
        data["default_export_path"] = str(base_root / export_path)
    backup_path = Path(data.get("backup_path", "backups"))
    if not backup_path.is_absolute():
        data["backup_path"] = str(base_root / backup_path)
    data["auto_backup_interval_minutes"] = int(data.get("auto_backup_interval_minutes", 5))
    data["auto_backup_keep_count"] = max(1, int(data.get("auto_backup_keep_count", 5)))
    data["app_version"] = str(data.get("app_version", "1.0.1"))
    data["app_description"] = str(data.get("app_description") or defaults["app_description"])
    fields = AppConfig.__dataclass_fields__
    return AppConfig(**{key: data[key] for key in fields})
