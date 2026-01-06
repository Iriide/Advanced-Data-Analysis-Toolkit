import importlib
from unittest.mock import MagicMock
import pytest

MODULE_PATH = "backend.visualizer.services.llm_client"


@pytest.fixture
def llm_module():
    return importlib.import_module(MODULE_PATH)


@pytest.fixture
def llm_client_class(llm_module):
    return llm_module.LLMClient


@pytest.fixture
def fake_load_dotenv(monkeypatch, llm_module):
    mock_load_dotenv = MagicMock()
    monkeypatch.setattr(llm_module, "load_dotenv", mock_load_dotenv)
    return mock_load_dotenv


# -------------------------
# clean_markdown_block tests
# -------------------------


def test_clean_markdown_block_strips_fences_and_lang_tag(llm_client_class):
    def assert_cleaned(text: str, expected: str, block_type: str):
        cleaned = llm_client_class.clean_markdown_block(text, block_type)
        assert expected == cleaned
        # Also test without specifying block_type
        cleaned = llm_client_class.clean_markdown_block(text)
        assert expected == cleaned

    assert_cleaned("```sql\nSELECT * FROM people;\n```", "SELECT * FROM people;", "sql")
    assert_cleaned(
        "```python\nprint('Hello, World!')\n```",
        "print('Hello, World!')",
        "python",
    )
    assert_cleaned(
        "```sql\nSELECT * FROM people;\n```", "SELECT * FROM people;", "sql(ite)?"
    )
    assert_cleaned(
        "```sqlite\nSELECT * FROM people;\n```", "SELECT * FROM people;", "sql(ite)?"
    )


def test_clean_markdown_block_returns_original_if_no_fences(llm_client_class):
    text = "SELECT * FROM people;"
    assert llm_client_class.clean_markdown_block(text, "sql") == text


def test_clean_markdown_block_mismatched_delimiters_keeps_content(llm_client_class):
    # Missing closing ```
    assert (
        llm_client_class.clean_markdown_block("```sql\nSELECT * FROM people;", "sql")
        == "SELECT * FROM people;"
    )


@pytest.mark.parametrize("value", [None, ""])
def test_clean_markdown_block_returns_empty_for_falsy_input(llm_client_class, value):
    assert llm_client_class.clean_markdown_block(value) == ""


def test_clean_markdown_block_whitespace_only_becomes_empty_after_strip(
    llm_client_class,
):
    assert llm_client_class.clean_markdown_block("   ") == ""


# -------------------------
# __init__ tests
# -------------------------


def test_init_initializes_dependencies_when_load_environment_enabled(
    monkeypatch, llm_module
):
    dotenv_calls = {"count": 0}
    retrier_count = {"count": 0}

    def fake_load_dotenv():
        dotenv_calls["count"] += 1

    class DummyRetrier:
        def __init__(self):
            retrier_count["count"] += 1

    class DummyClient:
        pass

    monkeypatch.setattr(llm_module, "load_dotenv", fake_load_dotenv)
    monkeypatch.setenv(llm_module.API_KEY_ENVIRONMENT_VARIABLE, "x")
    monkeypatch.setattr(llm_module.genai, "Client", DummyClient)
    monkeypatch.setattr(llm_module, "GeminiAPIRequestRetrier", DummyRetrier)

    llm_module.LLMClient(load_environment=True)

    assert dotenv_calls["count"] == 1
    assert retrier_count["count"] == 1


def test_init_logs_warning_when_api_key_missing(
    monkeypatch, llm_module, fake_load_dotenv
):
    class DummyRetrier:
        pass

    class DummyClient:
        pass

    monkeypatch.delenv(llm_module.API_KEY_ENVIRONMENT_VARIABLE, raising=False)

    monkeypatch.setattr(llm_module, "load_dotenv", fake_load_dotenv)
    monkeypatch.setattr(llm_module.genai, "Client", DummyClient)
    monkeypatch.setattr(llm_module, "GeminiAPIRequestRetrier", DummyRetrier)

    warnings = []
    monkeypatch.setattr(llm_module.logger, "warning", lambda msg: warnings.append(msg))

    llm_module.LLMClient(load_environment=False)

    assert warnings == [f"{llm_module.API_KEY_ENVIRONMENT_VARIABLE} not set"]


# -------------------------
# generate_content success
# -------------------------


def test_generate_content_returns_mocked_response(
    monkeypatch, llm_module, fake_load_dotenv
):
    class FakeGenAIClient:
        def __init__(self, *args, **kwargs):
            self.models = MagicMock()
            self.models.generate_content.return_value.text = "Mocked Response"

    monkeypatch.setattr(llm_module.genai, "Client", FakeGenAIClient)
    monkeypatch.setattr(llm_module, "load_dotenv", fake_load_dotenv)
    monkeypatch.setenv(llm_module.API_KEY_ENVIRONMENT_VARIABLE, "x")

    client = llm_module.LLMClient(load_environment=False)
    assert client.generate_content("Hello") == "Mocked Response"


def test_generate_content_calls_retrier_with_call_api_and_prompt(
    monkeypatch, llm_module, fake_load_dotenv
):
    class FakeGenAIClient:
        def __init__(self, *args, **kwargs):
            self.models = MagicMock()
            self.models.generate_content.return_value.text = "Mocked Response"

    class RetrierStub:
        def __init__(self):
            self.reset_arg = None
            self.run_called_with = None

        def reset_retries(self, n):
            self.reset_arg = n

        def run(self, fn, prompt):
            self.run_called_with = (fn, prompt)
            return fn(prompt)

    retrier = RetrierStub()

    monkeypatch.setattr(llm_module.genai, "Client", FakeGenAIClient)
    monkeypatch.setattr(llm_module, "load_dotenv", fake_load_dotenv)
    monkeypatch.setenv(llm_module.API_KEY_ENVIRONMENT_VARIABLE, "x")

    client = llm_module.LLMClient(load_environment=False)
    client._request_retrier = retrier

    response = client.generate_content("Hello", retry_count=7)

    assert response == "Mocked Response"
    assert retrier.reset_arg == 7

    fn, prompt = retrier.run_called_with
    assert callable(fn)
    assert prompt == "Hello"


# -------------------------
# generate_content error paths
# -------------------------


def _make_client_with_retrier(monkeypatch, llm_module, retrier_obj, fake_load_dotenv):
    class DummyClient:
        pass

    monkeypatch.setenv(llm_module.API_KEY_ENVIRONMENT_VARIABLE, "x")
    monkeypatch.setattr(llm_module, "load_dotenv", fake_load_dotenv)
    monkeypatch.setattr(llm_module.genai, "Client", DummyClient)

    client = llm_module.LLMClient(load_environment=False)
    client._request_retrier = retrier_obj

    return client


def test_generate_content_raises_source_exhausted_and_logs(
    monkeypatch, llm_module, fake_load_dotenv
):
    class RetrierStub:
        def __init__(self):
            self.reset_arg = None

        def reset_retries(self, n):
            self.reset_arg = n

        def run(self, fn, prompt):
            raise llm_module.GeminiAPIRequestRetrier.SourceExhaustedError("quota")

    retrier = RetrierStub()
    errors = []
    monkeypatch.setattr(llm_module.logger, "error", lambda msg: errors.append(msg))

    client = _make_client_with_retrier(
        monkeypatch, llm_module, retrier, fake_load_dotenv
    )

    with pytest.raises(llm_module.GeminiAPIRequestRetrier.SourceExhaustedError):
        client.generate_content("hi", retry_count=3)

    assert retrier.reset_arg == 3
    assert any("LLM API call failed after 3 retries" in m for m in errors)


def test_generate_content_raises_runtime_error_and_logs(
    monkeypatch, llm_module, fake_load_dotenv
):
    class RetrierStub:
        def __init__(self):
            self.reset_arg = None

        def reset_retries(self, n):
            self.reset_arg = n

        def run(self, fn, prompt):
            raise RuntimeError("boom")

    retrier = RetrierStub()
    errors = []
    monkeypatch.setattr(llm_module.logger, "error", lambda msg: errors.append(msg))

    client = _make_client_with_retrier(
        monkeypatch, llm_module, retrier, fake_load_dotenv
    )

    with pytest.raises(RuntimeError):
        client.generate_content("hi", retry_count=5)

    assert retrier.reset_arg == 5
    assert any("LLM API call failed with runtime error: boom" in m for m in errors)
