"""Tests for the Supabase persistence layer.

We mock the Supabase client because actually hitting Postgres in unit tests
would require network + credentials. The contract we lock down here is:

* The RPC name matches the SQL function (``upsert_reading``).
* Every parameter the SQL function expects is sent.
* A failure on one Reading is logged and counted but doesn't abort the batch.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

from scrapers.base import Reading
from scrapers.storage import RPC_NAME, persist_company_readings


def _make_reading(slug: str = "blue-rock-lake", volume: float = 153925.0) -> Reading:
    return Reading(
        company_slug="southern-rural-water",
        storage_name="Blue Rock Lake",
        storage_slug=slug,
        reading_date=date(2026, 5, 10),
        volume_ml=volume,
        capacity_ml=198280.0,
        percent_full=77.63,
        source_url="https://www.srw.com.au/water-and-storage/water-storages/blue-rock-lake",
    )


def _make_client() -> MagicMock:
    client = MagicMock()
    # client.rpc(...).execute() chain — return a fresh MagicMock each call
    client.rpc.return_value.execute.return_value = MagicMock(data=[{"id": 1}])
    return client


def test_persist_calls_upsert_reading_rpc_with_full_param_set() -> None:
    client = _make_client()
    reading = _make_reading()

    result = persist_company_readings(
        client,
        company_slug="southern-rural-water",
        company_name="Southern Rural Water",
        readings=[reading],
    )

    assert result.rows_inserted == 1
    assert result.rows_failed == 0
    client.rpc.assert_called_once()
    rpc_name, params = client.rpc.call_args.args
    assert rpc_name == RPC_NAME
    # Lock down the exact param set so a SQL signature change breaks the test.
    assert set(params) == {
        "p_company_slug",
        "p_company_name",
        "p_storage_slug",
        "p_storage_name",
        "p_source_url",
        "p_reading_date",
        "p_volume_ml",
        "p_capacity_ml",
        "p_percent_full",
    }
    assert params["p_company_slug"] == "southern-rural-water"
    assert params["p_company_name"] == "Southern Rural Water"
    assert params["p_storage_slug"] == "blue-rock-lake"
    # Dates serialise as ISO strings so PostgREST accepts them as DATE.
    assert params["p_reading_date"] == "2026-05-10"
    assert params["p_volume_ml"] == 153925.0
    assert params["p_capacity_ml"] == 198280.0
    assert params["p_percent_full"] == 77.63


def test_persist_writes_one_rpc_call_per_reading() -> None:
    client = _make_client()
    readings = [
        _make_reading(slug="blue-rock-lake"),
        _make_reading(slug="lake-glenmaggie", volume=91560.0),
        _make_reading(slug="lake-narracan", volume=5726.0),
    ]

    result = persist_company_readings(
        client,
        company_slug="southern-rural-water",
        company_name="Southern Rural Water",
        readings=readings,
    )

    assert result.rows_inserted == 3
    assert client.rpc.call_count == 3


def test_persist_continues_after_per_reading_failure() -> None:
    client = MagicMock()
    # Second call raises; first and third succeed.
    success = MagicMock()
    success.execute.return_value = MagicMock(data=[{"id": 1}])
    failing = MagicMock()
    failing.execute.side_effect = RuntimeError("503 service unavailable")
    client.rpc.side_effect = [success, failing, success]

    readings = [
        _make_reading(slug="blue-rock-lake"),
        _make_reading(slug="lake-glenmaggie"),
        _make_reading(slug="lake-narracan"),
    ]
    result = persist_company_readings(
        client,
        company_slug="southern-rural-water",
        company_name="Southern Rural Water",
        readings=readings,
    )

    assert result.rows_inserted == 2
    assert result.rows_failed == 1
    assert client.rpc.call_count == 3


def test_persist_handles_empty_reading_list() -> None:
    client = _make_client()
    result = persist_company_readings(
        client,
        company_slug="coliban-water",
        company_name="Coliban Water",
        readings=[],
    )
    assert result.rows_inserted == 0
    assert result.rows_failed == 0
    client.rpc.assert_not_called()


def test_persist_accepts_website_url_kwarg_for_runner_compat() -> None:
    # The runner still passes website_url. The storage layer accepts it for
    # forward-compatibility but doesn't store it yet.
    client = _make_client()
    persist_company_readings(
        client,
        company_slug="coliban-water",
        company_name="Coliban Water",
        website_url="https://coliban.com.au/about-us/our-reservoirs/reservoir-levels",
        readings=[_make_reading()],
    )
    client.rpc.assert_called_once()
