from __future__ import annotations

import argparse
from pathlib import Path

from loguru import logger

from .core.discovery import probe_career_pages
from .core.registry import load_registry
from .pipeline import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="AI job discovery engine")
    parser.add_argument("--sources", default="job_intel_sources.yaml", help="Registry YAML with companies and sources")
    parser.add_argument("--resume", default="resume.txt", help="Path to resume text file")
    parser.add_argument("--out-dir", default=".", help="Directory for CSV and markdown outputs")
    parser.add_argument("--db-path", default="cache/job_intel.sqlite3", help="SQLite database path")
    parser.add_argument("--min-score", type=float, default=0.45, help="Minimum ranked score to emit")
    parser.add_argument("--discover", action="store_true", help="Probe company domains for likely careers pages before running")
    args = parser.parse_args()

    registry_path = Path(args.sources)
    companies, sources = load_registry(registry_path)
    resume_path = Path(args.resume)
    resume_text = None
    if resume_path.exists():
        resume_text = resume_path.read_text(encoding="utf-8")
    else:
        logger.warning("Resume file not found; using heuristic-only ranking", resume=str(resume_path))

    if args.discover:
        for company in companies:
            results = probe_career_pages(company.domain)
            if not results:
                logger.info("Discovery found no pages", company=company.name, domain=company.domain)
                continue
            for result in results:
                logger.info(
                    "Discovered career page",
                    company=company.name,
                    url=result.url,
                    status_code=result.status_code,
                    ats_hints=result.ats_hints,
                )

    jobs, ranked, diagnostics = run_pipeline(
        companies=companies,
        sources=sources,
        out_dir=Path(args.out_dir),
        db_path=Path(args.db_path),
        min_score=args.min_score,
        resume_text=resume_text,
    )
    logger.info(
        "Run complete",
        normalized_jobs=len(jobs),
        ranked_jobs=len(ranked),
        diagnostics_rows=len(diagnostics),
        resume_loaded=bool(resume_text),
        out_dir=str(Path(args.out_dir).resolve()),
    )


if __name__ == "__main__":
    main()
