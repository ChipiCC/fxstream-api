"""Tests for the items CRUD endpoints."""

from __future__ import annotations

import uuid

from httpx import AsyncClient


async def test_create_item(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/items",
        json={"name": "Widget", "description": "A very nice widget"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Widget"
    assert body["description"] == "A very nice widget"
    assert uuid.UUID(body["id"])
    assert body["created_at"]


async def test_list_items(client: AsyncClient) -> None:
    for i in range(3):
        await client.post("/api/v1/items", json={"name": f"item-{i}"})

    response = await client.get("/api/v1/items", params={"limit": 2, "offset": 0})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["limit"] == 2
    assert body["offset"] == 0
    assert len(body["items"]) == 2


async def test_get_item(client: AsyncClient) -> None:
    created = (await client.post("/api/v1/items", json={"name": "thing"})).json()

    response = await client.get(f"/api/v1/items/{created['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


async def test_get_missing_item_returns_404(client: AsyncClient) -> None:
    response = await client.get(f"/api/v1/items/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_update_item(client: AsyncClient) -> None:
    created = (await client.post("/api/v1/items", json={"name": "old"})).json()

    response = await client.patch(f"/api/v1/items/{created['id']}", json={"name": "new"})
    assert response.status_code == 200
    assert response.json()["name"] == "new"


async def test_delete_item(client: AsyncClient) -> None:
    created = (await client.post("/api/v1/items", json={"name": "temp"})).json()

    response = await client.delete(f"/api/v1/items/{created['id']}")
    assert response.status_code == 204

    follow_up = await client.get(f"/api/v1/items/{created['id']}")
    assert follow_up.status_code == 404


async def test_create_validation_error(client: AsyncClient) -> None:
    response = await client.post("/api/v1/items", json={"name": ""})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_pagination_bounds(client: AsyncClient) -> None:
    response = await client.get("/api/v1/items", params={"limit": 999})
    assert response.status_code == 422
