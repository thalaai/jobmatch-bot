from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .models import CompanyRecord, CompanySource


def load_registry(path: str | Path) -> tuple[list[CompanyRecord], list[CompanySource]]:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    companies = [CompanyRecord(**item) for item in data.get("companies", [])]
    sources = [CompanySource(**item) for item in data.get("sources", []) if item.get("enabled", True)]
    return companies, sources


def dump_registry(path: str | Path, companies: list[CompanyRecord], sources: list[CompanySource]) -> None:
    payload: dict[str, Any] = {
        "companies": [company.model_dump(mode="json") for company in companies],
        "sources": [source.model_dump(mode="json") for source in sources],
    }
    with Path(path).open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False)

