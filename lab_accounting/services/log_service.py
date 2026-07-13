from __future__ import annotations

from lab_accounting.repositories.log_repository import LogRepository


class LogService:
    def __init__(self, repo: LogRepository) -> None:
        self.repo = repo

    def list(self, level: str = "", keyword: str = "") -> list[dict]:
        return self.repo.list(level, keyword)
