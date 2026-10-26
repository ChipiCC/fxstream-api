"""Tests for application wiring: lifespan, logging, and error envelopes."""

from __future__ import annotations

import logging

from httpx import AsyncClient

from app import app
from core.logging import configure_logging, get_logger


async def test_lifespan_starts_and_stops_cleanly() -> None:
    async with app.router.lifespan_context(app):
        pass


def test_configure_logging_json_and_console() -> None:
    configure_logging(log_level="DEBUG", json_logs=True)
    assert logging.getLogger().level == logging.DEBUG
    logger = get_logger("test")
    logger.info("json_event", key="value")

    configure_logging(log_level="INFO", json_logs=False)
    logger.info("console_event")


async def test_http_error_envelope(client: AsyncClient) -> None:
    response = await client.get("/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "http_error"
