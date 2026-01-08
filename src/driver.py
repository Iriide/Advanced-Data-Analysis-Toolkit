"""Application entry point that dispatches to server or CLI mode."""

import argparse
import logging
from backend.utils.logger import configure_logging, get_logger
from backend.cli.cli import run_cli
from backend.server.server import run_server

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


def main() -> None:
    """Entry point for the application."""
    arguments = parse_arguments()
    initialize_logging(arguments)

    if arguments.mode == "server":
        run_server(arguments)
    else:
        run_cli(arguments)


if __name__ == "__main__":
    main()
