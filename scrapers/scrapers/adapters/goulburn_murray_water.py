"""Goulburn-Murray Water adapter.

Parses the static storage-levels table at
https://www.g-mwater.com.au/water-operations/storage-levels.

The page renders one ``<table id="...Data">`` per region (Murray, Ovens,
Broken, Goulburn, Campaspe, Loddon, Bullarook Creek). Each row begins with a
``<th>`` containing the storage name (linked to a per-storage detail page
whose final URL segment is a stable slug), followed by ``<td>`` columns:
percentage, current volume (ML), level, capacity (ML), and others we ignore.

The page-level ``Last Updated: dd/mm/yyyy`` field is used as the reading date.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from selectolax.parser import HTMLParser, Node

from scrapers.base import BaseAdapter, Reading

SOURCE_URL = "https://www.g-mwater.com.au/water-operations/storage-levels"
COMPANY_SLUG = "goulburn-murray-water"
COMPANY_NAME = "Goulburn-Murray Water"

_DATE_RE = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")


def _parse_number(text: str) -> float | None:
    """Parse a numeric cell, tolerating commas, whitespace, and empty values."""
    cleaned = text.strip().replace(",", "")
    if not cleaned or cleaned.lower() in {"n/a", "-", "—"}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _slug_from_href(href: str) -> str | None:
    """Slug is the final path segment of the per-storage detail link."""
    if not href:
        return None
    parts = [p for p in href.rstrip("/").split("/") if p]
    return parts[-1] if parts else None


def _extract_reading_date(tree: HTMLParser) -> date:
    node = tree.css_first(".lastUpdated .value")
    if node is None:
        raise ValueError("G-MW: could not find .lastUpdated .value on page")
    match = _DATE_RE.search(node.text())
    if match is None:
        raise ValueError(f"G-MW: unparseable last-updated value: {node.text()!r}")
    day, month, year = match.groups()
    return datetime.strptime(f"{year}-{month}-{day}", "%Y-%m-%d").date()


def _row_to_reading(row: Node, reading_date: date) -> Reading | None:
    name_anchor = row.css_first("th a")
    if name_anchor is None:
        return None
    storage_name = name_anchor.text(strip=True)
    storage_slug = _slug_from_href(name_anchor.attributes.get("href") or "")
    if not storage_name or not storage_slug:
        return None

    cells = row.css("td")
    # Column order: 0=%, 1=volume ML, 2=level, 3=capacity ML, 4+=others we ignore.
    if len(cells) < 4:
        return None
    percent_full = _parse_number(cells[0].text())
    volume_ml = _parse_number(cells[1].text())
    capacity_ml = _parse_number(cells[3].text())

    return Reading(
        company_slug=COMPANY_SLUG,
        storage_name=storage_name,
        storage_slug=storage_slug,
        reading_date=reading_date,
        volume_ml=volume_ml,
        capacity_ml=capacity_ml,
        percent_full=percent_full,
        source_url=SOURCE_URL,
    )


def parse_storage_levels(html: str) -> list[Reading]:
    """Pure parser: takes raw HTML, returns Readings. Used by tests and adapter."""
    tree = HTMLParser(html)
    reading_date = _extract_reading_date(tree)

    readings: list[Reading] = []
    seen_slugs: set[str] = set()
    for table in tree.css("table[id$='Data']"):
        for row in table.css("tbody tr.data"):
            reading = _row_to_reading(row, reading_date)
            if reading is None:
                continue
            # G-MW occasionally lists the same storage in multiple regions
            # (e.g. shared MDBA assets). Keep the first occurrence.
            if reading.storage_slug in seen_slugs:
                continue
            seen_slugs.add(reading.storage_slug)
            readings.append(reading)
    return readings


class GoulburnMurrayWaterAdapter(BaseAdapter):
    company_slug = COMPANY_SLUG
    company_name = COMPANY_NAME
    source_url = SOURCE_URL

    def fetch(self) -> list[Reading]:
        response = self._client.get(self.source_url)
        response.raise_for_status()
        return parse_storage_levels(response.text)
