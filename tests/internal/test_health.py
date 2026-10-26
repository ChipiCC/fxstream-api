"""Tests for the internal domain: service metadata and health probes."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import cast

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import app
from db.session import get_session


class _BrokenSession:
    """A session whose queries always fail, to exercise the failure path."""

    async def execute(self, *args: object, **kwargs: object) -> object:
        raise RuntimeError("database is down")


@pytest.fixture
async def broken_db_client() -> AsyncIterator[AsyncClient]:
    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        yield cast(AsyncSession, _BrokenSession())

    app.dependency_overrides[get_session] = _override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
    app.dependency_overrides.clear()


async def test_root(client: AsyncClient) -> None:
    response = await client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["version"]
    assert body["docs"] == "/docs"


async def test_liveness(client: AsyncClient) -> None:
    response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readiness(client: AsyncClient) -> None:
    response = await client.get("/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"]["database"] == "ok"


async def test_readiness_reports_503_when_database_down(
    broken_db_client: AsyncClient,
) -> None:
    response = await broken_db_client.get("/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "error"
    assert body["checks"]["database"] == "error"
