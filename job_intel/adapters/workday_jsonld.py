from __future__ import annotations

from datetime import datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from ..core.extractors import extract_jsonld_job_postings
from ..core.interfaces import AdapterContext, BaseAdapter
from ..core.models import NormalizedJob, RawJob, SourceHealth, SourceRun
from ..core.normalization import canonicalize_url, normalize_job
from ..engine.utils import resilient_headers


class WorkdayAdapter(BaseAdapter):
    name = "workday"

    def __init__(self, context: AdapterContext):
        super().__init__(context)
        self._health = SourceHealth(company=context.company, source=context.source, adapter=self.name)

    def discover(self) -> list[str]:
        return [self.context.entrypoint]

    def fetch_raw(self, entrypoint: str, run: SourceRun) -> list[RawJob]:
        client = self.context.client or httpx.Client(headers=resilient_headers(), follow_redirects=True, timeout=self.context.timeout_s)
        close_client = self.context.client is None
        try:
            api_url = self.context.metadata.get("api_url")
            if api_url:
                jobs = self._fetch_api_jobs(client, api_url, run)
                if jobs:
                    run.raw_found += len(jobs)
                    self._health.last_success_at = datetime.utcnow()
                    return jobs
            response = client.get(entrypoint)
            run.pages_fetched += 1
            if response.status_code >= 400:
                run.error = f"{response.status_code} from {entrypoint}"
                run.adapter_status = "request_error"
                return []
            jobs: list[RawJob] = []
            for item in extract_jsonld_job_postings(response.text, str(response.url)):
                url = canonicalize_url(item.get("url") or entrypoint, base_url=str(response.url))
                title = (item.get("title") or "").strip()
                if not title or not url:
                    continue
                location = None
                location_block = item.get("jobLocation")
                if isinstance(location_block, dict):
                    address = location_block.get("address") or {}
                    location = address.get("addressLocality") or address.get("addressRegion")
                description = BeautifulSoup(item.get("description") or "", "lxml").get_text(" ", strip=True)
                source_id = item.get("identifier")
                if isinstance(source_id, dict):
                    source_id = source_id.get("value")
                jobs.append(
                    RawJob(
                        source=self.context.source,
                        source_type="workday",
                        company=(item.get("hiringOrganization") or {}).get("name", self.context.company),
                        source_id=str(source_id or ""),
                        title=title,
                        location_raw=location,
                        posted_date_raw=str(item.get("datePosted") or ""),
                        url_raw=url,
                        description_raw=description,
                        employment_type_raw=item.get("employmentType"),
                        raw_payload=item,
                        discovered_from=entrypoint,
                        fetched_at=datetime.utcnow(),
                    )
                )
            run.raw_found += len(jobs)
            if not jobs:
                run.adapter_status = "no_results"
            self._health.last_success_at = datetime.utcnow()
            return jobs
        except Exception as exc:
            run.error = str(exc)
            run.adapter_status = "parse_error"
            self._health.last_error = str(exc)
            raise
        finally:
            if close_client:
                client.close()

    def normalize(self, raw: RawJob) -> Optional[NormalizedJob]:
        return normalize_job(raw)

    def healthcheck(self) -> SourceHealth:
        return self._health

    def _fetch_api_jobs(self, client: httpx.Client, api_url: str, run: SourceRun) -> list[RawJob]:
        response = client.get(api_url)
        run.pages_fetched += 1
        if response.status_code >= 400:
            run.error = f"{response.status_code} from {api_url}"
            run.adapter_status = "request_error"
            return []
        payload = response.json()
        postings = payload.get("jobPostings") or payload.get("jobs") or []
        jobs: list[RawJob] = []
        for item in postings:
            title = (item.get("title") or "").strip()
            external_path = item.get("externalPath") or ""
            if not title or not external_path:
                continue
            base_url = api_url.split("/wday/")[0]
            job_url = canonicalize_url(f"{base_url}{external_path}")
            jobs.append(
                RawJob(
                    source=self.context.source,
                    source_type="workday",
                    company=self.context.company,
                    source_id=str(item.get("bulletFields", [{}])[0].get("id") or item.get("id") or ""),
                    title=title,
                    location_raw=item.get("locationsText") or item.get("location") or None,
                    posted_date_raw=str(item.get("postedOn") or item.get("postedDate") or ""),
                    url_raw=job_url,
                    description_raw=item.get("description") or "",
                    employment_type_raw=item.get("timeType") or None,
                    team_raw=item.get("jobFamily") or None,
                    raw_payload=item,
                    discovered_from=api_url,
                    fetched_at=datetime.utcnow(),
                )
            )
        return jobs


WorkdayJsonLdExtractor = WorkdayAdapter
