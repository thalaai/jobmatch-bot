from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable

import httpx
from loguru import logger

from .adapters.greenhouse import GreenhouseAdapter
from .adapters.lever import LeverAdapter
from .adapters.eightfold import EightfoldAdapter
from .adapters.amazon_json import AmazonJsonAdapter
from .adapters.microsoft_search import MicrosoftSearchAdapter
from .adapters.apple_jsonld import AppleJsonLdAdapter
from .adapters.meta_graphql import MetaGraphQLAdapter
from .adapters.workday_jsonld import WorkdayAdapter
from .core.diagnostics import track, write_diagnostics_csv
from .core.interfaces import AdapterContext, BaseAdapter
from .core.models import CompanyRecord, CompanySource, DiagnosticsRow, NormalizedJob, RankedJob
from .core.storage import ensure_sqlite
from .engine.dedupe import dedupe_jobs
from .engine.scoring import score_job
from .engine.utils import resilient_headers


ADAPTERS: dict[str, type[BaseAdapter]] = {
    "greenhouse": GreenhouseAdapter,
    "lever": LeverAdapter,
    "eightfold": EightfoldAdapter,
    "amazon_json": AmazonJsonAdapter,
    "workday": WorkdayAdapter,
    "jsonld": WorkdayAdapter,
    "microsoft_search": MicrosoftSearchAdapter,
    "apple_jsonld": AppleJsonLdAdapter,
    "meta_graphql": MetaGraphQLAdapter,
}


def build_adapter(source: CompanySource, client: httpx.Client) -> BaseAdapter | None:
    adapter_cls = ADAPTERS.get(source.source_type)
    if not adapter_cls:
        return None
    context = AdapterContext(
        company=source.company,
        source=source.source_name,
        source_type=source.source_type,
        entrypoint=source.entrypoint,
        metadata=source.metadata,
        client=client,
    )
    return adapter_cls(context)


def run_pipeline(
    companies: list[CompanyRecord],
    sources: list[CompanySource],
    out_dir: Path,
    db_path: Path,
    min_score: float = 0.45,
    resume_text: str | None = None,
) -> tuple[list[NormalizedJob], list[RankedJob], list[DiagnosticsRow]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    ensure_sqlite(db_path)

    company_names = {company.name for company in companies}
    diagnostics: list[DiagnosticsRow] = []
    normalized_jobs: list[NormalizedJob] = []

    with httpx.Client(headers=resilient_headers(), follow_redirects=True, timeout=30.0) as client:
        for source in sources:
            if company_names and source.company not in company_names:
                continue
            adapter = build_adapter(source, client)
            if not adapter:
                diagnostics.append(
                    DiagnosticsRow(
                        company=source.company,
                        source=source.source_name,
                        adapter=source.source_type,
                        adapter_status="unsupported",
                        error=f"Unsupported adapter type: {source.source_type}",
                    )
                )
                continue

            with track(company=source.company, source=source.source_name, adapter=adapter.name) as diag:
                try:
                    raw_jobs = list(adapter.fetch_all(diag.run))
                    if not raw_jobs and diag.run.adapter_status == "working":
                        diag.status("no_results")
                    for raw in raw_jobs:
                        try:
                            normalized = adapter.normalize(raw)
                        except Exception as exc:
                            diag.incr("dropped_keyword")
                            logger.exception("Normalization failed", company=source.company, source=source.source_name, error=str(exc))
                            continue
                        if not normalized:
                            diag.incr("dropped_title")
                            continue
                        normalized_jobs.append(normalized)
                        diag.incr("normalized_found")
                except Exception as exc:
                    diag.fail(str(exc))
                diagnostics.append(diag.row())

    deduped_jobs, deduped_out = dedupe_jobs(normalized_jobs)
    if diagnostics:
        for row in diagnostics:
            row.deduped_out = deduped_out

    ranked_jobs = [score_job(job, resume_text=resume_text) for job in deduped_jobs]
    ranked_jobs.sort(key=lambda item: item.score, reverse=True)
    filtered_ranked = [job for job in ranked_jobs if job.score >= min_score]

    score_by_uid = {job.job_uid: job for job in filtered_ranked}
    for row in diagnostics:
        company_scores = [score.score for score in filtered_ranked if _company_for_uid(score.job_uid, deduped_jobs) == row.company]
        row.scored_count = len(company_scores)
        row.max_score = max(company_scores) if company_scores else 0.0
        row.output_count = len(company_scores)

    write_outputs(out_dir, deduped_jobs, filtered_ranked, diagnostics, score_by_uid)
    return deduped_jobs, filtered_ranked, diagnostics


def _company_for_uid(job_uid: str, jobs: Iterable[NormalizedJob]) -> str | None:
    for job in jobs:
        if job.job_uid == job_uid:
            return job.company
    return None


def write_outputs(
    out_dir: Path,
    jobs: list[NormalizedJob],
    ranked_jobs: list[RankedJob],
    diagnostics: list[DiagnosticsRow],
    score_by_uid: dict[str, RankedJob],
) -> None:
    jobs_path = out_dir / "normalized_jobs.csv"
    ranked_path = out_dir / "ranked_jobs.csv"
    legacy_ranked_path = out_dir / "job_matches.csv"
    diagnostics_path = out_dir / "diagnostics.csv"
    markdown_path = out_dir / "job_matches.md"

    _write_csv(jobs_path, [job.model_dump(mode="json") for job in jobs])
    _write_csv(ranked_path, [job.model_dump(mode="json") for job in ranked_jobs])
    _write_csv(legacy_ranked_path, [job.model_dump(mode="json") for job in ranked_jobs])
    write_diagnostics_csv(diagnostics, diagnostics_path)

    jobs_by_uid = {job.job_uid: job for job in jobs}
    with markdown_path.open("w", encoding="utf-8") as handle:
        handle.write("# Top Jobs by Company\n\n")
        for ranked in ranked_jobs[:50]:
            job = jobs_by_uid[ranked.job_uid]
            handle.write(f"- **{job.company}** | {job.title} | {job.location or ''} | score={ranked.score:.3f}\n")
            handle.write(f"  - {job.apply_url}\n")
            handle.write(f"  - {'; '.join(ranked.explanation)}\n")


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            safe_row = {key: json.dumps(value) if isinstance(value, (dict, list)) else value for key, value in row.items()}
            writer.writerow(safe_row)
