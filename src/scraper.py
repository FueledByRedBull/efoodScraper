import asyncio
import json
import logging
import random
import re
from pathlib import Path

from playwright.async_api import Locator, Page, async_playwright

from . import vfm
from .config import Config
from .constants import (
    BROWSER_VIEWPORT_WIDTH,
    BROWSER_VIEWPORT_HEIGHT,
    TIMEOUT_COOKIE_ACCEPT,
    TIMEOUT_SCROLL,
    TIMEOUT_CLOSED_STORES_CLICK,
    TIMEOUT_CLOSED_STORES_LOAD,
    TIMEOUT_CLOSED_STORES_TEXT,
    TIMEOUT_POPUP_CLOSE,
    TIMEOUT_POPUP_ESCAPE,
    TIMEOUT_DYNAMIC_CONTENT,
    TIMEOUT_API_CALLS,
    TIMEOUT_OFFERS_CLICK,
    TIMEOUT_PIZZA_ITEM_CLICK,
    TIMEOUT_MODAL_STEP_CLICK,
    TIMEOUT_DEEP_SCAN_CLICK,
    TIMEOUT_MODAL_CLOSE,
    TIMEOUT_LAZY_LOAD,
    SCROLL_ITERATIONS,
    LAZY_LOAD_SCROLL_ITERATIONS,
    RATING_CANDIDATE_LIMIT,
    CM_ELEMENT_ITERATION_LIMIT,
    RATING_MIN,
    RATING_MAX,
    PRICE_MIN_FILTER,
    TOP_DEALS_LIMIT,
    DEAL_NAME_MAX_LENGTH,
)
from .models import Deal, Restaurant, ScrapeResult
from . import api_client

logger = logging.getLogger("efood.scraper")


class EfoodScraper:
    """Scraper using Playwright's native Python API."""

    def __init__(self, config: Config | None = None):
        self.config = config or Config()
        self._size_cache: dict[str, int] = {}
        self._restaurant_overrides = self._load_overrides()

    def _load_overrides(self) -> dict:
        """Load restaurant size overrides from JSON file."""
        overrides_path = Path(self.config.overrides_file)
        if overrides_path.exists():
            try:
                return json.loads(overrides_path.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning(f"Could not load overrides file: {e}")
        return {}

    def _apply_restaurant_overrides(self, name: str, url: str) -> None:
        """Apply size overrides for a restaurant if configured."""
        name_lower = name.lower()
        url_lower = url.lower()

        for restaurant_key, override_data in self._restaurant_overrides.items():
            # Check if restaurant name matches
            if restaurant_key.lower() in name_lower:
                self._populate_cache_from_override(restaurant_key, override_data)
                return

            # Check URL patterns
            url_patterns = override_data.get("url_patterns", [])
            for pattern in url_patterns:
                if pattern.lower() in url_lower:
                    self._populate_cache_from_override(restaurant_key, override_data)
                    return

    def _populate_cache_from_override(self, restaurant_key: str, override_data: dict) -> None:
        """Populate size cache from override data."""
        sizes = override_data.get("sizes", {})
        if sizes:
            logger.debug(f"Pre-populating size cache for {restaurant_key}")
            for size_name, diameter in sizes.items():
                self._size_cache[size_name] = diameter

    async def scrape(self) -> ScrapeResult:
        """Main entry point - runs the full scrape."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.config.headless)
            context = await browser.new_context(
                viewport={"width": BROWSER_VIEWPORT_WIDTH, "height": BROWSER_VIEWPORT_HEIGHT}
            )

            # Load cookies if they exist
            cookies_path = Path(self.config.cookies_file)
            if cookies_path.exists():
                cookies = json.loads(cookies_path.read_text())
                await context.add_cookies(cookies)

            page = await context.new_page()

            try:
                restaurants = await self._scrape_all(page)
                return ScrapeResult(restaurants=restaurants)
            finally:
                await browser.close()

    async def _scrape_all(self, page: Page) -> list[Restaurant]:
        """Scrape all restaurants."""
        await self._go_to_restaurant_list(page)
        restaurant_data = await self._get_restaurant_list(page)

        if self.config.max_restaurants:
            restaurant_data = restaurant_data[: self.config.max_restaurants]

        results = []
        for i, data in enumerate(restaurant_data, 1):
            logger.info(f"[{i}/{len(restaurant_data)}] {data['name'][:50]}")

            if self._should_skip(data["name"]):
                logger.debug("Skipped (in skip list)")
                continue

            try:
                if self.config.use_api:
                    restaurant = await self._process_restaurant_via_api(page, data)
                else:
                    restaurant = await self._process_restaurant(page, data)
                results.append(restaurant)
            except Exception as e:
                logger.error(f"Error: {e}")
                results.append(
                    Restaurant(
                        name=data["name"],
                        url=data["url"],
                        rating=data.get("rating"),
                        is_closed=data.get("is_closed", False),
                        deals=[],
                    )
                )

            await self._random_delay()

        return results

    async def _go_to_restaurant_list(self, page: Page) -> None:
        """Navigate to pizza restaurants list."""
        url = f"{self.config.base_url}/shops?vertical=food&user_address={self.config.user_address}&categories=pizza"
        await page.goto(url)
        await page.wait_for_load_state("domcontentloaded")

        # Handle cookie consent using locator
        accept_btn = page.get_by_role("button", name=re.compile(r"Αποδοχή|Accept", re.I))
        if await accept_btn.count() > 0:
            await accept_btn.first.click()
            # Wait for cookie banner to disappear
            try:
                await accept_btn.first.wait_for(state="hidden", timeout=5000)
            except Exception:
                pass

        # Check for Tyxeri Peiniata popup immediately after load/cookies
        await self._close_piniata_popup(page)

        # Scroll down multiple times to fully load the page and find closed stores button
        for _ in range(SCROLL_ITERATIONS):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass
            await self._close_piniata_popup(page)  # Close popup if it appears during scroll

        # Show closed stores - Try multiple selectors
        # The button contains exact text "Δες τα κλειστά καταστήματα"
        closed_btn = page.get_by_role("button", name=re.compile(r"Δες τα κλειστά", re.I))
        
        if await closed_btn.count() == 0:
            # Fallback: try locator with text filter
            closed_btn = page.locator("button:has-text('κλειστά καταστήματα')")
        
        if await closed_btn.count() > 0:
            logger.debug("Found 'Show closed stores' button, clicking...")
            try:
                await closed_btn.first.scroll_into_view_if_needed()
                await closed_btn.first.click(force=True)
                # Wait for network activity to settle after loading closed stores
                try:
                    await page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass
                logger.debug("Closed stores should now be visible.")
            except Exception as e:
                logger.warning(f"Could not click closed stores button: {e}")
        else:
            logger.debug("'Show closed stores' button not found. Trying text click...")
            # Last resort: click by text anywhere
            try:
                await page.click("text=Δες τα κλειστά καταστήματα", timeout=TIMEOUT_CLOSED_STORES_TEXT)
                try:
                    await page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass
                logger.debug("Clicked via text selector.")
            except Exception:
                logger.debug("Could not find closed stores button at all.")
            
        # Check again after interaction
        await self._close_piniata_popup(page)

    async def _close_piniata_popup(self, page: Page) -> None:
        """Close the 'Tyxeri Peiniata' popup or any other interruption."""
        try:
            # Check specifically for Peiniata or generic modals overlaying the page
            overlays = page.locator("text=Η Τυχερή Πεινιάτα").or_(page.locator(".modal-open"))
            if await overlays.count() > 0:
                logger.debug("Found potential blocking popup, attempting to close...")
                
                # 1. Try exact close button match for Peiniata (often top-right X)
                # Looking at your screenshot, it's a dedicated close icon top right
                # We try clicking the top-rightmost button in the dialog
                close_buttons = page.locator("button, [role='button'], svg").filter(has_text=re.compile(r"X|×|Close", re.I))
                
                if await close_buttons.count() > 0:
                    # Try the first visible one
                    for i in range(await close_buttons.count()):
                        if await close_buttons.nth(i).is_visible():
                            await close_buttons.nth(i).click()
                            # Wait for overlay to disappear
                            try:
                                await overlays.first.wait_for(state="hidden", timeout=3000)
                            except Exception:
                                pass
                            return

                # 2. Try clicking coordinates (Top Right of screen) usually works for full screen ads
                # but dangerous if it hits a menu item. Skipped for now.

                # 3. Fallback: Escape key is very effective for these
                await page.keyboard.press("Escape")
                try:
                    await overlays.first.wait_for(state="hidden", timeout=3000)
                except Exception:
                    pass
                
        except Exception as e:
            # Don't let this crash the scraper
            logger.debug(f"Popup close attempt failed: {e}")

    async def _get_restaurant_list(self, page: Page) -> list[dict]:
        """Get all restaurants from the list page."""
        
        # Scroll down to trigger lazy loading to ensure we find all requested restaurants
        last_height = await page.evaluate("document.body.scrollHeight")
        for _ in range(LAZY_LOAD_SCROLL_ITERATIONS):
             await page.mouse.wheel(0, 5000)
             # Wait for network to be idle after scroll
             try:
                 await page.wait_for_load_state("networkidle", timeout=3000)
             except Exception:
                 pass
             new_height = await page.evaluate("document.body.scrollHeight")
             if new_height == last_height:
                 break
             last_height = new_height
        
        # Wait for restaurant links to appear
        await page.locator('a[href*="/menu/"], a[href*="/delivery/"]').first.wait_for(
            timeout=self.config.timeout_ms
        )

        # Use evaluate for bulk extraction (much faster than iterating locators)
        restaurants = await page.evaluate("""() => {
            const results = [];
            const seen = new Set();
            const links = document.querySelectorAll('a[href*="/menu/"], a[href*="/delivery/"]');

            links.forEach(link => {
                // Get absolute URL to parse properly
                const fullUrl = link.href;
                if (!fullUrl) return;
                
                // Skip non-restaurant links (efood pro promo, category links, etc.)
                if (fullUrl.includes('/shops') || fullUrl.includes('efoodpro') || fullUrl.includes('categories')) return;
                
                // Must be a restaurant page link
                if (!fullUrl.includes('/menu/') && !fullUrl.includes('/delivery/')) return;

                // Normalize for deduplication: use pathname only, ignoring query params
                try {
                    const urlObj = new URL(fullUrl);
                    const uniqueKey = urlObj.pathname.replace(/\\/$/, '').toLowerCase(); // Remove trailing slash & lowercase
                    
                    if (seen.has(uniqueKey)) return;
                    seen.add(uniqueKey);
                } catch (e) {
                    return;
                }

                const url = link.getAttribute('href');
                const card = link.closest('[class*="Card"], [class*="card"]') || link.parentElement;
                
                // Try to get name from specific heading first
                let name = '';
                const nameEl = card?.querySelector('h3, [class*="name"], [class*="Name"]');
                if (nameEl) {
                    name = nameEl.textContent.trim();
                } else {
                    // Fallback to link text but try to clean it
                    name = link.textContent.trim();
                    // Basic cleanup: remove rating pattern if present at start/end
                    name = name.replace(/\\d+[.,]\\d+\\s*\\(\\d+\\).*$/, '').trim();
                }

                if (!name || name.length < 2) return;

                // Extract rating - look specifically for the number
                let rating = null;
                // Try to find rating element specifically
                const ratingEl = card?.querySelector('[class*="rating"], [class*="Rating"], [data-testid*="rating"]');
                if (ratingEl) {
                    const match = ratingEl.textContent.match(/(\\d+[.,]\\d+)/);
                    if (match) rating = parseFloat(match[1].replace(',', '.'));
                } else {
                    // Fallback: look for rating pattern in the whole card text
                    const match = link.textContent.match(/(\\d+[.,]\\d+)\\s*\\(\\d+\\)/);
                    if (match) rating = parseFloat(match[1].replace(',', '.'));
                }

                // Check if closed
                const isClosed = card?.textContent.includes('Κλειστό') || false;

                results.push({ name, url, rating, is_closed: isClosed });
            });

            return results;
        }""")

        logger.info(f"Found {len(restaurants)} restaurants")
        return restaurants

    async def _process_restaurant(self, page: Page, data: dict) -> Restaurant:
        """Process a single restaurant."""
        data = data.copy()  # Avoid modifying caller's dict
        url = data["url"]

        # Make URL absolute if relative
        if url.startswith("/"):
            url = f"{self.config.base_url}{url}"

        if "user_address" not in url:
            url = f"{url}?user_address={self.config.user_address}"

        await page.goto(url)
        await page.wait_for_load_state("domcontentloaded")
        # Wait for dynamic content to load
        try:
            await page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass

        # Extract real restaurant name from page
        try:
            name_el = page.locator("h1[class*='cc-title'], h1")
            if await name_el.count() > 0:
                data["name"] = await name_el.first.inner_text()
                logger.info(f"Restaurant: {data['name']}")
        except Exception:
            pass

        # Extract rating from page (overrides list rating, crucial for closed stores)
        try:
            # Look for exact rating number (e.g. "4.8")
            rating_candidates = page.locator("span, div").filter(
                has_text=re.compile(r"^\s*\d+[.,]\d+\s*$")
            )
            
            count = await rating_candidates.count()
            # Check the first few matches (rating usually appears early in DOM/header)
            for i in range(min(count, RATING_CANDIDATE_LIMIT)):
                el = rating_candidates.nth(i)
                # Ensure it's visible to avoid hidden metadata
                if not await el.is_visible():
                    continue

                text = (await el.inner_text()).strip()
                # Skip if it looks like a price or invalid
                if "€" in text or "%" in text:
                    continue
                    
                try:
                    val = float(text.replace(",", "."))
                    # Rating must be between 1 and 5
                    if RATING_MIN <= val <= RATING_MAX:
                        # Check context - usually near parentheses like "(245)"
                        # or has parent with "rating" class
                        parent_class = await el.evaluate("el => el.parentElement.className")
                        should_update = False
                        
                        if "rating" in str(parent_class).lower():
                            should_update = True
                        else:
                            # Fallback: assume top valid number 1-5 in header is rating
                            should_update = True
                            
                        if should_update:
                            data["rating"] = val
                            logger.info(f"Rating (from page): {val}")
                            break
                except ValueError:
                    continue
        except Exception as e:
            logger.warning(f"Rating extraction warning: {e}")

        # Reset size cache for new restaurant
        self._size_cache.clear()

        # Apply size overrides from configuration
        self._apply_restaurant_overrides(data["name"], data["url"])

        # Click on "Προσφορές" in the sidebar to go to deals section
        await self._click_offers_section(page)

        # Discover sizes by clicking on the first pizza deal
        await self._discover_sizes_from_deal(page)

        # Get all deals
        deals = await self._get_deals(page, data.get("rating"))
        
        # Sort by VFM (highest first) and keep top deals
        deals.sort(key=lambda d: d.vfm.vfm_index, reverse=True)
        top_deals = deals[:TOP_DEALS_LIMIT]
        
        logger.info(f"Found {len(deals)} deals. Keeping top {len(top_deals)}:")
        for i, deal in enumerate(top_deals, 1):
             logger.info(f"  {i}. {deal.name} ({deal.size_cm}cm) - {deal.vfm.area_per_euro} cm2/EUR")

        return Restaurant(
            name=data["name"],
            url=data["url"],
            rating=data["rating"],
            is_closed=data["is_closed"],
            deals=top_deals,  # Only return the top 5
        )

    def _extract_shop_id(self, url: str) -> int | None:
        """Extract shop_id from restaurant URL."""
        # URL format: /delivery/volos/la-strada-7527410 or /menu/la-strada-7527410
        match = re.search(r"-(\d+)(?:\?|$)", url)
        if match:
            return int(match.group(1))
        return None

    async def _process_restaurant_via_api(self, page: Page, data: dict) -> Restaurant:
        """Process a restaurant using the API instead of page scraping."""
        data = data.copy()  # Avoid modifying caller's dict

        # Navigate to page to get true rating and resolve ID from final URL
        url = data["url"]
        if url.startswith("/"):
            url = f"{self.config.base_url}{url}"
        if "user_address" not in url:
            url = f"{url}?user_address={self.config.user_address}"

        # Intercept network requests to capture shop_id from catalog API call
        captured_shop_id = None

        async def capture_catalog_request(route):
            nonlocal captured_shop_id
            request_url = route.request.url
            if "shops/catalog" in request_url and "shop_id=" in request_url:
                match = re.search(r'shop_id=(\d+)', request_url)
                if match:
                    captured_shop_id = int(match.group(1))
            await route.continue_()

        try:
            await page.route("**/api.e-food.gr/**", capture_catalog_request)
        except Exception as e:
            logger.debug(f"Route setup failed: {e}")

        try:
            await page.goto(url)
            await page.wait_for_load_state("domcontentloaded")
            # Wait for API calls to complete
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass

            # Updated Name
            name_el = page.locator("h1[class*='cc-title'], h1")
            if await name_el.count() > 0:
                data["name"] = await name_el.first.inner_text()
                logger.info(f"Restaurant: {data['name']}")

            # Updated Rating (Crucial for closed stores)
            rating_candidates = page.locator("span, div").filter(
                has_text=re.compile(r"^\s*\d+[.,]\d+\s*$")
            )
            count = await rating_candidates.count()
            for i in range(min(count, RATING_CANDIDATE_LIMIT)):
                el = rating_candidates.nth(i)
                if not await el.is_visible(): continue
                text = (await el.inner_text()).strip()
                if "€" in text or "%" in text: continue
                try:
                    val = float(text.replace(",", "."))
                    if RATING_MIN <= val <= RATING_MAX:
                        data["rating"] = val
                        logger.info(f"Rating (from page): {val}")
                        break
                except ValueError:
                    continue
        except Exception as e:
            logger.warning(f"Page navigation warning: {e}")

        # Unroute to clean up
        try:
            await page.unroute("**/api.e-food.gr/**")
        except Exception as e:
            logger.debug(f"Unroute cleanup failed: {e}")

        # Priority 1: Captured from network request
        shop_id = captured_shop_id
        if shop_id:
            logger.debug(f"Captured shop_id from API: {shop_id}")

        # Priority 2: Extract from current URL
        if not shop_id:
            shop_id = self._extract_shop_id(page.url)

        # Priority 3: Extract from original URL
        if not shop_id:
            shop_id = self._extract_shop_id(data["url"])

        # Fallback: Extract from page content
        if not shop_id:
            try:
                content = await page.content()
                # Try multiple patterns - order matters, most specific first
                patterns = [
                    r'"shop_id":\s*(\d+)',
                    r'"shopId":\s*(\d+)',
                    r'"restaurant_id":\s*(\d+)',
                    r'"restaurantId":\s*(\d+)',
                    r'shop_id=(\d+)',
                    r'/shops/catalog\?shop_id=(\d+)',
                    r'/shops/(\d+)/catalog',
                ]
                for pattern in patterns:
                    match = re.search(pattern, content)
                    if match:
                        found_id = int(match.group(1))
                        # Skip if it matches user_address (common false positive)
                        if str(found_id) != self.config.user_address:
                            shop_id = found_id
                            logger.debug(f"Found shop_id: {shop_id}")
                            break
            except Exception as e:
                logger.error(f"Content extraction error: {e}")

        if not shop_id:
            logger.warning("Could not extract shop_id, falling back to empty deals")
            return Restaurant(
                name=data["name"],
                url=data["url"],
                rating=data.get("rating"),
                is_closed=data.get("is_closed", False),
                deals=[],
            )

        # Get size overrides for this restaurant
        self._size_cache.clear()
        self._apply_restaurant_overrides(data["name"], data["url"])
        size_overrides = self._size_cache.copy() if self._size_cache else None

        try:
            deals = await api_client.fetch_and_parse_deals(
                shop_id=shop_id,
                latitude=self.config.latitude,
                longitude=self.config.longitude,
                rating=data.get("rating"),
                size_overrides=size_overrides,
            )

            # Sort by VFM and keep top deals
            deals.sort(key=lambda d: d.vfm.vfm_index, reverse=True)
            top_deals = deals[:TOP_DEALS_LIMIT]

            logger.info(f"Found {len(deals)} deals via API. Top {len(top_deals)}:")
            for i, deal in enumerate(top_deals, 1):
                logger.info(f"  {i}. VFM:{deal.vfm.vfm_index:.1f} | {deal.quantity}x{deal.size_cm}cm @ {deal.price:.2f}EUR")

            return Restaurant(
                name=data["name"],
                url=data["url"],
                rating=data.get("rating"),
                is_closed=data.get("is_closed", False),
                deals=top_deals,
            )

        except Exception as e:
            logger.error(f"API error: {e}")
            return Restaurant(
                name=data["name"],
                url=data["url"],
                rating=data.get("rating"),
                is_closed=data.get("is_closed", False),
                deals=[],
            )

    async def _click_offers_section(self, page: Page) -> None:
        """Click on Προσφορές in the sidebar."""
        # Look for "Προσφορές" link in sidebar/categories
        offers_link = page.locator("a, button, [role='button']").filter(
            has_text=re.compile(r"^Προσφορές$", re.I)
        )
        if await offers_link.count() > 0:
            await offers_link.first.click()
            # Wait for offers section to load
            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass
            logger.debug("Clicked on Προσφορές section")

    async def _discover_sizes_from_deal(self, page: Page) -> None:
        """Discover sizes by clicking on the first pizza deal and expanding Βήμα 1."""
        # Find any pizza deal item
        pizza_items = page.locator("text=/πίτσα|πίτσες|γίγας|οικογενειακ/i").filter(
            has_text="€"
        )

        if await pizza_items.count() == 0:
            logger.debug("No pizza items found to discover sizes")
            return

        # Click on the first pizza item to open modal
        try:
            await pizza_items.first.click()
            # Wait for modal to appear
            try:
                await page.locator("[class*='modal'], [class*='Modal']").first.wait_for(state="visible", timeout=5000)
            except Exception:
                pass
        except Exception as e:
            logger.debug("Click failed, checking for popup...")
            await self._close_piniata_popup(page)
            try:
                await pizza_items.first.click(force=True)
                try:
                    await page.locator("[class*='modal'], [class*='Modal']").first.wait_for(state="visible", timeout=5000)
                except Exception:
                    pass
            except Exception:
                logger.warning(f"Could not click pizza item: {e}")
                return

        # Click on "Βήμα 1" to expand size selector
        step1 = page.locator("text=/Βήμα 1/i")
        if await step1.count() > 0:
            await step1.first.click()
            # Wait a moment for expansion animation
            try:
                await page.wait_for_load_state("networkidle", timeout=3000)
            except Exception:
                pass
            logger.debug("Expanded Βήμα 1")

        # Extract ALL sizes from the modal
        await self._extract_sizes_from_modal(page)

        # Close modal
        await page.keyboard.press("Escape")
        # Wait for modal to close
        try:
            await page.locator("[class*='modal'], [class*='Modal']").first.wait_for(state="hidden", timeout=3000)
        except Exception:
            pass

    async def _extract_sizes_from_modal(self, page: Page) -> None:
        """Extract size name -> cm mapping from modal."""
        # Look for size options like "Κανονική(30cm | 8 κομμάτια)"
        size_pattern = re.compile(r"(κανονικ|μικρ|μεγάλ|γίγας|γιγας|οικογενειακ)[^(]*\((\d+)\s*cm", re.I)

        # Get all text from modal area
        modal = page.locator("[class*='modal'], [class*='Modal'], [class*='dialog'], [class*='Dialog']")
        if await modal.count() > 0:
            modal_text = await modal.first.inner_text()
        else:
            # Fallback to body text
            modal_text = await page.locator("body").inner_text()

        # Find all size patterns
        for match in size_pattern.finditer(modal_text):
            size_name_raw = match.group(1).lower()
            diameter = int(match.group(2))

            # Normalize size name
            size_name = self._normalize_size_name(size_name_raw)
            if size_name and size_name not in self._size_cache:
                self._size_cache[size_name] = diameter
                logger.debug(f"Cached: {size_name} = {diameter}cm")

        # Also look for standalone cm values
        if await modal.count() > 0:
            cm_elements = modal.first.locator("text=/\\d+\\s*cm/i")
        else:
            cm_elements = page.locator("text=/\\d+\\s*cm/i")
            
        count = await cm_elements.count()

        for i in range(min(count, CM_ELEMENT_ITERATION_LIMIT)):
            try:
                el = cm_elements.nth(i)
                text = await el.inner_text(timeout=500)
                if diameter := vfm.parse_diameter(text):
                    size_name = self._extract_size_name(text)
                    if size_name and size_name not in self._size_cache:
                        self._size_cache[size_name] = diameter
                        logger.debug(f"Cached: {size_name} = {diameter}cm")
                    elif not size_name and "default" not in self._size_cache:
                        self._size_cache["default"] = diameter
            except Exception:
                continue

        if self._size_cache:
            logger.debug(f"Size cache: {self._size_cache}")

    def _normalize_size_name(self, raw: str) -> str | None:
        """Normalize size name to standard form."""
        lower = raw.lower()
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

    def _extract_size_name(self, text: str) -> str | None:
        """Extract standardized size name from text."""
        return self._normalize_size_name(text)

    async def _deep_scan_deal_size(self, page: Page, deal_name: str) -> int | None:
        """Deep scan a specific deal by opening its modal to find size."""
        logger.debug(f"Deep scanning: {deal_name[:30]}...")

        try:
            # Use get_by_text for safer matching of special characters
            item = page.get_by_text(deal_name, exact=True)

            if await item.count() == 0:
                # Try partial match if exact fails
                item = page.get_by_text(deal_name, exact=False)

            if await item.count() > 0:
                try:
                    await item.first.scroll_into_view_if_needed()
                    await item.first.click(force=True)
                    # Wait for modal to appear
                    try:
                        await page.locator("[class*='modal'], [class*='Modal']").first.wait_for(state="visible", timeout=5000)
                    except Exception:
                        pass
                    
                    # Extract sizes
                    await self._extract_sizes_from_modal(page)
                    
                    # Close modal
                    await page.keyboard.press("Escape")
                    try:
                        await page.locator("[class*='modal'], [class*='Modal']").first.wait_for(state="hidden", timeout=3000)
                    except Exception:
                        pass

                    # Check cache
                    size_name = self._extract_size_name(deal_name)
                    if size_name and size_name in self._size_cache:
                        return self._size_cache[size_name]
                    return self._size_cache.get("default")
                except Exception as e:
                    logger.debug(f"Interaction failed: {e}")
                    # Ensure modal closed
                    await page.keyboard.press("Escape")
        except Exception as e:
            logger.debug(f"Deep scan failed: {e}")
            
        return None

    async def _get_deals(self, page: Page, rating: float | None) -> list[Deal]:
        """Get pizza deals from current restaurant page."""
        # Use evaluate for efficient bulk extraction of deal data
        raw_deals = await page.evaluate("""() => {
            const results = [];
            // Target the specific wrapper class we found
            const cards = document.querySelectorAll('[class*="cc-wrapper"]');

            cards.forEach(card => {
                const nameEl = card.querySelector('[class*="cc-name"], h3');
                const priceEl = card.querySelector('[class*="cc-price"]');

                if (!nameEl || !priceEl) return;

                const name = nameEl.textContent.trim();
                const priceText = priceEl.textContent.trim();

                // Must contain pizza-related keywords
                const hasPizza = /πίτσα|πίτσες|γίγας|οικογενειακ/i.test(name);
                if (!hasPizza) return;

                // Extract price
                const priceMatch = priceText.match(/(\\d+[,.]?\\d*)\\s*€/);
                if (!priceMatch) return;
                const price = parseFloat(priceMatch[1].replace(',', '.'));

                // Extract quantity - look for patterns like "1 Πίτσα", "3 Γίγας", "2 Κανονικές"
                const qtyMatch = name.match(/(\\d+)\\s*(πίτσα|πίτσες|γίγας|οικογενειακ|κανονικ|μεγάλ)/i);
                const quantity = qtyMatch ? parseInt(qtyMatch[1]) : 1;

                results.push({ name, price, quantity });
            });

            // Remove duplicates by name
            const seen = new Set();
            return results.filter(d => {
                if (seen.has(d.name)) return false;
                seen.add(d.name);
                return true;
            });
        }""")

        deals = []
        for raw in raw_deals:
            name = raw["name"]
            price = raw["price"]
            quantity = raw["quantity"]

            if price < PRICE_MIN_FILTER:
                continue

            # Extract size from FULL deal name text
            size_name = self._extract_size_name(name)

            # Get size from cache or estimate
            size_cm = None
            if size_name and size_name in self._size_cache:
                size_cm = self._size_cache[size_name]
            elif "default" in self._size_cache:
                size_cm = self._size_cache["default"]
            elif size_name:
                size_cm = vfm.estimate_diameter(size_name)

            # Also try to parse size directly from text (e.g., "4 Γίγας πίτσες (40cm)")
            if not size_cm:
                size_cm = vfm.parse_diameter(name)

            if not size_cm:
                # Try deep scan as a last resort
                size_cm = await self._deep_scan_deal_size(page, name)

            if not size_cm:
                logger.debug(f"Skipped (no size): {name[:40]}...")
                continue

            vfm_metrics = vfm.calculate_vfm(quantity, size_cm, price, rating)

            deals.append(
                Deal(
                    name=name[:DEAL_NAME_MAX_LENGTH].strip(),
                    quantity=quantity,
                    size_cm=size_cm,
                    price=price,
                    vfm=vfm_metrics,
                )
            )

            logger.debug(f"{quantity}x {size_name or 'default'} ({size_cm}cm) @ {price}EUR -> VFM: {vfm_metrics.vfm_index}")

        return deals

    def _should_skip(self, name: str) -> bool:
        """Check if restaurant should be skipped."""
        lower = name.lower()
        
        # If allowlist is present, ONLY allow those
        if self.config.allowed_restaurants:
            # Check if ANY of the allowed names are substring of the current name
            # We match strictly: allowed name must be in the current name
            match = any(allowed.lower() in lower for allowed in self.config.allowed_restaurants)
            return not match

        return any(skip.lower() in lower for skip in self.config.skip_restaurants)

    async def _random_delay(self) -> None:
        """Add random delay between requests."""
        delay_ms = random.randint(self.config.delay_min_ms, self.config.delay_max_ms)
        await asyncio.sleep(delay_ms / 1000)
