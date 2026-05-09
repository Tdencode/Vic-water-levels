"""Melbourne Water adapter.

Calls the public JSON API behind the official storage levels page:
    GET https://api.melbournewater.com.au/water-storage/levels/day?searchDate=YYYY-MM-DD

The response carries an authoritative ``date`` field (which can lag the
requested date by 1–3 days) and an array of catchment-level readings under
``waterStorageLevels.catchmentStorageLevels.catchments``. Each catchment is one
of Melbourne's 10 major reservoirs.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from typing import Any

from scrapers.base import BaseAdapter, Reading

API_BASE = "https://api.melbournewater.com.au/water-storage"
PUBLIC_PAGE_URL = "https://www.melbournewater.com.au/water-and-environment/water-management/water-storage-levels"
COMPANY_SLUG = "melbourne-water"
COMPANY_NAME = "Melbourne Water"

_SLUG_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _slugify(name: str) -> str:
    return _SLUG_NON_ALNUM.sub("-", name.lower()).strip("-")


def parse_levels_day(payload: dict[str, Any]) -> list[Reading]:
    """Pure parser: takes the JSON payload from /levels/day, returns Readings."""
    reading_date = datetime.strptime(payload["date"], "%Y-%m-%d").date()
    catchments = (
        payload.get("waterStorageLevels", {})
        .get("catchmentStorageLevels", {})
        .get("catchments", [])
    )
    readings: list[Reading] = []
    for c in catchments:
        name = c.get("name")
        if not name:
            continue
        readings.append(
            Reading(
                company_slug=COMPANY_SLUG,
                storage_name=name,
                storage_slug=_slugify(name),
                reading_date=reading_date,
                volume_ml=c.get("currentCapacity"),
                capacity_ml=c.get("totalCapacity"),
                percent_full=c.get("percentageFull"),
                source_url=PUBLIC_PAGE_URL,
            )
        )
    return readings


class MelbourneWaterAdapter(BaseAdapter):
    company_slug = COMPANY_SLUG
    company_name = COMPANY_NAME
    source_url = PUBLIC_PAGE_URL

    def fetch(self) -> list[Reading]:
        # The API returns the most recent published reading; passing today's
        # date is the same query the official page makes. If today's data
        # isn't yet available, the API echoes the previous available date.
        today = date.today()
        response = self._client.get(
            f"{API_BASE}/levels/day",
            params={"searchDate": today.isoformat()},
        )
        response.raise_for_status()
        return parse_levels_day(response.json())
