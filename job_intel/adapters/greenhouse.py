from __future__ import annotations

from datetime import datetime
from typing import Optional

import httpx

from ..core.interfaces import AdapterContext, BaseAdapter
from ..core.models import NormalizedJob, RawJob, SourceHealth, SourceRun
from ..core.normalization import normalize_job
from ..engine.utils import resilient_headers


class GreenhouseAdapter(BaseAdapter):
    name = "greenhouse"

    def __init__(self, context: AdapterContext):
        super().__init__(context)
        self._health = SourceHealth(company=context.company, source=context.source, adapter=self.name)

    def discover(self) -> list[str]:
        slug = self.context.metadata["slug"]
        content = self.context.metadata.get("content", True)
        suffix = "?content=true" if content else ""
        return [f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs{suffix}"]

    def fetch_raw(self, entrypoint: str, run: SourceRun) -> list[RawJob]:
        client = self.context.client or httpx.Client(headers=resilient_headers(), follow_redirects=True, timeout=self.context.timeout_s)
        close_client = self.context.client is None
        try:
            response = client.get(entrypoint)
            run.pages_fetched += 1
            if response.status_code >= 400:
                run.error = f"{response.status_code} from {entrypoint}"
                run.adapter_status = "request_error"
                self._health.last_error = run.error
                return []
            payload = response.json()
            jobs: list[RawJob] = []
            for item in payload.get("jobs", []):
                url = (item.get("absolute_url") or "").strip()
                title = (item.get("title") or "").strip()
                if not url or not title:
                    continue
                jobs.append(
                    RawJob(
                        source=self.context.source,
                        source_type="greenhouse",
                        company=self.context.company,
                        source_id=str(item.get("id") or ""),
                        title=title,
                        location_raw=(item.get("location") or {}).get("name"),
                        posted_date_raw=str(item.get("updated_at") or ""),
                        url_raw=url,
                        description_raw=item.get("content") or "",
                        team_raw=item.get("departments", [{}])[0].get("name") if item.get("departments") else None,
                        raw_payload=item,
                        discovered_from=entrypoint,
                        fetched_at=datetime.utcnow(),
                    )
                )
            run.raw_found += len(jobs)
            self._health.last_success_at = datetime.utcnow()
            return jobs
        except Exception as exc:
            run.error = str(exc)
            run.adapter_status = "request_error"
            self._health.last_error = str(exc)
            raise
        finally:
            if close_client:
                client.close()

    def normalize(self, raw: RawJob) -> Optional[NormalizedJob]:
        job = normalize_job(raw)
        if job:
            self._health.avg_jobs_per_run += 1
        return job

    def healthcheck(self) -> SourceHealth:
        return self._health

