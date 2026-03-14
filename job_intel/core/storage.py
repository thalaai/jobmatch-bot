from __future__ import annotations

from pathlib import Path
import sqlite3


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS companies (
    name TEXT PRIMARY KEY,
    domain TEXT NOT NULL,
    canonical_careers_url TEXT,
    ats_url TEXT,
    ats_type TEXT,
    last_verified_at TEXT,
    health_score REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS company_sources (
    company TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    entrypoint TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    metadata_json TEXT,
    PRIMARY KEY (company, source_name, entrypoint)
);

CREATE TABLE IF NOT EXISTS raw_jobs (
    source TEXT NOT NULL,
    source_id TEXT,
    company TEXT NOT NULL,
    title TEXT NOT NULL,
    location_raw TEXT,
    posted_date_raw TEXT,
    url_raw TEXT NOT NULL,
    description_raw TEXT,
    employment_type_raw TEXT,
    team_raw TEXT,
    level_raw TEXT,
    raw_payload_json TEXT,
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (source, url_raw)
);

CREATE TABLE IF NOT EXISTS normalized_jobs (
    job_uid TEXT PRIMARY KEY,
    fingerprint TEXT NOT NULL,
    source TEXT NOT NULL,
    source_type TEXT NOT NULL,
    company TEXT NOT NULL,
    title TEXT NOT NULL,
    normalized_title TEXT NOT NULL,
    title_family TEXT NOT NULL,
    location TEXT,
    country TEXT,
    remote_type TEXT,
    employment_type TEXT,
    description TEXT,
    apply_url TEXT NOT NULL,
    source_job_id TEXT,
    posted_at TEXT,
    team TEXT,
    level TEXT,
    first_seen_at TEXT,
    last_seen_at TEXT,
    active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS job_snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_uid TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    score REAL,
    explanation_json TEXT
);

CREATE TABLE IF NOT EXISTS source_health (
    company TEXT NOT NULL,
    source TEXT NOT NULL,
    adapter TEXT NOT NULL,
    last_success_at TEXT,
    last_error TEXT,
    consecutive_failures INTEGER DEFAULT 0,
    avg_jobs_per_run REAL DEFAULT 0,
    success_rate_7d REAL DEFAULT 0,
    median_latency_ms REAL DEFAULT 0,
    PRIMARY KEY (company, source, adapter)
);

CREATE TABLE IF NOT EXISTS diagnostics (
    run_id TEXT,
    company TEXT,
    source TEXT,
    adapter TEXT,
    adapter_status TEXT,
    raw_found INTEGER,
    normalized_found INTEGER,
    dropped_title INTEGER,
    dropped_location INTEGER,
    dropped_level INTEGER,
    dropped_keyword INTEGER,
    deduped_out INTEGER,
    scored_count INTEGER,
    max_score REAL,
    output_count INTEGER,
    error TEXT,
    started_at TEXT,
    ended_at TEXT
);
"""


def ensure_sqlite(path: str | Path) -> sqlite3.Connection:
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.executescript(SCHEMA_SQL)
    connection.commit()
    return connection

