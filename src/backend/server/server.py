import os
import logging
import argparse
import subprocess
import sys
import threading
from time import sleep
import uvicorn
from backend.utils.logger import get_logger
from backend.server.api import app as server_api_app

logger: logging.Logger = get_logger(__name__)


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
            server_api_app,
            host="0.0.0.0",
            port=arguments.port,
            reload=arguments.dev,
        )

    except KeyboardInterrupt:
        logger.info("Server stopped by user.")
    return
