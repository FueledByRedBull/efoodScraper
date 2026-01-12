"""
Parser for e-food.gr catalog JSON files.
Extracts pizza deals and calculates VFM metrics.
"""
import json
import logging
import re
from pathlib import Path
from dataclasses import dataclass

from .config import SIZE_DIAMETERS
from .models import Deal, VFMMetrics
from . import vfm

logger = logging.getLogger("efood.parser")


@dataclass
class ParsedDeal:
    """A deal extracted from catalog JSON."""
    title: str
    price: float | None
    quantity: int
    size_name: str | None
    size_cm: int | None
    category_name: str | None


def extract_size_from_text(text: str) -> str | None:
    """Extract size name from text (γίγας, οικογενειακή, etc.)."""
    lower = text.lower()

    if "γίγας" in lower or "γιγας" in lower:
        return "γίγας"
    if "οικογενειακ" in lower:
        return "οικογενειακή"
    if "μεγάλ" in lower:
        return "μεγάλη"
    if "κανονικ" in lower:
        return "κανονική"
    if "μικρ" in lower:
        return "μικρή"

    return None


def extract_quantity_from_title(title: str) -> int:
    """Extract pizza quantity from title like '2 Πίτσες' or '3 Πίτσες'."""
    # Match patterns like "2 Πίτσες", "3 Πίτσες", "1 Πίτσα"
    match = re.search(r"(\d+)\s*[Ππ]ίτσ", title)
    if match:
        return int(match.group(1))
    return 1


def discover_store_sizes(categories: list) -> dict[str, int]:
    """
    Scan the catalog to discover actual sizes for this store.
    Returns a mapping of keywords to cm (e.g. {'οικογενειακή': 30, 'γίγας': 40}).
    
    Scans:
    1. Main menu categories (e.g. "Πίτσες οικογενειακές")
    2. Offer tier item category_names (e.g. "Πίτσες οικογενειακές (30cm) προσφοράς")
    """
    discovered_sizes = {}
    
    # Keywords to look for in size categories
    size_keywords = {
        "ατομικ": "μικρή",
        "κανονικ": "κανονική",
        "μεσαι": "μεσαία",
        "μεγαλ": "μεγάλη",
        "οικογενειακ": "οικογενειακή",
        "γιγας": "γίγας",
        "γίγας": "γίγας",
        "jumbo": "jumbo",
        "τετραγων": "jumbo" 
    }
    
    def extract_size_mapping(text: str):
        """Extract size keyword and cm from text like 'Πίτσες οικογενειακές (30cm)'"""
        text_lower = text.lower()
        size_cm = vfm.parse_diameter(text)
        if not size_cm:
            return
            
        for key, normalized in size_keywords.items():
            if key in text_lower:
                # Found both keyword and size!
                if normalized not in discovered_sizes:
                    discovered_sizes[normalized] = size_cm
                return

    for cat in categories:
        cat_name = cat.get("name", "").lower()
        cat_title = cat.get("title", "").lower()
        
        # 1. Check if category name/title itself has size info
        extract_size_mapping(cat.get("name", ""))
        extract_size_mapping(cat.get("title", ""))
        
        # 2. Scan items in category for description/title with sizes
        for item in cat.get("items", []):
            desc = item.get("description", "")
            title = item.get("title", "") or item.get("name", "")
            extract_size_mapping(desc)
            extract_size_mapping(title)
            
        # 3. KEY: Scan offers and their tier items' category_name
        # This is where "Πίτσες οικογενειακές (30cm) προσφοράς" lives
        for offer in cat.get("offers", []):
            for tier in offer.get("tiers", []):
                for item in tier.get("items", []):
                    item_cat_name = item.get("category_name", "")
                    extract_size_mapping(item_cat_name)
                    # Also check item description
                    extract_size_mapping(item.get("description", ""))

    if discovered_sizes:
        logger.debug(f"Discovered store-specific sizes: {discovered_sizes}")
        
    return discovered_sizes


def parse_catalog(catalog_path: str | Path) -> list[ParsedDeal]:
    """Parse a catalog JSON file and extract pizza deals."""
    path = Path(catalog_path)

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if data.get("status") != "ok":
        raise ValueError(f"Catalog status not ok: {data.get('status')}")

    menu = data.get("data", {}).get("menu", {})
    categories = menu.get("categories", [])
    
    # Pre-scan: Discover store-specific sizes
    store_size_map = discover_store_sizes(categories)

    deals = []

    for category in categories:
        # Check if category is likely an "Offers" category
        cat_title = category.get("title", "").lower()
        is_offer_cat = "προσφορές" in cat_title or "offers" in cat_title or "deals" in cat_title

        # 1. Process explicit offers (usually contained in special 'offers' array)
        for offer in category.get("offers", []):
            deal = _parse_offer(offer, store_size_map)
            if deal and deal.price and deal.price > 0:
                deals.append(deal)

        # 2. Process items in "Offers" categories, in case they are listed as items
        if is_offer_cat:
            for item in category.get("items", []):
                # Try to parse item as if it were an offer
                # (Items often share similar structure or can be adapted)
                deal = _parse_offer(item, store_size_map)
                if deal and deal.price and deal.price > 0:
                    deals.append(deal)

    return deals


def _parse_calculated_price(text: str | None) -> float | None:
    """Parse calculated_price like '22,00€' to float."""
    if not text:
        return None
    # Remove € and convert comma to dot
    cleaned = text.replace("€", "").replace(",", ".").strip()
    match = re.search(r"(\d+\.?\d*)", cleaned)
    if match:
        return float(match.group(1))
    return None


def _parse_offer(offer: dict, store_size_map: dict[str, int] = None) -> ParsedDeal | None:
    """Parse a single offer from the catalog."""
    store_size_map = store_size_map or {}
    title = offer.get("title", "")

    # Skip non-pizza offers
    if not re.search(r"[Ππ]ίτσ", title):
        return None

    # Priority: price > calculated_price > calculate from items
    price = offer.get("price")

    if price is None:
        price = _parse_calculated_price(offer.get("calculated_price"))

    size_name = None
    pizza_quantity = 0
    candidate_size_text = ""

    # Extract size and count pizza quantity from tiers
    tiers = offer.get("tiers", [])

    for tier in tiers:
        tier_qty = tier.get("quantity", 1)
        items = tier.get("items", [])

        if not items:
            continue

        # Check if this tier is pizza-related
        first_item = items[0]
        item_cat = first_item.get("category_name", "")

        is_pizza_tier = bool(
            re.search(r"[Ππ]ίτσ|[Γγ]ίγας|[Οο]ικογενειακ", item_cat)
        )

        if is_pizza_tier:
            pizza_quantity += tier_qty
            candidate_size_text = item_cat

            # Extract size from category name
            if not size_name:
                size_name = extract_size_from_text(item_cat)

    # Fallback: extract size from title if not found in tiers
    if not size_name:
        size_name = extract_size_from_text(title)

    # Fallback: extract quantity from title if no pizza tiers found
    if pizza_quantity == 0:
        pizza_quantity = extract_quantity_from_title(title)

    # Priority 0: Explicit size in Title overrides everything
    size_cm = None
    explicit_cm = vfm.parse_diameter(title)
    if explicit_cm:
        size_cm = explicit_cm
    
    # Priority 1: Check category_name of items in tiers (e.g. "Πίτσες οικογενειακές (30cm) προσφοράς")
    if not size_cm and candidate_size_text:
        size_cm = vfm.parse_diameter(candidate_size_text)
    
    # Priority 2: Check description because often Title is vague (e.g. "3 Πίτσες οικογενειακές της επιλογής σας")
    # but Description has "30cm."
    if not size_cm and tiers:
         for tier in tiers:
            if not tier.get("items"): continue
            first_item = tier["items"][0]
            desc = first_item.get("description", "")
            if desc:
                desc_cm = vfm.parse_diameter(desc)
                if desc_cm: 
                    size_cm = desc_cm
                    break

    # Priority 3: Store Specific Mapping found during pre-scan
    # (e.g. "Family" mapped to 33cm for this store)
    if not size_cm and size_name and size_name in store_size_map:
        size_cm = store_size_map[size_name]
        
    # Priority 4: Standard Name Mapping (Global Defaults)
    if not size_cm:
        size_cm = SIZE_DIAMETERS.get(size_name) if size_name else None

    return ParsedDeal(
        title=title,
        price=price,
        quantity=pizza_quantity if pizza_quantity > 0 else 1,
        size_name=size_name,
        size_cm=size_cm,
        category_name=str(offer.get("category_name", "")),
    )


def catalog_to_deals(
    catalog_path: str | Path,
    rating: float | None = None,
    size_overrides: dict[str, int] | None = None,
) -> list[Deal]:
    """
    Parse catalog and convert to Deal objects with VFM calculations.

    Args:
        catalog_path: Path to catalog JSON file
        rating: Restaurant rating (for VFM calculation)
        size_overrides: Optional dict mapping size names to cm for this restaurant

    Returns:
        List of Deal objects with VFM metrics
    """
    parsed = parse_catalog(catalog_path)

    deals = []
    for p in parsed:
        # Apply size overrides if provided
        size_cm = p.size_cm
        if size_overrides and p.size_name and p.size_name in size_overrides:
            size_cm = size_overrides[p.size_name]

        # Skip deals without size or price
        if not size_cm or not p.price:
            continue

        vfm_metrics = vfm.calculate_vfm(
            quantity=p.quantity,
            diameter_cm=size_cm,
            price=p.price,
            rating=rating,
        )

        deals.append(Deal(
            name=p.title,
            quantity=p.quantity,
            size_cm=size_cm,
            price=p.price,
            vfm=vfm_metrics,
        ))

    return deals


def print_parsed_deals(deals: list[ParsedDeal]) -> None:
    """Print parsed deals for debugging."""
    logger.info("=" * 60)
    logger.info(f"Parsed {len(deals)} pizza deals from catalog")
    logger.info("=" * 60)

    for deal in deals:
        size_info = f"{deal.size_name} ({deal.size_cm}cm)" if deal.size_cm else f"{deal.size_name or 'unknown'} (?cm)"
        price_info = f"{deal.price:.2f}EUR" if deal.price else "dynamic"
        logger.info(f"  {deal.quantity}x {size_info} @ {price_info}")
        logger.info(f"    Title: {deal.title}")


if __name__ == "__main__":
    # Test with sample catalog
    import sys

    if len(sys.argv) > 1:
        catalog_file = sys.argv[1]
    else:
        catalog_file = "catalog_7527410.json"

    logger.info(f"Parsing: {catalog_file}")
    parsed = parse_catalog(catalog_file)
    print_parsed_deals(parsed)

    logger.info("--- Converting to Deals with VFM (rating=4.5) ---")
    deals = catalog_to_deals(catalog_file, rating=4.5)

    for deal in sorted(deals, key=lambda d: d.vfm.vfm_index, reverse=True):
        logger.info(f"  VFM: {deal.vfm.vfm_index:6.2f} | {deal.quantity}x {deal.size_cm}cm @ {deal.price:.2f}EUR | {deal.name}")
