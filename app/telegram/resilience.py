"""Network resilience, rate-limit backoff, and Telegram error recovery utilities."""

import asyncio
import random
from typing import Any, Callable, Coroutine, Optional, TypeVar
from telethon.errors import FloodWaitError, RPCError

from ..core.logger import get_logger
from .exceptions import TelegramAppError

logger = get_logger("telegram.resilience")

T = TypeVar("T")


class TelegramRateLimitError(TelegramAppError):
    """Raised when Telegram requests a long FloodWait pause exceeding allowable threshold."""

    def __init__(self, seconds: int):
        self.seconds = seconds
        super().__init__(
            f"Telegram rate limit exceeded. Telegram requested a wait of {seconds} seconds."
        )


async def execute_with_retry(
    operation: Callable[[], Coroutine[Any, Any, T]],
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    max_flood_wait: int = 60,
    on_flood_wait: Optional[Callable[[int], None]] = None,
) -> T:
    """Execute an asynchronous Telegram operation with intelligent backoff and FloodWait handling.

    Args:
        operation: Zero-argument callable that returns a fresh coroutine each attempt.
        max_retries: Maximum number of retry attempts for transient errors.
        base_delay: Starting delay in seconds for exponential backoff.
        max_delay: Cap for backoff delay.
        max_flood_wait: Maximum seconds of FloodWait to automatically pause and resume.
        on_flood_wait: Optional callback receiving wait seconds when FloodWait occurs.

    Returns:
        The result of the successfully executed operation.
    """
    attempt = 0
    while True:
        try:
            return await operation()
        except FloodWaitError as fwe:
            wait_s = fwe.seconds
            logger.warning("Telegram FloodWaitError: required to wait %d seconds.", wait_s)
            if on_flood_wait:
                on_flood_wait(wait_s)

            if wait_s <= max_flood_wait:
                logger.info("Automatically backing off for %d seconds (+1s safety buffer)...", wait_s)
                await asyncio.sleep(wait_s + 1)
                continue
            else:
                logger.error("FloodWait of %ds exceeds maximum threshold of %ds.", wait_s, max_flood_wait)
                raise TelegramRateLimitError(wait_s) from fwe

        except (ConnectionError, asyncio.TimeoutError, RPCError) as exc:
            attempt += 1
            if attempt > max_retries:
                logger.error("Operation failed after %d retries. Final error: %s", max_retries, exc)
                raise

            # Exponential backoff with jitter
            jitter = random.uniform(0.1, 0.5)
            delay = min(max_delay, (base_delay * (2 ** (attempt - 1)))) + jitter
            logger.warning(
                "Transient network error (%s). Retrying in %.2fs (attempt %d/%d)...",
                exc,
                delay,
                attempt,
                max_retries,
            )
            await asyncio.sleep(delay)
