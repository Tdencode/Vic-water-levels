"""Coliban Water adapter.

Each per-reservoir page (`/about-us/our-reservoirs/<slug>/levels`) renders a
chart that POSTs to a legacy ASP.NET ASMX service:

    POST https://webserver.coliban.com.au/ResLevelsService/webplace.asmx/WaterStorageLevels
    Content-Type: application/json; charset=utf-8
    {"to":"YYYY-MM-DD","from":"YYYY-MM-DD","reservoir":"<param>","granularity":"day"}

ASMX returns its envelope as a string-wrapped JSON value::

    {"d": "{\\"date\\":..., \\"waterStorageVolumes\\":[{...}], ...}"}

so we double-decode. Each `waterStorageVolumes` entry has
``waterStorageLevel`` (volume ML), ``percentageFull`` and ``date``. The
``waterStorageTotals.totalCapacity`` carries the reservoir's full capacity.

Quirks
------
* The ``reservoir`` parameter is a free-text name, not a URL slug — so
  ``upper coliban`` (with a space) instead of ``upper-coliban``. An unknown
  name silently returns the *combined* catchment numbers, which is a
  particularly nasty failure mode. The slug→param mapping is hardcoded and
  was discovered from each per-storage page's ``data-params`` attribute.
* A same-day ``from``/``to`` request returns HTTP 500 for Lake Eppalock
  (its readings update less frequently than daily). We always request a
  14-day window and read the last entry of ``waterStorageVolumes`` so we
  pick up the most recent reading whenever it landed.
* ``waterStorageTotals.currentCapacity`` is misleadingly named — it is the
  current *volume*, not the reservoir's capacity. The capacity lives in
  ``totalCapacity``. We read both from the per-reading entry to avoid that
  trap entirely.
* Coliban reports their share of Lake Eppalock (~55 GL) separately from
  Goulburn-Murray Water's reading on the full reservoir (~305 GL); both
  coexist under different ``company_slug`` / ``storage_slug`` keys.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any

from scrapers.base import BaseAdapter, Reading

API_URL = (
    "https://webserver.coliban.com.au/ResLevelsService/webplace.asmx/"
    "WaterStorageLevels"
)
PAGE_BASE = "https://coliban.com.au/about-us/our-reservoirs"
COMPANY_SLUG = "coliban-water"
COMPANY_NAME = "Coliban Water"

# (storage_slug, display_name, api_param). storage_slug matches the URL
# segment; api_param matches the chart's data-params attribute and is sent
# as the ``reservoir`` field in the POST body.
RESERVOIRS: tuple[tuple[str, str, str], ...] = (
    ("malmsbury-reservoir", "Malmsbury Reservoir", "malmsbury"),
    ("lauriston-reservoir", "Lauriston Reservoir", "lauriston"),
    ("upper-coliban-reservoir", "Upper Coliban Reservoir", "upper coliban"),
)


def parse_storage_response(
    body: dict[str, Any] | str,
    storage_slug: str,
    name: str,
) -> Reading | None:
    """Pure parser. Accepts the raw outer JSON dict or its serialised string.

    Returns ``None`` when the service responded with an ASMX error envelope or
    no readings landed in the requested window.
    """
    if isinstance(body, str):
        body = json.loads(body)
    if not isinstance(body, dict):
        return None
    # ASMX error envelope ({"Message": ..., "StackTrace": ...}) instead of {"d": "..."}.
    if "d" not in body:
        return None

    inner_raw = body["d"]
    inner = json.loads(inner_raw) if isinstance(inner_raw, str) else inner_raw
    if not isinstance(inner, dict):
        return None

    volumes = inner.get("waterStorageVolumes") or []
    if not volumes:
        return None
    latest = volumes[-1]

    try:
        volume_ml = float(latest["waterStorageLevel"])
    except (KeyError, TypeError, ValueError):
        return None
    try:
        reading_date = datetime.strptime(latest["date"], "%Y-%m-%d").date()
    except (KeyError, ValueError):
        return None

    capacity_ml: float | None = None
    totals = inner.get("waterStorageTotals") or {}
    try:
        capacity_ml = float(totals["totalCapacity"])
    except (KeyError, TypeError, ValueError):
        capacity_ml = None

    percent_full: float | None
    try:
        percent_full = round(float(latest["percentageFull"]), 2)
    except (KeyError, TypeError, ValueError):
        percent_full = (
            round(volume_ml / capacity_ml * 100, 2)
            if capacity_ml and capacity_ml > 0
            else None
        )

    return Reading(
        company_slug=COMPANY_SLUG,
        storage_name=name,
        storage_slug=storage_slug,
        reading_date=reading_date,
        volume_ml=volume_ml,
        capacity_ml=capacity_ml,
        percent_full=percent_full,
        source_url=f"{PAGE_BASE}/{storage_slug}/levels",
    )


class ColibanWaterAdapter(BaseAdapter):
    company_slug = COMPANY_SLUG
    company_name = COMPANY_NAME
    source_url = f"{PAGE_BASE}/reservoir-levels"

    # 14-day window covers Eppalock's slower update cadence while staying
    # small enough that the API responds in well under a second.
    LOOKBACK_DAYS = 14

    def fetch(self) -> list[Reading]:
        today = datetime.now(timezone.utc).date()
        start = today - timedelta(days=self.LOOKBACK_DAYS)
        readings: list[Reading] = []
        for storage_slug, name, api_param in RESERVOIRS:
            payload = {
                "to": today.isoformat(),
                "from": start.isoformat(),
                "reservoir": api_param,
                "granularity": "day",
            }
            response = self._client.post(
                API_URL,
                # Send as JSON body; ASMX requires content-type application/json.
                json=payload,
                headers={
                    "Content-Type": "application/json; charset=utf-8",
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": f"{PAGE_BASE}/{storage_slug}/levels",
                    "Origin": "https://coliban.com.au",
                },
            )
            if response.status_code >= 500:
                # Service returns 500 when the reservoir has no data in the
                # requested window — skip rather than abort the run.
                continue
            response.raise_for_status()
            try:
                body = response.json()
            except ValueError:
                continue
            reading = parse_storage_response(body, storage_slug, name)
            if reading is not None:
                readings.append(reading)
        return readings
