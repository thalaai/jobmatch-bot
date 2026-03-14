from __future__ import annotations

import re

from .models import SourceType


PATTERN_MAP: list[tuple[SourceType, tuple[str, ...]]] = [
    ("greenhouse", ("greenhouse.io", "boards-api.greenhouse.io", "job-boards.greenhouse.io")),
    ("lever", ("jobs.lever.co", "api.lever.co")),
    ("workday", ("myworkdayjobs.com", "wd1.", "wd5.")),
    ("smartrecruiters", ("smartrecruiters.com",)),
    ("ashby", ("jobs.ashbyhq.com", "ashbyhq.com")),
    ("icims", ("icims.com",)),
    ("successfactors", ("successfactors.com", "career5.successfactors.eu")),
    ("taleo", ("taleo.net", "oraclecloud.com", "oraclecloudapps.com")),
    ("phenom", ("phenompeople.com", "phenom.com")),
]


def detect_source_type(url: str, html: str = "") -> SourceType:
    haystack = f"{url.lower()} {html.lower()}"
    for source_type, patterns in PATTERN_MAP:
        if any(pattern in haystack for pattern in patterns):
            return source_type
    if "__NEXT_DATA__" in html or re.search(r'"@type"\s*:\s*"JobPosting"', html):
        return "jsonld"
    return "unknown"

