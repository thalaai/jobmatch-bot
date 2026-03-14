from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from ..core.extractors import extract_embedded_json, extract_jsonld_job_postings, extract_next_data
from ..core.interfaces import AdapterContext, BaseAdapter
from ..core.models import NormalizedJob, RawJob, SourceHealth, SourceRun
from ..core.normalization import canonicalize_url, normalize_job
from ..engine.utils import resilient_headers


class AppleJsonLdAdapter(BaseAdapter):
    name = "apple_jsonld"

    def __init__(self, context: AdapterContext):
        super().__init__(context)
        self._health = SourceHealth(company=context.company, source=context.source, adapter=self.name)

    def discover(self) -> list[str]:
        search_urls = self.context.metadata.get("search_urls")
        if search_urls:
            return search_urls
        return self.context.metadata.get("entry_urls", [self.context.entrypoint])

    def fetch_raw(self, entrypoint: str, run: SourceRun) -> list[RawJob]:
        client = self.context.client or httpx.Client(headers=resilient_headers(), follow_redirects=True, timeout=self.context.timeout_s)
        close_client = self.context.client is None
        try:
            response = client.get(entrypoint)
            run.pages_fetched += 1
            if response.status_code >= 400:
                run.error = f"{response.status_code} from {entrypoint}"
                run.adapter_status = "request_error"
                return []
            detail_urls = self._discover_detail_urls(entrypoint, response.text)
            if not detail_urls:
                detail_urls = [str(response.url)]
            jobs: list[RawJob] = []
            for detail_url in detail_urls[: int(self.context.metadata.get("max_detail_pages", 20))]:
                try:
                    detail_response = client.get(detail_url)
                    run.pages_fetched += 1
                    if detail_response.status_code >= 400:
                        continue
                except httpx.HTTPError:
                    continue
                for item in extract_jsonld_job_postings(detail_response.text, str(detail_response.url)):
                    title = (item.get("title") or "").strip()
                    url = canonicalize_url(item.get("url") or str(detail_response.url), str(detail_response.url))
                    if not title or not url:
                        continue
                    location = None
                    job_location = item.get("jobLocation")
                    if isinstance(job_location, dict):
                        address = job_location.get("address") or {}
                        location = address.get("addressLocality") or address.get("addressRegion")
                    source_id = item.get("identifier")
                    if isinstance(source_id, dict):
                        source_id = source_id.get("value")
                    jobs.append(
                        RawJob(
                            source=self.context.source,
                            source_type="apple_jsonld",
                            company=(item.get("hiringOrganization") or {}).get("name", self.context.company),
                            source_id=str(source_id or ""),
                            title=title,
                            location_raw=location,
                            posted_date_raw=str(item.get("datePosted") or ""),
                            url_raw=url,
                            description_raw=item.get("description") or "",
                            employment_type_raw=item.get("employmentType"),
                            raw_payload=item,
                            discovered_from=entrypoint,
                            fetched_at=datetime.utcnow(),
                        )
                    )
            run.raw_found += len(jobs)
            if not jobs:
                run.adapter_status = "no_results"
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

    def _discover_detail_urls(self, base_url: str, html: str) -> list[str]:
        detail_urls: set[str] = set()

        soup = BeautifulSoup(html, "lxml")
        for link in soup.select("a[href]"):
            href = (link.get("href") or "").strip()
            if "/en-us/details/" not in href:
                continue
            detail_urls.add(canonicalize_url(href, base_url))

        for match in re.findall(r"/en-us/details/[0-9A-Za-z\\-_/]+", html):
            detail_urls.add(canonicalize_url(match, base_url))

        next_data = extract_next_data(html)
        if next_data:
            self._collect_strings(next_data, detail_urls, base_url)

        for variable_name in ("__INITIAL_STATE__", "__PRELOADED_STATE__", "__APOLLO_STATE__"):
            payload = extract_embedded_json(html, variable_name)
            if payload:
                self._collect_strings(payload, detail_urls, base_url)

        return sorted(detail_urls)

    def _collect_strings(self, payload: object, detail_urls: set[str], base_url: str) -> None:
        if isinstance(payload, dict):
            for value in payload.values():
                self._collect_strings(value, detail_urls, base_url)
            return
        if isinstance(payload, list):
            for value in payload:
                self._collect_strings(value, detail_urls, base_url)
            return
        if isinstance(payload, str) and "/en-us/details/" in payload:
            detail_urls.add(canonicalize_url(payload, base_url))
