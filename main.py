import asyncio
import logging

from src.analysis import analyze, generate_charts, print_summary, to_dataframe
from src.config import Config
from src.export import export_csv, export_json
from src.logging_config import setup_logging
from src.scraper import EfoodScraper

logger = logging.getLogger("efood")


async def main():
    # Initialize logging
    setup_logging(level=logging.INFO)

    logger.info("=" * 50)
    logger.info("E-Food.gr Pizza VFM Scraper")
    logger.info("=" * 50)

    config = Config()
    logger.info(f"Location: Volos (Address ID: {config.user_address})")
    logger.info(f"Headless: {config.headless}")
    logger.info(f"Max restaurants: {config.max_restaurants or 'All'}")

    scraper = EfoodScraper(config)
    result = await scraper.scrape()

    # Export
    df = to_dataframe(result)
    if not df.empty:
        export_csv(df, "output/pizza_vfm.csv")
        export_json(result, "output/pizza_vfm.json")

        # Analysis
        stats = analyze(df)
        generate_charts(df)
        print_summary(stats)
    else:
        logger.warning("No deals found.")


if __name__ == "__main__":
    asyncio.run(main())
