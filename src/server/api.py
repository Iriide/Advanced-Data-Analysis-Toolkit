from pathlib import Path
from visualizer.llm_data_visualizer import LLMDataVisualizer
from core.logger import get_logger

logger = get_logger(__name__)


class DummyServer:
    def __init__(self) -> None:
        db_path = Path("data/chinook.db")
        logger.info("Server initialized. Loading visualizer for DB: %s", db_path)
        try:
            self.viz = LLMDataVisualizer(db_path=db_path)
            logger.debug("Visualizer instance created successfully")
        except Exception as e:
            logger.exception("Failed to initialize visualizer: %s", e)
            raise

    def start(self) -> None:
        logger.info("Server started (Dummy).")
        logger.info("Visualizer loaded successfully.")
        logger.info("DB Description Head:\n%s", self.viz.describe_database().head())


if __name__ == "__main__":
    server = DummyServer()
    server.start()
