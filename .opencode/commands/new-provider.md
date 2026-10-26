---
description: Scaffold a market data provider adapter
agent: build
---

Add a new price provider named $ARGUMENTS following AGENTS.md.

1. Add provider settings to `Settings` and `.env.local.example`: symbol list,
   endpoint, poll/connection options, staleness seconds, and backoff.
2. Add a pure normalizer in `src/providers/normalizer.py`; parse provider
   payloads into `Decimal` ticks. Never parse provider payloads elsewhere.
3. Add `src/providers/<name>.py` subclassing `BaseProvider`. Reuse its
   reconnect/backoff/circuit-breaker behavior; own only the protocol loop.
4. Register the adapter in `src/providers/registry.py` and wire its status into
   the existing `/v1/providers/status` endpoint.
5. Add fixture-driven unit tests for normalization, malformed payloads, and
   provider failure. Use injected fake clients; never call the live provider.
6. Add stale-threshold and config tests.
7. Document the provider in `docs/providers.md` and `docs/configuration.md`.

Finish with `mise run check`.
