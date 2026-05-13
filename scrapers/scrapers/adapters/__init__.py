"""Per-company scraper adapters. Populated as adapters are implemented."""

from scrapers.adapters.barwon_water import BarwonWaterAdapter
from scrapers.adapters.central_highlands_water import CentralHighlandsWaterAdapter
from scrapers.adapters.coliban_water import ColibanWaterAdapter
from scrapers.adapters.gippsland_water import GippslandWaterAdapter
from scrapers.adapters.goulburn_murray_water import GoulburnMurrayWaterAdapter
from scrapers.adapters.gwmwater import GWMWaterAdapter
from scrapers.adapters.melbourne_water import MelbourneWaterAdapter
from scrapers.adapters.southern_rural_water import SouthernRuralWaterAdapter
from scrapers.base import BaseAdapter

ALL_ADAPTERS: list[type[BaseAdapter]] = [
    MelbourneWaterAdapter,
    GoulburnMurrayWaterAdapter,
    GWMWaterAdapter,
    BarwonWaterAdapter,
    CentralHighlandsWaterAdapter,
    SouthernRuralWaterAdapter,
    ColibanWaterAdapter,
    GippslandWaterAdapter,
]
