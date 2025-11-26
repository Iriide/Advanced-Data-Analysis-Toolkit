import json
import re
import argparse
import pandas as pd
from pathlib import Path
from typing import Optional, Tuple
from matplotlib.axes import Axes

# Import Core Services
# Note: When running via driver.py, 'src' is in path.
from core.db_inspector import DBInspector
from core.llm_client import LLMClient
from core.plotting_engine import PlottingEngine
from core.logger import get_logger

logger = get_logger(__name__)


class LLMDataVisualizer:
    """
    Orchestrates the flow: Question -> SQL -> DataFrame -> Plot Params -> Visualization.
    """

    def __init__(
        self,
        db_path: "str | Path",
        db_type: str = "sqlite",
        model: str = "gemini-2.5-flash-lite",
        df_plot_parameters_file_path: Optional[Path] = None,
    ):
        self._db_path = db_path if isinstance(db_path, Path) else Path(db_path)
        self._db_type = db_type

        # Initialize Core Services
        self._db_inspector = DBInspector(self._db_path, db_type)
        self._llm_client = LLMClient(model)
        self._plotting_engine = PlottingEngine()

        # Load Configuration
        if df_plot_parameters_file_path is None:
            # Assumes config is at project_root/config/ relative to this file
            # src/visualizer/ -> src/ -> root/ -> config/
            root_dir = Path(__file__).resolve().parent.parent.parent
            df_plot_parameters_file_path = (
                root_dir / "config" / "df_plot_parameters.txt"
            )

        self._plot_parameters_txt = self._load_plot_parameters(
            df_plot_parameters_file_path
        )

    def _load_plot_parameters(self, path: Path) -> str:
        """Loads and sanitizes the plot parameters definition file."""
        if not path.exists():
            logger.warning("Config file not found at %s", path)
            return ""

        with open(path, "r") as f:
            plot_parameters = (
                f.read()
                .replace("\n        ", " - ")
                .replace("\n\n    ", " – ")
                .replace("\n\n", "\n")
            )

            for token in [
                "label",
                "int",
                "float",
                "bool",
                "str",
                "matplotlib axes object",
                "(2-|a )?tuple",
                "list",
                "sequence",
                "DataFrame",
            ]:
                plot_parameters = "\n".join(
                    [
                        re.sub(rf"^(\w+)({token})", r"\1, \2", line)
                        for line in plot_parameters.splitlines()
                    ]
                )
            return plot_parameters

    # --- PROMPT GENERATION ---

    def _construct_sql_prompt(self, question: str, schema: str) -> str:
        return f"""
        ```db-schema
        {schema}
        ```

        # Instructions

        Hello, knowing the schema, propose me sql query
        that will answer this question: {question}

        Note that I use {self._db_type}.
        Please make the result as informative and human readable as possible.

        Please provide ONLY the sql query, nothing else.
        """

    def _construct_plot_prompt(self, question: str, df: pd.DataFrame) -> str:
        return f"""
        ```df-plot-parameters
        {self._plot_parameters_txt}
        ```

        ```df-columns
        {df.columns.tolist()}
        ```

        ```df-index
        {df.index}
        ```

        ```df-head
        {df.head().to_string()}
        ```

        **Question**: {question}

        # Instructions

        Hello, knowing the data and the question,
        prepare me parameters dictionary (json)
        that will used for df.plot() as kwargs.
        Only use parameters from the df-plot-parameters that are relevant.

        The plot needs to be nice and informative.
        If there is more than one column, the plot may be complex
        (e.g. stacked plots, subplots, etc).

        Please provide ONLY the flat json, nothing else.

        Additionally, add a 'should_plot' key with boolean value
        indicating whether plotting is appropriate for this data.
        """

    # --- PUBLIC API ---

    def describe_database(self) -> pd.DataFrame:
        return self._db_inspector.describe_database()

    def export_schema(self) -> str:
        return self._db_inspector.export_schema()

    def plot_schema(self) -> Optional[Path]:
        return self._db_inspector.plot_schema()

    def question_to_df(self, question: str, retries: int = 3) -> pd.DataFrame:
        """Converts natural language question to DataFrame."""
        schema = self._db_inspector.export_schema()
        prompt = self._construct_sql_prompt(question, schema)

        raw_response = self._llm_client.generate_content(prompt, retries)
        sql_query = self._llm_client.clean_markdown_block(raw_response, "sql")
        # Log a concise summary for normal runs, full SQL at debug level
        if sql_query and len(sql_query) > 200:
            logger.info(
                "Generated SQL (truncated): %s...", sql_query[:200].replace("\n", " ")
            )
            logger.debug("Full generated SQL:\n%s", sql_query)
        else:
            logger.info("Generated SQL: %s", sql_query)

        # Execute and return
        try:
            df = self._db_inspector.run_query(sql_query)
            logger.info(
                "Query returned %d rows and %d columns", df.shape[0], df.shape[1]
            )
            logger.debug("Result preview:\n%s", df.head().to_markdown())
            return df
        except Exception as e:
            logger.exception("Failed to execute query: %s", e)
            raise

    def question_to_plot(
        self, question: str, retries: int = 3, show: bool = True, verbose: int = 1
    ) -> Tuple[Optional[Axes], bool]:
        """Full pipeline: Question -> Visual."""
        # 1. Get Data
        df = self.question_to_df(question, retries)
        logger.info("Dataframe shape: %s", df.shape)
        logger.debug("Dataframe head:\n%s", df.head().to_markdown())

        # 2. Get Plot Params
        prompt = self._construct_plot_prompt(question, df)
        raw_response = self._llm_client.generate_content(prompt, retries)
        json_str = self._llm_client.clean_markdown_block(raw_response, "json")

        try:
            params = json.loads(json_str)
            should_plot = params.pop("should_plot", False)
        except json.JSONDecodeError:
            logger.error("Failed to decode JSON: %s", json_str)
            should_plot = False
            params = {}

        # 3. Plot
        return self._plotting_engine.plot_data(df, params, should_plot, show, verbose)


if __name__ == "__main__":
    # Sample Usage within the module
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", type=str, default="data/chinook.db")
    args = parser.parse_args()

    logger.info("Initializing Visualizer...")
    viz = LLMDataVisualizer(Path(args.db_path))
    logger.info(viz.export_schema()[:100])
