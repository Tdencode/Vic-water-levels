"""Supabase persistence for scraped Readings.

The schema lives in its own ``water_levels`` Postgres schema (see
``supabase/migrations/20260510000000_create_water_levels_schema.sql``)
and exposes a single ``upsert_reading(...)`` RPC that atomically upserts
the company, storage and reading rows. We call it once per Reading.

Why one RPC per row rather than a bulk insert:
* The RPC handles the company + storage upsert side-effects so the scraper
  doesn't have to track which storages already exist.
* At ~90 readings per daily run the round-trip cost is negligible (a few
  seconds total), and per-row failures don't block the rest of the batch.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import structlog
from supabase import Client, ClientOptions, create_client

from scrapers.base import Reading

log = structlog.get_logger()

SCHEMA = "water_levels"
RPC_NAME = "upsert_reading"


@dataclass
class WriteResult:
    rows_inserted: int
    rows_failed: int = 0


def get_client() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    # Pin the client to our schema so plain ``rpc()`` calls hit the right
    # PostgREST profile. Other apps in the same Supabase project keep
    # using ``public``.
    return create_client(url, key, options=ClientOptions(schema=SCHEMA))


def _rpc_params(*, company_slug: str, company_name: str, reading: Reading) -> dict:
    return {
        "p_company_slug": company_slug,
        "p_company_name": company_name,
        "p_storage_slug": reading.storage_slug,
        "p_storage_name": reading.storage_name,
        "p_source_url": reading.source_url,
        "p_reading_date": reading.reading_date.isoformat(),
        "p_volume_ml": reading.volume_ml,
        "p_capacity_ml": reading.capacity_ml,
        "p_percent_full": reading.percent_full,
    }


def persist_company_readings(
    client: Client,
    *,
    company_slug: str,
    company_name: str,
    website_url: str | None = None,  # accepted for runner compat; not yet stored
    readings: list[Reading],
) -> WriteResult:
    """Upsert every Reading for one company via the ``upsert_reading`` RPC.

    Per-row errors are logged and counted but don't abort the batch — a
    transient failure on one storage shouldn't lose the other six readings
    that came back in the same scrape.
    """
    del website_url  # reserved for a future companies.website upsert
    written = 0
    failed = 0
    for reading in readings:
        try:
            client.rpc(
                RPC_NAME,
                _rpc_params(
                    company_slug=company_slug,
                    company_name=company_name,
                    reading=reading,
                ),
            ).execute()
            written += 1
        except Exception as exc:
            failed += 1
            log.error(
                "reading_write_failed",
                company=company_slug,
                storage=reading.storage_slug,
                reading_date=reading.reading_date.isoformat(),
                error=str(exc),
            )
    return WriteResult(rows_inserted=written, rows_failed=failed)
