# Metrics

Prometheus metrics are exposed at `METRICS_PATH` (default `/metrics`) using
[`prometheus-client`](https://github.com/prometheus/client_python). The code
lives in [`src/core/metrics.py`](../src/core/metrics.py).

## Endpoint

```bash
curl http://localhost:8000/metrics
```

The route is registered in [`src/app.py`](../src/app.py), excluded from the
OpenAPI schema, and left unauthenticated so scrapers can reach it. Disable it
with `METRICS_ENABLED=false`.

## Instruments

| Metric | Type | Labels | Meaning |
| --- | --- | --- | --- |
| `http_requests_total` | Counter | `method`, `route`, `status_code` | Total requests served. |
| `http_request_duration_seconds` | Histogram | `method`, `route` | Request latency. |
| `app_info` | Gauge | `version` | Always `1`; carries the app version. |
| `fxstream_provider_messages_total` | Counter | `provider` | Normalized ticks received. |
| `fxstream_provider_errors_total` | Counter | `provider`, `kind` | Provider failures/malformed messages/disconnects. |
| `fxstream_provider_reconnects_total` | Counter | `provider` | Reconnection attempts. |
| `fxstream_provider_state` | Gauge | `provider` | `down=0`, `degraded=1`, `up=2`. |
| `fxstream_provider_last_message_timestamp_seconds` | Gauge | `provider` | Last message time. |
| `fxstream_ws_subscribers` | Gauge | — | Active WebSocket subscribers. |
| `fxstream_ws_messages_total` | Counter | `outcome` | WebSocket ticks/errors. |
| `fxstream_quote_requests_total` | Counter | `outcome` | Quote outcomes (`success`, `stale`, `unavailable`). |
| `fxstream_quote_duration_seconds` | Histogram | — | Quote generation latency. |

`MetricsMiddleware` records counts and latency for every HTTP request. The
`route` label uses the **route template** (e.g. `/v1/quotes/{quote_id}`), not
the raw path, so path parameters do not explode label cardinality. Requests that
do not match a route (404s) are labelled `unmatched`.

## Scrape configuration

A minimal Prometheus job:

```yaml
scrape_configs:
  - job_name: fxstream-api
    metrics_path: /metrics
    static_configs:
      - targets: ["fxstream-api:8000"]
```

On Kubernetes, annotate the pod so your Prometheus operator scrapes it:

```yaml
metadata:
  annotations:
    prometheus.io/scrape: "true"
    prometheus.io/path: "/metrics"
    prometheus.io/port: "8000"
```

## Adding a metric

Define it at module scope in `src/core/metrics.py` so it is registered once:

```python
QUOTES_TOTAL = Counter("fxstream_quotes_total", "Quotes created.", ["side"])
```

Then increment it where the event happens. Keep label values low-cardinality —
never use free-form ids or symbols as labels.

## Extending the middleware

`MetricsMiddleware` is pure ASGI and wraps the whole app, so it captures
responses produced by exception handlers and other middleware too. If you need
per-route attributes (e.g. an endpoint name), prefer a small FastAPI dependency
or `APIRoute`-level instrumentation.

See [observability.md](observability.md) for logging and tracing.
