# Contributing

Thanks for contributing. This template values consistency and a green build —
please read [`AGENTS.md`](AGENTS.md) and the [`docs/`](docs/README.md) first.

## Setup

```bash
mise install
mise run sync
cp .env.example .env
mise run db:up
mise run migrate
```

## Before you push

Install the git hooks once:

```bash
uv run pre-commit install
```

Then make sure the full check passes:

```bash
mise run check     # lint + typecheck + tests (requires Postgres)
```

`mise run check` is the definition of done: Ruff, strict mypy, and the test
suite with the coverage gate all pass, and any schema change has a raw-SQL
migration (see [`docs/database.md`](docs/database.md)).

## Guidelines

- **Follow the layering.** Handlers stay thin; services hold logic; repositories
  hold SQL. Do not bypass the service layer from a handler.
- **Native SQL only.** No ORM, no autogenerate. Parameterize every value. See
  [`AGENTS.md`](AGENTS.md#native-sql).
- **Type everything.** mypy runs in strict mode; avoid `Any`.
- **Format with the tools.** Run `mise run fix`; do not hand-format.
- **Do not weaken tooling** (Ruff/mypy/coverage thresholds) to make code pass —
  fix the code.
- **Document.** New settings go in `.env.example` and
  [`docs/configuration.md`](docs/configuration.md); new subsystems get a page
  under [`docs/`](docs/README.md).
- **Tests.** Cover the happy path and error paths. Add new repository
  implementations to the parametrized contract fixture.

## Commit / PR

- Keep one logical change per migration and per PR where practical.
- Describe the change and note any new configuration or migration.
