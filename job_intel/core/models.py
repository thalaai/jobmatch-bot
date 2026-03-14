from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, HttpUrl


AdapterStatus = Literal[
    "working",
    "no_results",
    "blocked",
    "captcha",
    "selector_failure",
    "unsupported",
    "parse_error",
    "request_error",
    "failed",
]


SourceType = Literal[
    "greenhouse",
    "lever",
    "workday",
    "eightfold",
    "amazon_json",
    "microsoft_search",
    "apple_jsonld",
    "meta_graphql",
    "smartrecruiters",
    "ashby",
    "icims",
    "successfactors",
    "taleo",
    "phenom",
    "jsonld",
    "html",
    "unknown",
]


class CompanyRecord(BaseModel):
    name: str
    domain: str
    canonical_careers_url: Optional[HttpUrl] = None
    ats_url: Optional[HttpUrl] = None
    ats_type: SourceType = "unknown"
    last_verified_at: Optional[datetime] = None
    health_score: float = 0.0


class CompanySource(BaseModel):
    company: str
    source_name: str
    source_type: SourceType
    entrypoint: str
    enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class RawJob(BaseModel):
    source: str
    source_type: SourceType = "unknown"
    company: str
    source_id: Optional[str] = None
    title: str
    location_raw: Optional[str] = None
    posted_date_raw: Optional[str] = None
    url_raw: str
    description_raw: Optional[str] = None
    employment_type_raw: Optional[str] = None
    team_raw: Optional[str] = None
    level_raw: Optional[str] = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    discovered_from: Optional[str] = None
    fetched_at: datetime


class NormalizedJob(BaseModel):
    job_uid: str
    fingerprint: str
    source: str
    source_type: SourceType
    company: str
    title: str
    normalized_title: str
    title_family: str
    location: Optional[str] = None
    country: Optional[str] = None
    remote_type: Literal["remote", "hybrid", "onsite", "unknown"] = "unknown"
    employment_type: Optional[str] = None
    description: str = ""
    apply_url: str
    source_job_id: Optional[str] = None
    posted_at: Optional[date] = None
    team: Optional[str] = None
    level: Optional[str] = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class RankedJob(BaseModel):
    job_uid: str
    score: float
    resume_score: float = 0.0
    title_score: float
    seniority_score: float
    leadership_score: float
    domain_score: float
    location_score: float
    adjacent_role_penalty: float = 0.0
    explanation: list[str] = Field(default_factory=list)


class SourceRun(BaseModel):
    run_id: str
    company: str
    source: str
    adapter: str
    adapter_status: AdapterStatus = "working"
    raw_found: int = 0
    normalized_found: int = 0
    dropped_title: int = 0
    dropped_location: int = 0
    dropped_level: int = 0
    dropped_keyword: int = 0
    deduped_out: int = 0
    scored_count: int = 0
    max_score: float = 0.0
    output_count: int = 0
    error: Optional[str] = None
    pages_fetched: int = 0
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None


class SourceHealth(BaseModel):
    company: str
    source: str
    adapter: str
    last_verified_at: datetime = Field(default_factory=datetime.utcnow)
    adapter_status: AdapterStatus = "working"
    last_success_at: Optional[datetime] = None
    last_error: Optional[str] = None
    consecutive_failures: int = 0
    avg_jobs_per_run: float = 0.0
    success_rate_7d: float = 0.0
    median_latency_ms: float = 0.0


class DiagnosticsRow(BaseModel):
    company: str
    source: str
    adapter: str
    adapter_status: AdapterStatus
    raw_found: int = 0
    normalized_found: int = 0
    dropped_title: int = 0
    dropped_location: int = 0
    dropped_level: int = 0
    dropped_keyword: int = 0
    deduped_out: int = 0
    scored_count: int = 0
    max_score: float = 0.0
    output_count: int = 0
    error: Optional[str] = None
