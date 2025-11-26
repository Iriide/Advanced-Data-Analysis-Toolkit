# Data-Analysis-Tool

## Scope

This repository provides a general-purpose tool for analyzing and visualizing relational databases. After supplying connection parameters, users can generate and store reusable reports. The tool supports schema inspection, exploratory data analysis, and prompt-driven query generation using a RAG model.

## Reports

Each report consists of two components:

### Generic Section

Automatically derived from the connected database and includes:
- Database type: PostgreSQL, MySQL, SQLite, etc. which will determine query syntax.
- Core metadata: database name, version (if available), table list, row counts, and storage metrics.
- Schema diagram showing tables, primary keys, foreign keys, and relationships.
- Data-quality overview: missing-value summaries, null distributions, and column-level completeness.
- Descriptive statistics for numerical fields, including ranges, percentiles, distributions, and outlier indicators.

### Dynamic Section

Built from user-defined prompts converted into SQL through the RAG model and includes:
- The generated query or queries.
- Result tables produced by executing them.
- Corresponding visualizations.
- Optional narrative explanations of findings.

## CLI

The tool can be run from the command line. Example usage:

```bash
python ./src/driver.py --help
```

**Logging / Verbosity**

The CLI supports standard logging and verbosity flags. Use `-v` to increase verbosity:

- No `-v`: warnings and errors only
- `-v`: info messages
- `-vv` or more: debug messages

You can also write logs to a file with `--log-file path/to/file.log`.

Examples:

```bash
python ./src/driver.py --question "Which genre generated the highest revenue?" -v
python ./src/driver.py --plot-schema --log-file logs/app.log -vv
```

```txt
usage: driver.py [-h] [--mode {cli,server}] [--question QUESTION] [--db-path DB_PATH] [--plot-schema] [--describe]

LLM Data Visualizer Driver

options:
  -h, --help           show this help message and exit
  --mode {cli,server}  Run mode: 'cli' for visualizer, 'server' to run the server.
  --question QUESTION  Question to analyze. Does not apply in server mode.
  --db-path DB_PATH    Path to database. Does not apply in server mode.
  --plot-schema        Generate schema SVG. Does not apply in server mode.
  --describe           Describe (i.e. summarize) the database. Does not apply in server mode.
```
