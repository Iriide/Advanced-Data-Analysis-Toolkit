import os
from google import genai
import sqlite3
import matplotlib.pyplot as plt
import pandas as pd
import json
import numpy as np
from dotenv import load_dotenv
from pathlib import Path
import re
from matplotlib.axes import Axes
from sqlalchemy import create_engine, MetaData
from sqlalchemy_schemadisplay import create_schema_graph
import tempfile
import argparse
import textwrap
from typing import Optional, Tuple


class LLMDataVisualizer:
    def __init__(
        self,
        db_path: "str | Path",
        db_type: str = "sqlite",
        load_env: bool = True,
        model: str = "gemini-2.5-flash-lite",
        df_plot_parameters_file_path: Path = None,
    ):
        self._db_path = db_path if isinstance(db_path, Path) else Path(db_path)
        self._db_type = db_type

        if load_env:
            load_dotenv()
        if "GOOGLE_API_KEY" not in os.environ:
            print("GOOGLE_API_KEY not found in environment variables.")

        self._client = genai.Client()
        self._model = model

        if df_plot_parameters_file_path is None:
            df_plot_parameters_file_path = (
                Path(__file__).resolve().parent / "df_plot_parameters.txt"
            )
        self._plot_parameters_txt_path = df_plot_parameters_file_path
        self._plot_parameters_txt = self.load_plot_parameters()

    @classmethod
    def _get_tmp_file_candidate(_, prefix="", suffix="") -> Path:
        tmp_dir = Path(tempfile.gettempdir())
        tmp_path = tmp_dir / f"{prefix}{next(tempfile._get_candidate_names())}{suffix}"

        return tmp_path

    def load_plot_parameters(self) -> str:
        with open(self._plot_parameters_txt_path, "r") as f:
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

    def describe_table(self, table):
        con = sqlite3.connect(self._db_path)
        cur = con.cursor()

        # Get columns
        cur.execute(f"PRAGMA table_info({table});")
        columns = cur.fetchall()

        results = {}

        for cid, name, dtype, *_ in columns:
            if dtype.upper() in ("INTEGER", "REAL", "NUMERIC", "FLOAT", "DOUBLE"):
                # Numeric stats
                q = f"""
                    SELECT
                        COUNT([{name}]) AS count,
                        MIN([{name}]) AS min,
                        AVG([{name}]) AS mean,
                        MAX([{name}]) AS max
                    FROM {table};
                """
                count, min_val, mean_val, max_val = cur.execute(q).fetchone()
                results[name] = {
                    "count": count,
                    "min": min_val,
                    "mean": mean_val,
                    "max": max_val,
                    # object/text columns stats not applicable
                    "unique": pd.NA,
                    "top": pd.NA,
                    "freq": pd.NA,
                }
            else:
                # Text / object stats
                q = f"""
                    SELECT
                        COUNT([{name}]) AS count,
                        COUNT(DISTINCT [{name}]) AS unique_count,
                        (SELECT [{name}] FROM {table}
                        GROUP BY [{name}]
                        ORDER BY COUNT(*) DESC
                        LIMIT 1) AS top_value,
                        (SELECT COUNT(*) FROM {table}
                        GROUP BY [{name}]
                        ORDER BY COUNT(*) DESC
                        LIMIT 1) AS top_freq
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

        # Convert results dict to DataFrame
        df = pd.DataFrame(results).T
        df.insert(0, "dtype", np.array(columns)[:, 2])
        return df

    def describe_database(self):
        con = sqlite3.connect(self._db_path)
        cur = con.cursor()

        # Get all table names
        cur.execute(
            "SELECT name FROM sqlite_master"
            " WHERE type='table' AND name NOT LIKE 'sqlite_%';"
        )
        tables = [row[0] for row in cur.fetchall()]

        db_description = []
        for table in tables:
            df_table_desc = self.describe_table(table)
            table_name = pd.Index([table] * len(df_table_desc), name="table")
            df_table_desc.set_index(table_name, append=True, inplace=True)
            df_table_desc = df_table_desc.swaplevel(0, 1)
            db_description.append(df_table_desc)

        return pd.concat(db_description)

    def export_schema(self) -> str:
        con = sqlite3.connect(self._db_path)
        cur = con.cursor()
        cur.execute("SELECT sql FROM sqlite_master WHERE type='table'")
        return "\n".join(row[0] for row in cur.fetchall())

    def plot_schema(self, output_path: Path = None) -> Path:
        # Example URIs (switch depending on DB):
        # SQLite: sqlite:///path/to/db.sqlite
        # PostgreSQL: postgresql://user:pass@localhost/dbname
        # MySQL: mysql+pymysql://user:pass@localhost/dbname

        engine = create_engine(f"{self._db_type}:///{self._db_path}")
        metadata = MetaData()
        metadata.reflect(bind=engine)

        # graph = create_schema_graph(
        #     metadata=metadata,
        #     show_datatypes=True,
        #     show_indexes=True,
        #     concentrate=True,
        #     engine=engine
        # )

        graph = create_schema_graph(
            engine=engine,
            metadata=metadata,
            # Layout direction: left → right (more readable)
            rankdir="LR",
            # Clean, flat edges
            concentrate=False,  # do not merge parallel edges
            relation_options={
                "arrowsize": "0.7",
                "color": "#555555",
                "penwidth": "1.2",
            },
            # Colors and formatting
            show_datatypes=False,
            show_indexes=False,
            show_column_keys=True,
            font="Helvetica",
            # Table header color / font styling
            format_table_name={
                "color": "#1f2937",  # table name color
                "bold": True,
                "fontsize": 14,
            },
            # Schema prefixes (optional)
            show_schema_name=False,
        )

        table_options = {
            "bgcolor": "#f3f4f6",  # light gray table background
            "color": "#1f77b4",  # border color
            "penwidth": "1.5",
        }

        for node in graph.get_nodes():
            # node.set_bgcolor(table_options["bgcolor"])
            node.set_color(table_options["color"])
            node.set_penwidth(table_options["penwidth"])

        graph.set_splines("ortho")  # right-angled edges
        # graph.set_splines("line")   # straight edges

        graph.set_ranksep("1.0")
        graph.set_nodesep("0.6")
        graph.set_overlap("false")
        graph.set_concentrate("false")  # avoid merging edges
        graph.set_rankdir("LR")  # left → right

        graph.set_bgcolor("#ffffff")  # white canvas
        graph.set_fontname("Helvetica")
        graph.set_nodesep("0.5")
        graph.set_ranksep("1.0")
        graph.set_splines("ortho")

        graph.set_size("4,3!")
        graph.set_ratio("fill")
        graph.set_pagedir("BL")

        if output_path is None:
            output_path = self._get_tmp_file_candidate(
                f"{self._db_type}-schema-", ".svg"
            )
        graph.write_svg(output_path)
        return output_path

    def _find_query(self, question: str, retries: int = 3) -> str:
        prompt = textwrap.dedent(
            f"""

        ```db-schema
        {schema}
        ```

        Hello, knowing the schema, propose me sql query
        that will answer this question: {question}

        Note that i use {self._db_type}.

        Please provide ONLY the sql query, nothing else.
        """
        )

        retries = retries
        while retries > 0:
            try:
                response = self._client.models.generate_content(
                    model=self._model, contents=prompt
                )
                break
            except Exception as e:
                print(f"Error: {e}")
                retries -= 1
                if retries == 0:
                    raise

        # Extract SQL query from response
        query = response.text
        if query.startswith("```sql"):
            query = query.split("```sql")[1].strip("`").strip()
        return str(query)

    def _generate_plot_params(self, question: str, df: pd.DataFrame) -> None:
        plot_prompt = textwrap.dedent(
            f"""

        ```df-plot-parameters
        {self._plot_parameters_txt}
        ```

        ```df-columns
        {df.columns}
        ```

        ```df-index
        {df.index}
        ```

        ```df-head
        {df.head()}
        ```

        Question: {question}

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
        )

        # Use *Set2* colormap when you dont specify color
        # (when you do, dont use *Set2*).

        response = self._client.models.generate_content(
            model=self._model, contents=plot_prompt
        )

        plot_parameters_str = response.text
        if plot_parameters_str.startswith("```json"):
            plot_parameters_str = plot_parameters_str.split("```json")[1]
        plot_parameters_str = plot_parameters_str.strip("`").strip()

        try:
            plot_parameters_dict = json.loads(plot_parameters_str)
        except json.JSONDecodeError as e:
            print("Error decoding JSON from LLM response:")
            print(plot_parameters_str)
            raise e

        should_plot = plot_parameters_dict.get("should_plot", False)
        plot_parameters_dict.pop("should_plot", None)

        return should_plot, plot_parameters_dict

    def question_to_df(self, question: str, retries: int = 3) -> pd.DataFrame:
        query = self._find_query(question, retries=retries)
        con = sqlite3.connect(self._db_path)
        df = pd.read_sql(query, con=con)

        return df

    def _plot_df_as_table(self, df):
        fig, ax = plt.subplots()
        fig.patch.set_visible(False)
        ax.axis("off")
        ax.axis("tight")
        ax.table(cellText=df.values, colLabels=df.columns, loc="center")
        fig.tight_layout()
        return fig, ax

    def df_to_plot(
        self,
        df: pd.DataFrame,
        question: str,
        retries: int = 3,
        show: bool = True,
        verbose=0,
    ) -> Axes:
        should_plot, plot_parameters = self._generate_plot_params(question, df)

        r = retries
        while r > 0:
            try:
                ax = df.plot(**plot_parameters)
                break
            except Exception:
                r -= 1
                if r == 0:
                    return None, False

        # Try to obtain the Figure object associated with the Axes returned by
        # pandas. df.plot can return a single Axes, an array of Axes, or other
        # matplotlib objects depending on parameters.
        fig = None
        try:
            # If ax is an array-like of Axes, pick the first one's figure
            if hasattr(ax, "__iter__") and not isinstance(ax, Axes):
                first = None
                for item in ax:
                    if hasattr(item, "get_figure"):
                        first = item
                        break
                fig = first.get_figure() if first is not None else plt.gcf()
            elif hasattr(ax, "get_figure"):
                fig = ax.get_figure()
            else:
                fig = plt.gcf()
        except Exception:
            fig = plt.gcf()

        if show:
            plt.show()
            # Close the specific figure to free memory. If that fails, close all.
            try:
                plt.close(fig)
            except Exception:
                plt.close("all")

        if not should_plot and verbose > 0:
            print("Warning: Plotting may not be appropriate for this data.")

        return ax, should_plot

    def question_to_plot(
        self, question: str, retries: int = 3, **kwargs
    ) -> Tuple[Optional[Axes], bool]:
        df = self.question_to_df(question, retries=retries)

        ax, should_plot = self.df_to_plot(df, question, **kwargs)

        return ax, should_plot


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Analyze and plot data from the Chinook database."
    )
    parser.add_argument(
        "--question",
        type=str,
        help="The question to analyze and plot. "
        "If not provided, a random sample question will be used.",
    )
    parser.add_argument("--show", action="store_true", help="Whether to show the plot.")
    parser.add_argument(
        "--db-path",
        type=str,
        default="data/chinook.db",
        help="Path to the Chinook database.",
    )
    parser.add_argument("--plot-schema", action="store_true", help="dfafd")
    args = parser.parse_args()

    chinook_db_path = Path(args.db_path)

    visualizer = LLMDataVisualizer(db_path=chinook_db_path, db_type="sqlite")

    description_df = visualizer.describe_database()
    print(description_df.to_markdown(), "\n")

    schema = visualizer.export_schema()
    print(schema[:250], "\n...\n")

    schema_plot_path = visualizer.plot_schema()

    if args.plot_schema:
        import cairosvg
        from PIL import Image
        import io

        png_bytes = cairosvg.svg2png(url=str(schema_plot_path), scale=4)

        # Load into PIL
        image = Image.open(io.BytesIO(png_bytes))

        # Plot with matplotlib
        plt.imshow(image)
        plt.axis("off")
    # plt.show()

    if args.question:
        q = args.question
    else:
        # # data structure reference
        # https://www.sqlitetutorial.net/sqlite-sample-database/
        sample_questions = [
            "Give me a count of employees grouped by age?",
            "What are the top 10 most used genres?",  # one with no plot
            "Which genre generated the highest revenue?",
            "Which genre generated the highest revenue? "
            "What are the top 5 genres by revenue?",
            "What are the revenues and the number of tracks "
            "sold for each genre?",  # 2 plots
        ]

        q = np.random.choice(sample_questions)
        print(f"Question: {q}")

    df = visualizer.question_to_df(q)
    print(df.to_markdown(), "\n")

    ax, should_plot = visualizer.df_to_plot(df, q, show=True, verbose=1)
    if should_plot:
        print("Plot generated successfully.")
    elif ax is not None:
        print("Plot may not be appropriate for this data.")
    else:
        print("Plot could not be generated.")

    # @TODO: refactor + types
