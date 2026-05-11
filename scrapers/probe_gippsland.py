"""Reconnaissance probe for Gippsland Water — run locally from a residential IP.

Background: gippswater.com.au is fronted by Akamai. From the sandbox /
CI environments we tried it returned 403 to plain curl, WebFetch, and
curl_cffi Chrome impersonation (chrome131/124/120). Hopefully it works
from a normal home network.

This script does two things:
  1. Tries the main water-supply page + a handful of plausible sub-paths
     and API guesses, using curl_cffi Chrome impersonation.
  2. For every page that returns HTTP 200, saves the response to
     ./gippsland-probe-out/ and prints quick clues about where the
     storage data might live (storage-volume tables, inline JSON
     bootstraps, XHR endpoints referenced in <script> tags).

Run with::

    cd scrapers
    uv run python probe_gippsland.py

Then attach the contents of ./gippsland-probe-out/ (or paste the printed
clues) so we can design the proper adapter.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    from curl_cffi import requests as cffi_requests
except ImportError:
    sys.exit(
        "curl_cffi not installed. From the scrapers/ dir run `uv sync` or "
        "`uv pip install -e '.[dev]'` first, then re-run this script."
    )


PAGES_TO_TRY: tuple[str, ...] = (
    # The page the user pointed us at.
    "https://www.gippswater.com.au/water-and-waste/our-services/water-supply",
    # Storage / dam pages that other Vic water corps expose under similar slugs.
    "https://www.gippswater.com.au/water-and-waste/water-storages",
    "https://www.gippswater.com.au/water-and-waste/water-supply/storage-levels",
    "https://www.gippswater.com.au/about-us/our-water-storages",
    "https://www.gippswater.com.au/our-water/water-storages",
    "https://www.gippswater.com.au/water-storage-levels",
    "https://www.gippswater.com.au/storage-levels",
    # News / outlook pages — sometimes carry the current Moondarra %-full.
    "https://www.gippswater.com.au/about-us/news-and-publications/water-outlook",
    # The site root — useful for discovering the actual nav structure.
    "https://www.gippswater.com.au/",
)

# Chrome impersonation profiles to try in order, newest first. If one passes
# Akamai's TLS fingerprint check the rest are skipped for that page.
PROFILES: tuple[str, ...] = ("chrome131", "chrome124", "chrome120")

OUT_DIR = Path("gippsland-probe-out")

# Patterns we look for in successful responses to hint at how the data is
# rendered. Bias toward Gippsland-specific storage names.
DATA_HINT_PATTERNS: tuple[tuple[str, str], ...] = (
    ("Moondarra mention", r"Moondarra"),
    ("Storage / reservoir keyword", r"storage|reservoir|capacity"),
    ("Percent-full pattern", r"\b\d{1,3}(?:\.\d+)?\s*%\s*full"),
    ("Inline data table", r"<table[^>]*>"),
    ("Inline JSON bootstrap", r"<script[^>]*>[^<]*\{[^<]*\}\s*</script>"),
    ("XHR / fetch in script", r"(?:fetch|XMLHttpRequest|axios|\$\.get)\s*\(['\"][^'\"]+['\"]"),
    ("data-* JSON URLs", r"data-(?:api-url|json-url|src-url)=['\"]([^'\"]+)['\"]"),
    ("iframe to other domain", r"<iframe[^>]*src=['\"](https?://[^'\"]+)['\"]"),
)


def fetch(url: str) -> tuple[str | None, int, str | None]:
    """Return ``(profile_used, status_code, body)`` for the first profile that
    successfully reaches *url*. ``body`` is None on hard failure.
    """
    last_status = 0
    for profile in PROFILES:
        try:
            with cffi_requests.Session(impersonate=profile) as session:
                # Light warmup on the root to pick up any cookies Akamai
                # wants to see on subsequent hits.
                try:
                    session.get(
                        "https://www.gippswater.com.au/",
                        timeout=20,
                        headers={"Accept-Language": "en-AU,en;q=0.9"},
                    )
                except Exception:
                    pass
                response = session.get(
                    url,
                    timeout=30,
                    headers={
                        "Accept": (
                            "text/html,application/xhtml+xml,"
                            "application/xml;q=0.9,*/*;q=0.8"
                        ),
                        "Accept-Language": "en-AU,en;q=0.9",
                        "Referer": "https://www.gippswater.com.au/",
                    },
                )
            last_status = response.status_code
            if response.status_code == 200:
                return profile, response.status_code, response.text
        except Exception as exc:
            print(f"    {profile}: {exc}")
            continue
    return None, last_status, None


def summarise_body(url: str, body: str) -> list[str]:
    """Return human-readable clues about where storage data might be in *body*."""
    notes: list[str] = []
    for label, pattern in DATA_HINT_PATTERNS:
        matches = re.findall(pattern, body, flags=re.IGNORECASE)
        if matches:
            sample = matches[0] if isinstance(matches[0], str) else matches[0]
            sample = str(sample)[:120]
            notes.append(f"{label}: {len(matches)} match(es); first = {sample!r}")
    if not notes:
        notes.append("No high-signal patterns matched — see saved HTML.")
    return notes


def slugify(url: str) -> str:
    s = re.sub(r"^https?://", "", url).rstrip("/")
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "root"


def main() -> int:
    OUT_DIR.mkdir(exist_ok=True)
    print(f"Saving successful responses to {OUT_DIR.resolve()}/\n")

    successes = 0
    for url in PAGES_TO_TRY:
        print(f"→ {url}")
        profile, status, body = fetch(url)
        if body is None:
            print(f"    blocked (last status {status})\n")
            continue
        successes += 1
        path = OUT_DIR / f"{slugify(url)}.html"
        path.write_text(body, encoding="utf-8")
        print(f"    HTTP {status} via {profile}, {len(body):,} bytes  →  {path}")
        for note in summarise_body(url, body):
            print(f"      • {note}")
        print()

    print(
        f"Done — {successes}/{len(PAGES_TO_TRY)} pages reachable."
        + (
            "\nNext step: share gippsland-probe-out/ (or the printed clues above) "
            "so we can design the real adapter."
            if successes
            else "\nAkamai is still blocking everything from this network. "
            "Try a phone hotspot or a different connection."
        )
    )
    return 0 if successes else 2


if __name__ == "__main__":
    raise SystemExit(main())
