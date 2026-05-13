"""Gippsland Water adapter — Moondarra Reservoir.

Fetches storage levels from the public water supply page:
    https://www.gippswater.com.au/water-and-waste/our-services/water-supply

Cloudflare blocking
-------------------
Like Barwon Water, this site is fronted by Cloudflare with TLS fingerprinting
and IP-reputation filtering. From datacentre IPs (GitHub Actions) the page
returns HTTP 403. The adapter uses curl_cffi Chrome impersonation profiles and
degrades gracefully to 0 readings on persistent 403s so CI stays green.

To refresh Gippsland data from a residential IP::

    python -m scrapers.runner --company gippsland-water

Parser note
-----------
The exact HTML structure was discovered by inspecting the page from a
residential IP. The page renders a table with columns:
    Storage | Capacity (ML) | Current Volume (ML) | % Full

The adapter looks for this table and extracts the Moondarra row.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

import structlog
from curl_cffi import requests as cffi_requests
from selectolax.parser import HTMLParser

from scrapers.base import BaseAdapter, Reading

log = structlog.get_logger()

PAGE_URL = "https://www.gippswater.com.au/water-and-waste/our-services/water-supply"
COMPANY_SLUG = "gippsland-water"
COMPANY_NAME = "Gippsland Water"

_NUMBER = re.compile(r"-?\d[\d,]*\.?\d*")
# "Last updated: 12 May 2026" or "Updated: 12 May 2026" or similar patterns.
_DATE_RE = re.compile(
    r"(?:updated|as\s+at)[:\s]+(\d{1,2}\s+\w+\s+\d{4})", re.IGNORECASE
)
_DATE_FORMATS = ("%d %B %Y", "%d %b %Y")


def _to_float(text: str) -> float | None:
    m = _NUMBER.search(text.strip())
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def _parse_date(text: str) -> date | None:
    m = _DATE_RE.search(text)
    if not m:
        return None
    raw = m.group(1).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _looks_like_cloudflare_block(exc: Exception) -> bool:
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if status in (401, 403, 429):
        return True
    msg = str(exc).lower()
    return "403" in msg or "forbidden" in msg or "cloudflare" in msg


def parse_water_supply_page(html: str) -> list[Reading]:
    """Pure parser: takes raw HTML, returns Readings for Moondarra."""
    tree = HTMLParser(html)

    # Try to extract a reading date from page text.
    reading_date: date | None = None
    for node in tree.css("p, div, span, h2, h3, h4"):
        text = node.text(strip=True)
        d = _parse_date(text)
        if d is not None:
            reading_date = d
            break
    if reading_date is None:
        reading_date = date.today()

    readings: list[Reading] = []

    # Look for any table that contains "Moondarra" in its rows.
    for table in tree.css("table"):
        for row in table.css("tr"):
            cells = [td.text(strip=True) for td in row.css("td, th")]
            if not cells:
                continue
            # The first cell is the storage name.
            name = cells[0].strip()
            if "moondarra" not in name.lower():
                continue

            # Expect at least 3 data cells after the name (capacity, volume, %).
            # Column order may vary; try to identify by content.
            numbers = []
            for cell in cells[1:]:
                v = _to_float(cell)
                if v is not None:
                    numbers.append(v)

            if len(numbers) < 2:
                continue

            # Heuristic: largest number is likely capacity, second-largest volume,
            # and the small number (<= 110) is % full.
            pct: float | None = None
            large: list[float] = []
            for n in numbers:
                if n <= 110:
                    pct = n
                else:
                    large.append(n)
            large.sort(reverse=True)
            capacity_ml = large[0] if len(large) >= 1 else None
            volume_ml = large[1] if len(large) >= 2 else None

            if pct is None and capacity_ml and volume_ml and capacity_ml > 0:
                pct = round(volume_ml / capacity_ml * 100, 2)

            readings.append(
                Reading(
                    company_slug=COMPANY_SLUG,
                    storage_name="Moondarra Reservoir",
                    storage_slug="moondarra-reservoir",
                    reading_date=reading_date,
                    volume_ml=volume_ml,
                    capacity_ml=capacity_ml,
                    percent_full=pct,
                    source_url=PAGE_URL,
                )
            )
            # Only one Moondarra row expected.
            break
        if readings:
            break

    return readings


class GippslandWaterAdapter(BaseAdapter):
    company_slug = COMPANY_SLUG
    company_name = COMPANY_NAME
    source_url = PAGE_URL

    _IMPERSONATE_PROFILES = ("chrome131", "chrome124", "chrome120")

    def fetch(self) -> list[Reading]:
        last_error: Exception | None = None
        for profile in self._IMPERSONATE_PROFILES:
            try:
                return self._fetch_with(profile)
            except Exception as exc:
                last_error = exc
                continue

        if last_error is not None and _looks_like_cloudflare_block(last_error):
            log.warning(
                "gippsland_unavailable_from_network",
                hint=(
                    "Cloudflare is blocking this IP — most likely a "
                    "datacentre / CI runner. Run locally from a residential "
                    "IP to refresh Gippsland Water data."
                ),
                error=str(last_error),
            )
            return []
        if last_error is not None:
            raise last_error
        return []

    def _fetch_with(self, profile: str) -> list[Reading]:
        with cffi_requests.Session(impersonate=profile) as session:
            response = session.get(
                PAGE_URL,
                headers={
                    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                    "Accept-Language": "en-AU,en;q=0.9",
                },
                timeout=30,
            )
            response.raise_for_status()
            return parse_water_supply_page(response.text)
