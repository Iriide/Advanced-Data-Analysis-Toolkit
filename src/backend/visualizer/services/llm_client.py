import os
import re
from google import genai
from dotenv import load_dotenv
from backend.utils.logger import get_logger
from backend.visualizer.services.request_retrier import GeminiAPIRequestRetrier

logger = get_logger(__name__)

API_KEY_ENVIRONMENT_VARIABLE = "GOOGLE_API_KEY"


class LLMClient:
    """
    A generic client for interacting with the Google Gemini API.

    Attributes:
        _model (str): The model identifier (e.g., "gemma-3-4b-it").
        _client (genai.Client): The authenticated Gemini client instance.
    """

    def __init__(self, model: str = "gemma-3-4b-it", load_environment: bool = True):
        if load_environment:
            load_dotenv()

        if API_KEY_ENVIRONMENT_VARIABLE not in os.environ:
            logger.warning(f"{API_KEY_ENVIRONMENT_VARIABLE} not set")

        self._model = model
        self._client = genai.Client()
        self._request_retrier = GeminiAPIRequestRetrier()

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
            retry_count (int): Number of times to retry on failure.

        Returns:
            str: The raw text response from the LLM.

        Raises:
            Exception: If the API call fails after all retry_count.
        """

        retrier = self._request_retrier

        retrier.reset_retries(retry_count)

        try:

            result = retrier.run(
                self._call_api,
                prompt,
            )
            logger.debug("LLM API call succeeded.")
            return str(result)  # this is to satisfy type checker

        except GeminiAPIRequestRetrier.SourceExhaustedError as e:
            logger.error(f"LLM API call failed after {retry_count} retries: {e}")
        except RuntimeError as e:
            logger.error(f"LLM API call failed with runtime error: {e}")

        return ""

    @staticmethod
    def clean_markdown_block(text: str, block_type: str | None = None) -> str:
        """
        Strips Markdown code block delimiters from a string.

        Args:
            text: The input string containing code (potentially inside markdown fences).
            block_type: The expected language identifier (e.g., 'sql').
                        Accepts regex patterns (e.g., 'sql(lite)?').
        """
        if not text:
            return ""

        text = text.strip()

        lang_pattern = block_type if block_type else r"\w*"

        # Regex explanation:
        # ^```                 : Starts with ```
        # (?:{lang_pattern})?  : Optional non-capturing group for the language tag
        # \n?                  : Optional newline after the tag
        # (.*?)                : Capture group for the actual content (non-greedy)
        # (?:```)?$            : Optional closing fence at the end of string
        pattern = rf"^```(?:{lang_pattern})?\n?(?P<content>.*?)(?:```)?$"

        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)

        if match:
            return match.group("content").strip()

        return text


if __name__ == "__main__":
    import argparse
    from backend.utils.logger import configure_logging
    import re

    parser = argparse.ArgumentParser(description="Test the LLMClient independently.")
    parser.add_argument("--prompt", type=str, default="Hello, are you working?")
    arguments = parser.parse_args()
    configure_logging()

    client = LLMClient()
    logger.info("Sending prompt: %s", arguments.prompt)
    response = client.generate_content(arguments.prompt)
    logger.info("Response:\n%s", response)
