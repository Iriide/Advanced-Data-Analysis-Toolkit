import sqlite3
import json
from pathlib import Path
import pandas as pd
from backend.visualizer.llm_data_visualizer import LLMDataVisualizer


def create_test_db(path: Path) -> None:
    con = sqlite3.connect(path)
    cur = con.cursor()
    cur.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT, value REAL);")
    cur.executemany(
        "INSERT INTO items (name, value) VALUES (?, ?)", [("x", 1.0), ("y", 2.5)]
    )
    con.commit()
    con.close()


def test_question_to_df_and_plot(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "test_viz.db"
    create_test_db(db_path)

    viz = LLMDataVisualizer(database_path=db_path)

    # Provide a dummy LLM client that returns SQL for the first call and JSON for the second
    class DummyLLM:
        def generate_content(self, model_or_prompt, retry_count=3):
            prompt = model_or_prompt
            if "db-schema" in prompt:
                return "SELECT id, name, value FROM items"
            # plot prompt
            return json.dumps({"should_plot": False})

        @staticmethod
        def clean_markdown_block(text, block_type=""):
            # Simple mock implementation: return cleaned text
            if "json" in block_type and "should_plot" in text:
                return text  # It's already json in the mock
            return text.replace("```sql", "").replace("```", "").strip()

    viz._llm_client = DummyLLM()

    df = viz.question_to_dataframe("Give me items", retry_count=1)
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["id", "name", "value"]

    ax, plotted = viz.question_to_plot("Give me items", retry_count=1, show=False)
    assert isinstance(plotted, bool)
