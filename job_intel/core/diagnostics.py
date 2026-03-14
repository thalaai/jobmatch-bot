from __future__ import annotations

import csv
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator
from uuid import uuid4

from loguru import logger

from .models import DiagnosticsRow, SourceRun


class DiagnosticTracker:
    def __init__(self, company: str, source: str, adapter: str):
        self.run = SourceRun(
            run_id=str(uuid4()),
            company=company,
            source=source,
            adapter=adapter,
        )

    def incr(self, field: str, count: int = 1) -> None:
        if hasattr(self.run, field):
            setattr(self.run, field, getattr(self.run, field) + count)

    def status(self, value: str) -> None:
        self.run.adapter_status = value  # type: ignore[assignment]

    def fail(self, error: str, status: str = "failed") -> None:
        self.run.error = error
        self.run.adapter_status = status  # type: ignore[assignment]

    def finish(self) -> None:
        self.run.ended_at = datetime.utcnow()

    def log(self) -> None:
        payload = self.run.model_dump()
        logger.bind(**payload).info("Source run complete")

    def row(self) -> DiagnosticsRow:
        return DiagnosticsRow(
            company=self.run.company,
            source=self.run.source,
            adapter=self.run.adapter,
            adapter_status=self.run.adapter_status,
            raw_found=self.run.raw_found,
            normalized_found=self.run.normalized_found,
            dropped_title=self.run.dropped_title,
            dropped_location=self.run.dropped_location,
            dropped_level=self.run.dropped_level,
            dropped_keyword=self.run.dropped_keyword,
            deduped_out=self.run.deduped_out,
            scored_count=self.run.scored_count,
            max_score=self.run.max_score,
            output_count=self.run.output_count,
            error=self.run.error,
        )


@contextmanager
def track(company: str, source: str, adapter: str) -> Iterator[DiagnosticTracker]:
    tracker = DiagnosticTracker(company=company, source=source, adapter=adapter)
    try:
        yield tracker
        if tracker.run.adapter_status == "working" and tracker.run.raw_found == 0:
            tracker.status("no_results")
    except Exception as exc:
        tracker.fail(str(exc), status="failed")
        logger.exception("Adapter run failed", company=company, source=source, adapter=adapter)
        raise
    finally:
        tracker.finish()
        tracker.log()


def write_diagnostics_csv(rows: list[DiagnosticsRow], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(DiagnosticsRow.model_fields.keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.model_dump())

