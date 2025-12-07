from pathlib import Path
from backend.visualizer.llm_data_visualizer import LLMDataVisualizer
from backend.visualizer.services.logger import get_logger

logger = get_logger(__name__)


class DummyServer:
    def __init__(self) -> None:
        database_path = Path("data/chinook.db")
        logger.info("Server initialized. Loading visualizer for DB: %s", database_path)
        self.viz = LLMDataVisualizer(database_path=database_path)
        logger.debug("Visualizer instance created successfully")

    def start(self) -> None:
        logger.info("Server started (Dummy).")
        logger.info("Visualizer loaded successfully.")
        logger.info("DB Description Head:\n%s", self.viz.describe_database().head())


if __name__ == "__main__":
    server = DummyServer()
    server.start()
