from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

import httpx

from ..core.interfaces import AdapterContext, BaseAdapter
from ..core.models import NormalizedJob, RawJob, SourceHealth, SourceRun
from ..core.normalization import normalize_job
from ..engine.utils import resilient_headers


class MetaGraphQLAdapter(BaseAdapter):
    name = "meta_graphql"

    def __init__(self, context: AdapterContext):
        super().__init__(context)
        self._health = SourceHealth(company=context.company, source=context.source, adapter=self.name)

    def discover(self) -> list[str]:
        return [self.context.entrypoint]

    def fetch_raw(self, entrypoint: str, run: SourceRun) -> list[RawJob]:
        client = self.context.client or httpx.Client(headers=resilient_headers(), follow_redirects=True, timeout=self.context.timeout_s)
        close_client = self.context.client is None
        doc_id = self.context.metadata.get("doc_id", "")
        variables = self.context.metadata.get("variables", {})
        queries = self.context.metadata.get("queries") or [None]
        jobs: list[RawJob] = []
        try:
            if not doc_id:
                run.error = "Missing doc_id"
                run.adapter_status = "unsupported"
                return []
            for query in queries:
                request_variables = dict(variables)
                if query:
                    request_variables["search"] = query
                response = client.post(entrypoint, data={"doc_id": doc_id, "variables": json.dumps(request_variables)})
                run.pages_fetched += 1
                if response.status_code >= 400:
                    run.error = f"{response.status_code} from {entrypoint}"
                    run.adapter_status = "blocked" if response.status_code in (401, 403) else "request_error"
                    continue
                payload = response.json()
                items = payload.get("data", {}).get("job_search", {}).get("results", [])
                for item in items:
                    job_id = str(item.get("id") or "")
                    url = item.get("url") or f"https://www.metacareers.com/jobs/{job_id}/"
                    title = (item.get("title") or "").strip()
                    if not title or not url:
                        continue
                    jobs.append(
                        RawJob(
                            source=self.context.source,
                            source_type="unknown",
                            company=self.context.company,
                            source_id=job_id,
                            title=title,
                            location_raw=item.get("location"),
                            posted_date_raw=str(item.get("posted_date") or ""),
                            url_raw=url,
                            description_raw=item.get("description") or "",
                            raw_payload=item,
                            discovered_from=f"{entrypoint}:{query or 'default'}",
                            fetched_at=datetime.utcnow(),
                        )
                    )
            run.raw_found += len(jobs)
            if not jobs and run.adapter_status == "working":
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

