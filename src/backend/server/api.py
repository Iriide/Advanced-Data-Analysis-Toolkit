"""FastAPI server providing an API for LLM-based data visualization."""

import os
import logging
import textwrap
from pathlib import Path
from typing import Optional, Any, Dict, AsyncGenerator, Tuple

import numpy as np
import pandas as pd
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.concurrency import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.visualizer.llm_data_visualizer import LLMDataVisualizer
from backend.visualizer.services.plotting import save_plot

# --- Constants ---
DEFAULT_DB_PATH = Path("data/chinook.db")
DEFAULT_MODEL = "gemma-3-4b-it"
SUPPORTED_FORMATS = ("png", "svg", "pdf")

logger = logging.getLogger("uvicorn")


# -- Pydantic models for request payload validation --
class SettingsPayload(BaseModel):
    database_path: str = Field(..., min_length=1)
    database_type: str = Field(default="sqlite")
    model: Optional[str] = None


class QuestionPayload(BaseModel):
    question: str = Field(..., min_length=1)


def _clean_folder(folder_path: Path, recursive: bool = False) -> None:
    """Remove all files in the specified folder."""
    if not folder_path.exists() or not folder_path.is_dir():
        return

    for item in folder_path.iterdir():
        if item.is_file():
            item.unlink()
        elif item.is_dir() and recursive:
            _clean_folder(item, recursive=True)
            item.rmdir()

    logger.info(f"Cleaned folder: {folder_path}")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Run startup and shutdown hooks for the FastAPI application."""

    # --- Startup Logic ---
    logger.info("Server starting up...")

    yield

    # --- Shutdown Logic ---
    logger.info("Server shutting down...")
    plots_dir = Path(__file__).parents[2] / "frontend/static/plots"
    _clean_folder(plots_dir, recursive=True)


app = FastAPI(lifespan=lifespan, title="Advanced Data Analysis Toolkit API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ROOT_SRC = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = ROOT_SRC / "frontend"
STATIC_DIR = FRONTEND_DIR / "static"

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    logger.info(f"Mounted static files from {STATIC_DIR} at /static")
else:
    logger.warning(
        f"Static directory {STATIC_DIR} not found; not mounting static files"
    )

VISUALIZER: Optional[LLMDataVisualizer] = None

# --- Helper functions ---


def _normalize_image_format(fmt: Optional[str], default: str = "svg") -> str:
    """Normalize and validate the requested output format."""
    fmt2 = (fmt or default).lower()
    return fmt2 if fmt2 in SUPPORTED_FORMATS else default


def _plot_question(
    visualizer: LLMDataVisualizer,
    question: str,
    retry_count: int = 3,
    dataframe: Optional[pd.DataFrame] = None,
    fmt: str = "svg",
) -> Tuple[Any, bool]:
    """Generate plot axes for a question and return (axes, should_plot)."""
    ax, should_plot = visualizer.question_to_plot(
        question, retry_count=retry_count, show=False, verbosity=1, dataframe=dataframe
    )
    image_url = save_plot(ax, fmt=fmt, plots_dir=STATIC_DIR / "plots")

    if ax is None:
        raise RuntimeError("No axes generated for the question result")
    return image_url, bool(should_plot)


def _dataframe_to_json(df: Optional[pd.DataFrame]) -> Dict[str, Any]:
    """Convert a DataFrame into a JSON-serializable payload."""
    if df is None or df.empty:
        return {"columns": [], "rows": []}
    df2 = df.reset_index()
    rows = df2.replace({np.nan: None}).to_dict(orient="records")
    return {"columns": df2.columns.tolist(), "rows": rows}


def _get_visualizer() -> LLMDataVisualizer:
    """Return a singleton `LLMDataVisualizer` instance, lazily initialized."""
    global VISUALIZER
    if VISUALIZER is None:
        model = os.environ.get("LLM_DATA_VISUALIZER_MODEL")
        if not model:
            logger.error(
                "LLM_DATA_VISUALIZER_MODEL environment variable not set. Please set this variable to specify "
                "the LLM model to use. Example: export LLM_DATA_VISUALIZER_MODEL='gpt-3.5-turbo'"
            )
        logger.info(
            f"Initializing visualizer with DB: {DEFAULT_DB_PATH}, model: {model or DEFAULT_MODEL}"
        )
        VISUALIZER = LLMDataVisualizer(
            database_path=DEFAULT_DB_PATH,
            model=model or DEFAULT_MODEL,
        )
    return VISUALIZER


# --- API Endpoints ---


@app.get("/", response_class=FileResponse)
def serve_index() -> FileResponse:
    """Serve the frontend `index.html` file."""
    index_path = FRONTEND_DIR / "index.html"
    if not index_path.exists():
        logger.error(f"index.html not found at {index_path}")
        raise HTTPException(status_code=404, detail="index.html not found")
    return FileResponse(str(index_path), media_type="text/html")


@app.post("/settings")
def update_settings(payload: SettingsPayload) -> Dict[str, Any]:
    """Update database credentials / path and optionally model."""
    global VISUALIZER

    database_path = Path(payload.database_path)
    model = payload.model
    database_type = str(payload.database_type)
    logger.info(
        f"Updating settings: db={database_path}, type={database_type}, model={model}",
    )
    VISUALIZER = LLMDataVisualizer(
        database_path=database_path,
        database_type=database_type,
        model=model or DEFAULT_MODEL,
    )
    return {"status": "ok", "database_path": str(database_path)}


@app.get("/schema/image")
def get_schema_image() -> Response:
    """Return an image representing the DB schema."""
    visualizer = _get_visualizer()
    svg_path = visualizer.plot_schema()
    if svg_path and Path(svg_path).exists():
        content = Path(svg_path).read_bytes()
        return Response(content, media_type="image/svg+xml")
    else:
        logger.exception("Failed to generate schema image")
        raise HTTPException(status_code=500, detail="Failed to generate schema image")


@app.get("/describe")
def get_database_description() -> JSONResponse:
    """Return the database description as a JSON response."""
    visualizer = _get_visualizer()
    df = visualizer.describe_database()
    if df is None or df.empty:
        return JSONResponse(content={"rows": []})
    records = df.reset_index().to_dict(orient="records")
    return JSONResponse(content={"rows": records})


@app.post("/question")
def question_plot(payload: QuestionPayload, format: str = "svg") -> Response:
    """Answer a question and return a plot URL plus tabular results as JSON."""
    visualizer = _get_visualizer()
    question = payload.question
    fmt = _normalize_image_format(format, default="svg")

    df = visualizer.question_to_dataframe(question)
    image_url, should_plot = _plot_question(visualizer, question, 3, df, fmt)
    df_json = _dataframe_to_json(df)

    return JSONResponse(
        content={
            "df": df_json,
            "image_url": str(image_url),
            "should_plot": should_plot,
        }
    )


@app.get("/random-questions")
def random_questions(count: int = 10) -> JSONResponse:
    """Generate `count` random, interesting questions based on the DB schema."""
    visualizer = _get_visualizer()
    schema = visualizer.export_schema()
    prompt = textwrap.dedent(
        f"""
        You are a data analyst assistant.
        Based on the following database schema, generate {count} concise,
        diverse, and visually interesting natural-language questions
        that can be answered with data visualizations. Ensure the questions
        involve joining multiple tables where applicable and focus on generating
        plots that are clear and easy to interpret.

        Limit the data (the predicted row count) in the questions
        to ensure the visualizations are not overcrowded.
        For example, restrict the results to the top 5 or 10 items, or use filters
        to focus on specific subsets of the data.

        Avoid questions that require too much information to be displayed
        in a single plot, as the goal is to create readable and visually appealing
        visualizations.

        Schema:
        {schema}

        Provide exactly {count} questions, each on its own line, numbered sequentially.
        Do NOT produce SQL or overly complex queries.
        """
    )

    raw = visualizer._llm_client.generate_content(prompt, retry_count=3)
    text = raw.strip().strip("`").strip()
    lines = [
        line.strip().lstrip("-").lstrip("0123456789. ")
        for line in text.splitlines()
        if line.strip()
    ]
    questions = [line for line in lines if len(line) > 3][:count]

    return JSONResponse(content={"questions": questions})


if __name__ == "__main__":
    uvicorn.run("backend.server.api:app", host="0.0.0.0", port=8000, reload=False)
