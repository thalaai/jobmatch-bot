from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Optional
from urllib.parse import urlencode

import httpx
from bs4 import BeautifulSoup

from ..core.extractors import extract_embedded_json, extract_next_data
from ..core.interfaces import AdapterContext, BaseAdapter
from ..core.models import NormalizedJob, RawJob, SourceHealth, SourceRun
from ..core.normalization import canonicalize_url, normalize_job
from ..engine.utils import resilient_headers


class EightfoldAdapter(BaseAdapter):
    name = "eightfold"

    def __init__(self, context: AdapterContext):
        super().__init__(context)
        self._health = SourceHealth(company=context.company, source=context.source, adapter=self.name)

    def discover(self) -> list[str]:
        queries = self.context.metadata.get("queries", ["program manager"])
        base_url = self.context.entrypoint.rstrip("/")
        domain = self.context.metadata.get("domain", "")
        urls = []
        for query in queries:
            params = {"query": query, "sort_by": "relevance"}
            if domain:
                params["domain"] = domain
            urls.append(f"{base_url}?{urlencode(params)}")
        return urls

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

            links = self._extract_links(entrypoint, response.text)
            jobs: list[RawJob] = []
            for path in sorted(links):
                detail_url = canonicalize_url(path, self.context.entrypoint)
                try:
                    detail_response = client.get(detail_url)
                    run.pages_fetched += 1
                    if detail_response.status_code >= 400:
                        continue
                except httpx.HTTPError:
                    continue

                title = ""
                description = ""
                location = None

                match = re.search(r'"positionTitle"\s*:\s*"([^"]+)"', detail_response.text)
                if match:
                    title = match.group(1)
                desc_match = re.search(r'"jobDescription"\s*:\s*"([^"]+)"', detail_response.text)
                if desc_match:
                    description = desc_match.group(1)
                loc_match = re.search(r'"location"\s*:\s*"([^"]+)"', detail_response.text)
                if loc_match:
                    location = loc_match.group(1)

                if not title:
                    soup = BeautifulSoup(detail_response.text, "lxml")
                    heading = soup.find("h1")
                    if heading:
                        title = heading.get_text(" ", strip=True)
                    description = description or soup.get_text(" ", strip=True)

                if not title:
                    continue

                jobs.append(
                    RawJob(
                        source=self.context.source,
                        source_type="eightfold",
                        company=self.context.company,
                        source_id=path.split("/")[-1],
                        title=title,
                        location_raw=location,
                        posted_date_raw=None,
                        url_raw=detail_url,
                        description_raw=description,
                        raw_payload={"search_url": entrypoint},
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

    def _extract_links(self, base_url: str, html: str) -> set[str]:
        links = set(re.findall(r"/careers/job/\d+", html))
        links.update(re.findall(r"/jobs/\d+", html))
        links.update(re.findall(r"/job/\d+", html))

        next_data = extract_next_data(html)
        if next_data:
            self._collect_job_paths(next_data, links)

        for variable_name in ("__INITIAL_STATE__", "__PRELOADED_STATE__", "__APOLLO_STATE__"):
            payload = extract_embedded_json(html, variable_name)
            if payload:
                self._collect_job_paths(payload, links)

        return {canonicalize_url(link, base_url) for link in links}

    def _collect_job_paths(self, payload: object, links: set[str]) -> None:
        if isinstance(payload, dict):
            for value in payload.values():
                self._collect_job_paths(value, links)
            return
        if isinstance(payload, list):
            for value in payload:
                self._collect_job_paths(value, links)
            return
        if isinstance(payload, str):
            if "/careers/job/" in payload or "/jobs/" in payload or "/job/" in payload:
                links.add(payload)
