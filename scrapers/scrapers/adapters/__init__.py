"""Per-company scraper adapters. Populated as adapters are implemented."""

from scrapers.base import BaseAdapter

ALL_ADAPTERS: list[type[BaseAdapter]] = []
