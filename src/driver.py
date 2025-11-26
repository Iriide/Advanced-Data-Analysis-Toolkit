import argparse
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# Import the orchestrator
from visualizer.llm_data_visualizer import LLMDataVisualizer
from server.api import DummyServer
from core.logger import configure_logging, get_logger
import logging


def main() -> None:
    parser = argparse.ArgumentParser(description="LLM Data Visualizer Driver")
    parser.add_argument(
        "--mode",
        type=str,
        choices=["cli", "server"],
        default="cli",
        help="Run mode: 'cli' for visualizer, 'server' to run the server.",
    )
    parser.add_argument(
        "--question",
        type=str,
        help="Question to analyze. Does not apply in server mode.",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default="data/chinook.db",
        help="Path to database. Does not apply in server mode.",
    )
    parser.add_argument(
        "--plot-schema",
        action="store_true",
        help="Generate schema SVG. Does not apply in server mode.",
    )
    parser.add_argument(
        "--describe",
        action="store_true",
        help="Describe (i.e. summarize) the database. Does not apply in server mode.",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity (use -v, -vv for more verbose).",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="Optional path to write logs to a file.",
    )
    args = parser.parse_args()

    # Map verbosity count to logging level:
    # 0 (default) -> INFO (useful default for CLI),
    # 1 (-v) -> DEBUG (developer level)
    # 2+ (-vv) -> DEBUG with more verbosity enabled by downstream modules if needed
    # This choice keeps normal runs informative while -v gives detailed debug output.
    if hasattr(args, "verbose"):
        if args.verbose == 0:
            level = logging.INFO
        else:
            level = logging.DEBUG
    else:
        level = logging.INFO

    # Allow explicit override via env var LOG_LEVEL
    configure_logging(level=level, log_file=args.log_file)
    logger = get_logger(__name__)

    if args.mode == "server":
        logger.info("--- Starting Server ---")
        try:
            server = DummyServer()
            server.start()
        except KeyboardInterrupt:
            logger.info("Server stopped by user.")
        return

    # CLI Mode
    db_path = Path(args.db_path)
    if not db_path.exists():
        logger.error("Database not found at %s", db_path)
        return
    visualizer = LLMDataVisualizer(db_path=db_path)

    # 1. Schema Plot
    if args.plot_schema:
        logger.info("--- Generating Schema Plot ---")
        schema_path = visualizer.plot_schema()
        if schema_path:
            logger.info("Schema saved to: %s", schema_path)
            # Optional: Display if libraries exist
            try:
                import cairosvg
                from PIL import Image
                import io

                png_bytes = cairosvg.svg2png(url=str(schema_path), scale=2)
                image = Image.open(io.BytesIO(png_bytes))
                plt.imshow(image)
                plt.axis("off")
                plt.show()
            except ImportError:
                logger.warning("Cairosvg/PIL not installed, skipping schema display.")

    # 2. Question Processing
    if args.question:
        q = args.question
        if q == "random":
            sample_questions = [
                "Give me a count of employees grouped by age?",
                "What are the top 10 most used genres?",
                "Which genre generated the highest revenue?",
                "What are the revenues and the number of tracks sold for each genre?",
            ]
            q = np.random.choice(sample_questions)
            print(f"No question provided. Using random sample: '{q}'")

        logger.info("\n--- Analyzing: %s ---", q)
        visualizer.question_to_plot(q, show=True)

    # 3. Database Description
    if args.describe:
        logger.info("\n--- Database Description ---")
        description_df = visualizer.describe_database()
        logger.info("\n%s", description_df.to_markdown())


if __name__ == "__main__":
    main()
