from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

import httpx

from ..core.interfaces import BaseAdapter
from ..core.models import NormalizedJob, RawJob
from ..core.normalization import normalize
from ..core.diagnostics import track


class TeslaApiAdapter(BaseAdapter):
    name = "tesla_api"

    def __init__(self, api_url: str, company: str, params: dict[str, Any] | None = None, timeout_s: int = 30):
        self.api_url = api_url
        self.company = company
        self.params = params or {}
        self.timeout_s = timeout_s

    def discover(self) -> list[str]:
        return [self.api_url]

    def fetch_raw(self, entrypoint: str) -> list[RawJob]:
        with track(self.name, self.company) as diag:
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://www.tesla.com/careers/search",
            }
            resp = httpx.get(entrypoint, params=self.params, headers=headers, timeout=self.timeout_s)
            if resp.status_code in (403, 404):
                diag.incr("blocked", 1)
                return []
            if resp.status_code >= 500:
                diag.incr("errors", 1)
                return []
            resp.raise_for_status()
            data = resp.json()
            items = data.get("results") or data.get("jobs") or data.get("data") or []
            jobs: list[RawJob] = []
            for j in items:
                diag.incr("discovered", 1)
                job_id = str(j.get("id") or j.get("job_id") or "")
                url = j.get("url") or (f"https://www.tesla.com/careers/search/job/{job_id}" if job_id else "")
                title = j.get("title") or j.get("job_title") or ""
                location = j.get("location") or j.get("locations") or ""
                desc = j.get("description") or ""
                jobs.append(
                    RawJob(
                        source=self.name,
                        source_id=job_id,
                        company=self.company,
                        title=title,
                        location_raw=str(location),
                        posted_date_raw=str(j.get("datePosted") or j.get("posted") or ""),
                        url_raw=url,
                        description_raw=desc,
                        payload=j,
                        fetched_at=datetime.utcnow(),
                    )
                )
            diag.incr("fetched", len(jobs))
            return jobs

    def normalize(self, raw: RawJob) -> Optional[NormalizedJob]:
        return normalize(raw, source_run_id=f"{self.name}:{self.company}")

    def healthcheck(self) -> dict[str, Any]:
        return {"source": self.name, "company": self.company}
