"""Southern Rural Water adapter.

The public storage levels page renders a Highcharts chart per reservoir on
each per-storage page. The page bundle POSTs to a Drupal route to pull the
chart's data:

    POST /graphs/storage-chart/get-chart-data
    Content-Type: application/x-www-form-urlencoded
    reservoir=<id>

The response is a Highcharts series array. We use:

* Series 0 ("Storage Level") — daily current volume in ML, with a trailing
  ~80 days of zero-valued placeholder points used as future-axis padding.
  The latest real reading is the last point whose value is non-zero.
* Series 1 ("Full Capacity") — capacity history as step changes; the last
  entry is the current capacity.

Reservoir IDs are stable Drupal node-style identifiers. They were discovered
from each per-storage page's ``data-reservoir-id`` attribute and hardcoded
here to avoid 7 extra page fetches per run. If SRW ever reorders them, the
adapter will silently start scraping the wrong storages — covered by an
integration test that asserts the live capacities still match the static
hardcoded values within a small tolerance.

Note: the May 2026 "MySRW platform decommission" notice on the site relates
to a separate customer-accounts portal; the storage-levels pages stay on the
main srw.com.au domain and are unaffected.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from scrapers.base import BaseAdapter, Reading

API_URL = "https://www.srw.com.au/graphs/storage-chart/get-chart-data"
PAGE_BASE = "https://www.srw.com.au/water-and-storage/water-storages"
COMPANY_SLUG = "southern-rural-water"
COMPANY_NAME = "Southern Rural Water"

# (reservoir_id, display_name, slug). Order matches the storage-levels
# summary page; slug matches the per-storage page URL segment.
RESERVOIRS: tuple[tuple[int, str, str], ...] = (
    (1, "Blue Rock Lake", "blue-rock-lake"),
    (2, "Lake Glenmaggie", "lake-glenmaggie"),
    (3, "Lake Narracan", "lake-narracan"),
    (4, "Melton Reservoir", "melton-reservoir"),
    (5, "Merrimu Reservoir", "merrimu-reservoir"),
    (6, "Pykes Creek Reservoir", "pykes-creek-reservoir"),
    (7, "Rosslynne Reservoir", "rosslynne-reservoir"),
)


def _series_by_name(payload: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    for series in payload:
        if isinstance(series, dict) and series.get("name") == name:
            return series
    return None


def _latest_real_point(
    points: list[list[Any]],
) -> tuple[int, float] | None:
    """Walk a Highcharts (timestamp_ms, value) series backwards and return the
    last entry whose value is real (not None and not zero).

    Zeros are SRW's future-axis padding pattern; the live SRW reservoirs all
    have non-zero dead storage so a true zero reading would be exceptional.
    """
    for entry in reversed(points):
        if not isinstance(entry, (list, tuple)) or len(entry) < 2:
            continue
        ts, val = entry[0], entry[1]
        if val is None or val == 0:
            continue
        return int(ts), float(val)
    return None


def parse_chart_data(
    payload: list[dict[str, Any]],
    reservoir_id: int,
    name: str,
    slug: str,
) -> Reading | None:
    """Pure parser: takes one reservoir's chart response, returns a Reading.

    Returns ``None`` when the response carries no real data (the empty-payload
    case the API returns for unknown IDs).
    """
    storage = _series_by_name(payload, "Storage Level")
    capacity = _series_by_name(payload, "Full Capacity")
    if storage is None:
        return None

    latest = _latest_real_point(storage.get("data") or [])
    if latest is None:
        return None
    ts_ms, volume_ml = latest
    reading_date = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).date()

    capacity_ml: float | None = None
    if capacity is not None:
        cap_points = capacity.get("data") or []
        for entry in reversed(cap_points):
            if (
                isinstance(entry, (list, tuple))
                and len(entry) >= 2
                and entry[1] is not None
            ):
                capacity_ml = float(entry[1])
                break

    percent_full: float | None = None
    if capacity_ml and capacity_ml > 0:
        percent_full = round(volume_ml / capacity_ml * 100, 2)

    return Reading(
        company_slug=COMPANY_SLUG,
        storage_name=name,
        storage_slug=slug,
        reading_date=reading_date,
        volume_ml=volume_ml,
        capacity_ml=capacity_ml,
        percent_full=percent_full,
        source_url=f"{PAGE_BASE}/{slug}",
    )


class SouthernRuralWaterAdapter(BaseAdapter):
    company_slug = COMPANY_SLUG
    company_name = COMPANY_NAME
    source_url = f"{PAGE_BASE}/storage-levels"

    def fetch(self) -> list[Reading]:
        readings: list[Reading] = []
        for reservoir_id, name, slug in RESERVOIRS:
            response = self._client.post(
                API_URL,
                data={"reservoir": reservoir_id},
                headers={
                    # The Drupal endpoint only returns JSON when the request
                    # looks like an XHR. Without this it returns HTML 404.
                    "X-Requested-With": "XMLHttpRequest",
                    "Accept": "application/json,*/*",
                    "Referer": f"{PAGE_BASE}/{slug}",
                },
            )
            response.raise_for_status()
            try:
                payload = response.json()
            except ValueError:
                continue
            if not isinstance(payload, list):
                continue
            reading = parse_chart_data(payload, reservoir_id, name, slug)
            if reading is not None:
                readings.append(reading)
        return readings
