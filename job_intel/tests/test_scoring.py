from job_intel.engine.scoring import score_job
from job_intel.core.models import NormalizedJob


def test_scoring_basic():
    job = NormalizedJob(
        job_uid="x",
        fingerprint="fp",
        source="greenhouse",
        source_type="greenhouse",
        company="Acme",
        title="Senior Technical Program Manager",
        normalized_title="technical program manager",
        title_family="technical_program_manager",
        location="Remote - US",
        country="US",
        remote_type="remote",
        employment_type="full-time",
        description="platform systems cross-functional delivery",
        apply_url="https://example.com/job",
        source_job_id="123",
        posted_at=None,
        team="Platform",
        level="senior",
        raw_payload={},
    )
    score = score_job(job, resume_text="senior technical program manager platform systems delivery")
    assert score.score > 0.5
