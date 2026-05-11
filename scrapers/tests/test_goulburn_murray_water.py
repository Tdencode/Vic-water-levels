"""Tests for the G-MW Waterline adapter against saved HTML fixtures."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from scrapers.adapters.goulburn_murray_water import (
    IndexEntry,
    build_reading,
    parse_daily,
    parse_index,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "gmw"


def _load(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def test_index_extracts_all_26_storages() -> None:
    report_date, entries = parse_index(_load("status_index.shtml"))
    assert report_date == date(2026, 5, 11)
    assert len(entries) == 26


def test_index_basins_match_known_layout() -> None:
    _, entries = parse_index(_load("status_index.shtml"))
    by_basin: dict[str, int] = {}
    for e in entries:
        by_basin[e.basin] = by_basin.get(e.basin, 0) + 1
    # The 7 basins Waterline groups storages under, with the captured counts.
    assert by_basin == {
        "broken": 1,
        "campaspe": 1,
        "goulburn": 6,
        "loddon": 6,
        "murray": 7,
        "ovens": 2,
        "uppermurray": 3,
    }


def test_index_strips_head_gauge_suffix() -> None:
    _, entries = parse_index(_load("status_index.shtml"))
    by_id = {e.station_id: e for e in entries}
    assert by_id["G405258A"].name == "Lake Eildon"
    assert by_id["G406219A"].name == "Lake Eppalock"
    assert by_id["G405259A"].name == "Goulburn Weir"
    # "Res" abbreviation expanded.
    assert by_id["G407333A"].name == "Evansford Reservoir"
    # Parenthesised "Head Gauge" inside a name is preserved.
    assert by_id["G409216A"].name == "Yarrawonga Weir (Mulwala Head Gauge)"


def test_index_station_ids_are_unique() -> None:
    _, entries = parse_index(_load("status_index.shtml"))
    ids = [e.station_id for e in entries]
    assert len(ids) == len(set(ids))


def test_parse_daily_returns_latest_real_row() -> None:
    report_date = date(2026, 5, 11)
    parsed = parse_daily(_load("location_daily_G405259A.shtml"), report_date)
    assert parsed is not None
    reading_date, volume_ml, percent_full = parsed
    # Fixture's last real row is 11-05 at 24,707 ML / 96.9%; the 12-05 row
    # holds "-" placeholders and must be skipped.
    assert reading_date == date(2026, 5, 11)
    assert volume_ml == 24707.0
    assert percent_full == 96.9


def test_build_reading_goulburn_weir() -> None:
    entry = IndexEntry(basin="goulburn", station_id="G405259A", name="Goulburn Weir")
    reading = build_reading(
        entry, _load("location_daily_G405259A.shtml"), date(2026, 5, 11)
    )
    assert reading is not None
    assert reading.storage_slug == "g405259a"
    assert reading.storage_name == "Goulburn Weir"
    assert reading.company_slug == "goulburn-murray-water"
    assert reading.volume_ml == 24707.0
    assert reading.percent_full == 96.9
    # Capacity derived algebraically: 24,707 / 96.9 * 100 ≈ 25,497.42 ML.
    assert reading.capacity_ml is not None
    assert abs(reading.capacity_ml - 25497.42) < 0.5
    assert reading.source_url.startswith("https://waterline.g-mwater.com.au/")
    assert reading.source_url.endswith("/location_G405259A.shtml")


def test_build_reading_dartmouth() -> None:
    entry = IndexEntry(
        basin="uppermurray", station_id="G401224A", name="Dartmouth"
    )
    reading = build_reading(
        entry, _load("location_daily_G401224A.shtml"), date(2026, 5, 11)
    )
    assert reading is not None
    assert reading.storage_slug == "g401224a"
    # Dartmouth is the largest of the bunch — sanity-check that the volume
    # parser handled the comma-separated millions.
    assert reading.volume_ml is not None and reading.volume_ml > 2_000_000


def test_build_reading_eppalock_and_nillahcootie() -> None:
    """Cross-basin coverage check: one campaspe and one broken storage."""
    epp = build_reading(
        IndexEntry(basin="campaspe", station_id="G406219A", name="Lake Eppalock"),
        _load("location_daily_G406219A.shtml"),
        date(2026, 5, 11),
    )
    nill = build_reading(
        IndexEntry(basin="broken", station_id="G404218A", name="Lake Nillahcootie"),
        _load("location_daily_G404218A.shtml"),
        date(2026, 5, 11),
    )
    assert epp is not None and epp.storage_slug == "g406219a"
    assert nill is not None and nill.storage_slug == "g404218a"
