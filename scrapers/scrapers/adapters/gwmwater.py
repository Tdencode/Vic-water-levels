"""Grampians Wimmera Mallee Water (GWMWater) adapter.

Parses the static HTML table on the Reservoir Level Summary page. The table
has class ``bwmtable`` (BWM = Bulk Water Manager, GWMWater's storage manager
role). The page is updated weekly on Wednesday afternoons covering Thursday
through Wednesday readings.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from selectolax.parser import HTMLParser, Node

from scrapers.base import BaseAdapter, Reading

PUBLIC_PAGE_URL = (
    "https://www.gwmwater.org.au/"
    "reservoir-levels-and-other-information/reservoirs-level-summary"
)
COMPANY_SLUG = "gwmwater"
COMPANY_NAME = "GWMWater"

_SLUG_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_NUMBER = re.compile(r"-?\d[\d,]*\.?\d*")
_UPDATED_AS_OF = re.compile(r"Updated as of\s+(\d{1,2}\s+\w+\s+\d{4})", re.IGNORECASE)


def _slugify(name: str) -> str:
    return _SLUG_NON_ALNUM.sub("-", name.lower()).strip("-")


def _to_int(text: str) -> int | None:
    m = _NUMBER.search(text)
    if not m:
        return None
    return int(float(m.group(0).replace(",", "")))


def _to_float(text: str) -> float | None:
    m = _NUMBER.search(text)
    if not m:
        return None
    return float(m.group(0).replace(",", ""))


def _is_total_row(row: Node) -> bool:
    # The "Total supply" footer row is the only one wrapping the name in <strong>.
    return row.css_first("strong") is not None


def parse_reservoir_summary(html: str) -> list[Reading]:
    tree = HTMLParser(html)

    updated_header = tree.css_first(".table_updated")
    if updated_header is None:
        raise ValueError("Could not find 'Updated as of' header on GWMWater page")
    match = _UPDATED_AS_OF.search(updated_header.text(strip=True))
    if not match:
        raise ValueError(
            f"Unrecognised updated-as-of text: {updated_header.text()!r}"
        )
    reading_date = datetime.strptime(match.group(1), "%d %B %Y").date()

    table = tree.css_first("table.bwmtable")
    if table is None:
        raise ValueError("Could not find table.bwmtable on GWMWater page")

    readings: list[Reading] = []
    for row in table.css("tbody > tr"):
        if _is_total_row(row):
            continue
        cells = row.css("td")
        # Expected columns: name, FSL height, capacity ML, current height,
        # current volume ML, percent, change, year-ago volume, year-ago %, graph.
        if len(cells) < 6:
            continue
        # Strip "^" suffix used to footnote reservoirs excluded from totals.
        name = cells[0].text(strip=True).rstrip("^").strip()
        if not name:
            continue
        capacity = _to_int(cells[2].text(strip=True))
        volume = _to_int(cells[4].text(strip=True))
        percent = _to_float(cells[5].text(strip=True))
        readings.append(
            Reading(
                company_slug=COMPANY_SLUG,
                storage_name=name,
                storage_slug=_slugify(name),
                reading_date=reading_date,
                volume_ml=volume,
                capacity_ml=capacity,
                percent_full=percent,
                source_url=PUBLIC_PAGE_URL,
            )
        )
    return readings


class GWMWaterAdapter(BaseAdapter):
    company_slug = COMPANY_SLUG
    company_name = COMPANY_NAME
    source_url = PUBLIC_PAGE_URL

    def fetch(self) -> list[Reading]:
        response = self._client.get(PUBLIC_PAGE_URL)
        response.raise_for_status()
        return parse_reservoir_summary(response.text)
