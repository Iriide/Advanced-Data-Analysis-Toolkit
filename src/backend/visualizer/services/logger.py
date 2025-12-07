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
    return logging.getLogger(name)
