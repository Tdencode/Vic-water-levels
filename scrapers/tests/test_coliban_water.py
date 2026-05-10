"""Tests for the Coliban Water ASMX adapter."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from scrapers.adapters.coliban_water import (
    RESERVOIRS,
    parse_storage_response,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "coliban"


def _load_text(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def test_malmsbury_latest_reading() -> None:
    reading = parse_storage_response(
        _load_text("malmsbury.json"), "malmsbury-reservoir", "Malmsbury Reservoir"
    )
    assert reading is not None
    assert reading.company_slug == "coliban-water"
    assert reading.storage_name == "Malmsbury Reservoir"
    assert reading.storage_slug == "malmsbury-reservoir"
    assert reading.reading_date == date(2026, 5, 10)
    assert reading.volume_ml == 2574.0
    assert reading.capacity_ml == 11800.0
    assert reading.percent_full == 21.8
    assert reading.source_url.endswith("/malmsbury-reservoir/levels")


def test_eppalock_uses_last_volume_when_to_date_missing() -> None:
    # Eppalock updates less than daily — `waterStorageVolumes` is shorter
    # than the requested window. Adapter should report the last available
    # reading (2026-05-04, 15,689 ML) rather than failing or reporting a stale
    # `to` date.
    reading = parse_storage_response(
        _load_text("eppalock.json"), "lake-eppalock", "Lake Eppalock"
    )
    assert reading is not None
    assert reading.reading_date == date(2026, 5, 4)
    assert reading.volume_ml == 15689.0
    assert reading.capacity_ml == 54837.1458
    assert reading.percent_full == 29.0


def test_lauriston_decimal_handling() -> None:
    reading = parse_storage_response(
        _load_text("lauriston.json"), "lauriston-reservoir", "Lauriston Reservoir"
    )
    assert reading is not None
    assert reading.volume_ml == 16860.0
    assert reading.capacity_ml == 19790.0
    assert reading.percent_full == 85.2


def test_upper_coliban_decimal_volume() -> None:
    # Upper Coliban's latest reading carries a decimal volume (17543.8).
    reading = parse_storage_response(
        _load_text("upper_coliban.json"),
        "upper-coliban-reservoir",
        "Upper Coliban Reservoir",
    )
    assert reading is not None
    assert reading.volume_ml == 17543.8
    assert reading.capacity_ml == 37770.0


def test_error_envelope_returns_none() -> None:
    # 500-equivalent ASMX error response carries no `d` key.
    reading = parse_storage_response(
        _load_text("error.json"), "malmsbury-reservoir", "Malmsbury Reservoir"
    )
    assert reading is None


def test_handles_string_payload() -> None:
    # The adapter passes the parsed dict, but the helper accepts the raw
    # string body too — useful for direct fixture replay.
    reading = parse_storage_response(
        _load_text("malmsbury.json"), "malmsbury-reservoir", "Malmsbury Reservoir"
    )
    assert reading is not None


def test_returns_none_for_empty_volumes() -> None:
    body = {"d": '{"waterStorageVolumes":[],"waterStorageTotals":{}}'}
    assert (
        parse_storage_response(body, "lauriston-reservoir", "Lauriston Reservoir")
        is None
    )


def test_no_duplicate_storage_slugs() -> None:
    slugs = [slug for slug, _, _ in RESERVOIRS]
    assert len(slugs) == len(set(slugs))


def test_no_duplicate_api_params() -> None:
    # Two reservoirs sharing an api_param would silently report the same data.
    params = [param for _, _, param in RESERVOIRS]
    assert len(params) == len(set(params))


def test_upper_coliban_uses_space_param() -> None:
    # Documented quirk: Coliban's API expects "upper coliban" (with a space).
    # Sending the URL slug "upper-coliban" silently returns combined data.
    by_slug = {slug: param for slug, _, param in RESERVOIRS}
    assert by_slug["upper-coliban-reservoir"] == "upper coliban"
