---
description: Reviews FXStream changes against the HLD and repository invariants
mode: subagent
permissions:
  - action: edit
    resource: "*"
    effect: deny
  - action: shell
    resource: "*"
    effect: deny
  - action: shell
    resource: "mise run check"
    effect: allow
  - action: shell
    resource: "uv run pytest*"
    effect: allow
  - action: shell
    resource: "uv run ruff*"
    effect: allow
  - action: shell
    resource: "uv run mypy*"
    effect: allow
  - action: shell
    resource: "git status *"
    effect: allow
  - action: shell
    resource: "git diff *"
    effect: allow
  - action: shell
    resource: "git log *"
    effect: allow
---

Review the current changes for FXStream API. Do not edit files.

Check specifically:

- `Decimal` is used for every price, amount, spread, and candle value.
- Prices and quantities are serialized as strings at the API boundary.
- Quotes are immutable, expire correctly, and reject stale or missing rates.
- Staleness uses each tick's `as_of` with the correct per-provider threshold.
- The event bus never blocks; slow WebSocket clients keep the latest tick per
  symbol and never stall ingestion.
- Provider adapters isolate failures, reconnect with backoff, and do not crash
  the application on malformed payloads.
- Background candle writes own their session and do not reuse request sessions.
- All SQL is native, parameterized, and covered by a migration.
- REST and WebSocket contracts match `docs/high-level-design.md`.
- Tests do not call live providers and cover error paths.
- Ruff, mypy, and coverage rules are not weakened.

Report findings in severity order with file and line references. Finish with a
short list of missing tests, if any.
