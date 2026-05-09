"""Tests for the Melbourne Water adapter, run against a saved JSON fixture."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from scrapers.adapters.melbourne_water import _slugify, parse_levels_day

FIXTURE = Path(__file__).parent / "fixtures" / "mw_levels_day.json"


def _load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_parses_ten_reservoirs() -> None:
    readings = parse_levels_day(_load_fixture())
    # Melbourne Water operates 10 major reservoirs.
    assert len(readings) == 10


def test_reading_date_from_payload() -> None:
    readings = parse_levels_day(_load_fixture())
    assert {r.reading_date for r in readings} == {date(2026, 5, 6)}


def test_thomson_values() -> None:
    readings = parse_levels_day(_load_fixture())
    by_slug = {r.storage_slug: r for r in readings}
    thomson = by_slug["thomson"]
    assert thomson.storage_name == "Thomson"
    assert thomson.percent_full == 66.5
    assert thomson.volume_ml == 710305
    assert thomson.capacity_ml == 1_068_000
    assert thomson.company_slug == "melbourne-water"


def test_oshannassy_apostrophe_slugified() -> None:
    readings = parse_levels_day(_load_fixture())
    slugs = {r.storage_slug for r in readings}
    # "O'Shannassy" must produce a stable, URL-safe slug.
    assert "o-shannassy" in slugs


def test_slugify_examples() -> None:
    assert _slugify("Thomson") == "thomson"
    assert _slugify("Upper Yarra") == "upper-yarra"
    assert _slugify("O'Shannassy") == "o-shannassy"
    assert _slugify("Yan Yean") == "yan-yean"


def test_no_duplicate_slugs() -> None:
    readings = parse_levels_day(_load_fixture())
    slugs = [r.storage_slug for r in readings]
    assert len(slugs) == len(set(slugs))
