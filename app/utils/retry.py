from __future__ import annotations

import random
import time
from typing import Callable, Iterable, TypeVar

T = TypeVar("T")


def execute_with_retry(
    func: Callable[[], T],
    *,
    max_attempts: int = 3,
    base_delay: float = 1.5,
    cap_seconds: float = 30.0,
    jitter: bool = True,
    non_retry_exceptions: Iterable[type[BaseException]] = (),
) -> T:
    """
    Execute callable with retry logic and exponential backoff.

    Args:
        func: Callable to execute.
        max_attempts: Total attempts before giving up (must be >= 1).
        base_delay: Base delay factor for exponential backoff.
        cap_seconds: Maximum delay between attempts.
        jitter: Whether to apply random jitter (80%-120%) to delay.
        non_retry_exceptions: Iterable of exception classes that should not be retried.
    """
    attempts = 0
    non_retry_tuple = tuple(non_retry_exceptions)

    while True:
        try:
            return func()
        except non_retry_tuple:
            raise
        except Exception:
            attempts += 1
            if attempts >= max_attempts:
                raise

            delay = base_delay**attempts
            delay = min(delay, cap_seconds)
            if jitter:
                delay *= random.uniform(0.8, 1.2)
            time.sleep(delay)

