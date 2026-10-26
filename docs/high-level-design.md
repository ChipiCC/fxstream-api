# FXStream API: High-Level Design

## 1. Goal

A backend service that ingests FX rates and crypto prices from external providers, normalizes them, and exposes them in real time over WebSocket and over REST. It also issues quotes with a spread and an expiry.

## 2. Scope

### In scope

- Real-time ingestion from at least two providers (Binance WS and Frankfurter).
- Caching of the latest price per pair, with a staleness flag (`stale`).
- Price streaming to WebSocket subscribers.
- REST snapshots and historical candles.
- Quote generation with bid, ask, and a 30-second TTL.

### Out of scope (for now)

- Real trade execution or fund movement.
- Full user authentication (API key or per-IP rate limiting only).
- Equities or exchange-traded stock data.

## 3. Components

```
┌──────────────────────────── fxstream-api ────────────────────────────┐
│                                                                      │
│  Provider Adapters ──► Normalizer ──► Rate Store (cache + staleness) │
│  (Binance, Frankfurter)     │                  │                     │
│   · reconnect + backoff     │                  ▼                     │
│   · circuit breaker         │          Quote Engine (spread + TTL)   │
│                             ▼                  │                     │
│                     Event Bus (asyncio)  ◄─────┘                     │
│                        │         │                                   │
│                  WS Gateway    REST Router ──► Candle Store (DB)      │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

- **Provider Adapters**: one implementation per provider, all behind a `RateProvider` interface. They handle connection, reconnection with exponential backoff, and a circuit breaker.
- **Normalizer**: converts each provider's messages into the internal `Tick` model, with prices as `Decimal`.
- **Rate Store**: keeps the latest tick per pair in memory and computes `stale` using a threshold configured per provider.
- **Quote Engine**: computes bid and ask from the mid price and the configured spread, then assigns a `quote_id` and `expires_at`.
- **Event Bus**: delivers ticks to WebSocket subscribers through a per-client `asyncio` queue. If a client is slow, intermediate ticks are dropped.
- **Candle Store**: aggregates ticks into 1-minute candles and persists them (PostgreSQL or SQLite).

## 4. Domain Model

| Entity | Main fields |
| --- | --- |
| `Tick` | `symbol`, `bid`, `ask`, `last`, `source`, `as_of`, `received_at` |
| `Rate` | `symbol`, `price`, `source`, `as_of`, `stale` |
| `Quote` | `quote_id`, `symbol`, `bid`, `ask`, `mid`, `spread_bps`, `issued_at`, `expires_at` |
| `Candle` | `symbol`, `interval`, `open`, `high`, `low`, `close`, `volume`, `open_time` |
| `ProviderStatus` | `name`, `state` (`up`, `degraded`, `down`), `last_message_at`, `reconnects` |

Symbol convention: `BASE/QUOTE` (for example, `EUR/USD`, `BTC/USDT`).

## 5. API Contract

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | Service health |
| `GET` | `/v1/rates?symbols=EUR/USD,BTC/USDT` | Latest price snapshot per pair |
| `GET` | `/v1/rates/{base}/{quote}/candles?interval=1m&limit=100` | Historical candles |
| `POST` | `/v1/quotes` | Creates a quote from symbol and side (optional amount) |
| `GET` | `/v1/quotes/{quote_id}` | Retrieves a quote and whether it is still valid |
| `GET` | `/v1/providers/status` | Provider status |
| `WS` | `/v1/ws/rates` | Subscription-based price stream |

WebSocket protocol (JSON):

- Client → server: `{"action": "subscribe", "symbols": ["BTC/USDT"]}` and unsubscribe.
- Server → client: `{"type": "tick", "symbol": "...", "bid": "...", "ask": "...", "source": "...", "as_of": "...", "stale": false}`.
- Prices are sent as strings so the client does not lose precision.

## 6. Main Flow

1. The adapter receives a message from a provider and normalizes it into a `Tick`.
2. The Rate Store updates the latest price and recomputes `stale`.
3. The Event Bus publishes the tick to subscribers of that symbol.
4. A client requests a quote: the Quote Engine takes the latest non-stale price, computes bid and ask, and stores the quote with `expires_at`.
5. If the base price is stale, the quote is rejected with an explicit error.

## 7. Key Decisions

- **Modular monolith**: one service with separate modules, not microservices. Ingestion can be extracted later if the design justifies it.
- **Decimal across the domain**, and prices returned as strings in the API.
- **Per-provider staleness**: Binance is real time (threshold in seconds), Frankfurter is daily (threshold in hours). A single global threshold would produce false positives.
- **Immutable quotes**: once issued, a quote never changes. It can only expire.
- **Injectable clocks** so expiry tests do not depend on `sleep`.
- **WebSocket backpressure**: for each slow client, only the latest tick per pair is kept.

## 8. Resilience and Observability

- Circuit breaker per provider: if a provider fails repeatedly, it moves to `down` and the rest of the system keeps working.
- Rate limiting per IP on REST endpoints and on quote creation.
- Structured logs with `source`, `symbol`, and `latency_ms`.
- Basic metrics: messages per second per provider, subscriber count, quote latency, reconnections.

## 9. Testing Strategy

- **Unit**: normalization, spread and bid/ask calculation with `Decimal`, quote expiry, stale computation.
- **Integration**: mocked providers that emit ticks, disconnect, or send corrupted data. Verify the system degrades without crashing.
- **WebSocket**: `TestClient` tests for subscribe, unsubscribe, and backpressure.
- **Contract**: validate Pydantic schemas against the examples documented in the OpenAPI spec.

## 10. Deployment and Configuration

- Docker Compose with `api`, `postgres`, and optionally `redis` (only if an external bus is added).
- Configuration through environment variables: symbol list, staleness thresholds, spread per pair, quote TTL.
- Backend on Render or Fly.io; frontend deployed separately on Vercel.

## 11. Open Questions

- Will spreads be fixed per pair, or configurable per client?
- Are quotes executed by this service, or only issued (with execution mocked)?
- Do quotes need persistence for audit, or is memory enough?
- How many concurrent clients should the demo support? This determines whether Redis is needed.
