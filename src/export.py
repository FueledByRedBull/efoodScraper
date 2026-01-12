import json
import logging
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import pandas as pd

from .models import ScrapeResult

logger = logging.getLogger("efood.export")


def export_csv(df: pd.DataFrame, filepath: str) -> None:
    """Export DataFrame to CSV."""
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    df.sort_values("vfm_index", ascending=False).to_csv(filepath, index=False)
    logger.info(f"CSV exported: {filepath}")


def export_json(result: ScrapeResult, filepath: str) -> None:
    """Export results to JSON."""
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)

    def serialize(obj):
        """Custom serializer for dataclasses and datetime."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        return obj

    data = asdict(result)
    Path(filepath).write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=serialize),
        encoding="utf-8",
    )
    logger.info(f"JSON exported: {filepath}")
