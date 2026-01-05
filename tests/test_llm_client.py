from backend.visualizer.services.llm_client import LLMClient
from unittest.mock import MagicMock


def test_clean_markdown_block():

    def assert_cleaned(text: str, expected: str, block_type: str):
        cleaned = LLMClient.clean_markdown_block(text, block_type)
        assert expected == cleaned
        # Also test without specifying block_type
        cleaned = LLMClient.clean_markdown_block(text)
        assert expected == cleaned

    # Test with a valid SQL code block
    assert_cleaned("```sql\nSELECT * FROM people;\n```", "SELECT * FROM people;", "sql")

    # Test with a valid Python code block
    assert_cleaned(
        "```python\nprint('Hello, World!')\n```", "print('Hello, World!')", "python"
    )

    # Test with a regex pattern for SQL variants
    assert_cleaned(
        "```sql\nSELECT * FROM people;\n```", "SELECT * FROM people;", "sql(ite)?"
    )
    assert_cleaned(
        "```sqlite\nSELECT * FROM people;\n```", "SELECT * FROM people;", "sql(ite)?"
    )

    # Edge case: No code block delimiters
    assert_cleaned("SELECT * FROM people;", "SELECT * FROM people;", "sql")

    # Edge case: Mismatched code block delimiters
    assert_cleaned("```sql\nSELECT * FROM people;", "SELECT * FROM people;", "sql")


def test_generate_content_monkeypatch(monkeypatch):
    # 1. Create a fake Client class
    class FakeGenAIClient:
        def __init__(self, *args, **kwargs):
            self.models = MagicMock()
            # Mock the generate_content method return value
            self.models.generate_content.return_value.text = "Mocked Response"

    # 2. Patch the generic library import where it is USED
    monkeypatch.setattr(
        "backend.visualizer.services.llm_client.genai.Client", FakeGenAIClient
    )

    # 3. Now initialize your wrapper (it will use the FakeGenAIClient)
    client = LLMClient(load_environment=False)

    # 4. Run your test
    response = client.generate_content("Hello")
    assert response == "Mocked Response"
