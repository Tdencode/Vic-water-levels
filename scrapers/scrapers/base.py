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
        self._client = client or httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "vic-water-levels/0.1 (+https://github.com/tdencode/vic-water-levels)"
                ),
            },
        )

    @abstractmethod
    def fetch(self) -> list[Reading]:
        """Return all current storage readings for this company."""
