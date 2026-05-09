"""Tests for the G-MW adapter, run against a saved HTML fixture."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from scrapers.adapters.goulburn_murray_water import parse_storage_levels

FIXTURE = Path(__file__).parent / "fixtures" / "gmw_storage_levels.html"


def _load_fixture() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def test_parses_at_least_twenty_storages() -> None:
    readings = parse_storage_levels(_load_fixture())
    assert len(readings) >= 20, f"expected >=20 storages, got {len(readings)}"


def test_reading_date_extracted_from_last_updated() -> None:
    readings = parse_storage_levels(_load_fixture())
    # Fixture was captured 2026-05-08; assert all rows share that reading date.
    assert {r.reading_date for r in readings} == {date(2026, 5, 8)}


def test_dartmouth_dam_values() -> None:
    readings = parse_storage_levels(_load_fixture())
    by_slug = {r.storage_slug: r for r in readings}

    dartmouth = by_slug["dartmouthdam"]
    assert dartmouth.storage_name == "Dartmouth Dam (Lake Dartmouth)"
    assert dartmouth.percent_full == 65.10
    assert dartmouth.volume_ml == 2510473.0
    assert dartmouth.capacity_ml == 3856232.0
    assert dartmouth.company_slug == "goulburn-murray-water"
    assert dartmouth.source_url.startswith("https://www.g-mwater.com.au/")


def test_eildon_present() -> None:
    readings = parse_storage_levels(_load_fixture())
    by_slug = {r.storage_slug: r for r in readings}
    assert "lakeeildon" in by_slug
    eildon = by_slug["lakeeildon"]
    assert eildon.capacity_ml is not None and eildon.capacity_ml > 3_000_000


def test_no_duplicate_slugs() -> None:
    readings = parse_storage_levels(_load_fixture())
    slugs = [r.storage_slug for r in readings]
    assert len(slugs) == len(set(slugs)), "duplicate storage slugs found"
