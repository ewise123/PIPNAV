"""Logging configuration — writes to ~/.pipnav/debug.log."""

import logging
from pathlib import Path

_logger: logging.Logger | None = None


def setup_logging() -> logging.Logger:
    """Configure and return the pipnav logger. Idempotent."""
    global _logger
    if _logger is not None:
        return _logger

    log_path = Path.home() / ".pipnav" / "debug.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("pipnav")
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        handler = logging.FileHandler(log_path)
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        logger.addHandler(handler)

    _logger = logger
    return logger


def get_logger() -> logging.Logger:
    """Return the pipnav logger, initializing if needed."""
    if _logger is None:
        return setup_logging()
    return _logger
