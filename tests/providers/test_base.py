"""Tests for shared provider resilience and status reporting."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from market.models import ProviderState
from providers.base import BaseProvider, TickSink
from tests.helpers.fakes import FakeClock, make_tick


class FlakyProvider(BaseProvider):
    name = "flaky"

    def __init__(self, failures: int, *, sleep: Callable[[float], Awaitable[None]]) -> None:
        super().__init__(
            clock=FakeClock(),
            failure_threshold=3,
            backoff_initial_seconds=1,
            backoff_max_seconds=10,
            sleep=sleep,
        )
        self.failures = failures
        self.calls = 0

    async def _run(self, sink: TickSink) -> None:
        self.calls += 1
        if self.calls <= self.failures:
            raise RuntimeError("temporary provider failure")
        self._emit(make_tick(source="flaky"), sink)
        await self.stop()


async def test_provider_retries_with_backoff_and_recovers() -> None:
    sleeps: list[float] = []
    statuses: list[ProviderState] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    provider = FlakyProvider(2, sleep=fake_sleep)

    def sink(tick: object) -> None:
        statuses.append(provider.status().state)

    await provider.run(sink)

    assert sleeps == [1.0, 2.0]
    assert provider.calls == 3
    assert statuses[-1] is ProviderState.UP
    assert provider.status().last_message_at is not None
    assert provider.status().reconnects == 2


async def test_provider_opens_circuit_after_threshold() -> None:
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    class AlwaysFailing(BaseProvider):
        name = "failing"

        def __init__(self) -> None:
            super().__init__(
                clock=FakeClock(),
                failure_threshold=3,
                backoff_initial_seconds=1,
                backoff_max_seconds=10,
                sleep=fake_sleep,
            )
            self.calls = 0

        async def _run(self, sink: TickSink) -> None:
            self.calls += 1
            if self.calls >= 3:
                await self.stop()
            raise RuntimeError("down")

    provider = AlwaysFailing()
    await provider.run(lambda _tick: None)

    assert provider.calls == 3
    assert provider.status().state is ProviderState.DOWN
    assert sleeps == [1.0, 2.0]


async def test_message_error_degrades_without_stopping() -> None:
    class MessageErrorProvider(BaseProvider):
        name = "message-error"

        async def _run(self, sink: TickSink) -> None:
            self._record_message_error(ValueError("bad payload"))
            self._emit(make_tick(source="message-error"), sink)
            await self.stop()

    provider = MessageErrorProvider(clock=FakeClock())
    await provider.run(lambda _tick: None)
    assert provider.status().state is ProviderState.DOWN
