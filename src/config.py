from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Scraper configuration with validation."""

    base_url: str = "https://www.e-food.gr"
    user_address: str  # Required: Get from e-food.gr Network tab
    latitude: float    # Required: Your delivery location latitude
    longitude: float   # Required: Your delivery location longitude

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

    model_config = SettingsConfigDict(
        env_prefix="EFOOD_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, v: float) -> float:
        """Validate latitude is within valid range."""
        if not -90.0 <= v <= 90.0:
            raise ValueError("Latitude must be between -90 and 90")
        return v

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v: float) -> float:
        """Validate longitude is within valid range."""
        if not -180.0 <= v <= 180.0:
            raise ValueError("Longitude must be between -180 and 180")
        return v

    @field_validator("timeout_ms")
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        """Validate timeout is reasonable."""
        if v < 1000:
            raise ValueError("timeout_ms must be at least 1000ms")
        return v

    @field_validator("delay_max_ms")
    @classmethod
    def validate_delay_order(cls, v: int, info) -> int:
        """Validate delay_max_ms is greater than or equal to delay_min_ms."""
        if "delay_min_ms" in info.data and v < info.data["delay_min_ms"]:
            raise ValueError("delay_max_ms must be >= delay_min_ms")
        return v


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
