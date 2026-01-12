# 🍕 E-Food.gr Pizza VFM Scraper

A sophisticated web scraper that analyzes pizza deals from e-food.gr to find the best value-for-money offers in Greece. The scraper uses Playwright for automation and calculates Value For Money (VFM) metrics based on pizza size, price, and restaurant rating.

## Features

- **Automated Scraping**: Uses Playwright to scrape restaurant data and pizza deals
- **API Integration**: Fetches catalog data directly from e-food.gr API for faster processing
- **Dynamic Size Discovery**: Automatically detects store-specific pizza sizes from catalogs
- **VFM Calculation**: Ranks deals by value using formula: `VFM = (pizza_area / price) × (rating / 5.0)`
- **Smart Filtering**: Support for restaurant allowlists and blocklists
- **Comprehensive Output**: Generates CSV, JSON, and visualization charts
- **Closed Store Support**: Extracts ratings and deals even from currently closed restaurants
- **Popup Handling**: Automatically closes interrupting popups and modals

## VFM Formula

```
VFM Index = (Total Pizza Area / Price) × (Rating / 5.0)

Where:
- Total Pizza Area = π × (diameter/2)² × quantity
- Rating Factor = Linear penalty from 1.0 (5-star) to 0.2 (1-star)
```

## Installation

### Prerequisites

- Python 3.10 or higher
- Git

### Setup

1. **Clone the repository**
```bash
git clone https://github.com/FueledByRedBull/efoodScraper.git
cd efoodScraper
```

2. **Create a virtual environment**
```bash
python -m venv venv
```

3. **Activate the virtual environment**
- Windows (PowerShell):
  ```powershell
  venv\Scripts\Activate.ps1
  ```
- Windows (Command Prompt):
  ```cmd
  venv\Scripts\activate.bat
  ```
- macOS/Linux:
  ```bash
  source venv/bin/activate
  ```

4. **Install dependencies**
```bash
pip install -r requirements.txt
```

5. **Install Playwright browsers**
```bash
playwright install chromium
```

## Configuration

### Quick Setup with .env File

**REQUIRED**: Configure your delivery location before running:

1. **Copy the example file**:
   ```bash
   cp .env.example .env
   ```

2. **Find your coordinates** from e-food.gr:
   - Open e-food.gr in your browser and select your delivery address
   - Navigate to any restaurant page (e.g., pizza category)
   - Open Developer Tools (**F12**) → **Network** tab
   - Look for a request to `catalog?shop_id=...` or similar API endpoint
   - Click on it and check the **Query String Parameters** or **Payload**:
     - Copy the `latitude` value (e.g., `0.0`)
     - Copy the `longitude` value (e.g., `0.0`)
     - Copy the `user_address` ID from the URL or parameters

3. **Edit `.env` file** with your values:
   ```bash
   EFOOD_USER_ADDRESS=YOUR_ADDRESS_ID
   EFOOD_LATITUDE=0.0
   EFOOD_LONGITUDE=0.0
   
   # Optional settings
   EFOOD_HEADLESS=false
   EFOOD_USE_API=true
   ```

The configuration is automatically loaded from `.env` file when you run the scraper.

### Additional Configuration

#### Restaurant Filtering

Create `restaurant_filters.json` to customize which restaurants to scrape:

1. **Copy the example file**:
   ```bash
   cp restaurant_filters.example.json restaurant_filters.json
   ```

2. **Edit the file**:
   ```json
   {
     "skip_restaurants": [
       "Toronto",
       "Pizza Fan"
     ],
     "allowed_restaurants": []
   }
   ```

- **`skip_restaurants`**: Blacklist (skip these restaurants)
- **`allowed_restaurants`**: Whitelist (only scrape these, overrides blacklist)

**Note**: The configuration is automatically loaded when you run the scraper.

#### Other Settings

You can customize behavior by editing `.env`:

| Setting | Description | Default |
|---------|-------------|---------|
| `EFOOD_HEADLESS` | Run browser in headless mode | `false` |
| `EFOOD_USE_API` | Use API (faster) vs page scraping | `true` |
| `EFOOD_MAX_RESTAURANTS` | Limit number of restaurants | `None` (all) |

## Usage

### Basic Usage

```bash
python main.py
```

### Headless Mode

```bash
# PowerShell
$env:EFOOD_HEADLESS = "true"
python main.py

# Or edit config.py and set headless = True
```

### Filter Specific Restaurants

**Using allowlist** (only scrape these):
```python
# In src/config.py
allowed_restaurants: list[str] = Field(default_factory=lambda: [
    "Papagalino",
    "Pizza Crust",
    "La Strada"
])
```

**Using blocklist** (skip these):
```python
# In src/config.py
skip_restaurants: list[str] = Field(default_factory=lambda: [
    "Pizza Fan",
    "Toronto"
])
```

## Output

The scraper generates several outputs in the `output/` directory:

### Files Generated

- **`pizza_vfm.csv`**: Complete dataset with all deals and VFM metrics
- **`pizza_vfm.json`**: JSON format of complete scrape results
- **`charts/vfm_distribution.png`**: Histogram of VFM scores
- **`charts/restaurant_comparison.png`**: Average VFM by restaurant
- **`charts/top10_deals.png`**: Bar chart of top 10 deals

### Console Output

The scraper prints:
- Progress for each restaurant
- Top 10 deals for 2-pizza, 3-pizza, and 4-pizza categories
- Summary statistics

Example output:
```
==================================================
SCRAPING SUMMARY
==================================================
Total Restaurants: 45
Total Deals: 231
Average VFM: 145.67 cm2/EUR

Top 10 Deals with 2 Pizzas:
  1. Papagalino (4.5) - 2 Οικογενειακές Πίτσες : 189.32 cm2/EUR (VFM: 170.39)
  2. Pizza Crust (4.3) - 2 Γίγας της επιλογής σας : 176.45 cm2/EUR (VFM: 151.75)
  ...
```

## Project Structure

```
efoodScraper/
├── src/
│   ├── __init__.py
│   ├── analysis.py           # Analysis and reporting logic
│   ├── api_client.py         # E-food API client
│   ├── catalog_parser.py     # JSON catalog parser
│   ├── config.py             # Configuration settings
│   ├── constants.py          # Centralized constants
│   ├── export.py             # CSV/JSON export functions
│   ├── logging_config.py     # Logging configuration
│   ├── models.py             # Data models (Restaurant, Deal, VFM)
│   ├── scraper.py            # Main Playwright scraper
│   └── vfm.py                # VFM calculation functions
├── output/                   # Generated reports (gitignored)
├── main.py                   # Entry point
├── requirements.txt          # Python dependencies
├── .gitignore
└── README.md
```

## Size Mappings

Default pizza size mappings (in cm diameter):

| Greek Name | English | Diameter |
|------------|---------|----------|
| μικρή | Small | 25cm |
| κανονική | Regular | 30cm |
| μεσαία | Medium | 32cm |
| μεγάλη | Large | 36cm |
| οικογενειακή | Family | 36cm |
| γίγας | Giant | 40cm |
| jumbo | Jumbo | 45cm |

**Note**: The scraper dynamically discovers store-specific sizes that override these defaults.

## Advanced Features

### Custom Size Overrides (Optional)

If you discover restaurants with non-standard pizza sizes, you can create `restaurant_overrides.json` to override the dynamic size discovery:

1. Copy the example file:
   ```bash
   cp restaurant_overrides.example.json restaurant_overrides.json
   ```

2. Edit `restaurant_overrides.json` with restaurant-specific sizes:
   ```json
   {
     "Pizza Mare": {
       "sizes": {
         "οικογενειακή": 30,
         "γίγας": 40
       },
       "url_patterns": ["pizza-mare", "pizzamare"]
     }
   }
   ```

**Note**: This file is optional. The scraper automatically discovers sizes from each store's catalog, so overrides are only needed for edge cases.

### Cookies for Authenticated Scraping (Optional)

Save authenticated cookies to `cookies.json` for accessing delivery-specific pricing:

```json
[
  {
    "name": "session_id",
    "value": "your_session_value",
    "domain": ".e-food.gr",
    "path": "/"
  }
]
```

**Security Warning**: The `cookies.json` file contains sensitive personal information including session tokens, addresses, and coordinates. This file is gitignored by default but you should:
- Never commit this file to version control
- Keep it private and do not share
- Regenerate cookies periodically

## Troubleshooting

### Playwright Installation Issues
```bash
# Reinstall Playwright
pip uninstall playwright
pip install playwright
playwright install chromium
```

### Popup Interference
The scraper automatically handles the "Tyxeri Peiniata" popup, but if issues persist:
- Set `headless: bool = False` to watch the browser
- The scraper presses ESC to close modals

### Missing Ratings
If ratings aren't extracted:
- The scraper navigates to each restaurant's detail page
- Closed stores have ratings extracted from their detail page

### No Deals Found
- Check `allowed_restaurants` configuration
- Verify the restaurant has deals in the "Προσφορές" section
- Run with `headless=False` to debug visually

## Dependencies

- **playwright** - Browser automation
- **aiohttp** - Async HTTP client for API calls
- **pandas** - Data analysis and CSV export
- **matplotlib** - Chart generation
- **pydantic** - Configuration validation

See [requirements.txt](requirements.txt) for full list.

## License

MIT License - feel free to use and modify.

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## Disclaimer

This tool is for educational purposes only. Please respect e-food.gr's terms of service and use rate limiting appropriately. The scraper includes delays between requests to be respectful of the service.

---

**Made with love for finding the best pizza deals**
