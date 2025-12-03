"""Logging helpers for the backend services.

Provide a simple `configure_logging` utility and a convenience
function to retrieve a named logger.
"""

import logging
from typing import Optional


DEFAULT_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


def configure_logging(
    level: int = logging.INFO, log_file: Optional[str] = None
) -> None:
    """Configure root logger for the application.

    Args:
        level: Logging level (e.g., logging.INFO, logging.DEBUG).
        log_file: Optional path to a log file. If provided, file handler is added.
    """
    handlers = [logging.StreamHandler()]
    logging.basicConfig(level=level, format=DEFAULT_LOG_FORMAT, handlers=handlers)

    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(DEFAULT_LOG_FORMAT))
        logging.getLogger().addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger with the given `name`.

    The returned logger will use the root configuration applied by
    `configure_logging` if it has been called.
    """
    return logging.getLogger(name)
