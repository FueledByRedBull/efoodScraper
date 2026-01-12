import asyncio

from src.analysis import analyze, generate_charts, print_summary, to_dataframe
from src.config import Config
from src.export import export_csv, export_json
from src.scraper import EfoodScraper


async def main():
    print("=" * 50)
    print("E-Food.gr Pizza VFM Scraper")
    print("=" * 50)

    config = Config()
    print(f"Location: Volos (Address ID: {config.user_address})")
    print(f"Headless: {config.headless}")
    print(f"Max restaurants: {config.max_restaurants or 'All'}")
    print()

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
        print("No deals found.")


if __name__ == "__main__":
    asyncio.run(main())
