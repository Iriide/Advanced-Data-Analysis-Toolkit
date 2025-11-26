import os
import time
from google import genai
from dotenv import load_dotenv
from core.logger import get_logger

logger = get_logger(__name__)


class LLMClient:
    """
    A generic client for interacting with the Google Gemini API.

    Attributes:
        _model (str): The model identifier (e.g., "gemini-2.5-flash-lite").
        _client (genai.Client): The authenticated Gemini client instance.
    """

    def __init__(self, model: str = "gemini-2.5-flash-lite", load_env: bool = True):
        """
        Initializes the LLMClient.

        Args:
            model (str): The name of the model to use.
            load_env (bool): Whether to load environment variables from .env file.

        Raises:
            ValueError: If GOOGLE_API_KEY is not found in environment variables.
        """
        if load_env:
            load_dotenv()

        if "GOOGLE_API_KEY" not in os.environ:
            logger.warning("GOOGLE_API_KEY not found in environment variables.")
            # Depending on strictness, you might want to raise an error here
            # raise ValueError("GOOGLE_API_KEY not set")

        self._model = model
        self._client = genai.Client()

    def generate_content(self, prompt: str, retries: int = 3) -> str:
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
        for attempt in range(1, retries + 1):
            try:
                response = self._client.models.generate_content(
                    model=self._model, contents=prompt
                )
                logger.debug("LLM API call succeeded on attempt %d", attempt)
                # Ensure we return a str (some client response types are not typed)
                return str(response.text)
            except Exception as e:
                # Log a warning during retries to avoid noisy error level logs.
                logger.warning(
                    "LLM API call failed on attempt %d/%d: %s", attempt, retries, e
                )
                if attempt == retries:
                    # Final failure: include stack trace and re-raise
                    logger.exception("LLM API call failed after %d attempts", retries)
                    raise
                time.sleep(1)  # Backoff slightly
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
            # Split by the header, take the rest, then rstrip the trailing ```
            parts = text.split(pattern, 1)
            if len(parts) > 1:
                return parts[1].strip().rstrip("```").strip()

        # Fallback: just strip backticks if strictly wrapped
        return text.strip("`").strip()


if __name__ == "__main__":
    import argparse

    # Sample usage for independent testing
    parser = argparse.ArgumentParser(description="Test the LLMClient independently.")
    parser.add_argument(
        "--prompt", type=str, default="Hello, are you working?", help="Prompt to send."
    )
    args = parser.parse_args()

    try:
        # Try to ensure logging configured downstream if not already
        from core.logger import configure_logging

        configure_logging()
    except Exception:
        pass

    client = LLMClient()
    logger.info("Sending prompt: %s", args.prompt)
    try:
        response = client.generate_content(args.prompt)
        logger.info("Response:\n%s", response)
    except Exception as e:
        logger.exception("Test failed: %s", e)
