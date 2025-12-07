from backend.visualizer.services.llm_client import LLMClient
from unittest.mock import MagicMock


def test_clean_markdown_block():
    text = "```sql\nSELECT * FROM people;\n```"
    cleaned = LLMClient.clean_markdown_block(text, "sql")
    assert "SELECT * FROM people" in cleaned


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
