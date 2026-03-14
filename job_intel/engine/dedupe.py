from __future__ import annotations

from collections import defaultdict

from ..core.models import NormalizedJob


def dedupe_jobs(jobs: list[NormalizedJob]) -> tuple[list[NormalizedJob], int]:
    kept: list[NormalizedJob] = []
    seen_urls: set[str] = set()
    seen_keys: set[tuple[str, str, str]] = set()
    seen_fingerprints: set[str] = set()
    deduped_out = 0

    for job in jobs:
        key = (
            job.company.lower(),
            job.normalized_title,
            (job.location or "").lower(),
        )
        if job.apply_url in seen_urls or key in seen_keys or job.fingerprint in seen_fingerprints:
            deduped_out += 1
            continue
        seen_urls.add(job.apply_url)
        seen_keys.add(key)
        seen_fingerprints.add(job.fingerprint)
        kept.append(job)

    return kept, deduped_out


def cluster_duplicates(jobs: list[NormalizedJob]) -> dict[str, list[NormalizedJob]]:
    clusters: dict[str, list[NormalizedJob]] = defaultdict(list)
    for job in jobs:
        clusters[job.fingerprint].append(job)
    return dict(clusters)
