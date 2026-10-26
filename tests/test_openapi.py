"""Contract checks for the public API schema."""

from __future__ import annotations

from httpx import AsyncClient

from quotes.models import Quote


async def test_openapi_contains_hld_paths(client: AsyncClient) -> None:
    document = (await client.get("/openapi.json")).json()
    paths = document["paths"]
    assert "/health" in paths
    assert "/v1/rates" in paths
    assert "/v1/rates/{base}/{quote}/candles" in paths
    assert "/v1/quotes" in paths
    assert "/v1/quotes/{quote_id}" in paths
    assert "/v1/providers/status" in paths


def test_quote_example_matches_model() -> None:
    schema = Quote.model_json_schema()
    example = schema["example"]
    quote = Quote.model_validate(example)
    assert quote.symbol == "BTC/USDT"
    assert quote.side.value == "buy"
    assert quote.bid < quote.ask
