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

`MetricsMiddleware` records counts and latency for every HTTP request. The
`route` label uses the **route template** (e.g. `/api/v1/items/{item_id}`), not
the raw path, so path parameters do not explode label cardinality. Requests that
do not match a route (404s) are labelled `unmatched`.

## Scrape configuration

A minimal Prometheus job:

```yaml
scrape_configs:
  - job_name: fastapi-service
    metrics_path: /metrics
    static_configs:
      - targets: ["fastapi-service:8000"]
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
ORDERS_TOTAL = Counter("orders_total", "Orders created.", ["status"])
```

Then increment it where the event happens (e.g. in the items service or a new
domain service). Keep label values low-cardinality — never use free-form ids.

## Extending the middleware

`MetricsMiddleware` is pure ASGI and wraps the whole app, so it captures
responses produced by exception handlers and other middleware too. If you need
per-route attributes (e.g. an endpoint name), prefer a small FastAPI dependency
or `APIRoute`-level instrumentation.

See [observability.md](observability.md) for logging and tracing.
