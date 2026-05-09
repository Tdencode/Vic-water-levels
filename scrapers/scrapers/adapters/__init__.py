"""Per-company scraper adapters. Populated as adapters are implemented."""

from scrapers.adapters.goulburn_murray_water import GoulburnMurrayWaterAdapter
from scrapers.adapters.melbourne_water import MelbourneWaterAdapter
from scrapers.base import BaseAdapter

ALL_ADAPTERS: list[type[BaseAdapter]] = [
    MelbourneWaterAdapter,
    GoulburnMurrayWaterAdapter,
]
