import json
import re
import argparse
import pandas as pd
import textwrap
from pathlib import Path
from typing import Any, Optional, Tuple
from matplotlib.axes import Axes
from backend.visualizer.services.db_inspector import DatabaseInspector
from backend.visualizer.services.llm_client import LLMClient
from backend.visualizer.services.plotting import PlottingEngine
from backend.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_PLOT_PARAMETERS_PATH = Path("config/df_plot_parameters.txt")
SQL_QUERY_LOG_TRUNCATION_LENGTH = 200


class LLMDataVisualizer:

    def __init__(
        self,
        database_path: Path,
        database_type: str = "sqlite",
        model: str = "gemma-3-4b-it",
        plot_parameters_file_path: Optional[Path] = None,
    ):
        self._database_path = self._validate_database_path(database_path)
        self._database_type = database_type
        self._database_inspector = DatabaseInspector(
            self._database_path, self._database_type
        )
        self._llm_client = LLMClient(model)
        self._plotting_engine = PlottingEngine()
        self._plot_parameters_text = self._load_plot_parameters(
            plot_parameters_file_path
        )

    def _validate_database_path(self, database_path: Path) -> Path:
        """Validate that the database path exists and return it as a Path."""
        if not database_path.exists():
            raise FileNotFoundError(f"Database not found at {database_path}")
        return database_path

    def _load_plot_parameters(self, path: Optional[Path]) -> str:
        """Loads and sanitizes the plot parameters definition file."""

        if path is None:
            path = DEFAULT_PLOT_PARAMETERS_PATH

        if not path.exists():
            logger.warning(f"Config file not found at {path}")
            return ""

        with open(path, "r", encoding="utf-8") as f:
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

    def _construct_sql_prompt(self, question: str, schema: str) -> str:
        """Construct an LLM prompt for generating an SQL query."""
        return textwrap.dedent(
            f"""
        ```db-schema
        {schema}
        ```
        # Instructions

        Based on the provided database schema, construct an SQL query
        that answers the following question: "{question}".

        - The database type is {self._database_type}.
        - Ensure the query is optimized and aggregates data where it makes sense.
        - The result should be human-readable and provide meaningful insights.
        - Avoid unnecessary complexity and ensure the query
            is valid for the given database type.

        Please return ONLY the SQL query as plain text,
        without any additional explanations or formatting.
        """
        )

    def _construct_plot_prompt(self, question: str, dataframe: pd.DataFrame) -> str:
        """Construct an LLM prompt for generating dataframe plot parameters."""
        return textwrap.dedent(
            f"""

        ```df-plot-parameters
        {self._plot_parameters_text}
        ```

        ```df-metadata
        Columns: {dataframe.columns.tolist()}
        Index: {dataframe.index.tolist()}
        Head: {dataframe.head().to_dict()}
        ```

        **Question**: {question}

        # Instructions

        Based on the provided data and question, generate a JSON dictionary
        with parameters for `df.plot()` that are relevant and appropriate.
        Ensure the plot is clear, informative, and visually appealing.
        Consider using advanced plot types (e.g., stacked plots, subplots)
        if the data has multiple columns.

        The JSON dictionary should include:
        - Parameters for `df.plot()` as flat key-value pairs.
        - A `should_plot` key with a boolean value indicating whether
          plotting is suitable for this data.

        Return ONLY the JSON dictionary as plain text,
        without any additional explanations.
        """
        )

    def _log_sql_query(self, sql_query: str) -> None:
        """Log the generated SQL query, truncating if necessary."""
        if sql_query and len(sql_query) > SQL_QUERY_LOG_TRUNCATION_LENGTH:
            truncated = sql_query[:SQL_QUERY_LOG_TRUNCATION_LENGTH].replace("\n", " ")
            logger.info(
                f"Generated SQL (truncated): {textwrap.indent(truncated, '  > ')}...\n"
            )
            logger.debug(f"Full generated SQL:\n{sql_query}")
        else:
            logger.info(f"Generated SQL: {sql_query}")

    def _generate_sql_query(self, question: str, retry_count: int) -> str:
        """Generate an SQL query from a natural language question."""
        schema = self._database_inspector.export_schema()
        prompt = self._construct_sql_prompt(question, schema)
        raw_response = self._llm_client.generate_content(prompt, retry_count)
        return self._llm_client.clean_markdown_block(raw_response, "sql(ite)?")

    def _execute_sql_query(self, sql_query: str) -> pd.DataFrame:
        """Execute an SQL query and return the results as a DataFrame."""
        dataframe = self._database_inspector.execute_query(sql_query)
        logger.info(
            "Query returned %d rows and %d columns",
            dataframe.shape[0],
            dataframe.shape[1],
        )
        logger.debug(f"Result preview:\n{dataframe.head().to_markdown()}")
        return dataframe

    def _generate_plot_parameters(
        self, question: str, dataframe: pd.DataFrame, retry_count: int
    ) -> str:
        """Generate JSON plot parameters for a dataframe using the LLM."""
        prompt = self._construct_plot_prompt(question, dataframe)
        raw_response = self._llm_client.generate_content(prompt, retry_count)
        return self._llm_client.clean_markdown_block(raw_response, "json")

    def _validate_plot_parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Validate and sanitize plot parameters."""
        valid_parameters_keys = [
            line.split(",")[0]
            for line in self._plot_parameters_text.splitlines()
            if not line.startswith(" ")
        ]
        sanitized_parameters = {
            k: v for k, v in parameters.items() if k in valid_parameters_keys
        }
        return sanitized_parameters

    def _parse_plot_parameters(self, json_string: str) -> Tuple[dict[str, Any], bool]:
        """Parse plot parameters and plotting decision from JSON."""
        try:
            parameters = json.loads(json_string)
            should_plot = parameters.pop("should_plot", False)
            parameters = self._validate_plot_parameters(parameters)
            return parameters, should_plot
        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON: {json_string}")
            return {}, False

    def describe_database(self) -> pd.DataFrame:
        """Return a summary description of the database schema."""
        return self._database_inspector.describe_database()

    def export_schema(self) -> str:
        """Export the database schema as a textual representation."""
        return self._database_inspector.export_schema()

    def plot_schema(self) -> Optional[Path]:
        """Generate and save a visual representation of the database schema."""
        return self._database_inspector.plot_schema()

    def question_to_dataframe(
        self, question: str, retry_count: int = 3
    ) -> pd.DataFrame:
        """Generates and executes a SQL query based on the user's question."""
        for attempt in range(retry_count, 0, -1):
            try:
                sql_query = self._generate_sql_query(question, retry_count)
                self._log_sql_query(sql_query)
                return self._execute_sql_query(sql_query)
            except pd.errors.DatabaseError as e:
                logger.error(f"SQL execution error: {e}")
                if attempt == 1:
                    logger.error("All retries exhausted. Returning empty DataFrame.")
                    raise e
                logger.info(
                    f"Retrying SQL generation and execution ({attempt - 1} retries left)..."
                )
        raise RuntimeError("Unexpected error in question_to_dataframe")

    def question_to_plot(
        self,
        question: str,
        retry_count: int = 3,
        show: bool = True,
        verbosity: int = 1,
        dataframe: Optional[pd.DataFrame] = None,
    ) -> Tuple[Optional[Axes], bool]:
        """Generates and displays a plot based on the user's question."""
        dataframe = (
            dataframe
            if dataframe is not None
            else self.question_to_dataframe(question, retry_count)
        )

        logger.info(f"Dataframe shape: {dataframe.shape}")
        logger.debug(f"Dataframe head:\n{dataframe.head().to_markdown()}")

        json_string = self._generate_plot_parameters(question, dataframe, retry_count)
        parameters, should_plot = self._parse_plot_parameters(json_string)
        return self._plotting_engine.plot_data(
            dataframe, parameters, should_plot, show, verbosity
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", type=str, default="data/chinook.db")
    arguments = parser.parse_args()

    logger.info("Initializing Visualizer...")
    visualizer = LLMDataVisualizer(Path(arguments.database_path))
    logger.info(visualizer.export_schema()[:100])

    print(visualizer._plot_parameters_text)
