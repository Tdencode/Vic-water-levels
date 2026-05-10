"""Tests for the Southern Rural Water adapter, against per-reservoir fixtures."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from scrapers.adapters.southern_rural_water import (
    RESERVOIRS,
    _latest_real_point,
    parse_chart_data,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "srw"


def _load(rid: int) -> list:
    return json.loads((FIXTURE_DIR / f"r{rid}.json").read_text(encoding="utf-8"))


def _load_empty() -> list:
    return json.loads((FIXTURE_DIR / "r8_empty.json").read_text(encoding="utf-8"))


def test_blue_rock_lake_latest_reading() -> None:
    reading = parse_chart_data(_load(1), 1, "Blue Rock Lake", "blue-rock-lake")
    assert reading is not None
    # Live data captured on 2026-05-10 had Blue Rock at ~153,925 ML / 198,280 ML cap.
    assert reading.storage_name == "Blue Rock Lake"
    assert reading.storage_slug == "blue-rock-lake"
    assert reading.company_slug == "southern-rural-water"
    assert reading.reading_date == date(2026, 5, 10)
    assert reading.volume_ml == 153925.0
    assert reading.capacity_ml == 198280.0
    assert reading.percent_full == 77.63


def test_skips_trailing_zero_padding() -> None:
    # SRW's chart series carries ~80 days of trailing zero-valued points as
    # future-axis padding. The parser must walk past them to the last real
    # reading rather than reporting a 0 ML / 0 % reservoir.
    reading = parse_chart_data(_load(1), 1, "Blue Rock Lake", "blue-rock-lake")
    assert reading is not None
    assert reading.volume_ml > 0
    assert reading.reading_date <= date(2026, 5, 31)


def test_all_seven_reservoirs_parse() -> None:
    for reservoir_id, name, slug in RESERVOIRS:
        reading = parse_chart_data(_load(reservoir_id), reservoir_id, name, slug)
        assert reading is not None, f"{name} produced no reading"
        assert reading.volume_ml is not None and reading.volume_ml > 0
        assert reading.capacity_ml is not None and reading.capacity_ml > 0
        assert reading.percent_full is not None
        assert 0 < reading.percent_full <= 200


def test_empty_payload_returns_none() -> None:
    # The endpoint returns the same envelope for unknown reservoir IDs:
    # series structures are present but every data array is empty.
    reading = parse_chart_data(
        _load_empty(), 8, "Phantom Reservoir", "phantom-reservoir"
    )
    assert reading is None


def test_latest_real_point_picks_last_nonzero() -> None:
    points = [
        [1746489600000, 100.0],
        [1746576000000, 110.0],
        [1746662400000, 0],  # padding
        [1746748800000, 0],
        [1746835200000, None],
    ]
    result = _latest_real_point(points)
    assert result == (1746576000000, 110.0)


def test_latest_real_point_returns_none_when_all_padding() -> None:
    assert _latest_real_point([]) is None
    assert _latest_real_point([[1, 0], [2, None], [3, 0]]) is None


def test_no_duplicate_slugs() -> None:
    slugs = [slug for _, _, slug in RESERVOIRS]
    assert len(slugs) == len(set(slugs))


def test_source_urls_per_storage() -> None:
    # Each reading should cite the per-storage page, not the summary.
    for reservoir_id, name, slug in RESERVOIRS:
        reading = parse_chart_data(_load(reservoir_id), reservoir_id, name, slug)
        assert reading is not None
        assert reading.source_url.endswith(f"/{slug}")
