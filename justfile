

fetch-chinook:
    @echo "Fetching Chinook sample database..."
    curl https://www.sqlitetutorial.net/wp-content/uploads/2018/03/chinook.zip --output chinook.db.zip
    unzip -n chinook.db.zip
    rm chinook.db.zip
    mkdir -p data
    mv chinook.db data/chinook.db


# Run all linters: Ruff, Black (check), Mypy
lint:
    ruff check .
    black --check .
    mypy .
    vulture src/ . --exclude venv,tests --min-confidence 80
    pip-audit -r requirements.txt

lint-fix:
    black .
    ruff check --fix .

test *args:
    pytest {{args}}

coverage:
    coverage report --fail-under=10
