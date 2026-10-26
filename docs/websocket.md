# WebSocket Rates

`WS /v1/ws/rates` streams normalized ticks to subscribed clients. The protocol
is JSON text frames.

## Subscribe

```json
{"action": "subscribe", "symbols": ["BTC/USDT", "EUR/USD"]}
```

- Symbols use `BASE/QUOTE`; they are normalized to uppercase.
- Unknown or malformed symbols return an error frame and leave the connection
  open.
- On subscribe, the server offers the latest cached tick for each newly added
  symbol, so a client does not have to wait for the next provider update.

## Unsubscribe

```json
{"action": "unsubscribe", "symbols": ["BTC/USDT"]}
```

Unsubscribing removes buffered ticks for those symbols.

## Tick messages

```json
{
  "type": "tick",
  "symbol": "BTC/USDT",
  "bid": "100.04995",
  "ask": "100.15005",
  "source": "binance",
  "as_of": "2026-10-26T12:00:00Z",
  "stale": false
}
```

Prices are strings so clients do not lose precision. `stale` is computed at send
time from the latest rate.

## Errors

```json
{"type": "error", "code": "unknown_symbol", "message": "Unknown symbols: DOGE/USD"}
```

Codes: `invalid_json`, `invalid_message`, `invalid_action`, `invalid_symbols`,
`invalid_symbol`, `unknown_symbol`. Protocol errors do not close the socket.

## Backpressure

Each connection has a coalescing buffer keyed by symbol. `EventBus.publish` never
awaits client I/O. If a client is slow:

- intermediate ticks for a symbol are replaced by newer ones;
- the client always receives at most one tick per symbol on the next drain;
- ingestion and other subscribers are never blocked.

A client that cannot keep up loses data, not liveness. The server does not
buffer an unbounded history.

## Testing

`tests/streaming/` covers the protocol, buffer coalescing, and the route via
`TestClient`. Tests use fake providers and never open public sockets.
