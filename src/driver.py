"""Application entry point that dispatches to server or CLI mode."""

import argparse
import os
import logging
import uvicorn
import subprocess
import sys
import threading
from time import sleep
from pathlib import Path
from backend.visualizer.llm_data_visualizer import LLMDataVisualizer
from backend.utils.logger import configure_logging, get_logger
from backend.cli.cli import (
    generate_and_display_schema,
    analyze_question,
    print_database_description,
)

logger: logging.Logger


def _parse_cli_arguments(parser: argparse.ArgumentParser, postfix: str) -> None:
    """Add CLI-specific command-line arguments to the parser."""
    parser.add_argument(
        "--question",
        type=str,
        help="Question to analyze." + postfix,
    )
    parser.add_argument(
        "--database-path",
        type=str,
        default="data/chinook.db",
        help="Path to database." + postfix,
    )
    parser.add_argument(
        "--plot-schema",
        action="store_true",
        help="Generate schema SVG." + postfix,
    )
    parser.add_argument(
        "--describe",
        action="store_true",
        help="Describe (i.e. summarize) the database." + postfix,
    )


def _parse_server_arguments(parser: argparse.ArgumentParser, postfix: str) -> None:
    """Add server-specific command-line arguments to the parser."""
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Enable server reloading." + postfix,
    )
    parser.add_argument(
        "--open-browser",
        action="store_true",
        help="Open the server in a web browser after starting." + postfix,
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to run the server on." + postfix,
    )


def create_argument_parser() -> argparse.ArgumentParser:
    """Create and configure the main argument parser."""
    parser = argparse.ArgumentParser(description="LLM Data Visualizer Driver")

    parser.add_argument(
        "--mode",
        type=str,
        choices=["cli", "server"],
        default="cli",
        help="Run mode: 'cli' for visualizer, 'server' to run the server.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gemma-3-4b-it",
        help="LLM model to use (e.g., gemma-3-4b-it, gemini-2.5-flash).",
    )
    parser.add_argument(
        "-v",
        "--verbosity",
        action="count",
        default=0,
        help="Increase verbosity (use -v, -vv for more verbosity).",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="Optional path to write logs to a file.",
    )

    _parse_cli_arguments(parser, " (CLI mode only).")
    _parse_server_arguments(parser, " (Server mode only).")

    return parser


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments and return the populated namespace."""
    return create_argument_parser().parse_args()


def determine_logging_level(arguments: argparse.Namespace) -> int:
    """Determine logging level based on verbosity flags."""
    if hasattr(arguments, "verbosity") and arguments.verbosity > 0:
        return logging.DEBUG
    return logging.INFO


def initialize_logging(arguments: argparse.Namespace) -> None:
    """Initialize application logging configuration."""
    global logger
    logging_level = determine_logging_level(arguments)
    configure_logging(level=logging_level, log_file=arguments.log_file)
    logger = get_logger(__name__)


def _open_browser(port: int, delay: int = 3) -> None:
    """Open the default web browser to the local server after an optional delay."""
    if delay and delay > 0:
        sleep(delay)
    browser_opened = subprocess.call(
        [
            sys.executable,
            "-c",
            f"import webbrowser; webbrowser.open('http://localhost:{port}')",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if browser_opened == 0:
        logger.info(f"Opened web browser to http://localhost:{port}")
    else:
        logger.warning("Failed to open web browser automatically.")


def run_server(arguments: argparse.Namespace) -> None:
    """Start the FastAPI server using uvicorn."""
    logger.info("--- Starting Server ---")

    try:
        if arguments.open_browser:
            threading.Thread(target=_open_browser, args=(arguments.port,)).start()

        os.environ["LLM_DATA_VISUALIZER_MODEL"] = arguments.model

        uvicorn.run(
            "backend.server.api:app",
            host="0.0.0.0",
            port=arguments.port,
            reload=arguments.dev,
        )

    except KeyboardInterrupt:
        logger.info("Server stopped by user.")
    return


def _validate_database_path(database_path: Path) -> Path:
    """Validate that the database path exists and return it as a Path."""
    if not database_path.exists():
        raise FileNotFoundError(f"Database not found at {database_path}")
    return database_path


def run_cli_mode(arguments: argparse.Namespace) -> None:
    """Execute the application in CLI mode."""
    database_path = _validate_database_path(Path(arguments.database_path))
    visualizer = LLMDataVisualizer(
        database_path=database_path,
        model=arguments.model,
    )

    if arguments.plot_schema:
        generate_and_display_schema(visualizer)
    if arguments.question:
        analyze_question(arguments.question, visualizer)
    if arguments.describe:
        print_database_description(visualizer)


def main() -> None:
    """Entry point for the application."""
    arguments = parse_arguments()
    initialize_logging(arguments)

    if arguments.mode == "server":
        run_server(arguments)
        return

    run_cli_mode(arguments)


if __name__ == "__main__":
    main()
