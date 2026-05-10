"""Tests for the Central Highlands Water adapter, against per-area HTML fixtures."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from scrapers.adapters.central_highlands_water import (
    _is_total_row,
    _slugify,
    parse_area,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "chw"


def _load(area_id: int) -> str:
    return (FIXTURE_DIR / f"area{area_id}.html").read_text(encoding="utf-8")


def test_ballarat_skips_total_rows() -> None:
    readings = parse_area(_load(0), 0)
    names = {r.storage_name for r in readings}
    # "Ballarat Total" and "Lal Lal Reservoir (Total)" must be filtered out.
    assert "Ballarat Total" not in names
    assert "Lal Lal Reservoir (Total)" not in names
    # CHW's own Lal Lal share must be retained.
    assert "Lal Lal Reservoir (CHW)" in names


def test_ballarat_count_is_ten() -> None:
    # Ballarat area: 1 region total + 1 Lal Lal total + 10 reservoirs = 12 rows.
    readings = parse_area(_load(0), 0)
    assert len(readings) == 10


def test_lal_lal_chw_values() -> None:
    readings = parse_area(_load(0), 0)
    by_slug = {r.storage_slug: r for r in readings}
    lal_lal = by_slug["lal-lal-reservoir-chw"]
    assert lal_lal.capacity_ml == 35670.0
    assert lal_lal.volume_ml == 17576.0
    assert lal_lal.percent_full == 49.0
    assert lal_lal.company_slug == "central-highlands-water"


def test_reading_date_from_as_at_header() -> None:
    readings = parse_area(_load(0), 0)
    assert {r.reading_date for r in readings} == {date(2026, 5, 5)}


def test_maryborough_count_excludes_total() -> None:
    # Area 1 fixture has 1 "Maryborough Total" + 4 reservoirs.
    readings = parse_area(_load(1), 1)
    assert len(readings) == 4
    assert {r.storage_name for r in readings} == {
        "Evansford Reservoir",
        "Talbot Reservoir",
        "Centenary Reservoir",
        "Tullaroop Reservoir",
    }


def test_daylesford_count() -> None:
    readings = parse_area(_load(2), 2)
    # 1 Daylesford Total + 3 reservoirs.
    assert len(readings) == 3


def test_regional_count() -> None:
    # Regional area has no roll-up row — 8 distinct reservoirs.
    readings = parse_area(_load(3), 3)
    assert len(readings) == 8


def test_source_url_includes_area_id() -> None:
    for area_id in (0, 1, 2, 3):
        readings = parse_area(_load(area_id), area_id)
        if not readings:
            continue
        assert all(
            r.source_url.endswith(f"?Area={area_id}") for r in readings
        ), f"area {area_id} source_url mismatch"


def test_total_row_detection() -> None:
    assert _is_total_row("Ballarat Total")
    assert _is_total_row("Maryborough Total")
    assert _is_total_row("Lal Lal Reservoir (Total)")
    assert not _is_total_row("Lal Lal Reservoir (CHW)")
    assert not _is_total_row("White Swan Reservoir")
    # Reservoirs whose names contain "Total" elsewhere wouldn't trigger the
    # suffix check; none exist on the live page today, but be explicit:
    assert not _is_total_row("Total Recall Reservoir")


def test_slugify_keeps_disambiguation_suffix() -> None:
    # The "(CHW)" annotation distinguishes CHW's Lal Lal share from Barwon
    # Water's row (which slugifies to "lal-lal-reservoir-barwon-water-s-share").
    assert _slugify("Lal Lal Reservoir (CHW)") == "lal-lal-reservoir-chw"


def test_no_duplicate_slugs_within_area() -> None:
    for area_id in (0, 1, 2, 3):
        readings = parse_area(_load(area_id), area_id)
        slugs = [r.storage_slug for r in readings]
        assert len(slugs) == len(set(slugs)), f"duplicate slug in area {area_id}"
