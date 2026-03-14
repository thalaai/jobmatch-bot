from __future__ import annotations

from datetime import datetime
from typing import Optional

import httpx

from ..core.interfaces import AdapterContext, BaseAdapter
from ..core.models import NormalizedJob, RawJob, SourceHealth, SourceRun
from ..core.normalization import normalize_job
from ..engine.utils import resilient_headers


class AmazonJsonAdapter(BaseAdapter):
    name = "amazon_json"

    def __init__(self, context: AdapterContext):
        super().__init__(context)
        self._health = SourceHealth(company=context.company, source=context.source, adapter=self.name)

    def discover(self) -> list[str]:
        return [self.context.entrypoint]

    def fetch_raw(self, entrypoint: str, run: SourceRun) -> list[RawJob]:
        client = self.context.client or httpx.Client(headers=resilient_headers(), follow_redirects=True, timeout=self.context.timeout_s)
        close_client = self.context.client is None
        queries = self.context.metadata.get("queries", ["technical program manager", "program manager"])
        page_size = int(self.context.metadata.get("page_size", 100))
        jobs: list[RawJob] = []
        try:
            for query in queries:
                params = {"offset": 0, "result_limit": page_size, "sort": "relevant", "base_query": query}
                response = client.get(entrypoint, params=params)
                run.pages_fetched += 1
                if response.status_code >= 400:
                    run.error = f"{response.status_code} from {entrypoint}"
                    run.adapter_status = "request_error"
                    continue
                payload = response.json()
                items = payload.get("jobs") or payload.get("search_job_cards") or []
                for item in items:
                    title = (item.get("title") or item.get("title_text") or "").strip()
                    raw_url = (item.get("url") or item.get("url_next_step") or "").strip()
                    if not title or not raw_url:
                        continue
                    if raw_url.startswith("http://") or raw_url.startswith("https://"):
                        url = raw_url
                    else:
                        if not raw_url.startswith("/"):
                            raw_url = "/" + raw_url
                        url = "https://www.amazon.jobs" + raw_url
                    location = item.get("location") or ", ".join(item.get("locations", []) or [])
                    description = item.get("description") or item.get("description_short") or ""
                    jobs.append(
                        RawJob(
                            source=self.context.source,
                            source_type="amazon_json",
                            company=self.context.company,
                            source_id=str(item.get("id") or item.get("job_path") or ""),
                            title=title,
                            location_raw=location,
                            posted_date_raw=str(item.get("posted_date") or item.get("updated_time") or ""),
                            url_raw=url,
                            description_raw=description,
                            team_raw=item.get("business_category") or None,
                            raw_payload=item,
                            discovered_from=f"{entrypoint}?base_query={query}",
                            fetched_at=datetime.utcnow(),
                        )
                    )
            run.raw_found += len(jobs)
            if not jobs:
                run.adapter_status = "no_results"
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

