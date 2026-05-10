"""Central Highlands Water adapter.

Parses the static HTML table on https://www.chw.net.au/community/water-storage-levels.
The page renders one ``<table class="chw-data-table">`` per "area" (Ballarat,
Maryborough, Daylesford, Regional). Switching areas is done with a ``?Area=N``
query string (N = 0..3). Each area's table is preceded by an ``<h3>`` naming
the area and a ``<div>CHW Reservoir Water Storages, as at DD MMM YYYY</div>``
giving the reading date.

CHW sits behind Cloudflare; the shared HTTP client in ``scrapers.base`` already
sends the Chrome-shaped header set required to pass the JS challenge.

Note on Lal Lal: the page lists three rows for it — "Lal Lal Reservoir (CHW)"
(CHW's 35,670 ML share), a Barwon share row published on Barwon's own site,
and "Lal Lal Reservoir (Total)" (the whole-reservoir aggregate). We keep only
the CHW share row to avoid double-counting against Barwon's adapter.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from selectolax.parser import HTMLParser, Node

from scrapers.base import BaseAdapter, Reading

PAGE_BASE = "https://www.chw.net.au/community/water-storage-levels"
COMPANY_SLUG = "central-highlands-water"
COMPANY_NAME = "Central Highlands Water"

AREA_IDS = (0, 1, 2, 3)

_SLUG_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_NUMBER = re.compile(r"-?\d[\d,]*\.?\d*")
_AS_AT = re.compile(r"as at\s+(\d{1,2}\s+\w+\s+\d{4})", re.IGNORECASE)
# Total rows end with the word "Total" (e.g. "Ballarat Total") or with
# "(Total)" as a parenthetical (e.g. "Lal Lal Reservoir (Total)").
_TOTAL_SUFFIX = re.compile(r"\bTotal\)?\s*$", re.IGNORECASE)


def _slugify(name: str) -> str:
    return _SLUG_NON_ALNUM.sub("-", name.lower()).strip("-")


def _to_float(text: str) -> float | None:
    m = _NUMBER.search(text)
    if not m:
        return None
    return float(m.group(0).replace(",", ""))


def _is_total_row(name: str) -> bool:
    return bool(_TOTAL_SUFFIX.search(name.strip()))


def _extract_reading_date(tree: HTMLParser) -> date:
    header = tree.css_first(".chw-water-storage-level-detail__header")
    if header is None:
        raise ValueError("CHW: could not find storage detail header")
    match = _AS_AT.search(header.text(separator=" ", strip=True))
    if not match:
        raise ValueError(
            f"CHW: 'as at DD MMM YYYY' not found in header: {header.text()!r}"
        )
    return datetime.strptime(match.group(1), "%d %B %Y").date()


def _row_cells(row: Node) -> list[str]:
    cells: list[str] = []
    for cell in row.css("td"):
        content = cell.css_first(".chw-data-table__body__cell__content")
        text_node = content if content is not None else cell
        cells.append(text_node.text(strip=True))
    return cells


def parse_area(html: str, area_id: int) -> list[Reading]:
    """Pure parser: takes one area's HTML page and returns Readings."""
    tree = HTMLParser(html)
    reading_date = _extract_reading_date(tree)
    source_url = f"{PAGE_BASE}?Area={area_id}"

    table = tree.css_first("table.chw-data-table")
    if table is None:
        # Some areas may legitimately render no table; treat as empty rather
        # than failing the whole adapter run.
        return []

    readings: list[Reading] = []
    for row in table.css("tbody.chw-data-table__body > tr"):
        cells = _row_cells(row)
        # Expected: name, capacity ML, current ML, current %, last year %.
        if len(cells) < 4:
            continue
        name = cells[0]
        if not name or _is_total_row(name):
            continue
        readings.append(
            Reading(
                company_slug=COMPANY_SLUG,
                storage_name=name,
                storage_slug=_slugify(name),
                reading_date=reading_date,
                volume_ml=_to_float(cells[2]),
                capacity_ml=_to_float(cells[1]),
                percent_full=_to_float(cells[3]),
                source_url=source_url,
            )
        )
    return readings


class CentralHighlandsWaterAdapter(BaseAdapter):
    company_slug = COMPANY_SLUG
    company_name = COMPANY_NAME
    source_url = PAGE_BASE

    def fetch(self) -> list[Reading]:
        readings: list[Reading] = []
        seen: set[str] = set()
        for area_id in AREA_IDS:
            response = self._client.get(PAGE_BASE, params={"Area": area_id})
            response.raise_for_status()
            for reading in parse_area(response.text, area_id):
                # Defensive de-dupe in case CHW ever lists a reservoir under
                # multiple areas (the published pages don't today).
                if reading.storage_slug in seen:
                    continue
                seen.add(reading.storage_slug)
                readings.append(reading)
        return readings
