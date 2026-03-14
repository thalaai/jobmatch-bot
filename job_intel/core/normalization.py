from __future__ import annotations

import hashlib
import re
from datetime import date, datetime
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

from .models import NormalizedJob, RawJob


TITLE_FAMILIES: dict[str, tuple[str, ...]] = {
    "technical_program_manager": (
        "technical program manager",
        "tpm",
        "technical project manager",
    ),
    "engineering_program_manager": ("engineering program manager", "epm"),
    "systems_program_manager": ("systems program manager", "system integration manager"),
    "platform_program_manager": ("platform program manager", "ai platform", "platform delivery"),
    "operations_program_manager": ("operations program manager", "product operations"),
    "npi_program_manager": ("npi program manager", "new product introduction"),
    "technical_product_manager": (
        "technical product manager",
        "ai product manager",
        "platform product manager",
    ),
    "delivery_transformation_portfolio": (
        "delivery manager",
        "portfolio manager",
        "transformation manager",
    ),
    "program_manager": ("program manager", "program lead", "program management"),
}


EXCLUSION_TERMS = {
    "recruiter",
    "intern",
    "internship",
    "contractor",
    "sales",
    "designer",
    "software engineer",
    "data scientist",
    "finance",
}


def canonicalize_url(url: str, base_url: Optional[str] = None) -> str:
    resolved = urljoin(base_url or "", url.strip())
    parsed = urlparse(resolved)
    query = [(k, v) for k, v in parse_qsl(parsed.query) if not k.lower().startswith("utm_")]
    cleaned = parsed._replace(query=urlencode(query, doseq=True), fragment="")
    return urlunparse(cleaned)


def normalize_whitespace(text: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def normalize_title(title: str) -> str:
    text = normalize_whitespace(title).lower()
    text = re.sub(r"[^a-z0-9\s/+&-]", " ", text)
    text = re.sub(r"\bpm\b", " program manager ", text)
    text = re.sub(r"\btpm\b", " technical program manager ", text)
    text = re.sub(r"\bepm\b", " engineering program manager ", text)
    return normalize_whitespace(text)


def classify_title_family(title: str) -> str:
    normalized = normalize_title(title)
    for family, terms in TITLE_FAMILIES.items():
        if any(term in normalized for term in terms):
            return family
    return "other"


def infer_seniority(title: str) -> Optional[str]:
    text = normalize_title(title)
    if any(term in text for term in ("principal", "staff")):
        return "principal"
    if any(term in text for term in ("senior", "sr", "lead")):
        return "senior"
    if "manager" in text:
        return "manager"
    return None


def infer_remote_type(location: Optional[str], description: Optional[str]) -> str:
    haystack = f"{location or ''} {description or ''}".lower()
    if "remote" in haystack:
        return "remote"
    if "hybrid" in haystack:
        return "hybrid"
    if normalize_whitespace(location):
        return "onsite"
    return "unknown"


def parse_posted_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    raw = str(value).strip()
    if raw.isdigit() and len(raw) >= 10:
        timestamp = int(raw)
        if timestamp > 10_000_000_000:
            timestamp = timestamp // 1000
        try:
            return datetime.utcfromtimestamp(timestamp).date()
        except ValueError:
            return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def infer_country(location: Optional[str]) -> Optional[str]:
    text = (location or "").lower()
    if any(token in text for token in ("united states", " usa", ", us", "remote-us")):
        return "US"
    return None


def fingerprint(company: str, normalized_title: str, location: Optional[str], key: str) -> str:
    base = "|".join(
        [
            normalize_whitespace(company).lower(),
            normalized_title,
            normalize_whitespace(location).lower(),
            key,
        ]
    )
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def should_soft_exclude(title: str) -> bool:
    normalized = normalize_title(title)
    return any(term in normalized for term in EXCLUSION_TERMS)


def normalize_job(raw: RawJob) -> Optional[NormalizedJob]:
    title = normalize_whitespace(raw.title)
    apply_url = canonicalize_url(raw.url_raw)
    if not title or not apply_url:
        return None

    description = normalize_whitespace(raw.description_raw)
    location = normalize_whitespace(raw.location_raw) or None
    normalized_title = normalize_title(title)
    source_key = raw.source_id or apply_url
    job_uid = fingerprint(raw.company, normalized_title, location, source_key)

    return NormalizedJob(
        job_uid=job_uid,
        fingerprint=fingerprint(raw.company, normalized_title, location, apply_url),
        source=raw.source,
        source_type=raw.source_type,
        company=normalize_whitespace(raw.company),
        title=title,
        normalized_title=normalized_title,
        title_family=classify_title_family(title),
        location=location,
        country=infer_country(location),
        remote_type=infer_remote_type(location, description),
        employment_type=normalize_whitespace(raw.employment_type_raw) or None,
        description=description,
        apply_url=apply_url,
        source_job_id=raw.source_id,
        posted_at=parse_posted_date(raw.posted_date_raw),
        team=normalize_whitespace(raw.team_raw) or None,
        level=normalize_whitespace(raw.level_raw) or infer_seniority(title),
        raw_payload=raw.raw_payload,
    )

