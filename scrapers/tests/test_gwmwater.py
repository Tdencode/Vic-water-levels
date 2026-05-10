"""Tests for the GWMWater adapter, against a saved HTML fixture."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from scrapers.adapters.gwmwater import _slugify, parse_reservoir_summary

FIXTURE = Path(__file__).parent / "fixtures" / "gwm_reservoir_summary.html"


def _load_fixture() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def test_parses_ten_reservoirs_excluding_total() -> None:
    readings = parse_reservoir_summary(_load_fixture())
    # 10 reservoirs in the fixture; the "Total supply" footer row must be skipped.
    assert len(readings) == 10
    assert all(r.storage_name != "Total supply" for r in readings)


def test_reading_date_from_updated_header() -> None:
    readings = parse_reservoir_summary(_load_fixture())
    assert {r.reading_date for r in readings} == {date(2026, 5, 6)}


def test_lake_bellfield_values() -> None:
    readings = parse_reservoir_summary(_load_fixture())
    by_slug = {r.storage_slug: r for r in readings}
    bellfield = by_slug["lake-bellfield"]
    assert bellfield.storage_name == "Lake Bellfield"
    assert bellfield.capacity_ml == 78_550
    assert bellfield.volume_ml == 51_040
    assert bellfield.percent_full == 65.0
    assert bellfield.company_slug == "gwmwater"


def test_green_lake_caret_stripped() -> None:
    # The fixture's row reads "Green Lake^" (excluded-from-total footnote).
    # The adapter must strip the caret so the slug is stable.
    readings = parse_reservoir_summary(_load_fixture())
    by_slug = {r.storage_slug: r for r in readings}
    assert "green-lake" in by_slug
    assert by_slug["green-lake"].storage_name == "Green Lake"


def test_mt_cole_present_despite_blank_fsl() -> None:
    # Mt Cole has an empty "Water level at FSL" cell — make sure it still parses.
    readings = parse_reservoir_summary(_load_fixture())
    by_slug = {r.storage_slug: r for r in readings}
    mt_cole = by_slug["mt-cole-reservoir"]
    assert mt_cole.capacity_ml == 801
    assert mt_cole.volume_ml == 600
    assert mt_cole.percent_full == 74.0


def test_no_duplicate_slugs() -> None:
    readings = parse_reservoir_summary(_load_fixture())
    slugs = [r.storage_slug for r in readings]
    assert len(slugs) == len(set(slugs))


def test_slugify_examples() -> None:
    assert _slugify("Lake Bellfield") == "lake-bellfield"
    assert _slugify("Mt Cole Reservoir") == "mt-cole-reservoir"
    assert _slugify("Moora Moora Reservoir") == "moora-moora-reservoir"
