from __future__ import annotations

from .greenhouse import GreenhouseAdapter


class UberFreightGreenhouseAdapter(GreenhouseAdapter):
    """Uber Freight via Greenhouse board token."""

    name = "uberfreight_greenhouse"
