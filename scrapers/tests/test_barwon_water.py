"""Tests for the Barwon Water adapter, against saved per-region JSON fixtures."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from unittest.mock import patch

from scrapers.adapters.barwon_water import (
    BarwonWaterAdapter,
    _is_total_row,
    _looks_like_cloudflare_block,
    _slugify,
    parse_region,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "barwon"


class _FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class _FakeHTTPError(Exception):
    def __init__(self, msg: str, status: int | None = None) -> None:
        super().__init__(msg)
        self.response = _FakeResponse(status) if status is not None else None


def test_looks_like_cloudflare_block_detects_status_codes() -> None:
    assert _looks_like_cloudflare_block(_FakeHTTPError("403 Forbidden", status=403))
    assert _looks_like_cloudflare_block(_FakeHTTPError("rate limited", status=429))
    assert _looks_like_cloudflare_block(_FakeHTTPError("auth", status=401))


def test_looks_like_cloudflare_block_detects_message_text() -> None:
    # Some curl_cffi errors stringify without a .response attribute.
    assert _looks_like_cloudflare_block(Exception("HTTP Error 403: "))
    assert _looks_like_cloudflare_block(Exception("Cloudflare challenge"))


def test_looks_like_cloudflare_block_ignores_other_errors() -> None:
    # Real failures (DNS, parse, etc.) must still propagate.
    assert not _looks_like_cloudflare_block(Exception("connection refused"))
    assert not _looks_like_cloudflare_block(_FakeHTTPError("server error", status=500))


def test_fetch_swallows_403_and_returns_empty() -> None:
    # When every impersonation profile returns 403, fetch() degrades to []
    # rather than raising — keeps the daily CI run green and leaves any
    # existing Barwon rows in Supabase as the most recent reading.
    adapter = BarwonWaterAdapter()
    with patch.object(
        adapter,
        "_fetch_with",
        side_effect=_FakeHTTPError("HTTP Error 403: Forbidden", status=403),
    ):
        assert adapter.fetch() == []


def test_fetch_propagates_non_cloudflare_errors() -> None:
    # A genuine bug (e.g. parser crash, DNS down) should still surface so we
    # notice it instead of silently writing zero readings forever.
    adapter = BarwonWaterAdapter()
    with patch.object(adapter, "_fetch_with", side_effect=ValueError("boom")):
        try:
            adapter.fetch()
        except ValueError as exc:
            assert "boom" in str(exc)
        else:
            raise AssertionError("expected ValueError to propagate")


def _load(region: str) -> dict:
    return json.loads((FIXTURE_DIR / f"{region}.json").read_text(encoding="utf-8"))


def test_geelong_six_reservoirs_total_row_skipped() -> None:
    readings = parse_region(_load("geelong"), "geelong")
    assert len(readings) == 6
    assert all(not r.storage_name.lower().endswith(" total") for r in readings)


def test_colac_four_reservoirs_total_row_skipped() -> None:
    readings = parse_region(_load("colac"), "colac")
    assert len(readings) == 4
    names = {r.storage_name for r in readings}
    assert "West Gellibrand Reservoir" in names
    assert "Colac Total" not in names


def test_lorne_single_reservoir() -> None:
    readings = parse_region(_load("lorne"), "lorne")
    assert len(readings) == 1
    assert readings[0].storage_name == "Allen Reservoir"


def test_apollo_bay_error_envelope_returns_empty() -> None:
    # Apollo Bay's backend currently returns an error envelope rather than
    # a reservoir payload. The adapter must skip the region cleanly.
    readings = parse_region(_load("apollo-bay"), "apollo-bay")
    assert readings == []


def test_reading_date_from_last_water_storage_levels() -> None:
    readings = parse_region(_load("geelong"), "geelong")
    # date_updated in fixture is May 10 (publish), but the latest measurement
    # in water_storage_levels is May 9 — that's what we want as the reading.
    assert {r.reading_date for r in readings} == {date(2026, 5, 9)}


def test_west_barwon_values() -> None:
    readings = parse_region(_load("geelong"), "geelong")
    by_slug = {r.storage_slug: r for r in readings}
    west_barwon = by_slug["west-barwon-reservoir"]
    assert west_barwon.volume_ml == 6076.0
    assert west_barwon.capacity_ml == 21504.0
    assert west_barwon.percent_full == 28.3
    assert west_barwon.company_slug == "barwon-water"


def test_lal_lal_share_in_name() -> None:
    # Lal Lal is shared with Central Highlands Water; Barwon's published row
    # makes that explicit in the location string. The adapter must keep that
    # information so we don't claim the whole reservoir as Barwon's.
    readings = parse_region(_load("geelong"), "geelong")
    by_slug = {r.storage_slug: r for r in readings}
    assert "lal-lal-reservoir-barwon-water-s-share" in by_slug
    assert "share" in by_slug["lal-lal-reservoir-barwon-water-s-share"].storage_name


def test_no_duplicate_slugs_within_region() -> None:
    for region in ["geelong", "colac", "lorne"]:
        readings = parse_region(_load(region), region)
        slugs = [r.storage_slug for r in readings]
        assert len(slugs) == len(set(slugs)), f"duplicate slug in {region}"


def test_source_url_includes_region() -> None:
    geelong = parse_region(_load("geelong"), "geelong")
    colac = parse_region(_load("colac"), "colac")
    assert all(r.source_url.endswith("/geelong") for r in geelong)
    assert all(r.source_url.endswith("/colac") for r in colac)


def test_is_total_row() -> None:
    assert _is_total_row("Geelong total")
    assert _is_total_row("Colac Total")
    assert not _is_total_row("West Barwon Reservoir")


def test_slugify_handles_punctuation() -> None:
    assert _slugify("Stony Creek Reservoirs") == "stony-creek-reservoirs"
    assert _slugify("No. 4 Basin, Colac") == "no-4-basin-colac"
