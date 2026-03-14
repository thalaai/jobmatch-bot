from __future__ import annotations

import re

from rapidfuzz import fuzz

from ..core.models import NormalizedJob, RankedJob


TITLE_WEIGHTS = {
    "technical_program_manager": 1.0,
    "engineering_program_manager": 0.95,
    "platform_program_manager": 0.94,
    "systems_program_manager": 0.92,
    "program_manager": 0.88,
    "npi_program_manager": 0.86,
    "operations_program_manager": 0.8,
    "technical_product_manager": 0.78,
    "delivery_transformation_portfolio": 0.72,
    "other": 0.45,
}

LEADERSHIP_TERMS = {
    "cross functional",
    "execution",
    "delivery",
    "roadmap",
    "stakeholder",
    "program",
    "launch",
}

DOMAIN_TERMS = {
    "hardware",
    "software",
    "ai",
    "llm",
    "platform",
    "infrastructure",
    "embedded",
    "manufacturing",
    "systems",
    "operations",
}

EXCLUSION_TERMS = {"recruiter", "intern", "designer", "sales", "account executive"}

TARGET_TITLES = [
    "technical program manager",
    "senior technical program manager",
    "program manager",
    "engineering program manager",
    "platform program manager",
]


def normalize_resume_text(text: str) -> str:
    lowered = text.lower()
    lowered = re.sub(r"[^a-z0-9\s/+&-]", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def _fuzzy_title_score(job: NormalizedJob) -> float:
    comparisons = [fuzz.token_set_ratio(job.normalized_title, title) for title in TARGET_TITLES]
    base = max(comparisons) / 100.0 if comparisons else 0.0
    family = TITLE_WEIGHTS.get(job.title_family, TITLE_WEIGHTS["other"])
    return round(0.6 * family + 0.4 * base, 4)


def _seniority_score(job: NormalizedJob) -> float:
    text = f"{job.title} {job.level or ''}".lower()
    if any(term in text for term in ("principal", "staff")):
        return 1.0
    if any(term in text for term in ("senior", "sr", "lead")):
        return 0.85
    if "manager" in text:
        return 0.65
    return 0.45


def _keyword_score(haystack: str, terms: set[str]) -> float:
    text = haystack.lower()
    hits = sum(1 for term in terms if term in text)
    return min(1.0, hits / max(4, len(terms) // 2))


def _location_score(job: NormalizedJob) -> float:
    text = f"{job.location or ''} {job.remote_type}".lower()
    if "remote" in text:
        return 1.0
    if any(token in text for token in ("ca", "california", "wa", "washington", "seattle", "bay area", "cupertino")):
        return 0.9
    if "united states" in text or "usa" in text:
        return 0.75
    return 0.5


def _resume_score(job: NormalizedJob, resume_text: str | None) -> float:
    if not resume_text:
        return 0.0
    resume = normalize_resume_text(resume_text)
    if not resume:
        return 0.0
    job_text = normalize_resume_text(f"{job.title} {job.description} {job.team or ''}")
    if not job_text:
        return 0.0
    return round(fuzz.token_set_ratio(resume, job_text) / 100.0, 4)


def score_job(job: NormalizedJob, resume_text: str | None = None) -> RankedJob:
    combined_text = f"{job.title} {job.description} {job.team or ''}"
    resume_score = _resume_score(job, resume_text)
    title_score = _fuzzy_title_score(job)
    seniority_score = _seniority_score(job)
    leadership_score = _keyword_score(combined_text, LEADERSHIP_TERMS)
    domain_score = _keyword_score(combined_text, DOMAIN_TERMS)
    location_score = _location_score(job)

    penalty = 0.0
    if any(term in job.normalized_title for term in EXCLUSION_TERMS):
        penalty = 0.75
    elif job.title_family == "other":
        penalty = 0.15

    score = (
        0.25 * title_score
        + 0.1 * seniority_score
        + 0.15 * leadership_score
        + 0.15 * domain_score
        + 0.1 * location_score
        + 0.25 * resume_score
        - penalty
    )
    score = max(0.0, min(1.0, round(score, 4)))

    explanation = [
        f"resume_similarity={resume_score:.2f}",
        f"title_family={job.title_family} ({title_score:.2f})",
        f"seniority={job.level or job.title} ({seniority_score:.2f})",
        f"leadership_signals={leadership_score:.2f}",
        f"domain_signals={domain_score:.2f}",
        f"location_fit={location_score:.2f}",
    ]
    if penalty:
        explanation.append(f"adjacent_role_penalty={penalty:.2f}")

    return RankedJob(
        job_uid=job.job_uid,
        score=score,
        resume_score=resume_score,
        title_score=title_score,
        seniority_score=seniority_score,
        leadership_score=leadership_score,
        domain_score=domain_score,
        location_score=location_score,
        adjacent_role_penalty=penalty,
        explanation=explanation,
    )
