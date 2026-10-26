# CORS

Cross-Origin Resource Sharing is handled by Starlette's `CORSMiddleware`,
installed in [`src/app.py`](../src/app.py). It is added **outermost** so its
headers are attached to every response, including errors and rate-limit
rejections.

## Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `CORS_ORIGINS` | *(empty)* | Comma-separated or JSON list of allowed origins. |
| `CORS_ALLOW_CREDENTIALS` | `false` | Send `Access-Control-Allow-Credentials`. |
| `CORS_ALLOW_METHODS` | `*` | Allowed methods. |
| `CORS_ALLOW_HEADERS` | `*` | Allowed request headers. |

With no origins configured the middleware emits no CORS headers — i.e. CORS is
effectively off, which is correct for a server-to-server service.

```bash
CORS_ORIGINS=https://app.example.com,https://admin.example.com
CORS_ALLOW_CREDENTIALS=false
```

## Behaviour

- **Simple requests** get `Access-Control-Allow-Origin` when the `Origin`
  matches.
- **Preflight** (`OPTIONS`) requests are answered by the middleware before
  routing, so they are never rate limited or blocked by auth.
- **Credentials** (`cookies`, `Authorization`) require an explicit origin list;
  `*` is not allowed together with `CORS_ALLOW_CREDENTIALS=true`.

## Security note

Only ever list origins you control. Prefer explicit origins over `*`,
especially once `CORS_ALLOW_CREDENTIALS` is on. `CORS_ORIGINS` is one of the
settings enforced by the production guard (see
[configuration.md](configuration.md#production-validation)) when left empty is
allowed — CORS is opt-in.

See [security.md](security.md) for the wider hardening checklist.
