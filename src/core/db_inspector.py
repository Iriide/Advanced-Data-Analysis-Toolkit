import sqlite3
import pandas as pd
import numpy as np
import tempfile
from pathlib import Path
from typing import Optional

try:
    from sqlalchemy import create_engine, MetaData
    from sqlalchemy_schemadisplay import create_schema_graph

    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False


class DBInspector:
    """
    Handles database connection, introspection, and schema operations.
    """

    def __init__(self, db_path: Path, db_type: str = "sqlite"):
        """
        Args:
            db_path (Path): Path to the database file.
            db_type (str): Database type (default: "sqlite").
        """
        self._db_path = db_path
        self._db_type = db_type

        if self._db_type == "sqlite":
            self._connection_string = f"sqlite:///{self._db_path}"

    def get_connection(self) -> sqlite3.Connection:
        """Returns a raw sqlite3 connection."""
        return sqlite3.connect(self._db_path)

    def run_query(self, query: str) -> pd.DataFrame:
        """
        Executes a SQL query and returns the result as a DataFrame.
        """
        con = self.get_connection()
        try:
            df = pd.read_sql(query, con=con)
            return df
        finally:
            try:
                con.close()
            except Exception:
                pass

    def describe_table(self, table: str) -> pd.DataFrame:
        """Generates statistical description of a specific table."""
        con = self.get_connection()
        cur = con.cursor()

        # Get columns
        cur.execute(f"PRAGMA table_info({table});")
        columns = cur.fetchall()

        results = {}

        for cid, name, dtype, *_ in columns:
            if dtype.upper() in ("INTEGER", "REAL", "NUMERIC", "FLOAT", "DOUBLE"):
                q = f"""
                    SELECT COUNT([{name}]), MIN([{name}]), AVG([{name}]), MAX([{name}])
                    FROM {table};
                """
                count, min_val, mean_val, max_val = cur.execute(q).fetchone()
                results[name] = {
                    "count": count,
                    "min": min_val,
                    "mean": mean_val,
                    "max": max_val,
                    "unique": pd.NA,
                    "top": pd.NA,
                    "freq": pd.NA,
                }
            else:
                q = f"""
                    SELECT COUNT([{name}]), COUNT(DISTINCT [{name}]),
                    (
                        SELECT [{name}]
                        FROM {table}
                        GROUP BY [{name}]
                        ORDER BY COUNT(*) DESC
                        LIMIT 1
                    ),
                    (
                        SELECT COUNT(*)
                        FROM {table}
                        GROUP BY [{name}]
                        ORDER BY COUNT(*) DESC
                        LIMIT 1
                    )
                    FROM {table};
                """
                count, unique_count, top_value, top_freq = cur.execute(q).fetchone()
                results[name] = {
                    "count": count,
                    "min": pd.NA,
                    "mean": pd.NA,
                    "max": pd.NA,
                    "unique": unique_count,
                    "top": top_value,
                    "freq": top_freq,
                }

        con.close()
        df = pd.DataFrame(results).T
        df.insert(0, "dtype", np.array(columns)[:, 2])
        return df

    def describe_database(self) -> pd.DataFrame:
        """Generates statistical description for the entire database."""
        con = self.get_connection()
        try:
            cur = con.cursor()
            cur.execute(
                "SELECT name "
                "FROM sqlite_master "
                "WHERE "
                "   type='table' "
                "   AND name NOT LIKE 'sqlite_%';"
            )
            tables = [row[0] for row in cur.fetchall()]
        finally:
            try:
                con.close()
            except Exception:
                pass

        db_description = []
        for table in tables:
            df_table_desc = self.describe_table(table)
            table_name = pd.Index([table] * len(df_table_desc), name="table")
            df_table_desc.set_index(table_name, append=True, inplace=True)
            df_table_desc = df_table_desc.swaplevel(0, 1)
            df_table_desc.index.names = ["table", "column"]
            db_description.append(df_table_desc)

        return pd.concat(db_description) if db_description else pd.DataFrame()

    def export_schema(self) -> str:
        """Returns the DDL (Create Table statements) for the database."""
        con = self.get_connection()
        cur = con.cursor()
        cur.execute("SELECT sql FROM sqlite_master WHERE type='table'")
        schema_str = "\n".join(row[0] for row in cur.fetchall() if row[0])
        con.close()
        return schema_str

    def plot_schema(self) -> Optional[Path]:
        """
        Generates an SVG graph of the schema.

        Returns:
            Path: Path to the generated SVG temporary file,
            or None if dependencies missing.
        """
        if not HAS_SQLALCHEMY:
            from core.logger import get_logger

            logger = get_logger(__name__)
            logger.warning(
                "SQLAlchemy or SchemaDisplay not installed. Skipping schema plot."
            )
            return None

        engine = create_engine(self._connection_string)
        metadata = MetaData()
        metadata.reflect(bind=engine)

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

        for node in graph.get_nodes():
            node.set_color("#1f77b4")
            node.set_penwidth("1.5")

        graph.set_splines("ortho")
        graph.set_bgcolor("#ffffff")

        import uuid

        tmp_dir = Path(tempfile.gettempdir())
        tmp_fname = tmp_dir / f"{self._db_type}-schema-{uuid.uuid4().hex}.svg"
        graph.write_svg(str(tmp_fname))
        return tmp_fname


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test DB Inspector")
    parser.add_argument("--db-path", type=str, default="data/chinook.db")
    args = parser.parse_args()

    from core.logger import configure_logging, get_logger

    configure_logging()
    logger = get_logger(__name__)

    inspector = DBInspector(Path(args.db_path))
    logger.info("Schema Snippet:\n%s", inspector.export_schema()[:200])
    logger.info("\nStats Snippet:\n%s", inspector.describe_database().head())
