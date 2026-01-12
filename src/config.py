from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Scraper configuration with validation."""

    base_url: str = "https://www.e-food.gr"
    user_address: str = "YOUR_ADDRESS_ID"  # Get from e-food.gr URL
    latitude: float = 0.0  # Your delivery location latitude
    longitude: float = 0.0  # Your delivery location longitude

    headless: bool = False
    timeout_ms: int = 60_000
    use_api: bool = True  # Use API instead of page scraping for deals

    delay_min_ms: int = 1000
    delay_max_ms: int = 3000
    max_restaurants: int | None = None
    skip_restaurants: list[str] = Field(default_factory=lambda: [
        "Toronto",
        "Pizza Fan",
        "Pizza Volos",
        "Lola e Luna",
        "Grappa on the road",
        "Sogno di San",
        "Ιππόκαμπος",
        "Egalite Experience",
        "myVegan",
        "Evelin",
        "Pleasures",
    ])
    allowed_restaurants: list[str] = Field(default_factory=list)

    output_dir: str = "output"
    cookies_file: str = "cookies.json"
    overrides_file: str = "restaurant_overrides.json"

    model_config = SettingsConfigDict(env_prefix="EFOOD_")


# Size name to diameter mapping (in cm)
SIZE_DIAMETERS: dict[str, int] = {
    "μικρή": 25,
    "κανονική": 30,
    "μεσαία": 32,
    "μεγάλη": 36,
    "οικογενειακή": 36,
    "γίγας": 40,
    "jumbo": 45,
}
