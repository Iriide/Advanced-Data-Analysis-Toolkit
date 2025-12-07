import json
import re
import argparse
import pandas as pd
from pathlib import Path
from typing import Any, Optional, Tuple
from matplotlib.axes import Axes
from backend.visualizer.services.db_inspector import DatabaseInspector
from backend.visualizer.services.llm_client import LLMClient
from backend.visualizer.services.plotting_engine import PlottingEngine
from backend.visualizer.services.logger import get_logger

logger = get_logger(__name__)

DEFAULT_PLOT_PARAMETERS_PATH = Path("config/df_plot_parameters.txt")
SQL_QUERY_LOG_TRUNCATION_LENGTH = 200


class LLMDataVisualizer:

    def __init__(
        self,
        database_path: Path,
        database_type: str = "sqlite",
        model: str = "gemini-2.5-flash-lite",
        plot_parameters_file_path: Optional[Path] = None,
    ):
        self._database_path = database_path
        self._database_type = database_type
        self._database_inspector = DatabaseInspector(
            self._database_path, self._database_type
        )
        self._llm_client = LLMClient(model)
        self._plotting_engine = PlottingEngine()
        self._plot_parameters_text = self._load_plot_parameters(
            plot_parameters_file_path
        )

    def _load_plot_parameters(self, path: Optional[Path]) -> str:
        """Loads and sanitizes the plot parameters definition file."""

        if path is None:
            path = DEFAULT_PLOT_PARAMETERS_PATH

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

    def _construct_sql_prompt(self, question: str, schema: str) -> str:
        return f"""
        ```db-schema
        {schema}
        ```
        # Instructions

        Hello, knowing the schema, propose me a SQL query
        that will answer this question: {question}

        Note that I use {self._database_type}.
        Please make the result as informative and human readable as possible.

        Please provide ONLY the sql query, nothing else.
        """

    def _construct_plot_prompt(self, question: str, dataframe: pd.DataFrame) -> str:
        return f"""
        ```df-plot-parameters
        {self._plot_parameters_text}
        ```

        ```df-columns
        {dataframe.columns.tolist()}
        ```

        ```df-index
        {dataframe.index}
        ```

        ```df-head
        {dataframe.head().to_string()}
        ```

        **Question**: {question}

        # Instructions

        Hello, knowing the data and the question,
        prepare me parameters dictionary (json)
        that will be used for df.plot() as kwargs.
        Only use parameters from the df-plot-parameters that are relevant.

        The plot needs to be nice and informative.
        If there is more than one column, the plot may be complex
        (e.g. stacked plots, subplots, etc).

        Please provide ONLY the flat json, nothing else.

        Additionally, add a 'should_plot' key with boolean value
        indicating whether plotting is appropriate for this data.
        """

    def _log_sql_query(self, sql_query: str) -> None:
        if sql_query and len(sql_query) > SQL_QUERY_LOG_TRUNCATION_LENGTH:
            truncated = sql_query[:SQL_QUERY_LOG_TRUNCATION_LENGTH].replace("\n", " ")
            logger.info("Generated SQL (truncated): %s...", truncated)
            logger.debug("Full generated SQL:\n%s", sql_query)
        else:
            logger.info("Generated SQL: %s", sql_query)

    def describe_database(self) -> pd.DataFrame:
        return self._database_inspector.describe_database()

    def export_schema(self) -> str:
        return self._database_inspector.export_schema()

    def plot_schema(self) -> Optional[Path]:
        return self._database_inspector.plot_schema()

    def _generate_sql_query(self, question: str, retry_count: int) -> str:
        schema = self._database_inspector.export_schema()
        prompt = self._construct_sql_prompt(question, schema)
        raw_response = self._llm_client.generate_content(prompt, retry_count)
        return self._llm_client.clean_markdown_block(raw_response, "sql")

    def _execute_sql_query(self, sql_query: str) -> pd.DataFrame:
        dataframe = self._database_inspector.execute_query(sql_query)
        logger.info(
            "Query returned %d rows and %d columns",
            dataframe.shape[0],
            dataframe.shape[1],
        )
        logger.debug("Result preview:\n%s", dataframe.head().to_markdown())
        return dataframe

    def question_to_dataframe(
        self, question: str, retry_count: int = 3
    ) -> pd.DataFrame:
        """Generates and executes a SQL query based on the user's question."""
        sql_query = self._generate_sql_query(question, retry_count)
        self._log_sql_query(sql_query)
        return self._execute_sql_query(sql_query)

    def _generate_plot_parameters(
        self, question: str, dataframe: pd.DataFrame, retry_count: int
    ) -> str:
        prompt = self._construct_plot_prompt(question, dataframe)
        raw_response = self._llm_client.generate_content(prompt, retry_count)
        return self._llm_client.clean_markdown_block(raw_response, "json")

    def _parse_plot_parameters(self, json_string: str) -> Tuple[dict[str, Any], bool]:
        try:
            parameters = json.loads(json_string)
            should_plot = parameters.pop("should_plot", False)
            return parameters, should_plot
        except json.JSONDecodeError:
            logger.error("Failed to decode JSON: %s", json_string)
            return {}, False

    def question_to_plot(
        self, question: str, retry_count: int = 3, show: bool = True, verbosity: int = 1
    ) -> Tuple[Optional[Axes], bool]:
        """Generates and displays a plot based on the user's question."""
        dataframe = self.question_to_dataframe(question, retry_count)
        logger.info("Dataframe shape: %s", dataframe.shape)
        logger.debug("Dataframe head:\n%s", dataframe.head().to_markdown())

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
    visualizer = LLMDataVisualizer(Path(arguments.db_path))
    logger.info(visualizer.export_schema()[:100])
