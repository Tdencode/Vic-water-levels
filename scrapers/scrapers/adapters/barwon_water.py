"""Barwon Water adapter.

Fetches the public ``waterstorage`` JSON web service that powers the storage
pages at ``/water-and-waste/water-storages/<region>``. Discovered by reading
the inline page bootstrap which references
``_webservices/json/waterstorage?region_name=<region>``.

Cloudflare WAF on this site fingerprints the TLS handshake (JA3 hash), not
just HTTP headers — Python's stdlib SSL gets blocked from datacentre IPs
(GitHub Actions runners) even with Chrome-shaped HTTP headers. Locally
from residential IPs the bare httpx client passes; from CI it 403s. We
use ``curl_cffi`` (libcurl-impersonate) to mimic Chrome's TLS fingerprint
for just this adapter — the other six adapters stay on httpx.

Four regions exist (Geelong, Colac, Lorne, Apollo Bay). At time of writing
the Apollo Bay endpoint returns a backend-error envelope (no reservoir data
published); the parser logs and skips that region.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from curl_cffi import requests as cffi_requests

from scrapers.base import BaseAdapter, Reading

API_BASE = "https://www.barwonwater.vic.gov.au/_webservices/json/waterstorage"
PAGE_BASE = "https://www.barwonwater.vic.gov.au/water-and-waste/water-storages"
COMPANY_SLUG = "barwon-water"
COMPANY_NAME = "Barwon Water"

REGIONS = ("geelong", "colac", "lorne", "apollo-bay")

_SLUG_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_NUMBER = re.compile(r"-?\d[\d,]*\.?\d*")
# "May, 09 2026 00:00:00" — note the comma after the month name.
_API_DATE_FORMAT = "%B, %d %Y %H:%M:%S"


def _slugify(name: str) -> str:
    return _SLUG_NON_ALNUM.sub("-", name.lower()).strip("-")


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value)
    m = _NUMBER.search(text)
    if not m:
        return None
    return float(m.group(0).replace(",", ""))


def _is_total_row(location: str) -> bool:
    # Each region's payload includes a roll-up row whose location ends with
    # " total" / " Total" (e.g. "Geelong total", "Colac Total"). Skip it.
    return location.strip().lower().endswith(" total")


def _extract_reading_date(payload: dict[str, Any]) -> date | None:
    """Use the latest entry of water_storage_levels as the measurement date.

    ``date_updated`` is the publish timestamp (typically today); the actual
    reading the site reports is yesterday's, which is the last entry in the
    daily series.
    """
    levels = payload.get("water_storage_levels")
    if isinstance(levels, list) and levels:
        last = levels[-1]
        date_str = last.get("date") if isinstance(last, dict) else None
        if isinstance(date_str, str):
            try:
                return datetime.strptime(date_str, _API_DATE_FORMAT).date()
            except ValueError:
                pass
    # Fallback: date_updated.
    updated = payload.get("date_updated")
    if isinstance(updated, str):
        try:
            return datetime.strptime(updated, _API_DATE_FORMAT).date()
        except ValueError:
            return None
    return None


def parse_region(payload: dict[str, Any], region: str) -> list[Reading]:
    """Pure parser for one region's JSON payload."""
    # Apollo Bay (and any region whose backend errors) returns an envelope
    # with `body`/`headers`/`info` keys instead of `reservoir_levels`.
    reservoirs = payload.get("reservoir_levels")
    if not isinstance(reservoirs, list) or not reservoirs:
        return []

    reading_date = _extract_reading_date(payload)
    if reading_date is None:
        return []

    source_url = f"{PAGE_BASE}/{region}"
    readings: list[Reading] = []
    for entry in reservoirs:
        if not isinstance(entry, dict):
            continue
        name = (entry.get("location") or "").strip()
        if not name or _is_total_row(name):
            continue
        readings.append(
            Reading(
                company_slug=COMPANY_SLUG,
                storage_name=name,
                storage_slug=_slugify(name),
                reading_date=reading_date,
                volume_ml=_to_float(entry.get("present_volume")),
                capacity_ml=_to_float(entry.get("total_capacity")),
                percent_full=_to_float(entry.get("percentage_full")),
                source_url=source_url,
            )
        )
    return readings


class BarwonWaterAdapter(BaseAdapter):
    company_slug = COMPANY_SLUG
    company_name = COMPANY_NAME
    source_url = PAGE_BASE

    # Try newer Chrome impersonation profiles first; fall back to older
    # ones if Cloudflare's fingerprint database has caught up to a profile.
    _IMPERSONATE_PROFILES = ("chrome131", "chrome124", "chrome120")

    def fetch(self) -> list[Reading]:
        # See module docstring for why this adapter doesn't use self._client.
        last_error: Exception | None = None
        for profile in self._IMPERSONATE_PROFILES:
            try:
                return self._fetch_with(profile)
            except Exception as exc:
                last_error = exc
                continue
        # Re-raise the final error so the runner records the adapter failure.
        if last_error is not None:
            raise last_error
        return []

    def _fetch_with(self, profile: str) -> list[Reading]:
        readings: list[Reading] = []
        with cffi_requests.Session(impersonate=profile) as session:
            # Warmup: hit the public storage page first. On some Cloudflare
            # configs this returns a cf_clearance cookie that the API
            # endpoint then accepts — even when a bare API call from the
            # same IP is rejected.
            try:
                session.get(f"{PAGE_BASE}/geelong", timeout=30)
            except Exception:
                # Warmup is best-effort; if the page itself blocks, the
                # API call below may still succeed (or fail with a
                # cleaner error we can act on).
                pass

            for region in REGIONS:
                response = session.get(
                    API_BASE,
                    params={"region_name": region},
                    headers={
                        "Accept": "application/json,*/*;q=0.8",
                        "Referer": f"{PAGE_BASE}/{region}",
                        "X-Requested-With": "XMLHttpRequest",
                    },
                    timeout=30,
                )
                response.raise_for_status()
                try:
                    payload = response.json()
                except ValueError:
                    continue
                readings.extend(parse_region(payload, region))
        return readings
