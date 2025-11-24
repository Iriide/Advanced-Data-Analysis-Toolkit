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
