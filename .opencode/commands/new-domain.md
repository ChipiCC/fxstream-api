---
description: Scaffold a new REST domain following the FXStream recipe
agent: build
---

Add a new domain named $ARGUMENTS following the architecture and invariants in
AGENTS.md.

1. Decide whether the domain needs persistence. If it does, create a raw-SQL
   migration with `mise run revision "add <name>"`.
2. Add Pydantic request/response models under `src/<name>/models.py` (or
   `models/` when there are several).
3. Add business logic in `src/<name>/engine.py` or `service.py`; it must not
   parse provider payloads or write SQL.
4. Add native parameterized SQL in `src/<name>/repository.py` only when the
   domain persists data. Repositories do not commit.
5. Add one handler module per endpoint under `src/<name>/handlers/`.
6. Add `src/<name>/router.py` and `dependencies.py`; use the shared market
   runtime dependency instead of constructing stores in handlers.
7. Register the router in `src/app.py` under `settings.api_v1_prefix`.
8. Add unit and API tests under `tests/<name>/`. No live network.
9. Update `docs/`, `.env.local.example`, and AGENTS.md when the domain adds
   settings or conventions.

Finish with `mise run check`.
