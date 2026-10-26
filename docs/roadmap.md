# Roadmap

Deliberately out of scope for the template, with pointers for adding them. None
of these are required to run in production; they are the next layers a service
usually grows into.

## Observability

- **Distributed tracing** (OpenTelemetry): spans across ASGI + SQLAlchemy, with
  the trace id added to the log context. See
  [observability.md](observability.md#tracing-roadmap).
- **Error tracking** (Sentry et al.): initialise in the app lifespan and rely on
  the existing exception handlers.
- **Push metrics / exemplars** if you move beyond pull-based scraping.

## Security

- **JWT / OAuth2** bearer auth with scopes and a user identity, replacing the
  static API-key list. See [authentication.md](authentication.md#swapping-in-jwt--oauth).
- **Shared rate limiting** (Redis/edge) for multi-worker deployments.
- **Request body size limits** and upload scanning for endpoints that accept
  large payloads.
- **mTLS / service mesh** policy for internal traffic.

## Data

- **Read replicas** — note that the request-scoped transaction means reads see
  the request's own writes; replicas need a separate read session.
- **Cursor pagination** for large, ordered collections (offset pagination is
  provided today).
- **Optimistic concurrency** (`version` column / `ETag` / `If-Match`).
- **Audit columns** (`created_by`, `updated_by`) and soft deletes.
- **Idempotency keys** for `POST`.

## API

- **Problem details** (RFC 9457) if you need a standard error body over the
  current `{ "error": { ... } }` envelope.
- **Sorting/filtering** on list endpoints.
- **Response caching** (`ETag`/`Cache-Control`).

## Platform

- **Kubernetes manifests / Helm chart** with resource limits, probes, and a
  `PodDisruptionBudget`.
- **CD pipeline** that builds/pushes a signed image and runs `alembic upgrade
  head` as a release step.
- **SBOM** generation and image scanning (Trivy/Grype) in CI.

If you implement any of these, add a page under `docs/` and link it from
[the index](README.md), and update [`AGENTS.md`](../AGENTS.md) if it changes a
convention.
