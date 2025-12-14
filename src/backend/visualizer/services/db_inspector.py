import sqlite3
import uuid
import argparse
import tempfile
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Any, Optional
from sqlalchemy import create_engine, MetaData, Engine
from sqlalchemy_schemadisplay import create_schema_graph
from backend.utils.logger import configure_logging, get_logger

NUMERIC_DATA_TYPES = ("INTEGER", "REAL", "NUMERIC", "FLOAT", "DOUBLE")


class DatabaseInspector:
    """
    Handles database connection, introspection, and schema operations.
    """

    def __init__(self, database_path: Path, database_type: str = "sqlite"):
        """Initialize the inspector with database location and type."""
        self._database_path = database_path
        self._database_type = database_type
        self._connection_string = (
            f"sqlite:///{self._database_path}" if database_type == "sqlite" else None
        )

    def create_connection(self) -> sqlite3.Connection:
        """Returns a raw sqlite3 connection."""
        return sqlite3.connect(self._database_path)

    def execute_query(self, query: str) -> pd.DataFrame:
        """
        Executes a SQL query and returns the result as a DataFrame.
        """
        connection = self.create_connection()
        try:
            return pd.read_sql(query, con=connection)
        finally:
            connection.close()

    def _get_numeric_column_statistics(
        self, cursor: sqlite3.Cursor, table_name: str, column_name: str
    ) -> dict[str, Optional[float]]:
        """Compute basic statistics for a numeric column."""

        query = f"""
            SELECT COUNT([{column_name}]), MIN([{column_name}]), AVG([{column_name}]), MAX([{column_name}])
            FROM {table_name};
        """
        count, minimum, mean, maximum = cursor.execute(query).fetchone()
        return {
            "count": count,
            "min": minimum,
            "mean": mean,
            "max": maximum,
            "unique": pd.NA,
            "top": pd.NA,
            "freq": pd.NA,
        }

    def _get_categorical_column_statistics(
        self, cursor: sqlite3.Cursor, table_name: str, column_name: str
    ) -> dict[str, Optional[float]]:
        """Compute frequency-based statistics for a categorical column."""
        query = f"""
            SELECT COUNT([{column_name}]), COUNT(DISTINCT [{column_name}]),
            (SELECT [{column_name}] FROM {table_name} GROUP BY [{column_name}] ORDER BY COUNT(*) DESC LIMIT 1),
            (SELECT COUNT(*) FROM {table_name} GROUP BY [{column_name}] ORDER BY COUNT(*) DESC LIMIT 1)
            FROM {table_name};
        """
        count, unique_count, top_value, top_frequency = cursor.execute(query).fetchone()
        return {
            "count": count,
            "min": pd.NA,
            "mean": pd.NA,
            "max": pd.NA,
            "unique": unique_count,
            "top": top_value,
            "freq": top_frequency,
        }

    def _get_column_statistics(
        self, cursor: sqlite3.Cursor, table_name: str, column_name: str, data_type: str
    ) -> dict[str, Optional[float]]:
        """Dispatch to numeric or categorical statistics based on column type."""
        if data_type.upper() in NUMERIC_DATA_TYPES:
            return self._get_numeric_column_statistics(cursor, table_name, column_name)
        return self._get_categorical_column_statistics(cursor, table_name, column_name)

    def describe_table(self, table_name: str) -> pd.DataFrame:
        """Generates statistical description of a specific table."""
        connection = self.create_connection()
        cursor = connection.cursor()
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = cursor.fetchall()

        statistics = {}
        for _, column_name, data_type, *_ in columns:
            statistics[column_name] = self._get_column_statistics(
                cursor, table_name, column_name, data_type
            )

        connection.close()
        result = pd.DataFrame(statistics).T
        result.insert(0, "dtype", np.array(columns)[:, 2])
        return result

    def _get_table_names(self) -> list[str]:
        """Return a list of user-defined table names in the database."""
        connection = self.create_connection()
        try:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
            )
            return [row[0] for row in cursor.fetchall()]
        finally:
            connection.close()

    def _create_table_description_with_index(self, table_name: str) -> pd.DataFrame:
        """Create a table description DataFrame with a hierarchical index."""
        table_description = self.describe_table(table_name)
        table_index = pd.Index([table_name] * len(table_description), name="table")
        table_description.set_index(table_index, append=True, inplace=True)
        table_description = table_description.swaplevel(0, 1)
        table_description.index.names = ["table", "column"]
        return table_description

    def describe_database(self) -> pd.DataFrame:
        """Generates statistical description for the entire database."""
        table_names = self._get_table_names()
        table_descriptions = [
            self._create_table_description_with_index(name) for name in table_names
        ]
        return pd.concat(table_descriptions) if table_descriptions else pd.DataFrame()

    def export_schema(self) -> str:
        """Returns the DDL (Create Table statements) for the database."""
        connection = self.create_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table'")
        schema_statements = [row[0] for row in cursor.fetchall() if row[0]]
        connection.close()
        return "\n".join(schema_statements)

    def _configure_schema_graph_nodes(self, graph: Any) -> None:
        """Apply visual styling to schema graph nodes."""
        for node in graph.get_nodes():
            node.set_color("#1f77b4")
            node.set_penwidth("1.5")
        graph.set_splines("ortho")
        graph.set_bgcolor("#ffffff")

    def _create_schema_graph(self, engine: Engine, metadata: MetaData) -> Any:
        """Create a schema graph using SQLAlchemy metadata."""
        graph = create_schema_graph(
            engine=engine,
            metadata=metadata,
            rankdir="LR",
            concentrate=False,
            relation_options={
                "arrowsize": "0.7",
                "color": "#555555",
                "penwidth": "1.2",
            },
            show_datatypes=False,
            show_indexes=False,
            show_column_keys=True,
            font="Helvetica",
            format_table_name={"color": "#1f2937", "bold": True, "fontsize": 14},
            show_schema_name=False,
        )
        self._configure_schema_graph_nodes(graph)
        return graph

    def _generate_schema_svg_path(self) -> Path:
        """Generate a temporary file path for the schema SVG."""
        temporary_directory = Path(tempfile.gettempdir())
        return (
            temporary_directory / f"{self._database_type}-schema-{uuid.uuid4().hex}.svg"
        )

    def plot_schema(self) -> Optional[Path]:
        """
        Generates an SVG graph of the schema.

        Returns:
            Path: Path to the generated SVG temporary file,
            or None if dependencies missing.
        """
        if not self._connection_string:
            raise ValueError("Connection string cannot be None")
        engine = create_engine(self._connection_string)
        metadata = MetaData()
        metadata.reflect(bind=engine)
        graph = self._create_schema_graph(engine, metadata)

        output_path = self._generate_schema_svg_path()
        graph.write_svg(str(output_path))
        return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Database Inspector")
    parser.add_argument("--db-path", type=str, default="data/chinook.db")
    arguments = parser.parse_args()

    configure_logging()
    logger = get_logger(__name__)

    inspector = DatabaseInspector(Path(arguments.database_path))
    logger.info("Schema Snippet:\n%s", inspector.export_schema()[:200])
    logger.info("\nStats Snippet:\n%s", inspector.describe_database().head())
