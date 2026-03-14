from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

import httpx

from .models import NormalizedJob, RawJob, SourceHealth, SourceRun


@dataclass
class AdapterContext:
    company: str
    source: str
    source_type: str
    entrypoint: str
    metadata: dict[str, Any] = field(default_factory=dict)
    timeout_s: float = 30.0
    client: Optional[httpx.Client] = None


class BaseAdapter(ABC):
    """Structured ingestion interface for ATS-backed sources."""

    name: str

    def __init__(self, context: AdapterContext):
        self.context = context

    @abstractmethod
    def discover(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def fetch_raw(self, entrypoint: str, run: SourceRun) -> list[RawJob]:
        raise NotImplementedError

    @abstractmethod
    def normalize(self, raw: RawJob) -> Optional[NormalizedJob]:
        raise NotImplementedError

    @abstractmethod
    def healthcheck(self) -> SourceHealth:
        raise NotImplementedError

    def fetch_all(self, run: SourceRun) -> Iterable[RawJob]:
        for entry in self.discover():
            yield from self.fetch_raw(entry, run)

