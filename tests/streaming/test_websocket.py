"""End-to-end WebSocket route tests via TestClient."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app import app


def test_websocket_route_reports_protocol_errors() -> None:
    with TestClient(app) as client, client.websocket_connect("/v1/ws/rates") as websocket:
        websocket.send_text("not-json")
        assert websocket.receive_json()["code"] == "invalid_json"

        websocket.send_json({"action": "subscribe", "symbols": ["DOGE/USD"]})
        assert websocket.receive_json()["code"] == "unknown_symbol"
