# Configuration

All settings live in [`src/core/config.py`](../src/core/config.py) as a
`pydantic-settings` `Settings` model. They are read from environment variables
and, outside production, from a `.env.local` file, then validated at startup.

- Read settings through `get_settings()` (cached) — never call `os.environ`.
- List settings (`ALLOWED_HOSTS`, `CORS_ORIGINS`, `API_KEYS`,
  `CORS_ALLOW_METHODS`, `CORS_ALLOW_HEADERS`) accept either a comma-separated
  string (`a,b,c`) or a JSON array (`["a","b"]`).
- `.env.local` is gitignored; only [`.env.local.example`](../.env.local.example)
  ships. Copy it to `.env.local` to configure a local run.

## How configuration is resolved

Sources are applied in order of decreasing precedence:

1. Real environment variables (`POSTGRES_HOST=x mise run dev`, or whatever the
   platform injects) — always win, so container/CI/deploy config is never
   shadowed by a stray file.
2. `.env.local` in the working directory — **only when `ENVIRONMENT` is not
   `production`**. If the file is absent it is silently skipped and the field
   defaults below apply.
3. Field defaults defined on `Settings`.

`ENVIRONMENT=production` is detected from the **process** environment before any
dotfile is read (a production process must never be configured by a local
file). In production `.env.local` is not read at all.

## Settings

### Application

| Variable | Default | Description |
| --- | --- | --- |
| `APP_NAME` | `FastAPI Service` | Service name (also the DB `application_name`). |
| `ENVIRONMENT` | `local` | `local`, `staging`, or `production`. |
| `DEBUG` | `false` | Debug mode; also enables SQL echo. |
| `API_V1_PREFIX` | `/api/v1` | Prefix for public domain routers. |
| `DOCS_ENABLED` | `true` | Serve `/docs`, `/redoc`, `/openapi.json`. |

### HTTP server

| Variable | Default | Description |
| --- | --- | --- |
| `HOST` / `PORT` | `0.0.0.0` / `8000` | Bind address (used by compose/deploy). |

### Observability

| Variable | Default | Description |
| --- | --- | --- |
| `LOG_LEVEL` | `INFO` | Root log level. |
| `LOG_JSON` | `true` | JSON logs (`false` for pretty console). |
| `METRICS_ENABLED` | `true` | Expose the Prometheus endpoint. |
| `METRICS_PATH` | `/metrics` | Path for the scrape endpoint. |

See [metrics.md](metrics.md) and [observability.md](observability.md).

### Security

| Variable | Default | Description |
| --- | --- | --- |
| `API_KEYS` | *(empty)* | Valid API keys. Empty disables auth. See [authentication.md](authentication.md). |
| `CORS_ORIGINS` | *(empty)* | Allowed browser origins. See [cors.md](cors.md). |
| `CORS_ALLOW_CREDENTIALS` | `false` | Allow cookies/credentials on CORS requests. |
| `ALLOWED_HOSTS` | `*` | Trusted `Host` headers. Set explicitly in production. |
| `SECURITY_HEADERS_ENABLED` | `true` | Attach security response headers. |
| `RATE_LIMIT_ENABLED` | `false` | Enable the in-process rate limiter. |
| `RATE_LIMIT_REQUESTS` | `100` | Requests per window per client. |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Window length in seconds. |

See [security.md](security.md).

### Database

| Variable | Default | Description |
| --- | --- | --- |
| `DATABASE_URL` | *(unset)* | Full DSN; wins over `POSTGRES_*`. Driver is upgraded to `asyncpg`. |
| `POSTGRES_HOST` | `localhost` | Database host. |
| `POSTGRES_PORT` | `5432` | Database port. |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `postgres` / `postgres` / `app` | Credentials. |
| `POSTGRES_SSL` | *(unset)* | `disable` \| `allow` \| `prefer` \| `require` \| `verify-ca` \| `verify-full`. |
| `DB_ECHO` | `false` | Echo SQL statements. |
| `DB_POOL_SIZE` | `5` | Connection pool size. |
| `DB_MAX_OVERFLOW` | `10` | Extra connections above the pool size. |
| `DB_POOL_RECYCLE_SECONDS` | `1800` | Recycle connections older than this (`-1` disables). |
| `DB_POOL_TIMEOUT_SECONDS` | `30` | Seconds to wait for a pooled connection. |
| `DB_STATEMENT_TIMEOUT_MS` | `0` | Postgres `statement_timeout` (`0` disables). |

See [database.md](database.md).

## Credentials and DSNs

`database_url` URL-encodes the user and password, so passwords containing
reserved characters (`@ : / ? # &`) are safe. Prefer supplying a single
`DATABASE_URL` on managed platforms (Heroku, Render, Fly, ...); a bare
`postgresql://` is automatically upgraded to `postgresql+asyncpg://`.

## Production validation

The `Settings` model refuses to start when `ENVIRONMENT=production` and any of
the following hold, so misconfiguration fails fast instead of leaking:

- `DEBUG=true`
- `DOCS_ENABLED=true`
- `POSTGRES_PASSWORD` left at the `postgres` default
- `API_KEYS` empty
- `ALLOWED_HOSTS` still `*`

## Secrets

For Docker/Kubernetes secret mounts, provide each secret as an environment
variable (or use `DATABASE_URL`). Application code never reads files directly;
wire secret files to env vars in your platform's manifest.
