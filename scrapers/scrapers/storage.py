"""Supabase persistence for scraped Readings.

Idempotent upserts:
- ``water_companies`` keyed on ``slug``
- ``storages`` keyed on ``(company_id, slug)``
- ``readings`` keyed on ``(storage_id, reading_date)``

Capacity values from the source are written to ``storages.capacity_ml`` so they
stay current as published numbers change.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from supabase import Client, create_client

from scrapers.base import Reading


@dataclass
class WriteResult:
    rows_inserted: int
    rows_updated: int


def get_client() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


def upsert_company(
    client: Client, *, slug: str, name: str, website_url: str | None
) -> str:
    """Upsert a water_companies row and return its id."""
    payload: dict[str, Any] = {"slug": slug, "name": name}
    if website_url:
        payload["website_url"] = website_url
    result = (
        client.table("water_companies")
        .upsert(payload, on_conflict="slug")
        .execute()
    )
    return result.data[0]["id"]


def upsert_storages(
    client: Client, *, company_id: str, readings: list[Reading]
) -> dict[str, str]:
    """Upsert one row per unique storage and return ``{slug: storage_id}``."""
    seen: dict[str, dict[str, Any]] = {}
    for r in readings:
        if r.storage_slug in seen:
            continue
        seen[r.storage_slug] = {
            "company_id": company_id,
            "slug": r.storage_slug,
            "name": r.storage_name,
            "capacity_ml": r.capacity_ml,
        }
    if not seen:
        return {}
    result = (
        client.table("storages")
        .upsert(list(seen.values()), on_conflict="company_id,slug")
        .execute()
    )
    return {row["slug"]: row["id"] for row in result.data}


def upsert_readings(
    client: Client, *, storage_ids: dict[str, str], readings: list[Reading]
) -> WriteResult:
    """Upsert readings keyed on (storage_id, reading_date).

    Supabase doesn't return per-row "inserted vs updated" so we conservatively
    treat the whole batch as inserts; the unique constraint silently makes
    repeat-day runs no-ops at the DB level.
    """
    rows: list[dict[str, Any]] = []
    for r in readings:
        sid = storage_ids.get(r.storage_slug)
        if sid is None:
            continue
        rows.append(
            {
                "storage_id": sid,
                "reading_date": r.reading_date.isoformat(),
                "volume_ml": r.volume_ml,
                "percent_full": r.percent_full,
                "source_url": r.source_url,
            }
        )
    if not rows:
        return WriteResult(0, 0)
    (
        client.table("readings")
        .upsert(rows, on_conflict="storage_id,reading_date")
        .execute()
    )
    return WriteResult(rows_inserted=len(rows), rows_updated=0)


def start_scrape_run(client: Client, *, company_id: str) -> int:
    result = (
        client.table("scrape_runs")
        .insert({"company_id": company_id, "status": "running"})
        .execute()
    )
    return result.data[0]["id"]


def finish_scrape_run(
    client: Client,
    *,
    run_id: int,
    status: str,
    rows_inserted: int = 0,
    error_message: str | None = None,
) -> None:
    client.table("scrape_runs").update(
        {
            "status": status,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "rows_inserted": rows_inserted,
            "error_message": error_message,
        }
    ).eq("id", run_id).execute()


def persist_company_readings(
    client: Client,
    *,
    company_slug: str,
    company_name: str,
    website_url: str,
    readings: list[Reading],
) -> WriteResult:
    """Top-level: upsert company + storages + readings, log a scrape_run."""
    company_id = upsert_company(
        client, slug=company_slug, name=company_name, website_url=website_url
    )
    run_id = start_scrape_run(client, company_id=company_id)
    try:
        storage_ids = upsert_storages(
            client, company_id=company_id, readings=readings
        )
        result = upsert_readings(
            client, storage_ids=storage_ids, readings=readings
        )
    except Exception as exc:
        finish_scrape_run(
            client, run_id=run_id, status="failed", error_message=str(exc)
        )
        raise
    finish_scrape_run(
        client,
        run_id=run_id,
        status="success",
        rows_inserted=result.rows_inserted,
    )
    return result
