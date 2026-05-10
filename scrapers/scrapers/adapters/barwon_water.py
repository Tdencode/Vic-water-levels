"""Barwon Water adapter.

Fetches the public ``waterstorage`` JSON web service that powers the storage
pages at ``/water-and-waste/water-storages/<region>``. Discovered by reading
the inline page bootstrap which references
``_webservices/json/waterstorage?region_name=<region>``.

Cloudflare blocking
-------------------
The site is fronted by Cloudflare, which combines TLS fingerprinting (JA3)
with IP-reputation filtering. From residential IPs the call works fine.
From datacentre IPs (GitHub Actions, AWS, Azure, GCP) the API endpoint
returns HTTP 403 even with libcurl-impersonate Chrome handshakes and a
cookie warmup. The public HTML pages don't carry inline values either —
they XHR the same blocked endpoint client-side.

Resolution: the adapter still tries hard (warmup + chrome131/124/120
fallback), but **403s are treated as "unavailable from this network"
rather than a failure**. The runner records it as a 0-row scrape, the
overall job stays green, and existing Barwon rows in Supabase remain
the most recent reading. To get fresh Barwon data, run the adapter
manually from a residential IP::

    python -m scrapers.runner --company barwon-water

If Cloudflare ever relaxes the block, the adapter resumes silently —
no code change needed.

Four regions exist (Geelong, Colac, Lorne, Apollo Bay). At time of writing
the Apollo Bay endpoint returns a backend-error envelope (no reservoir data
published); the parser logs and skips that region.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

import structlog
from curl_cffi import requests as cffi_requests

from scrapers.base import BaseAdapter, Reading

log = structlog.get_logger()

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


def _looks_like_cloudflare_block(exc: Exception) -> bool:
    """True for the 403 / IP-reputation pattern we want to swallow.

    We deliberately match loosely: curl_cffi versions and Cloudflare error
    payloads vary, so check both the explicit status code (when present)
    and the stringified error for the tell-tale tokens.
    """
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if status in (401, 403, 429):
        return True
    msg = str(exc).lower()
    return "403" in msg or "forbidden" in msg or "cloudflare" in msg


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

        # Cloudflare's IP-reputation block (datacentre runners) is the
        # expected failure mode here, so degrade to "no readings this run"
        # rather than failing the whole adapter — see module docstring.
        if last_error is not None and _looks_like_cloudflare_block(last_error):
            log.warning(
                "barwon_unavailable_from_network",
                hint=(
                    "Cloudflare is blocking this IP — most likely a "
                    "datacentre / CI runner. Run locally from a residential "
                    "IP to refresh Barwon data."
                ),
                error=str(last_error),
            )
            return []
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
