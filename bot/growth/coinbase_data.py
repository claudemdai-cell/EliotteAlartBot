"""
Cliente de datos de mercado de Coinbase Exchange (API publica, sin API key).
Base: https://api.exchange.coinbase.com

Endpoints usados:
- GET /products                     -> lista de pares
- GET /products/{id}/candles        -> velas OHLCV
- GET /products/{id}/ticker         -> precio actual
- GET /products/{id}/stats          -> stats 24h (volumen, etc.)

Formato de vela de Coinbase: [time, low, high, open, close, volume]
(orden distinto al tipico OHLC — ojo con los indices)
"""

import time
import requests

BASE = "https://api.exchange.coinbase.com"

# Granularidades validas en segundos
G_1H = 3600
G_6H = 21600
G_1D = 86400

_HEADERS = {"User-Agent": "growth-bot/1.0", "Accept": "application/json"}


def _get(path: str, params: dict = None, retries: int = 2):
    """GET con reintentos suaves. Retorna JSON o None."""
    url = f"{BASE}{path}"
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, params=params, headers=_HEADERS, timeout=12)
            if r.status_code == 429:  # rate limit
                time.sleep(1.0 + attempt)
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt == retries:
                print(f"[COINBASE] Error {path}: {e}")
                return None
            time.sleep(0.5)
    return None


def get_candles(product_id: str, granularity: int = G_1D, limit: int = 90) -> list:
    """
    Retorna lista de velas como dicts ordenadas de mas antigua a mas reciente:
    [{ 't', 'o', 'h', 'l', 'c', 'v' }, ...]
    Coinbase devuelve max 300 velas y en orden descendente (reciente primero).
    """
    data = _get(f"/products/{product_id}/candles", {"granularity": granularity})
    if not data or not isinstance(data, list):
        return []
    # Coinbase: [time, low, high, open, close, volume], reciente primero
    candles = [
        {"t": c[0], "l": float(c[1]), "h": float(c[2]),
         "o": float(c[3]), "c": float(c[4]), "v": float(c[5])}
        for c in data if len(c) >= 6
    ]
    candles.sort(key=lambda x: x["t"])  # ascendente
    if limit and len(candles) > limit:
        candles = candles[-limit:]
    return candles


def get_ticker(product_id: str) -> dict | None:
    """Precio y volumen actuales. { price, bid, ask, volume }."""
    data = _get(f"/products/{product_id}/ticker")
    if not data:
        return None
    try:
        return {
            "price":  float(data["price"]),
            "bid":    float(data.get("bid", 0) or 0),
            "ask":    float(data.get("ask", 0) or 0),
            "volume": float(data.get("volume", 0) or 0),
        }
    except (KeyError, ValueError):
        return None


def get_price(product_id: str) -> float | None:
    """Atajo: solo el precio actual."""
    t = get_ticker(product_id)
    return t["price"] if t else None


def get_stats(product_id: str) -> dict | None:
    """Stats de 24h: { open, high, low, last, volume }."""
    data = _get(f"/products/{product_id}/stats")
    if not data:
        return None
    try:
        return {k: float(data[k]) for k in ("open", "high", "low", "last", "volume") if k in data}
    except (ValueError, TypeError):
        return None


def list_usd_products() -> list[str]:
    """
    Pares -USD activos y operables (no delisted, no solo-cancel).
    Excluye stablecoins y wrapped.
    """
    data = _get("/products")
    if not data or not isinstance(data, list):
        return []
    out = []
    for p in data:
        try:
            if p.get("quote_currency") != "USD":
                continue
            if p.get("status") != "online":
                continue
            if p.get("trading_disabled") or p.get("cancel_only") or p.get("post_only"):
                continue
            base = p.get("base_currency", "")
            if base in _EXCLUDE_BASE:
                continue
            out.append(p["id"])
        except Exception:
            continue
    return out


# Stablecoins y tokens que no queremos cazar como "gemas"
_EXCLUDE_BASE = {
    "USDC", "USDT", "DAI", "USDP", "GUSD", "PYUSD", "PAX", "BUSD",
    "WBTC", "CBETH", "WETH",
}
