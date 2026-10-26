# Security

This page covers the request-hardening middleware. Authentication and CORS have
their own pages: [authentication.md](authentication.md), [cors.md](cors.md).

## Security headers

[`SecurityHeadersMiddleware`](../src/core/middleware.py) attaches conservative
headers to every response:

| Header | Value |
| --- | --- |
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `Referrer-Policy` | `no-referrer` |
| `Permissions-Policy` | `geolocation=(), microphone=(), camera=()` |
| `Strict-Transport-Security` | `max-age=63072000; includeSubDomains` **only when `ENVIRONMENT=production`** |

Headers use `setdefault`, so an endpoint may override any of them. Disable the
whole set with `SECURITY_HEADERS_ENABLED=false`.

HSTS is emitted only in production because it must only ever be sent over
HTTPS.

## Trusted hosts

`TrustedHostMiddleware` rejects requests whose `Host` header is not in
`ALLOWED_HOSTS`. The default `*` allows everything; **set it explicitly in
production** (the production guard enforces this).

```bash
ALLOWED_HOSTS=api.example.com,internal.example.com
```

## Rate limiting

`RateLimitMiddleware` is an **in-process** fixed-window limiter, disabled by
default:

```bash
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW_SECONDS=60
```

- Keys on the client IP (`scope["client"]`).
- Returns `429` with a `Retry-After` header and the standard error envelope.
- `/health/live`, `/health/ready`, and `METRICS_PATH` are exempt.

> **Multi-worker caveat:** the counter lives in memory, so each worker/replica
> has its own budget. For a global limit, front the service with an edge proxy
> (nginx, Envoy, a cloud WAF) or a shared store (Redis).

## Ordered middleware stack

Execution is outer → inner (middleware added later runs first):

```
RequestContext (access log) → Metrics → CORS → Security headers → Trusted host → Rate limit
                                  ↓
                          ExceptionMiddleware → router
```

This ordering means:

- Everything is timed and logged, including CORS preflights.
- CORS headers are present even on `400`/`429` responses.
- Security headers are present on responses that still reach the app.

## Error responses

Errors use a single envelope (see
[`src/core/exceptions.py`](../src/core/exceptions.py)):

```json
{ "error": { "code": "not_found", "message": "Item ... not found" } }
```

Available error types: `BadRequestError` (400), `UnauthorizedError` (401),
`ForbiddenError` (403), `NotFoundError` (404), `ConflictError` (409),
`TooManyRequestsError` (429), `ServiceUnavailableError` (503), plus the base
`AppError` (400). Validation failures return `422` with a `validation_error`
code and the field errors.

## Hardening checklist

- [ ] `API_KEYS` set (see [authentication.md](authentication.md)).
- [ ] `ALLOWED_HOSTS` explicit.
- [ ] `ENVIRONMENT=production`, `DEBUG=false`, `DOCS_ENABLED=false`.
- [ ] `POSTGRES_PASSWORD` changed; secrets injected, not committed.
- [ ] `CORS_ORIGINS` limited to origins you control.
- [ ] TLS terminated in front of the app (HSTS is only sent in production).
- [ ] Dependencies audited in CI (`pip-audit`) and kept current (Dependabot — see [dependencies.md](dependencies.md)).
- [ ] Rate limiting in place — shared/edge if you run more than one worker.
