import logging
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from .models import ScrapeResult

logger = logging.getLogger("efood.analysis")


def to_dataframe(result: ScrapeResult) -> pd.DataFrame:
    """Convert scrape results to a flat DataFrame."""
    rows = []
    for restaurant in result.restaurants:
        for deal in restaurant.deals:
            rows.append(
                {
                    "restaurant": restaurant.name[:40],
                    "rating": restaurant.rating,
                    "deal": deal.name,
                    "quantity": deal.quantity,
                    "size_cm": deal.size_cm,
                    "price": deal.price,
                    "total_area": deal.vfm.total_area_cm2,
                    "area_per_euro": deal.vfm.area_per_euro,
                    "vfm_index": deal.vfm.vfm_index,
                }
            )
    return pd.DataFrame(rows)


def analyze(df: pd.DataFrame) -> dict:
    """Generate summary statistics."""
    if df.empty:
        return {}

    # Filter out rows with NaN vfm_index
    valid_df = df.dropna(subset=["vfm_index"])
    if valid_df.empty:
        return {}

    # Categorized Top Deals
    top_deals_by_qty = {}
    for qty in [2, 3, 4]:
        deals = valid_df[valid_df["quantity"] == qty].nlargest(10, "vfm_index")
        top_deals_by_qty[qty] = deals[
            ["restaurant", "rating", "deal", "vfm_index", "area_per_euro"]
        ].to_dict("records")

    return {
        "total_restaurants": valid_df["restaurant"].nunique(),
        "total_deals": len(valid_df),
        "avg_vfm": round(valid_df["vfm_index"].mean(), 2),
        "best_deal": valid_df.loc[valid_df["vfm_index"].idxmax()].to_dict(),
        "worst_deal": valid_df.loc[valid_df["vfm_index"].idxmin()].to_dict(),
        "top_deals_by_qty": top_deals_by_qty,
    }


def generate_charts(df: pd.DataFrame, output_dir: str = "output/charts") -> None:
    """Generate analysis charts."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # VFM Distribution
    fig, ax = plt.subplots(figsize=(10, 6))
    df["vfm_index"].hist(bins=20, ax=ax, edgecolor="black")
    ax.set_title("VFM Index Distribution")
    ax.set_xlabel("VFM (cm²/€)")
    ax.set_ylabel("Count")
    fig.savefig(f"{output_dir}/vfm_distribution.png", dpi=150)
    plt.close(fig)

    # Top restaurants by average VFM
    fig, ax = plt.subplots(figsize=(12, 6))
    rest_avg = df.groupby("restaurant")["vfm_index"].mean().sort_values(ascending=True)
    rest_avg.plot(kind="barh", ax=ax)
    ax.set_title("Average VFM by Restaurant")
    ax.set_xlabel("VFM Index")
    fig.tight_layout()
    fig.savefig(f"{output_dir}/restaurant_comparison.png", dpi=150)
    plt.close(fig)

    # Top 10 deals chart - updated to show generic top 10 for visualization
    fig, ax = plt.subplots(figsize=(12, 6))
    top10 = df.nlargest(10, "vfm_index")
    ax.barh(top10["deal"].str[:30], top10["vfm_index"])
    ax.set_title("Top 10 Best Value Deals (All Categories)")
    ax.set_xlabel("VFM Index")
    fig.tight_layout()
    fig.savefig(f"{output_dir}/top10_deals.png", dpi=150)
    plt.close(fig)

    logger.info(f"Charts saved to {output_dir}/")


def print_summary(stats: dict) -> None:
    """Print analysis summary to console."""
    if not stats:
        logger.info("No data to summarize.")
        return

    logger.info("=" * 50)
    logger.info("SCRAPING SUMMARY")
    logger.info("=" * 50)
    logger.info(f"Total Restaurants: {stats['total_restaurants']}")
    logger.info(f"Total Deals: {stats['total_deals']}")
    logger.info(f"Average VFM: {stats['avg_vfm']} cm2/EUR")
    logger.info(f"Best Deal: {stats['best_deal']['deal'][:50]}")
    logger.info(f"  VFM: {stats['best_deal']['vfm_index']} cm2/EUR")

    # Print categorized deals
    for qty in [2, 3, 4]:
        deals = stats["top_deals_by_qty"].get(qty, [])
        if not deals:
            continue

        logger.info(f"Top 10 Deals with {qty} Pizzas:")
        for i, deal in enumerate(deals, 1):
            logger.info(f"  {i}. {deal['restaurant']} ({deal.get('rating', 'N/A')}) - {deal['deal'][:50]} : {deal['area_per_euro']} cm2/EUR (VFM: {round(deal['vfm_index'], 2)})")
