"""
Logging configuration for the scraper.
"""
import logging
import sys
from pathlib import Path


def setup_logging(
    level: int = logging.INFO,
    log_file: str | None = None,
) -> logging.Logger:
    """
    Configure and return the root logger.

    Args:
        level: Logging level (default: INFO)
        log_file: Optional path to log file

    Returns:
        Configured logger
    """
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # Root logger for efood
    logger = logging.getLogger("efood")
    logger.setLevel(level)

    # Avoid adding duplicate handlers
    if not logger.handlers:
        logger.addHandler(console_handler)

    # Optional file handler
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
