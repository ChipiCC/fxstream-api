# Observability

The template provides structured logging, request IDs, access logs, and
Prometheus metrics. Distributed tracing is **not** wired up yet — see
[roadmap.md](roadmap.md).

## Logging

`structlog` is configured in [`src/core/logging.py`](../src/core/logging.py) and
initialised once during startup (`configure_logging` in the app lifespan). The
stdlib root logger is redirected through structlog so third-party logs share the
same formatting.

- `LOG_JSON=true` (default) emits one JSON object per line — ideal for log
  aggregators.
- `LOG_LEVEL` sets the root level.
- Noisy loggers (`uvicorn.access`, `sqlalchemy.engine.Engine`) are quieted.

Emit logs with `get_logger(__name__)` and pass structured fields:

```python
logger = get_logger(__name__)
logger.info("order_created", order_id=str(order.id), total=order.total)
```

`print` is banned by Ruff (`T20`).

## Request context and access logs

[`RequestContextMiddleware`](../src/core/middleware.py) is a pure-ASGI
middleware that:

1. Reads `X-Request-ID` (or generates a UUID) and binds `request_id`, `method`,
   and `path` to the structlog context.
2. Echoes the id back in the `X-Request-ID` response header.
3. Emits one `http_request` access-log event per request with `status_code` and
   `duration_ms`.

Because the fields are bound to context variables, every log line emitted while
handling the request — including repository errors — automatically carries the
request id.

Clients can correlate by sending their own `X-Request-ID`:

```bash
curl -H "X-Request-ID: trace-123" http://localhost:8000/health/live
```

## Metrics

See [metrics.md](metrics.md) for Prometheus instrumentation and the `/metrics`
endpoint.

## Tracing (roadmap)

OpenTelemetry is not included to keep the dependency surface small. To add it:

1. Add `opentelemetry-distro` and the exporter/auto-instrumentation packages.
2. Initialise a `TracerProvider` with a resource (`service.name`,
   `service.version`) in the app lifespan.
3. Instrument ASGI and SQLAlchemy (`opentelemetry-instrumentation-asgi`,
   `-sqlalchemy`).
4. Propagate the trace id alongside `request_id` in the log context.

Until then, `request_id` plus access logs give most of the correlation value.

## Health endpoints

- `GET /health/live` — liveness; process is up, no dependencies touched.
- `GET /health/ready` — readiness; checks the database and returns **503** when
  it is unreachable. See [operations.md](operations.md).
