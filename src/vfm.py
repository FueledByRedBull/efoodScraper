import math
import re

from .config import SIZE_DIAMETERS
from .models import VFMMetrics


def pizza_area(diameter_cm: int) -> float:
    """Calculate pizza area from diameter."""
    return math.pi * (diameter_cm / 2) ** 2


def calculate_vfm(
    quantity: int,
    diameter_cm: int,
    price: float,
    rating: float | None = None,
) -> VFMMetrics:
    """Calculate VFM metrics for a deal."""
    if price <= 0:
        raise ValueError(f"Price must be positive, got {price}")

    single_area = pizza_area(diameter_cm)
    total_area = quantity * single_area
    rating_factor = (rating or 5.0) / 5.0  # Linear penalty
    area_per_euro = total_area / price
    vfm_index = area_per_euro * rating_factor

    return VFMMetrics(
        quantity=quantity,
        diameter_cm=diameter_cm,
        single_area_cm2=round(single_area, 2),
        total_area_cm2=round(total_area, 2),
        area_per_euro=round(area_per_euro, 2),
        rating_factor=round(rating_factor, 2),
        vfm_index=round(vfm_index, 2),
    )


def parse_diameter(text: str) -> int | None:
    """Extract diameter in cm from text like '36cm' or '36 cm'."""
    if match := re.search(r"(\d+)\s*cm", text, re.IGNORECASE):
        return int(match.group(1))
    return None


def estimate_diameter(size_name: str) -> int | None:
    """Estimate diameter from Greek size name."""
    lower = size_name.lower()
    for name, diameter in SIZE_DIAMETERS.items():
        if name in lower:
            return diameter
    return None


def parse_price(text: str) -> float | None:
    """Extract price from text like '18,00€' or '€18.00'."""
    cleaned = text.replace("€", "").replace(",", ".").strip()
    if match := re.search(r"(\d+\.?\d*)", cleaned):
        return float(match.group(1))
    return None
