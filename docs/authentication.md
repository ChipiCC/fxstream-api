# Authentication

The template ships **opt-in API-key authentication**. It is disabled by default
so local development stays frictionless, and enforced as soon as you configure
at least one key.

## How it works

The guard lives in [`src/core/security.py`](../src/core/security.py):

```python
async def require_api_key(api_key, settings) -> None:
    if not settings.api_keys:
        return  # auth disabled
    if api_key and any(secrets.compare_digest(api_key, key) for key in settings.api_keys):
        return
    raise UnauthorizedError("Invalid or missing API key")
```

- The key is sent in the `X-API-Key` request header.
- Comparison uses `secrets.compare_digest` to avoid timing attacks.
- When `API_KEYS` is empty the dependency is a no-op.
- Failures raise `UnauthorizedError` → HTTP `401` with a
  `WWW-Authenticate: ApiKey` header and the standard error envelope.

## Enabling it

Set one or more keys (comma-separated or JSON):

```bash
API_KEYS=local-dev-key
# or
API_KEYS=key-one,key-two
```

```bash
curl -H "X-API-Key: local-dev-key" http://localhost:8000/api/v1/items
```

Without the header (or with a wrong key) protected routes return `401`:

```json
{ "error": { "code": "unauthorized", "message": "Invalid or missing API key" } }
```

The `X-API-Key` scheme shows up in the OpenAPI schema, so `/docs` gets an
**Authorize** button automatically.

## Protecting routes

The public `items` router applies the guard to every route:

```python
# src/items/router.py
router = APIRouter(prefix="/items", tags=["items"], dependencies=[Depends(require_api_key)])
```

Do the same for a new domain router. Apply it per-route when only some
endpoints are protected:

```python
router.add_api_route("/admin", handler, methods=["POST"], dependencies=[Depends(require_api_key)])
```

Health probes and `/metrics` are intentionally left public so orchestrators and
scrapers can reach them.

## Swapping in JWT / OAuth

API keys are a starting point, not the only option. To use bearer tokens:

1. Add a scheme: `HTTPBearer` (or `fastapi-security`/`authlib`) in
   `src/core/security.py`.
2. Reuse `UnauthorizedError` / `ForbiddenError` from
   [`src/core/exceptions.py`](../src/core/exceptions.py) so the error shape stays
   consistent.
3. Keep the same dependency-alias pattern and attach it at the router level.

Add the token issuer, JWKS URL, and audience as settings in
[`src/core/config.py`](../src/core/config.py) and document them in
[configuration.md](configuration.md).

## Notes

- Keys are compared in plaintext; store strong, random values and inject them
  as secrets (see [configuration.md](configuration.md#secrets)).
- For per-user identities, scopes, and auditing, replace the static key list
  with a lookup (database or identity provider) inside `require_api_key`.
