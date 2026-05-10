"""Adapter interface and shared dataclasses for water company scrapers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date

import httpx


@dataclass(frozen=True)
class Reading:
    """A single storage reading scraped from a water company source."""

    company_slug: str
    storage_name: str
    storage_slug: str
    reading_date: date
    volume_ml: float | None
    capacity_ml: float | None
    percent_full: float | None
    source_url: str


class BaseAdapter(ABC):
    """Subclass per water company. Implement :meth:`fetch`."""

    company_slug: str
    company_name: str
    source_url: str

    def __init__(self, client: httpx.Client | None = None) -> None:
        # Some targets (notably Barwon Water) sit behind Cloudflare bot
        # protection that returns a JS challenge unless the request looks like
        # a real browser. Sending a Chrome-shaped header set is enough to pass.
        self._client = client or httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            http2=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,"
                    "application/json;q=0.9,*/*;q=0.8"
                ),
                "Accept-Language": "en-AU,en;q=0.9",
                "Sec-Ch-Ua": (
                    '"Chromium";v="124", "Google Chrome";v="124", '
                    '"Not-A.Brand";v="99"'
                ),
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Linux"',
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
            },
        )

    @abstractmethod
    def fetch(self) -> list[Reading]:
        """Return all current storage readings for this company."""
