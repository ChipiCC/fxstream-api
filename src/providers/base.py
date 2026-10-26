"""Provider contract and shared reconnect/circuit-breaker behaviour."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from datetime import datetime

from core.clock import Clock
from core.logging import get_logger
from core.metrics import (
    PROVIDER_ERRORS,
    PROVIDER_LAST_MESSAGE,
    PROVIDER_MESSAGES,
    PROVIDER_RECONNECTS,
    PROVIDER_STATE,
)
from market.models import ProviderState, ProviderStatus, Tick

logger = get_logger(__name__)

TickSink = Callable[[Tick], None]
Sleep = Callable[[float], Awaitable[None]]

_STATE_VALUES: dict[ProviderState, int] = {
    ProviderState.DOWN: 0,
    ProviderState.DEGRADED: 1,
    ProviderState.UP: 2,
}


class RateProvider(ABC):
    """A source of normalized ticks."""

    name: str

    @abstractmethod
    async def run(self, sink: TickSink) -> None:
        """Connect or poll until stopped, emitting ticks through ``sink``."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop the provider and close owned resources."""

    @abstractmethod
    def status(self) -> ProviderStatus:
        """Return the provider's observable state."""


class BaseProvider(RateProvider):
    """Reusable resilience: backoff, circuit breaker, status, and metrics."""

    name = "base"

    def __init__(
        self,
        *,
        clock: Clock,
        failure_threshold: int = 3,
        backoff_initial_seconds: float = 1.0,
        backoff_max_seconds: float = 60.0,
        sleep: Sleep | None = None,
    ) -> None:
        self._clock = clock
        self._failure_threshold = failure_threshold
        self._backoff_initial = backoff_initial_seconds
        self._backoff_max = backoff_max_seconds
        self._sleep = sleep or asyncio.sleep
        self._state = ProviderState.DOWN
        self._last_message_at: datetime | None = None
        self._reconnects = 0
        self._failures = 0
        self._attempts = 0
        self._stop = asyncio.Event()
        self._set_state(ProviderState.DOWN)

    def stop_requested(self) -> bool:
        """Whether shutdown has been requested; method form prevents narrowing."""
        return self._stop.is_set()

    async def run(self, sink: TickSink) -> None:
        """Run the provider with reconnect and exponential backoff."""
        while not self._stop.is_set():
            self._attempts += 1
            if self._attempts > 1:
                self._reconnects += 1
                PROVIDER_RECONNECTS.labels(provider=self.name).inc()
            try:
                await self._run(sink)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._record_failure(exc)
            else:
                if self._stop.is_set():
                    break
                self._record_disconnect()

            if self._stop.is_set():
                break
            await self._sleep(self._backoff_seconds())

    async def stop(self) -> None:
        self._stop.set()
        await self._close()
        self._set_state(ProviderState.DOWN)

    def status(self) -> ProviderStatus:
        return ProviderStatus(
            name=self.name,
            state=self._state,
            last_message_at=self._last_message_at,
            reconnects=self._reconnects,
        )

    def _emit(self, tick: Tick, sink: TickSink) -> None:
        self._last_message_at = tick.received_at
        self._failures = 0
        self._set_state(ProviderState.UP)
        PROVIDER_MESSAGES.labels(provider=self.name).inc()
        PROVIDER_LAST_MESSAGE.labels(provider=self.name).set(tick.received_at.timestamp())
        logger.debug(
            "tick_received",
            source=self.name,
            symbol=tick.symbol,
            latency_ms=round((tick.received_at - tick.as_of).total_seconds() * 1000, 2),
        )
        sink(tick)

    def _record_message_error(self, exc: Exception) -> None:
        PROVIDER_ERRORS.labels(provider=self.name, kind="message").inc()
        if self._state is ProviderState.UP:
            self._set_state(ProviderState.DEGRADED)
        logger.warning(
            "provider_message_error",
            provider=self.name,
            error=str(exc),
        )

    def _record_failure(self, exc: Exception) -> None:
        self._failures += 1
        state = (
            ProviderState.DOWN
            if self._failures >= self._failure_threshold
            else ProviderState.DEGRADED
        )
        self._set_state(state)
        PROVIDER_ERRORS.labels(provider=self.name, kind="connection").inc()
        logger.warning(
            "provider_failure",
            provider=self.name,
            failures=self._failures,
            state=state.value,
            error=str(exc),
        )

    def _record_disconnect(self) -> None:
        self._failures += 1
        state = (
            ProviderState.DOWN
            if self._failures >= self._failure_threshold
            else ProviderState.DEGRADED
        )
        self._set_state(state)
        PROVIDER_ERRORS.labels(provider=self.name, kind="disconnect").inc()
        logger.warning(
            "provider_disconnected",
            provider=self.name,
            failures=self._failures,
            state=state.value,
        )

    def _backoff_seconds(self) -> float:
        exponent = max(0, self._failures - 1)
        return float(min(self._backoff_max, self._backoff_initial * (2**exponent)))

    def _set_state(self, state: ProviderState) -> None:
        self._state = state
        PROVIDER_STATE.labels(provider=self.name).set(_STATE_VALUES[state])

    @abstractmethod
    async def _run(self, sink: TickSink) -> None:
        """One connection/polling session. Implemented by concrete providers."""

    async def _close(self) -> None:
        """Close provider-owned resources; subclasses override when needed."""
