---
description: Run a local REST/WebSocket smoke test
agent: build
---

Run the local FXStream smoke test.

1. Start Postgres with `mise run db:up` and apply migrations with
   `mise run migrate`.
2. Start the API in the background with `mise run dev`.
3. Verify `GET /health`, `GET /v1/rates`, and `GET /v1/providers/status`.
4. Create a quote with `POST /v1/quotes` and fetch it with
   `GET /v1/quotes/{quote_id}`. If `API_KEYS` is configured, send the
   `X-API-Key` header.
5. Connect to `WS /v1/ws/rates`, subscribe to a configured symbol, and confirm
   at least one tick arrives. Use a short Python `websockets` snippet if
   `websocat` is unavailable.
6. Stop the server and report the observed results. Do not leave background
   processes running.
