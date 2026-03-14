from __future__ import annotations

from datetime import datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from ..core.interfaces import AdapterContext, BaseAdapter
from ..core.models import NormalizedJob, RawJob, SourceHealth, SourceRun
from ..core.normalization import normalize_job
from ..engine.utils import resilient_headers


class MicrosoftSearchAdapter(BaseAdapter):
    name = "microsoft_search"

    def __init__(self, context: AdapterContext):
        super().__init__(context)
        self._health = SourceHealth(company=context.company, source=context.source, adapter=self.name)

    def discover(self) -> list[str]:
        return [self.context.entrypoint]

    def fetch_raw(self, entrypoint: str, run: SourceRun) -> list[RawJob]:
        client = self.context.client or httpx.Client(headers=resilient_headers(), follow_redirects=True, timeout=self.context.timeout_s)
        close_client = self.context.client is None
        queries = self.context.metadata.get("queries") or [self.context.metadata.get("query", "program manager")]
        location = self.context.metadata.get("location", "United States")
        page_size = int(self.context.metadata.get("page_size", 20))
        jobs: list[RawJob] = []
        try:
            for query in queries:
                payload = None
                for params in self._param_variants(query, location, page_size):
                    response = client.get(entrypoint, params=params)
                    run.pages_fetched += 1
                    if response.status_code >= 500:
                        run.error = f"{response.status_code} from {entrypoint}"
                        run.adapter_status = "request_error"
                        continue
                    if response.status_code >= 400:
                        run.error = f"{response.status_code} from {entrypoint}"
                        run.adapter_status = "blocked" if response.status_code in (401, 403) else "request_error"
                        continue
                    payload = response.json()
                    break
                if payload is not None:
                    items = payload.get("operationResult", {}).get("result", {}).get("jobs") or payload.get("jobs") or payload.get("data") or []
                else:
                    items = self._fallback_html_jobs(client, query, run)
                for item in items:
                    url = (
                        item.get("url")
                        or item.get("applyUrl")
                        or item.get("jobApplyUrl")
                        or item.get("properties", {}).get("primaryURL")
                        or ""
                    ).strip()
                    title = (item.get("title") or item.get("jobTitle") or item.get("properties", {}).get("title") or "").strip()
                    if not url or not title:
                        continue
                    jobs.append(
                        RawJob(
                            source=self.context.source,
                            source_type="unknown",
                            company=self.context.company,
                            source_id=str(item.get("jobId") or item.get("id") or ""),
                            title=title,
                            location_raw=item.get("location") or item.get("primaryLocation") or item.get("properties", {}).get("location"),
                            posted_date_raw=str(item.get("postedDate") or item.get("postingDate") or ""),
                            url_raw=url,
                            description_raw=item.get("description") or item.get("summary") or "",
                            team_raw=item.get("businessFunction") or item.get("category") or None,
                            raw_payload=item,
                            discovered_from=f"{entrypoint}?q={query}",
                            fetched_at=datetime.utcnow(),
                        )
                    )
            run.raw_found += len(jobs)
            if not jobs and run.adapter_status == "working":
                run.adapter_status = "no_results"
            else:
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
        return normalize_job(raw)

    def healthcheck(self) -> SourceHealth:
        return self._health

    def _param_variants(self, query: str, location: str, page_size: int) -> list[dict[str, object]]:
        return [
            {"q": query, "lc": location, "l": "en_us", "pg": 1, "pgSz": page_size},
            {"q": query, "l": "en_us", "pg": 1, "pgSz": page_size},
            {"q": query, "pg": 1, "pgSz": page_size},
        ]

    def _fallback_html_jobs(self, client: httpx.Client, query: str, run: SourceRun) -> list[dict]:
        urls = self.context.metadata.get("fallback_urls", [])
        collected: list[dict] = []
        query_lower = query.lower()
        for url in urls:
            try:
                response = client.get(url)
                run.pages_fetched += 1
                if response.status_code >= 400:
                    continue
            except httpx.HTTPError:
                continue
            soup = BeautifulSoup(response.text, "lxml")
            text = soup.get_text("\n", strip=True)
            if query_lower not in text.lower() and "program manager" not in text.lower():
                continue
            for heading in soup.select("h2, h3, h4"):
                title = heading.get_text(" ", strip=True)
                if "program manager" not in title.lower() and "technical program manager" not in title.lower():
                    continue
                collected.append(
                    {
                        "title": title,
                        "location": url,
                        "url": url,
                        "description": text[:4000],
                        "id": f"html:{abs(hash((url, title)))}",
                    }
                )
        return collected
