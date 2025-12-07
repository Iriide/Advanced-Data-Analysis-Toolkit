import argparse
import io
import logging
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
from pathlib import Path
from backend.visualizer.llm_data_visualizer import LLMDataVisualizer
from backend.server.api import DummyServer
from backend.visualizer.services.logger import configure_logging, get_logger

logger: logging.Logger

SAMPLE_QUESTIONS = [
    "Give me a count of employees grouped by age?",
    "What are the top 10 most used genres?",
    "Which genre generated the highest revenue?",
    "What are the revenues and the number of tracks sold for each genre?",
]


def create_argument_parser() -> argparse.ArgumentParser:
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
    return parser


def parse_arguments() -> argparse.Namespace:
    return create_argument_parser().parse_args()


def determine_logging_level(arguments: argparse.Namespace) -> int:
    if hasattr(arguments, "verbose") and arguments.verbose > 0:
        return logging.DEBUG
    return logging.INFO


def initialize_logging(arguments: argparse.Namespace) -> None:
    global logger
    logging_level = determine_logging_level(arguments)
    configure_logging(level=logging_level, log_file=arguments.log_file)
    logger = get_logger(__name__)


def run_server() -> None:
    logger.info("--- Starting Server ---")
    try:
        server = DummyServer()
        server.start()
    except KeyboardInterrupt:
        logger.info("Server stopped by user.")
    return


def validate_database_path(arguments: argparse.Namespace) -> Path:
    database_path = Path(arguments.db_path)
    if not database_path.exists():
        raise FileNotFoundError(f"Database not found at {database_path}")
    return database_path


def convert_svg_to_image(svg_path: Path) -> Image.Image:
    import cairosvg

    png_bytes = cairosvg.svg2png(url=str(svg_path), scale=2)
    return Image.open(io.BytesIO(png_bytes))


def display_image(image: Image.Image) -> None:
    plt.imshow(image)
    plt.axis("off")
    plt.show()


def generate_and_display_schema(visualizer: LLMDataVisualizer) -> None:
    logger.info("--- Generating Schema Plot ---")
    schema_path = visualizer.plot_schema()
    if not schema_path:
        return

    logger.info("Schema saved to: %s", schema_path)
    image = convert_svg_to_image(schema_path)
    display_image(image)


def select_question(question: str) -> str:
    if question == "random":
        selected: str = np.random.choice(SAMPLE_QUESTIONS)
        print(f"Using random sample: '{selected}'")
        return selected
    return question


def analyze_question(question: str, visualizer: LLMDataVisualizer) -> None:
    selected_question = select_question(question)
    logger.info("\n--- Analyzing: %s ---", selected_question)
    visualizer.question_to_plot(selected_question, show=True)


def display_database_description(visualizer: LLMDataVisualizer) -> None:
    logger.info("\n--- Database Description ---")
    description_dataframe = visualizer.describe_database()
    logger.info("\n%s", description_dataframe.to_markdown())


def run_cli_mode(arguments: argparse.Namespace) -> None:
    database_path = validate_database_path(arguments)
    visualizer = LLMDataVisualizer(database_path=database_path)

    if arguments.plot_schema:
        generate_and_display_schema(visualizer)
    if arguments.question:
        analyze_question(arguments.question, visualizer)
    if arguments.describe:
        display_database_description(visualizer)


def main() -> None:
    arguments = parse_arguments()
    initialize_logging(arguments)

    if arguments.mode == "server":
        run_server()
        return

    run_cli_mode(arguments)


if __name__ == "__main__":
    main()
