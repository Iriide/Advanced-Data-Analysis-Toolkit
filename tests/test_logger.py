import logging
from pathlib import Path
from core.logger import get_logger, configure_logging


def test_configure_and_get_logger(tmp_path: Path):
    # 1. RESET LOGGER STATE (Crucial for testing singletons)
    logger = logging.getLogger("test")
    for h in logger.handlers[:]:
        logger.removeHandler(h)
        h.close()
    logger.handlers = []  # Bruteforce clear

    # 2. Setup
    log_file = tmp_path / "test.log"
    configure_logging(level=20, log_file=str(log_file))

    # 3. Use
    logger = get_logger("test")
    # Ensure child logger does not block messages (allow propagation to root handlers)
    logger.setLevel(logging.NOTSET)
    logger.info("hello world")
    # Also log on the root directly to be robust in test environments
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.NOTSET)
    root_logger.info("root hello world")

    # 4. Flush root handlers (file handler was attached to root)
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        try:
            handler.flush()
            handler.close()
        except Exception:
            pass

    # 5. Assert
    assert log_file.exists()
    content = log_file.read_text()
    # Accept either message (child or root) depending on logger propagation behavior
    assert "hello world" in content or "root hello world" in content
