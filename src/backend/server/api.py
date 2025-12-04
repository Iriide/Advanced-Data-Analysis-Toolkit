import numpy as np
from io import BytesIO
from pathlib import Path
from typing import Optional, Any, Iterable, Dict, AsyncGenerator
import uuid
import logging

from fastapi import FastAPI, HTTPException
from fastapi.concurrency import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.visualizer.llm_data_visualizer import LLMDataVisualizer
from backend.utils.logger import get_logger

logger = get_logger(__name__)
"""API server for the Advanced Data Analysis Toolkit.

This module exposes a small FastAPI app that serves the frontend
and provides endpoints for describing the database, generating
visualizations from natural-language questions, and updating
settings (database path / model).
"""


class SettingsPayload(BaseModel):
    db_path: str
    db_type: Optional[str] = "sqlite"
    model: Optional[str] = None


class QuestionPayload(BaseModel):
    question: str


logger = logging.getLogger("uvicorn")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # --- Startup Logic (if any) ---
    logger.info("Server starting up...")
    yield
    # --- Shutdown Logic (Runs when server stops) ---
    print("do widzenia")

    # Adjust path logic relative to THIS file location
    # You might need to adjust parents depending on where api.py sits
    plots_dir = Path(__file__).parents[2] / "frontend/static/plots"

    if plots_dir.exists() and plots_dir.is_dir():
        for plot_file in plots_dir.iterdir():
            if plot_file.is_file():
                plot_file.unlink()
        logger.info("All plots removed from %s", plots_dir)


app = FastAPI(lifespan=lifespan, title="Advanced Data Analysis Toolkit API")

# Allow requests from file:// or local frontend during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend static files (index.html + static/)
# Resolve the frontend directory relative to this file: src/backend/server -> src
ROOT_SRC = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = ROOT_SRC / "frontend"
STATIC_DIR = FRONTEND_DIR / "static"

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    logger.info("Mounted static files from %s at /static", STATIC_DIR)
else:
    logger.warning(
        "Static directory %s not found; not mounting static files", STATIC_DIR
    )


@app.get("/", response_class=FileResponse)
def serve_index() -> FileResponse:
    """Serve the frontend `index.html` file.

    Returns a `FileResponse` with the HTML content or raises
    `HTTPException(404)` if the file cannot be found.
    """
    index_path = FRONTEND_DIR / "index.html"
    if not index_path.exists():
        logger.error("index.html not found at %s", index_path)
        raise HTTPException(status_code=404, detail="index.html not found")
    return FileResponse(str(index_path), media_type="text/html")


# Global visualizer instance (simple single-process server)
_VIZ: Optional[LLMDataVisualizer] = None


def get_viz() -> LLMDataVisualizer:
    """Return a singleton `LLMDataVisualizer` instance.

    The visualizer is lazily initialized with a reasonable default
    database path when first requested.
    """
    global _VIZ
    if _VIZ is None:
        default_db = Path("data/chinook.db")
        logger.info("Initializing visualizer with default DB: %s", default_db)
        _VIZ = LLMDataVisualizer(db_path=default_db)
    return _VIZ


def fig_to_png_bytes(fig: Any) -> bytes:
    """Serialize a Matplotlib figure to PNG bytes.

    This is a thin wrapper around `fig_to_bytes(..., fmt='png')`.
    """
    return fig_to_bytes(fig, fmt="png")


def ax_to_png_bytes(ax: Any) -> bytes:
    # Accept Axes or iterable of Axes
    import matplotlib.pyplot as plt

    fig = None
    try:
        if hasattr(ax, "get_figure"):
            fig = ax.get_figure()
        elif isinstance(ax, Iterable):
            for item in ax:
                if hasattr(item, "get_figure"):
                    fig = item.get_figure()
                    break
        if fig is None:
            fig = plt.gcf()
        return fig_to_bytes(fig, fmt="png")
    finally:
        try:
            plt.close(fig)
        except Exception:
            plt.close("all")


def fig_to_bytes(fig: Any, fmt: str = "png") -> bytes:
    """Serialize a Matplotlib figure to bytes in the requested format.

    Supported formats: `png`, `svg`, `pdf`.
    The function returns the raw bytes for the saved figure.
    """
    buf = BytesIO()
    try:
        fmt = (fmt or "png").lower()
        if fmt not in ("png", "svg", "pdf"):
            fmt = "png"
        # bbox_inches for raster formats; for vector formats leave default
        save_kwargs = {"format": fmt}
        if fmt == "png":
            save_kwargs["bbox_inches"] = "tight"

        fig.savefig(buf, **save_kwargs)
        buf.seek(0)
        return buf.read()
    finally:
        try:
            import matplotlib.pyplot as plt

            plt.close(fig)
        except Exception:
            pass


def ax_to_bytes(ax: Any, fmt: str = "png") -> bytes:
    """Accept Axes or an iterable of Axes and serialize to bytes.

    Returns the serialized bytes in the requested `fmt`.
    """
    import matplotlib.pyplot as plt

    fig = None
    try:
        if hasattr(ax, "get_figure"):
            fig = ax.get_figure()
        elif isinstance(ax, Iterable):
            for item in ax:
                if hasattr(item, "get_figure"):
                    fig = item.get_figure()
                    break
        if fig is None:
            fig = plt.gcf()
        return fig_to_bytes(fig, fmt=fmt)
    finally:
        try:
            plt.close(fig)
        except Exception:
            plt.close("all")


@app.post("/settings")
def update_settings(payload: SettingsPayload) -> Dict[str, Any]:
    """Update database credentials / path and optionally model.

    Example payload: { "db_path": "data/chinook.db", "db_type": "sqlite" }
    Returns a dict confirming the new settings on success.
    """
    global _VIZ
    try:
        db_path = Path(payload.db_path)
        model = payload.model
        db_type = str(payload.db_type)
        logger.info(
            "Updating settings: db=%s, type=%s, model=%s",
            db_path,
            db_type,
            model,
        )
        _VIZ = LLMDataVisualizer(
            db_path=db_path,
            db_type=db_type,
            model=model or "gemini-2.5-flash-lite",
        )
        return {"status": "ok", "db_path": str(db_path)}
    except Exception as e:
        logger.exception("Failed to update settings: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/schema/image")
def get_schema_image() -> Response:
    """Return an image representing the DB schema.

    Tries to return an SVG when possible, otherwise returns a PNG image.
    """
    viz = get_viz()
    try:
        svg_path = viz.plot_schema()
        if svg_path is not None and Path(svg_path).exists():
            content = Path(svg_path).read_bytes()
            return Response(content, media_type="image/svg+xml")

        # Fallback: render schema text into a PNG image
        schema_text = viz.export_schema()
        import matplotlib.pyplot as plt

        fig = plt.figure(figsize=(8, 10))
        fig.patch.set_visible(False)
        plt.axis("off")
        plt.text(0, 1, schema_text, fontsize=8, va="top", family="monospace")
        png = fig_to_png_bytes(fig)
        return Response(png, media_type="image/png")
    except Exception as e:
        logger.exception("Failed to generate schema image: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/describe")
def get_db_description() -> JSONResponse:
    """Return the database description as a JSON response.

    The response content contains a `rows` key with an array of
    table/column description objects.
    """
    viz = get_viz()
    try:
        df = viz.describe_database()
        if df is None or df.empty:
            return JSONResponse(content={"rows": []})
        # Reset index so table/column become columns
        df2 = df.reset_index()
        records = df2.to_dict(orient="records")
        return JSONResponse(content={"rows": records})
    except Exception as e:
        logger.exception("Failed to describe database: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/question")
def question_plot(payload: QuestionPayload, format: str = "svg") -> Response:
    """Accept a question and return the generated plot image.

    Query param `format` supports: `png`, `svg`, `pdf`. The endpoint
    returns a `Response` with the appropriate content type.
    """
    viz = get_viz()
    try:
        # 1) get dataframe (as pandas DataFrame)
        df = viz.question_to_df(payload.question)

        # 2) build plot (axes) -- do not show
        ax, should_plot = viz.question_to_plot(payload.question, show=False, verbose=1)
        if ax is None:
            raise RuntimeError("No axes generated for the question result")

        fmt = (format or "svg").lower()
        if fmt not in ("png", "svg", "pdf"):
            fmt = "svg"

        # 3) serialize image bytes
        img_bytes = ax_to_bytes(ax, fmt=fmt)

        # 4) save image into frontend static plots directory so clients can fetch by URL
        plots_dir = STATIC_DIR / "plots"
        plots_dir.mkdir(parents=True, exist_ok=True)
        ext = "svg" if fmt == "svg" else ("pdf" if fmt == "pdf" else "png")
        filename = f"plot_{uuid.uuid4().hex}.{ext}"
        file_path = plots_dir / filename
        file_path.write_bytes(img_bytes)

        image_url = f"/static/plots/{filename}"

        # 5) convert DataFrame to JSON-serializable structure
        if df is None or df.empty:
            records = []
            columns = []
        else:
            df2 = df.reset_index()
            records = df2.replace({np.nan: None}).to_dict(orient="records")
            columns = df2.columns.tolist()

        return JSONResponse(
            content={
                "df": {"columns": columns, "rows": records},
                "image_url": image_url,
                "should_plot": bool(should_plot),
            }
        )
    except Exception as e:
        logger.exception("Failed to generate plot for question: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/random-questions")
def random_questions(count: int = 10) -> JSONResponse:
    """Generate `count` random, interesting questions based on the DB schema.

    Uses the internal LLM client to propose natural-language questions
    that could be used to create visualizations. Returns a JSON
    response with a `questions` list.
    """
    viz = get_viz()
    try:
        schema = viz.export_schema()
        prompt = f"""
        You are a data analyst assistant.
        Given the following database schema, generate {count} concise,
        diverse and interesting natural-language questions
        that could be asked about the data.
        The questions should utilize joining multiple tables
        and ask the questions that the answer could be plotted nicely.
        Number each question and provide them as plain text lines. Do NOT produce SQL.

        Schema:
        {schema}

        Provide exactly {count} questions if possible, each on its own line.
        """

        raw = viz._llm_client.generate_content(prompt, retries=3)
        # basic cleanup: strip fences and split lines
        text = raw.strip().strip("`").strip()
        lines = [
            line.strip().lstrip("-").lstrip("0123456789. ")
            for line in text.splitlines()
            if line.strip()
        ]
        # keep non-empty and limit
        questions = [line for line in lines if len(line) > 3][:count]
        # fallback: if not enough, repeat a prompt to get simpler output
        if len(questions) < count:
            # try splitting by double newlines
            parts = [p.strip() for p in text.split("\n\n") if p.strip()]
            for p in parts:
                for line in p.splitlines():
                    s = line.strip()
                    if s and s not in questions:
                        questions.append(s)
                    if len(questions) >= count:
                        break
                if len(questions) >= count:
                    break

        return JSONResponse(content={"questions": questions})
    except Exception as e:
        logger.exception("Failed to generate random questions: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.server.api:app", host="0.0.0.0", port=8000, reload=False)
