import os
import time
from google import genai
from dotenv import load_dotenv
from backend.visualizer.services.logger import get_logger

logger = get_logger(__name__)

API_KEY_ENVIRONMENT_VARIABLE = "GOOGLE_API_KEY"
DEFAULT_RETRY_DELAY_SECONDS = 1


class LLMClient:
    """
    A generic client for interacting with the Google Gemini API.

    Attributes:
        _model (str): The model identifier (e.g., "gemini-2.5-flash-lite").
        _client (genai.Client): The authenticated Gemini client instance.
    """

    def __init__(
        self, model: str = "gemini-2.5-flash-lite", load_environment: bool = True
    ):
        if load_environment:
            load_dotenv()

        if API_KEY_ENVIRONMENT_VARIABLE not in os.environ:
            raise ValueError(f"{API_KEY_ENVIRONMENT_VARIABLE} not set")

        self._model = model
        self._client = genai.Client()

    def _call_api(self, prompt: str) -> str:
        response = self._client.models.generate_content(
            model=self._model, contents=prompt
        )
        return str(response.text)

    def generate_content(self, prompt: str, retry_count: int = 3) -> str:
        """
        Sends a prompt to the LLM and retrieves the text response.

        Args:
            prompt (str): The input text prompt.
            retries (int): Number of times to retry on failure.

        Returns:
            str: The raw text response from the LLM.

        Raises:
            Exception: If the API call fails after all retries.
        """
        for attempt in range(1, retry_count + 1):
            try:
                result = self._call_api(prompt)
                logger.debug("LLM API call succeeded on attempt %d", attempt)
                return result
            except (ConnectionError, TimeoutError) as error:
                logger.warning(
                    "LLM API call failed on attempt %d/%d: %s",
                    attempt,
                    retry_count,
                    error,
                )
                if attempt == retry_count:
                    logger.exception(
                        "LLM API call failed after %d attempts", retry_count
                    )
                    raise
                time.sleep(DEFAULT_RETRY_DELAY_SECONDS)
        return ""

    @staticmethod
    def clean_markdown_block(text: str, block_type: str = "") -> str:
        """
        Utilities to strip markdown code blocks (e.g., ```sql ... ```).

        Args:
            text (str): The text containing markdown.
            block_type (str): The tag to look for (e.g., "sql", "json").
                              If empty, cleans generic blocks.

        Returns:
            str: The cleaned string content.
        """
        pattern = f"```{block_type}"
        if text.startswith(pattern):
            parts = text.split(pattern, 1)
            if len(parts) > 1:
                return parts[1].strip().rstrip("```").strip()
        return text.strip("`").strip()


if __name__ == "__main__":
    import argparse
    from backend.visualizer.services.logger import configure_logging

    parser = argparse.ArgumentParser(description="Test the LLMClient independently.")
    parser.add_argument("--prompt", type=str, default="Hello, are you working?")
    arguments = parser.parse_args()
    configure_logging()

    client = LLMClient()
    logger.info("Sending prompt: %s", arguments.prompt)
    response = client.generate_content(arguments.prompt)
    logger.info("Response:\n%s", response)
