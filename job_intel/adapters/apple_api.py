from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

import httpx

from ..core.interfaces import BaseAdapter
from ..core.models import NormalizedJob, RawJob
from ..core.normalization import normalize
from ..core.diagnostics import track


class AppleApiAdapter(BaseAdapter):
    name = "apple_api"

    def __init__(
        self,
        api_url: str,
        company: str,
        queries: list[str],
        locations: list[str],
        page_size: int = 20,
        timeout_s: int = 30,
    ):
        self.api_url = api_url
        self.company = company
        self.queries = queries
        self.locations = locations
        self.page_size = page_size
        self.timeout_s = timeout_s

    def discover(self) -> list[str]:
        return [self.api_url]

    def _payload(self, query: str, start: int) -> dict[str, Any]:
        return {
            "query": query,
            "filters": {
                "range": {"standardRequests": {"start": start, "size": self.page_size}},
                "location": self.locations,
            },
        }

    def fetch_raw(self, entrypoint: str) -> list[RawJob]:
        with track(self.name, self.company) as diag:
            jobs: list[RawJob] = []
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://jobs.apple.com/en-us/search",
            }
            for q in self.queries:
                start = 0
                while True:
                    payload = self._payload(q, start)
                    try:
                        resp = httpx.post(entrypoint, json=payload, headers=headers, timeout=self.timeout_s)
                    except httpx.ReadTimeout:
                        diag.incr("errors", 1)
                        break
                    if resp.status_code in (401, 403):
                        diag.incr("blocked", 1)
                        break
                    if resp.status_code >= 500:
                        diag.incr("errors", 1)
                        break
                    resp.raise_for_status()
                    data = resp.json()
                    results = data.get("results") or data.get("jobPostings") or []
                    if not results:
                        break
                    for j in results:
                        diag.incr("discovered", 1)
                        url = j.get("postingUrl") or j.get("url") or ""
                        title = j.get("postingTitle") or j.get("title") or ""
                        location = j.get("locations") or j.get("location") or ""
                        job_id = str(j.get("reqId") or j.get("id") or "")
                        desc = j.get("jobSummary") or ""
                        jobs.append(
                            RawJob(
                                source=self.name,
                                source_id=job_id,
                                company=self.company,
                                title=title,
                                location_raw=str(location),
                        posted_date_raw=str(j.get("postingDate") or ""),
                                url_raw=url,
                                description_raw=desc,
                                payload=j,
                                fetched_at=datetime.utcnow(),
                            )
                        )
                    diag.incr("fetched", len(results))
                    if len(results) < self.page_size:
                        break
                    start += self.page_size
            return jobs

    def normalize(self, raw: RawJob) -> Optional[NormalizedJob]:
        return normalize(raw, source_run_id=f"{self.name}:{self.company}")

    def healthcheck(self) -> dict[str, Any]:
        return {"source": self.name, "company": self.company}
