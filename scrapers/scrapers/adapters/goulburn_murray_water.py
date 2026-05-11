"""Goulburn-Murray Water adapter (Waterline data source).

Sources live storage levels from G-MW's Waterline status site at
https://waterline.g-mwater.com.au/waterstatus/. This replaces the earlier
static-table source at ``www.g-mwater.com.au/water-operations/storage-levels``
— Waterline carries the same storages plus extras and exposes a clean per-
station daily table.

Two-step fetch
--------------
1. ``/SSR/status.shtml`` is the index. It hard-codes 26 storages across 7
   basins (broken, campaspe, goulburn, loddon, murray, ovens, uppermurray)
   via JS hooks::

      on_image_clicked('waterApp','./SSR/<basin>/storage/<id>//location_<id>.shtml')

   Each adjacent ``<img title="<NAME>: ...">`` carries the storage name.
   The page header includes a ``Time of Report: DD/MM/YYYY HH:MM AEST``
   stamp which gives us the year for the daily-table dates (the table
   column is ``DD-MM`` only).

2. For each ``(basin, station_id)`` we fetch
   ``/SSR/<basin>/storage/<id>//location_daily_<id>.shtml`` — a small
   ``<table id="tableStyle7">`` with rows ``Date/Time | Observed Level (m)
   | Calculated Volume (ML) | Percentage full (%)``. The table runs ~30 days
   and ends with placeholder ``-`` rows for future days; the latest real
   row is the current reading.

Capacity is not in the daily table; we derive ``volume / percent * 100``
when the percent is non-zero — algebraically identical to what the page
would report.

Storage slugs use the raw Waterline station code (e.g. ``g405259a``,
``g10132``). These differ from the old adapter's slugs (``dartmouthdam`` etc.)
— old rows remain in Supabase as historical records; new readings flow into
new rows under the station-ID slugs.
"""

from __future__ import annotations

import re
from datetime import date
from typing import NamedTuple

from selectolax.parser import HTMLParser

from scrapers.base import BaseAdapter, Reading

WATERLINE_BASE = "https://waterline.g-mwater.com.au/waterstatus"
SOURCE_URL = f"{WATERLINE_BASE}/SSR/status.shtml"
COMPANY_SLUG = "goulburn-murray-water"
COMPANY_NAME = "Goulburn-Murray Water"

_INDEX_ROW_RE = re.compile(
    r"on_image_clicked\('waterApp','\./SSR/(?P<basin>[^/]+)/storage/"
    r"(?P<station>[^/]+)//location_[^']+\.shtml'\)\"\s*>\s*<img[^>]*"
    r"title=\"(?P<title>[^\"]+)\""
)
_REPORT_TIME_RE = re.compile(r"Time of Report:.*?(\d{2})/(\d{2})/(\d{4})", re.DOTALL)
_TRAILING_HEAD_GAUGE_RE = re.compile(r"\s+Head Gauge$")
_TABLE_DATE_RE = re.compile(r"^(\d{2})-(\d{2})\b")


class IndexEntry(NamedTuple):
    basin: str
    station_id: str
    name: str


def _parse_number(text: str) -> float | None:
    cleaned = text.strip().replace(",", "")
    if not cleaned or cleaned in {"-", "n/a", "—"}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _clean_storage_name(title: str) -> str:
    # Title format: "<NAME>: 1 hr rainfall total" — the suffix after the
    # colon is the icon's hover text, not part of the storage name.
    name = title.split(":", 1)[0].strip()
    # "Lake Eppalock Head Gauge" → "Lake Eppalock". Only strip when it's
    # the trailing token so "Yarrawonga Weir (Mulwala Head Gauge)" survives.
    name = _TRAILING_HEAD_GAUGE_RE.sub("", name).strip()
    if name.endswith(" Res"):
        name = name[:-4] + " Reservoir"
    return name


def parse_index(html: str) -> tuple[date, list[IndexEntry]]:
    """Return ``(report_date, [storage_entries])`` from ``status.shtml``."""
    m = _REPORT_TIME_RE.search(html)
    if not m:
        raise ValueError("G-MW Waterline: could not find 'Time of Report' stamp")
    day, month, year = m.groups()
    report_date = date(int(year), int(month), int(day))

    seen: set[str] = set()
    entries: list[IndexEntry] = []
    for match in _INDEX_ROW_RE.finditer(html):
        sid = match.group("station")
        if sid in seen:
            continue
        seen.add(sid)
        entries.append(
            IndexEntry(
                basin=match.group("basin"),
                station_id=sid,
                name=_clean_storage_name(match.group("title")),
            )
        )
    return report_date, entries


def parse_daily(
    html: str, report_date: date
) -> tuple[date, float | None, float | None] | None:
    """Return ``(reading_date, volume_ml, percent_full)`` for the latest real row.

    Returns ``None`` if the table has no parseable data row (e.g. the station
    page is empty). The trailing ``-`` placeholder rows the page leaves for
    future days are skipped.
    """
    tree = HTMLParser(html)
    rows = tree.css("table#tableStyle7 tr")
    latest: tuple[date, float | None, float | None] | None = None
    for row in rows:
        cells = row.css("td")
        if len(cells) < 4:
            continue
        m = _TABLE_DATE_RE.match(cells[0].text(strip=True))
        if not m:
            continue
        volume_ml = _parse_number(cells[2].text())
        percent_full = _parse_number(cells[3].text())
        if volume_ml is None and percent_full is None:
            continue
        day, month = int(m.group(1)), int(m.group(2))
        # Daily series rows span ~30 days and can cross a year boundary
        # (Dec→Jan). Pick the year that keeps the row on or before the
        # report date.
        reading_date = date(report_date.year, month, day)
        if reading_date > report_date:
            reading_date = date(report_date.year - 1, month, day)
        latest = (reading_date, volume_ml, percent_full)
    return latest


def build_reading(
    entry: IndexEntry, daily_html: str, report_date: date
) -> Reading | None:
    parsed = parse_daily(daily_html, report_date)
    if parsed is None:
        return None
    reading_date, volume_ml, percent_full = parsed
    capacity_ml: float | None = None
    if volume_ml is not None and percent_full is not None and percent_full > 0:
        capacity_ml = round(volume_ml / percent_full * 100.0, 2)
    storage_url = (
        f"{WATERLINE_BASE}/SSR/{entry.basin}/storage/{entry.station_id}/"
        f"/location_{entry.station_id}.shtml"
    )
    return Reading(
        company_slug=COMPANY_SLUG,
        storage_name=entry.name,
        storage_slug=entry.station_id.lower(),
        reading_date=reading_date,
        volume_ml=volume_ml,
        capacity_ml=capacity_ml,
        percent_full=percent_full,
        source_url=storage_url,
    )


def _daily_url(entry: IndexEntry) -> str:
    return (
        f"{WATERLINE_BASE}/SSR/{entry.basin}/storage/{entry.station_id}/"
        f"/location_daily_{entry.station_id}.shtml"
    )


class GoulburnMurrayWaterAdapter(BaseAdapter):
    company_slug = COMPANY_SLUG
    company_name = COMPANY_NAME
    source_url = SOURCE_URL

    def fetch(self) -> list[Reading]:
        index_response = self._client.get(self.source_url)
        index_response.raise_for_status()
        report_date, entries = parse_index(index_response.text)

        readings: list[Reading] = []
        for entry in entries:
            response = self._client.get(_daily_url(entry))
            if response.status_code != 200:
                continue
            reading = build_reading(entry, response.text, report_date)
            if reading is not None:
                readings.append(reading)
        return readings
