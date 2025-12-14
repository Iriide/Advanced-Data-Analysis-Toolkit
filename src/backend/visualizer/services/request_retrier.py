import re
from typing import Callable, Optional, Any
import time
from google import genai
from backend.utils.logger import get_logger
from google.genai.errors import ClientError, ServerError

logger = get_logger(__name__)


class GeminiAPIRequestRetrier:

    class SourceExhaustedError(Exception):
        pass

    def __init__(
        self,
        retries: int = 3,
        wait_seconds_client: int = 60,
        wait_seconds_server: int = 5,
    ):
        """Initialize retry limits and backoff timings."""
        self._retries = retries
        self._original_retries = retries
        self._wait_seconds_client = wait_seconds_client
        self._wait_seconds_server = wait_seconds_server

    def _extract_status_from_error(
        self, error: ClientError
    ) -> Optional[tuple[int, str]]:
        """Extract HTTP status code and status string from a client error."""
        error_details = error.details.get("error", {})
        return error_details.get("code", None), error_details.get("status", None)

    def _extract_wait_time_from_error(
        self, error: ClientError, zero_to_minute: bool = True
    ) -> int:
        """Extract retry delay in seconds from a Gemini API error response."""
        # sample error details for reference:
        # {
        #   'error': {
        #       'code': 429,
        #       'message': 'You exceeded your current quota, please check your plan and billing details.
        #           For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits.
        #           To monitor your current usage, head to: https://ai.dev/usage?tab=rate-limit. \n
        #           * Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_input_token_count,
        #               limit: 15000,
        #               model: gemma-3-12b\n
        #               Please retry in 3.427436554s.',
        #       'status': 'RESOURCE_EXHAUSTED',
        #       'details': [
        #           {
        #               '@type': 'type.googleapis.com/google.rpc.Help',
        #               'links': [
        #                   {
        #                       'description': 'Learn more about Gemini API quotas',
        #                       'url': 'https://ai.google.dev/gemini-api/docs/rate-limits'
        #                   }
        #               ]
        #           },
        #           {
        #               '@type': 'type.googleapis.com/google.rpc.QuotaFailure',
        #               'violations': [
        #                   {
        #                       'quotaMetric': 'generativelanguage.googleapis.com/generate_content_free_tier_input_token_count',
        #                       'quotaId': 'GenerateContentInputTokensPerModelPerMinute-FreeTier',
        #                       'quotaDimensions': {'location': 'global', 'model': 'gemma-3-12b'},
        #                       'quotaValue': '15000'
        #                   }
        #               ]
        #           },
        #           {
        #               '@type': 'type.googleapis.com/google.rpc.RetryInfo',
        #               'retryDelay': '3s'
        #           }
        #       ]
        #   }
        # }

        error_details = error.details.get("error", {})

        seconds = None

        for detail in error_details.get("details", []):

            if detail.get("@type") != "type.googleapis.com/google.rpc.RetryInfo":
                continue

            match = re.match(r"(\d+)(\.\d+)?s", detail.get("retryDelay", ""))

            if match:
                seconds = float(match.group(1))
                if match.group(2):
                    seconds += float(match.group(2))
                if zero_to_minute and seconds == 0:
                    return 60
                break

        if seconds is None:
            return self._wait_seconds_client

        return int(seconds)

    def _handle_client_error(self, error: ClientError) -> int:
        """Handle client-side API errors and determine retry delay."""
        retry_timeout = self._wait_seconds_client

        e_for_print = str(error)

        error_details = error.details.get("error", {})
        if error_details.get("code") == 429:
            retry_timeout = self._extract_wait_time_from_error(error)
            status = self._extract_status_from_error(error)
            e_for_print = f"{status[0]} {status[1]}" if status else "429 (Unknown)"
        if error_details.get("code") == 404:
            raise RuntimeError("Gemini API model not found (404). Check model name.")

        logger.warning(f"ClientError encountered: {e_for_print}")

        return retry_timeout

    def _handle_server_error(self, error: ServerError) -> int:
        """Handle server-side API errors and determine retry delay."""
        logger.warning(f"ServerError encountered: {error}")
        return self._wait_seconds_server

    def _sleep(self, seconds: int) -> None:
        """Sleep for the given number of seconds."""
        for _ in range(seconds):
            time.sleep(1)

    def run(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Execute a callable with retry logic for Gemini API errors."""
        retries_left = self._retries

        while True:
            retry_timeout = None
            try:
                return func(*args, **kwargs)

            except genai.errors.ClientError as e:
                retry_timeout = self._handle_client_error(e)

            except genai.errors.ServerError as e:
                retry_timeout = self._handle_server_error(e)

            if retries_left <= 0:
                logger.info("No retries left. Raising exception.")
                raise self.SourceExhaustedError("All retries exhausted.")

            logger.info(f"Retrying in {retry_timeout} seconds...")
            self._sleep(retry_timeout)
            retries_left -= 1

    def reset_retries(self, new_retries: Optional[int] = None) -> None:
        """Reset retry counter to the original or a new value."""
        if new_retries is not None:
            self._retries = new_retries
        else:
            self._retries = self._original_retries

    def retries_exhausted(self) -> bool:
        """Return True if no retries remain."""
        return self._retries <= 0
