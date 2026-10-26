"""Tests for the Frankfurter polling adapter."""

from __future__ import annotations

import httpx
import pytest

from market.models import Tick
from providers.frankfurter import FrankfurterProvider
from tests.helpers.fakes import FakeClock


async def test_poll_once_emits_one_tick_per_quote() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["from"] == "EUR"
        assert request.url.params["to"] == "USD,GBP"
        return httpx.Response(
            200,
            json={
                "base": "EUR",
                "date": "2026-10-26",
                "rates": {"USD": 1.08, "GBP": 0.86},
            },
        )

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://frankfurter.test",
    )
    provider = FrankfurterProvider(
        clock=FakeClock(),
        symbols=["EUR/USD", "EUR/GBP"],
        base_url="https://frankfurter.test",
        client=client,
    )
    ticks: list[Tick] = []

    def sink(tick: Tick) -> None:
        ticks.append(tick)

    try:
        await provider.poll_once(sink)
    finally:
        await client.aclose()

    assert [tick.symbol for tick in ticks] == ["EUR/USD", "EUR/GBP"]
    assert provider.status().state.value == "up"


async def test_poll_once_propagates_http_errors() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://frankfurter.test",
    )
    provider = FrankfurterProvider(
        clock=FakeClock(),
        symbols=["EUR/USD"],
        base_url="https://frankfurter.test",
        client=client,
    )
    try:
        with pytest.raises(httpx.HTTPStatusError):
            await provider.poll_once(lambda _tick: None)
    finally:
        await client.aclose()


async def test_poll_once_rejects_non_object_response() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=["not", "an", "object"])

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://frankfurter.test",
    )
    provider = FrankfurterProvider(
        clock=FakeClock(),
        symbols=["EUR/USD"],
        base_url="https://frankfurter.test",
        client=client,
    )
    try:
        with pytest.raises(ValueError):
            await provider.poll_once(lambda _tick: None)
    finally:
        await client.aclose()


async def test_owned_client_is_closed() -> None:
    provider = FrankfurterProvider(
        clock=FakeClock(),
        symbols=[],
        base_url="https://frankfurter.test",
    )
    await provider.stop()
    assert provider.status().state.value == "down"
