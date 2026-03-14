from __future__ import annotations

from datetime import datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from ..core.interfaces import AdapterContext, BaseAdapter
from ..core.models import NormalizedJob, RawJob, SourceHealth, SourceRun
from ..core.normalization import normalize_job
from ..engine.utils import resilient_headers


class LeverAdapter(BaseAdapter):
    name = "lever"

    def __init__(self, context: AdapterContext):
        super().__init__(context)
        self._health = SourceHealth(company=context.company, source=context.source, adapter=self.name)

    def discover(self) -> list[str]:
        slug = self.context.metadata["slug"]
        return [f"https://api.lever.co/v0/postings/{slug}?mode=json"]

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
            payload = response.json()
            jobs: list[RawJob] = []
            for item in payload:
                url = ((item.get("hostedUrl") or item.get("applyUrl") or "")).strip()
                title = (item.get("text") or "").strip()
                if not title or not url or not url.startswith("http"):
                    continue
                description = item.get("descriptionPlain") or ""
                if not description:
                    description = BeautifulSoup(item.get("description") or "", "lxml").get_text(" ", strip=True)
                jobs.append(
                    RawJob(
                        source=self.context.source,
                        source_type="lever",
                        company=self.context.company,
                        source_id=str(item.get("id") or ""),
                        title=title,
                        location_raw=((item.get("categories") or {}).get("location") or "").strip() or None,
                        posted_date_raw=str(item.get("createdAt") or ""),
                        url_raw=url,
                        description_raw=description,
                        employment_type_raw=((item.get("categories") or {}).get("commitment") or "").strip() or None,
                        team_raw=((item.get("categories") or {}).get("team") or "").strip() or None,
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
        return normalize_job(raw)

    def healthcheck(self) -> SourceHealth:
        return self._health

