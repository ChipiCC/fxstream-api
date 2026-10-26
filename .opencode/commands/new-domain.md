---
description: Scaffold a new domain following the repo recipe
agent: build
---

Add a new domain named $ARGUMENTS following the "Adding a new domain" recipe in
AGENTS.md:

1. `mise run revision "add <name>"` with hand-written `CREATE TABLE` / `CREATE INDEX` SQL.
2. `src/<name>/models/` — `XCreate`, `XUpdate`, `XRead`; re-export from `__init__.py`.
3. `src/<name>/repository.py` — `<Name>Repository(BaseRepository[...])` with module-level `text(...)` SQL.
4. `src/<name>/service.py` — business logic only.
5. `src/<name>/handlers/<endpoint>.py` — one module per endpoint.
6. `src/<name>/router.py` — `APIRouter(prefix="/<names>", tags=[...])`.
7. `src/<name>/dependencies.py` — repository and service dependency aliases.
8. Register the router in `src/app.py`.
9. Add tests under `tests/<name>/`.

Use native parameterized SQL only (no ORM, no autogenerate). Repositories must
not commit — the session owns the transaction. Finish by running `mise run check`.
