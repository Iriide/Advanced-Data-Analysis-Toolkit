"""Command-line interface logic for non-server mode execution."""

import io
import logging
import numpy as np
import matplotlib.pyplot as plt
import cairosvg
from PIL import Image
from pathlib import Path
from backend.visualizer.services.plotting import save_plot
from backend.visualizer.llm_data_visualizer import LLMDataVisualizer
from backend.utils.logger import get_logger


SAMPLE_QUESTIONS = [
    "Give me a count of employees grouped by age?",
    "What are the top 10 most used genres?",
    "Which genre generated the highest revenue?",
    "What are the revenues and the number of tracks sold for each genre?",
]

logger: logging.Logger = get_logger(__name__)


def _convert_svg_to_image(svg_path: Path) -> Image.Image:
    """Convert an SVG file to a PIL Image."""
    png_bytes = cairosvg.svg2png(url=str(svg_path), scale=2)
    return Image.open(io.BytesIO(png_bytes))


def _display_image(image: Image.Image) -> None:
    """Display a PIL Image using matplotlib."""
    plt.imshow(image)
    plt.axis("off")
    plt.show()


def _select_question(question: str) -> str:
    """Select a random sample question if requested."""
    if question == "input":
        user_input = input("Please enter your question: ")
        question = user_input.strip()
    if question == "random":
        selected: str = np.random.choice(SAMPLE_QUESTIONS)
        print(f"Using random sample: '{selected}'")
        return selected
    if question is None or question.strip() == "":
        raise ValueError("No question provided for analysis.")
    return question.strip()


def generate_and_display_schema(visualizer: LLMDataVisualizer) -> None:
    """Generate the database schema visualization and display it."""
    logger.info("--- Generating Schema Plot ---")
    schema_path = visualizer.plot_schema()
    if not schema_path:
        return

    logger.info(f"Schema saved to: {schema_path}")
    image = _convert_svg_to_image(schema_path)
    _display_image(image)


def analyze_question(question: str, visualizer: LLMDataVisualizer) -> None:
    """Analyze a question and generate a corresponding visualization."""
    selected_question = _select_question(question)
    logger.info(f"\n--- Analyzing: {selected_question} ---")
    ax, _ = visualizer.question_to_plot(selected_question, show=True)
    save_plot(ax, format="svg")


def print_database_description(visualizer: LLMDataVisualizer) -> None:
    """Display a summary description of the database."""
    logger.info("\n--- Database Description ---")
    description_dataframe = visualizer.describe_database()
    logger.info(f"\n{description_dataframe.to_markdown()}")
