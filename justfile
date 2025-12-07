fetch-chinook:
    @echo "Fetching Chinook sample database..."
    curl https://www.sqlitetutorial.net/wp-content/uploads/2018/03/chinook.zip --output chinook.db.zip
    unzip -n chinook.db.zip
    rm chinook.db.zip
    mkdir -p data
    mv chinook.db data/chinook.db


lint:
    uv run ruff check .
    uv run black --check .
    uv run mypy . --strict --pretty
    uv run vulture src/ . --exclude venv,tests --min-confidence 80
    uv run pip-audit

lint-fix:
    uv run black .
    uv run ruff check --fix .

test *args:
    uv run pytest {{args}}

coverage:
    uv run coverage report --fail-under=10
