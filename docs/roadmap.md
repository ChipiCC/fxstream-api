# Roadmap

Deliberately out of scope for the current FXStream scaffold.

## Scaling and state

- **Redis pub/sub + quote store** for multi-worker/multi-replica deployment.
- **Single-writer ingestion leader** if ingestion is split from the API.
- **Cross-process WebSocket fan-out**.
- **Shared rate limiting** at the edge or in Redis.

## Market data

- **Trade streams** for real volume and last-trade prices.
- **More providers** (e.g. OANDA, Polygon, Coinbase) behind `RateProvider`.
- **Candle retention/compaction** and time-range queries.
- **Order-book depth** if quote sizing needs liquidity.
- **Provider priority/failover** when two sources cover the same symbol.
- **Backfill/replay** for candles after downtime.

## Quotes

- **Quote persistence and audit** if regulators or clients require history.
- **Per-client spreads** or tiered pricing.
- **Execution/mock execution** and fill events.
- **Idempotency keys** for quote creation.

## API

- **Cursor pagination** for candle history.
- **REST snapshot pagination/filtering** if the symbol set grows.
- **Problem Details (RFC 9457)** instead of the current error envelope.
- **OpenAPI contract tests** generated from a published schema.

## Observability

- **Distributed tracing** (OpenTelemetry) across ASGI, provider clients, and SQL.
- **Error tracking** (Sentry et al.).
- **Provider latency and message-rate dashboards**.
- **Alerting** on provider `down`, stale feeds, and candle flush failures.

## Operations

- **Kubernetes manifests / Helm chart** with probes and disruption budgets.
- **CD pipeline** with migrations as a release step.
- **SBOM/image scanning**.
- **Runbooks** for provider outages and quote-store saturation.
