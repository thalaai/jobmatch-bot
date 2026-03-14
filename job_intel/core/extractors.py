from __future__ import annotations

import json
import re
from typing import Any

import extruct


def extract_jsonld_job_postings(html: str, base_url: str) -> list[dict[str, Any]]:
    data = extruct.extract(html, base_url=base_url, syntaxes=["json-ld"])
    found: list[dict[str, Any]] = []
    for item in data.get("json-ld", []):
        if isinstance(item, dict) and item.get("@type") == "JobPosting":
            found.append(item)
        elif isinstance(item, list):
            found.extend(sub for sub in item if isinstance(sub, dict) and sub.get("@type") == "JobPosting")
    return found


def extract_next_data(html: str) -> dict[str, Any] | None:
    match = re.search(r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def extract_embedded_json(html: str, variable_name: str) -> dict[str, Any] | None:
    pattern = rf"{re.escape(variable_name)}\s*=\s*(\{{.*?\}});"
    match = re.search(pattern, html, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None

