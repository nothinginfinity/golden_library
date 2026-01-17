#!/usr/bin/env python3
"""
Retry Utilities for Phase 4C

Provides retry logic with exponential backoff for transient failures.
"""

import asyncio
import functools
import logging
from typing import Callable, TypeVar, Any, Optional, Tuple, Type
from dataclasses import dataclass

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)


DEFAULT_CONFIG = RetryConfig()


class RetryExhausted(Exception):
    """Raised when all retry attempts are exhausted."""
    def __init__(self, last_exception: Exception, attempts: int):
        self.last_exception = last_exception
        self.attempts = attempts
        super().__init__(f"Retry exhausted after {attempts} attempts: {last_exception}")


async def retry_async(
    func: Callable[..., T],
    *args,
    config: Optional[RetryConfig] = None,
    **kwargs
) -> T:
    """
    Retry an async function with exponential backoff.

    Args:
        func: Async function to retry
        *args: Arguments to pass to func
        config: Retry configuration
        **kwargs: Keyword arguments to pass to func

    Returns:
        Result of func

    Raises:
        RetryExhausted: When all retry attempts fail
    """
    cfg = config or DEFAULT_CONFIG
    last_exception = None

    for attempt in range(1, cfg.max_attempts + 1):
        try:
            return await func(*args, **kwargs)
        except cfg.retryable_exceptions as e:
            last_exception = e

            if attempt == cfg.max_attempts:
                logger.warning(f"Retry exhausted for {func.__name__} after {attempt} attempts")
                raise RetryExhausted(e, attempt)

            # Calculate delay with exponential backoff
            delay = min(
                cfg.initial_delay * (cfg.exponential_base ** (attempt - 1)),
                cfg.max_delay
            )

            # Add jitter to prevent thundering herd
            if cfg.jitter:
                import random
                delay = delay * (0.5 + random.random())

            logger.info(f"Retry {attempt}/{cfg.max_attempts} for {func.__name__}, waiting {delay:.2f}s")
            await asyncio.sleep(delay)

    # Should not reach here, but just in case
    raise RetryExhausted(last_exception, cfg.max_attempts)


def retry(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    Decorator for adding retry logic to async functions.

    Usage:
        @retry(max_attempts=3, retryable_exceptions=(ConnectionError, TimeoutError))
        async def fetch_data():
            ...
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        initial_delay=initial_delay,
        max_delay=max_delay,
        retryable_exceptions=retryable_exceptions
    )

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            return await retry_async(func, *args, config=config, **kwargs)
        return wrapper

    return decorator


class CircuitBreaker:
    """
    Circuit breaker for protecting against cascading failures.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Failures exceeded threshold, requests fail immediately
    - HALF_OPEN: Testing if service recovered
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = self.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0

    @property
    def state(self) -> str:
        return self._state

    def _should_allow_request(self) -> bool:
        """Check if request should be allowed based on current state."""
        if self._state == self.CLOSED:
            return True

        if self._state == self.OPEN:
            # Check if recovery timeout has passed
            import time
            if self._last_failure_time and \
               (time.time() - self._last_failure_time) >= self.recovery_timeout:
                self._state = self.HALF_OPEN
                self._half_open_calls = 0
                logger.info("Circuit breaker entering HALF_OPEN state")
                return True
            return False

        if self._state == self.HALF_OPEN:
            return self._half_open_calls < self.half_open_max_calls

        return False

    def record_success(self):
        """Record a successful call."""
        if self._state == self.HALF_OPEN:
            self._half_open_calls += 1
            if self._half_open_calls >= self.half_open_max_calls:
                self._state = self.CLOSED
                self._failure_count = 0
                logger.info("Circuit breaker CLOSED - service recovered")
        else:
            self._failure_count = 0

    def record_failure(self):
        """Record a failed call."""
        import time
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._state == self.HALF_OPEN:
            self._state = self.OPEN
            logger.warning("Circuit breaker OPEN - failure during half-open")
        elif self._failure_count >= self.failure_threshold:
            self._state = self.OPEN
            logger.warning(f"Circuit breaker OPEN - {self._failure_count} failures")

    async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute function through circuit breaker.

        Raises:
            CircuitBreakerOpen: If circuit is open
        """
        if not self._should_allow_request():
            raise CircuitBreakerOpen(f"Circuit breaker is {self._state}")

        try:
            result = await func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            raise


class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is open."""
    pass


# Pre-configured circuit breakers for external services
_circuit_breakers = {}


def get_circuit_breaker(service_name: str) -> CircuitBreaker:
    """Get or create circuit breaker for a service."""
    if service_name not in _circuit_breakers:
        _circuit_breakers[service_name] = CircuitBreaker()
    return _circuit_breakers[service_name]


def circuit_breaker(service_name: str):
    """
    Decorator for adding circuit breaker protection.

    Usage:
        @circuit_breaker("deepseek_api")
        async def call_deepseek():
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            cb = get_circuit_breaker(service_name)
            return await cb.call(func, *args, **kwargs)
        return wrapper
    return decorator


if __name__ == "__main__":
    import asyncio

    # Test retry
    async def test_retry():
        attempt = [0]

        @retry(max_attempts=3, initial_delay=0.1)
        async def flaky_function():
            attempt[0] += 1
            if attempt[0] < 3:
                raise ConnectionError("Simulated failure")
            return "success"

        result = await flaky_function()
        print(f"Result after {attempt[0]} attempts: {result}")

    # Test circuit breaker
    async def test_circuit_breaker():
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1.0)

        async def failing_service():
            raise ConnectionError("Service down")

        # Trigger failures
        for i in range(5):
            try:
                await cb.call(failing_service)
            except (ConnectionError, CircuitBreakerOpen) as e:
                print(f"Call {i+1}: {type(e).__name__}")

        print(f"Circuit state: {cb.state}")

    asyncio.run(test_retry())
    print()
    asyncio.run(test_circuit_breaker())
