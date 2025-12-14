import sqlite3
from pathlib import Path
import pandas as pd
from backend.visualizer.services.db_inspector import DatabaseInspector


def create_test_db(path: Path) -> None:
    con = sqlite3.connect(path)
    cur = con.cursor()
    cur.execute("CREATE TABLE people (id INTEGER PRIMARY KEY, name TEXT, age INTEGER);")
    cur.executemany(
        "INSERT INTO people (name, age) VALUES (?, ?)",
        [("Alice", 30), ("Bob", 25), ("Charlie", 35)],
    )
    con.commit()
    con.close()


def test_database_inspector_execute_query_and_describe(tmp_path: Path):
    database_path = tmp_path / "test.db"
    create_test_db(database_path)

    inspector = DatabaseInspector(database_path=database_path, database_type="sqlite")
    df = inspector.execute_query("SELECT * FROM people ORDER BY id;")
    assert isinstance(df, pd.DataFrame)
    assert df.shape[0] == 3
    assert list(df.columns) == ["id", "name", "age"]
    desc = inspector.describe_table("people")
    assert "age" in desc.index
    assert "dtype" in desc.columns

    schema = inspector.export_schema()
    assert "CREATE TABLE people" in schema
