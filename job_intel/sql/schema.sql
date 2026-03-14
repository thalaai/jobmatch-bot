CREATE TABLE companies (
    name TEXT PRIMARY KEY,
    domain TEXT NOT NULL,
    canonical_careers_url TEXT,
    ats_url TEXT,
    ats_type TEXT,
    last_verified_at TIMESTAMP,
    health_score DOUBLE PRECISION DEFAULT 0
);

CREATE TABLE company_sources (
    company TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    entrypoint TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    metadata_json JSONB,
    PRIMARY KEY (company, source_name, entrypoint)
);

CREATE TABLE raw_jobs (
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
    raw_payload JSONB,
    fetched_at TIMESTAMP NOT NULL,
    PRIMARY KEY (source, url_raw)
);

CREATE TABLE normalized_jobs (
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
    posted_at DATE,
    team TEXT,
    level TEXT,
    first_seen_at TIMESTAMP,
    last_seen_at TIMESTAMP,
    active BOOLEAN DEFAULT TRUE
);

CREATE TABLE job_snapshots (
    snapshot_id BIGSERIAL PRIMARY KEY,
    job_uid TEXT NOT NULL,
    captured_at TIMESTAMP NOT NULL,
    score DOUBLE PRECISION,
    explanation_json JSONB
);

CREATE TABLE source_health (
    company TEXT NOT NULL,
    source TEXT NOT NULL,
    adapter TEXT NOT NULL,
    last_success_at TIMESTAMP,
    last_error TEXT,
    consecutive_failures INTEGER DEFAULT 0,
    avg_jobs_per_run DOUBLE PRECISION DEFAULT 0,
    success_rate_7d DOUBLE PRECISION DEFAULT 0,
    median_latency_ms DOUBLE PRECISION DEFAULT 0,
    PRIMARY KEY (company, source, adapter)
);

CREATE TABLE diagnostics (
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
    max_score DOUBLE PRECISION,
    output_count INTEGER,
    error TEXT,
    started_at TIMESTAMP,
    ended_at TIMESTAMP
);
