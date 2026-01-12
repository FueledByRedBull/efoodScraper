from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class VFMMetrics:
    """Value For Money calculation results."""

    quantity: int
    diameter_cm: int
    single_area_cm2: float
    total_area_cm2: float
    area_per_euro: float
    rating_factor: float
    vfm_index: float


@dataclass
class Deal:
    """A pizza deal from a restaurant."""

    name: str
    quantity: int
    size_cm: int
    price: float
    vfm: VFMMetrics


@dataclass
class Restaurant:
    """A restaurant with its deals."""

    name: str
    url: str
    rating: float | None = None
    is_closed: bool = False
    deals: list[Deal] = field(default_factory=list)
    scraped_at: datetime = field(default_factory=lambda: datetime.now())


@dataclass
class ScrapeResult:
    """Complete scrape results."""

    restaurants: list[Restaurant]
    scraped_at: datetime = field(default_factory=lambda: datetime.now())
    total_deals: int = 0

    def __post_init__(self):
        self.total_deals = sum(len(r.deals) for r in self.restaurants)
