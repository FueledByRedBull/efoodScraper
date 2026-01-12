# 🍕 E-Food.gr Pizza VFM Scraper

A sophisticated web scraper that analyzes pizza deals from e-food.gr to find the best value-for-money offers in Volos, Greece. The scraper uses Playwright for automation and calculates Value For Money (VFM) metrics based on pizza size, price, and restaurant rating.

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
git clone https://github.com/yourusername/efood-pizza-scraper.git
cd efood-pizza-scraper
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

Edit [src/config.py](src/config.py) to customize the scraper:

```python
class Config(BaseSettings):
    base_url: str = "https://www.e-food.gr"
    user_address: str = "YOUR_ADDRESS_ID"  # Volos address ID
    latitude: float = 0.0      # Volos coordinates
    longitude: float = 0.0
    
    headless: bool = False           # Set to True for headless mode
    use_api: bool = True             # Use API (faster) vs page scraping
    
    max_restaurants: int | None = None  # Limit number of restaurants
    skip_restaurants: list[str] = [...]  # Blacklist
    allowed_restaurants: list[str] = []  # Whitelist (overrides blacklist)
```

### Environment Variables

You can override configuration using environment variables with `EFOOD_` prefix:

```bash
# Windows PowerShell
$env:EFOOD_HEADLESS = "true"
$env:EFOOD_MAX_RESTAURANTS = "10"

# macOS/Linux
export EFOOD_HEADLESS=true
export EFOOD_MAX_RESTAURANTS=10
```

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
efood-pizza-scraper/
├── src/
│   ├── __init__.py
│   ├── analysis.py           # Analysis and reporting logic
│   ├── api_client.py          # E-food API client
│   ├── catalog_parser.py      # JSON catalog parser
│   ├── config.py              # Configuration settings
│   ├── export.py              # CSV/JSON export functions
│   ├── models.py              # Data models (Restaurant, Deal, VFM)
│   ├── scraper.py             # Main Playwright scraper
│   └── vfm.py                 # VFM calculation functions
├── output/                    # Generated reports (gitignored)
├── main.py                    # Entry point
├── requirements.txt           # Python dependencies
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

### Custom Size Overrides

Create `restaurant_overrides.json` for restaurant-specific size mappings:

```json
{
  "Pizza Mare": {
    "sizes": {
      "οικογενειακή": 30
    },
    "url_patterns": ["pizza-mare"]
  }
}
```

### Cookies for Authenticated Scraping

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

**Made with ❤️ for finding the best pizza deals in Volos**
