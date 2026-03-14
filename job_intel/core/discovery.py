from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from ..engine.utils import resilient_headers


COMMON_CAREER_PATHS = ["/careers", "/jobs", "/careers/jobs", "/join-us", "/careers/search"]


@dataclass
class DiscoveryResult:
    url: str
    status_code: int
    ats_hints: list[str]


def probe_career_pages(domain: str, client: httpx.Client | None = None) -> list[DiscoveryResult]:
    base = f"https://{domain.strip('/')}"
    session = client or httpx.Client(headers=resilient_headers(), follow_redirects=True, timeout=15.0)
    results: list[DiscoveryResult] = []
    own_client = client is None
    try:
        for path in COMMON_CAREER_PATHS:
            url = urljoin(base, path)
            try:
                response = session.get(url)
            except httpx.HTTPError:
                continue
            if response.status_code >= 400:
                continue
            hints = inspect_ats_hints(response.text)
            results.append(DiscoveryResult(url=str(response.url), status_code=response.status_code, ats_hints=hints))
    finally:
        if own_client:
            session.close()
    return results


def inspect_ats_hints(html: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    blob = soup.get_text(" ", strip=True).lower()
    hints: list[str] = []
    for marker in ("greenhouse", "lever", "workday", "smartrecruiters", "ashby", "icims", "successfactors", "taleo", "phenom"):
        if marker in blob or marker in html.lower():
            hints.append(marker)
    return hints


def extract_outbound_links(html: str, base_url: str) -> Iterable[str]:
    soup = BeautifulSoup(html, "lxml")
    for link in soup.select("a[href]"):
        href = link.get("href")
        if not href:
            continue
        yield urljoin(base_url, href)

