"""
E-food.gr API client for fetching restaurant catalogs.
"""
import json
import uuid
from pathlib import Path

import aiohttp

from .models import Deal, Restaurant
from .catalog_parser import catalog_to_deals


# API configuration
API_BASE = "https://api.e-food.gr/v3"
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "el",
    "Accept-Encoding": "gzip, deflate",
    "X-core-platform": "web",
    "X-core-version": "2.100.36",
    "X-core-theme": "default:light",
    "Origin": "https://www.e-food.gr",
    "Referer": "https://www.e-food.gr/",
}


def _generate_session_headers() -> dict:
    """Generate unique session headers for API requests."""
    session_id = str(uuid.uuid4())
    installation_id = str(uuid.uuid4())

    return {
        **DEFAULT_HEADERS,
        "X-core-session-id": session_id,
        "X-core-installation-id": installation_id,
    }


async def fetch_catalog(
    shop_id: int,
    latitude: float,
    longitude: float,
    save_path: str | Path | None = None,
) -> dict:
    """
    Fetch restaurant catalog from e-food API.

    Args:
        shop_id: Restaurant ID
        latitude: User latitude
        longitude: User longitude
        save_path: Optional path to save JSON response

    Returns:
        Catalog data as dict
    """
    url = f"{API_BASE}/shops/catalog"
    params = {
        "shop_id": shop_id,
        "version": 3,
        "latitude": latitude,
        "longitude": longitude,
        "category_slug": "",
    }

    headers = _generate_session_headers()

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers) as response:
            if response.status != 200:
                raise Exception(f"API error: {response.status}")

            data = await response.json()

            if save_path:
                path = Path(save_path)
                path.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

            return data


async def fetch_and_parse_deals(
    shop_id: int,
    latitude: float,
    longitude: float,
    rating: float | None = None,
    size_overrides: dict[str, int] | None = None,
    save_catalog: bool = False,
) -> list[Deal]:
    """
    Fetch catalog and parse pizza deals.

    Args:
        shop_id: Restaurant ID
        latitude: User latitude
        longitude: User longitude
        rating: Restaurant rating for VFM calculation
        size_overrides: Optional size name -> cm mapping
        save_catalog: Whether to save catalog JSON to file

    Returns:
        List of Deal objects with VFM metrics
    """
    save_path = f"catalog_{shop_id}.json" if save_catalog else None

    catalog = await fetch_catalog(
        shop_id=shop_id,
        latitude=latitude,
        longitude=longitude,
        save_path=save_path,
    )

    # Parse directly from dict (not file)
    return _parse_catalog_dict(catalog, rating, size_overrides)


def _parse_catalog_dict(
    data: dict,
    rating: float | None = None,
    size_overrides: dict[str, int] | None = None,
) -> list[Deal]:
    """Parse catalog dict directly (without saving to file)."""
    from .catalog_parser import _parse_offer, discover_store_sizes
    from . import vfm

    if data.get("status") != "ok":
        return []

    menu = data.get("data", {}).get("menu", {})
    categories = menu.get("categories", [])
    
    # Discover store-specific sizes FIRST
    store_size_map = discover_store_sizes(categories)
    
    # Merge with provided overrides (overrides take priority)
    if size_overrides:
        store_size_map.update(size_overrides)

    deals = []

    for category in categories:
        for offer in category.get("offers", []):
            parsed = _parse_offer(offer, store_size_map)

            if not parsed or not parsed.price or parsed.price <= 0:
                continue

            size_cm = parsed.size_cm
            if not size_cm:
                continue

            vfm_metrics = vfm.calculate_vfm(
                quantity=parsed.quantity,
                diameter_cm=size_cm,
                price=parsed.price,
                rating=rating,
            )

            deals.append(Deal(
                name=parsed.title,
                quantity=parsed.quantity,
                size_cm=size_cm,
                price=parsed.price,
                vfm=vfm_metrics,
            ))

    return deals


async def get_restaurant_deals(
    restaurant: Restaurant,
    latitude: float,
    longitude: float,
    size_overrides: dict[str, int] | None = None,
) -> list[Deal]:
    """
    Fetch and parse deals for a restaurant.

    Args:
        restaurant: Restaurant object (must have shop_id in URL)
        latitude: User latitude
        longitude: User longitude
        size_overrides: Optional size overrides

    Returns:
        List of deals with VFM metrics
    """
    # Extract shop_id from URL
    # URL format: /delivery/volos/la-strada-7527410 or /menu/la-strada-7527410
    match = re.search(r"-(\d+)(?:\?|$)", restaurant.url)
    if not match:
        print(f"  Could not extract shop_id from URL: {restaurant.url}")
        return []

    shop_id = int(match.group(1))

    try:
        deals = await fetch_and_parse_deals(
            shop_id=shop_id,
            latitude=latitude,
            longitude=longitude,
            rating=restaurant.rating,
            size_overrides=size_overrides,
        )
        return deals
    except Exception as e:
        print(f"  API fetch error for {restaurant.name}: {e}")
        return []
