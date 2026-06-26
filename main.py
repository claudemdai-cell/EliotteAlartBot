"""
Scanner autónomo — corre cada 4 horas sin TradingView.
Obtiene datos OHLCV de Crypto.com y evalúa las 5 capas.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'bot'))

import time
import requests
from layers import WebhookPayload, evaluate_layers, format_alert_text
from alerts import send_telegram
from log import log_alert

# Activos a monitorear con sus niveles Elliott actuales
# ACTUALIZAR manualmente cuando cambie el conteo
# Última actualización: 2026-06-26

WATCHLIST = [
    {
        "asset": "BTCUSD",
        "symbol": "BTC_USDT",
        "wave_start": 60171,       # inicio O1d — PENDIENTE RECONTEO (R1 posible violación)
        "wave_end":   76013,       # fin O1d / invalidación R3
        "stop":       59000,       # bajo mínimo reciente
        "target":     95000,       # extensión 161.8%
        "in_elliott_zone": False,  # ⚠️ BLOQUEADO — reconteo diario urgente antes de operar
    },
    {
        "asset": "ETHUSD",
        "symbol": "ETH_USDT",
        "wave_start": 1505,        # inicio O1d (reconteo jun 21 2026)
        "wave_end":   1848,        # fin O1d
        "stop":       1505,        # invalidación R1 diario
        "target":     3170,        # T1: extensión 161.8% desde O2d
        "in_elliott_zone": True,   # Zona entrada: $1,634–$1,676
    },
    {
        "asset": "LINKUSD",
        "symbol": "LINK_USDT",
        "wave_start": 4.83,        # invalidación O2 semanal
        "wave_end":   14.0,        # máximo O1 semanal (referencia)
        "stop":       4.83,
        "target":     9.35,        # proyección Mesa Redonda
        "in_elliott_zone": False,  # Esperando señal de reversión semanal
    },
]

CRYPTO_API = "https://api.crypto.com/exchange/v1/public"


def get_ohlcv(symbol: str, timeframe: str = "4h", limit: int = 25) -> list:
    """Obtiene velas OHLCV de Crypto.com."""
    url = f"{CRYPTO_API}/get-candlestick"
    params = {"instrument_name": symbol, "timeframe": timeframe, "count": limit}
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        return data.get("result", {}).get("data", [])
    except Exception as e:
        print(f"[SCANNER] Error obteniendo {symbol}: {e}")
        return []


def get_ticker(symbol: str) -> dict:
    """Obtiene ticker actual."""
    url = f"{CRYPTO_API}/get-ticker"
    params = {"instrument_name": symbol}
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        return r.json().get("result", {}).get("data", [{}])[0]
    except Exception as e:
        print(f"[SCANNER] Error ticker {symbol}: {e}")
        return {}


def compute_rsi(closes: list, period: int = 14) -> float:
    """RSI simple."""
    if len(closes) < period + 1:
        return 50.0
    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gains  = [d for d in deltas[-period:] if d > 0]
    losses = [-d for d in deltas[-period:] if d < 0]
    avg_gain = sum(gains) / period if gains else 0.001
    avg_loss = sum(losses) / period if losses else 0.001
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def compute_ema(closes: list, period: int = 21) -> float:
    """EMA simple."""
    if len(closes) < period:
        return closes[-1] if closes else 0.0
    k = 2 / (period + 1)
    ema = sum(closes[:period]) / period
    for price in closes[period:]:
        ema = price * k + ema * (1 - k)
    return round(ema, 4)


def scan_asset(cfg: dict) -> None:
    symbol = cfg["symbol"]
    candles = get_ohlcv(symbol, "4h", 26)  # 26 = 25 + 1 para tener vela anterior

    if len(candles) < 22:
        print(f"[SCANNER] {symbol}: datos insuficientes")
        return

    # Crypto.com devuelve [t, o, h, l, c, v]
    opens   = [float(c[1]) for c in candles]
    highs   = [float(c[2]) for c in candles]
    lows    = [float(c[3]) for c in candles]
    closes  = [float(c[4]) for c in candles]
    volumes = [float(c[5]) for c in candles]

    # Vela actual (última) y anterior (penúltima)
    last_open,  last_close  = opens[-1],  closes[-1]
    last_high,  last_low    = highs[-1],  lows[-1]
    prev_open,  prev_close  = opens[-2],  closes[-2]
    prev_high,  prev_low    = highs[-2],  lows[-2]

    # RSI: necesitamos el valor actual y el de la vela anterior
    rsi_current  = compute_rsi(closes[:-1])   # RSI sin la vela actual (cierre previo)
    rsi_prev     = compute_rsi(closes[:-2])   # RSI dos velas atrás
    # RSI con la vela actual para mostrar en alerta
    rsi_now      = compute_rsi(closes)

    ema21 = compute_ema(closes, 21)

    # Volumen: avg5 de las 5 velas ANTES de la actual (para spike comparison)
    current_volume = volumes[-1]
    vol_avg5       = sum(volumes[-6:-1]) / 5   # últimas 5 sin la actual
    vol_avg20      = sum(volumes[-21:-1]) / 20  # últimas 20 sin la actual

    payload = WebhookPayload(
        asset           = cfg["asset"],
        price           = last_close,
        open_4h         = last_open,
        close_4h        = last_close,
        high_4h         = last_high,
        low_4h          = last_low,
        rsi_4h          = rsi_current,
        rsi_prev_4h     = rsi_prev,
        volume_avg5     = vol_avg5,
        volume_avg20    = vol_avg20,
        current_volume  = current_volume,
        ema21_4h        = ema21,
        in_elliott_zone = cfg["in_elliott_zone"],
        wave_start      = cfg["wave_start"],
        wave_end        = cfg["wave_end"],
        prev_open_4h    = prev_open,
        prev_close_4h   = prev_close,
        prev_high_4h    = prev_high,
        prev_low_4h     = prev_low,
    )

    result = evaluate_layers(payload)
    score  = result["score"]
    layers_passed = [k for k, v in result["layers"].items() if v.passed or v.partial]

    print(f"[SCANNER] {cfg['asset']} | Score: {score}/5 | RSI: {rsi_now:.1f} | Price: {last_close}")

    sent = False
    if result["alert_ready"]:
        text = format_alert_text(payload, result, cfg["stop"], cfg["target"])
        sent = send_telegram(text)

    log_alert(cfg["asset"], score, last_close, cfg["stop"], cfg["target"], layers_passed, sent)


def run_scanner(interval_hours: int = 4) -> None:
    """Loop principal — corre cada 4 horas."""
    print(f"[SCANNER] Iniciando. Revisando cada {interval_hours}h.")
    send_telegram("🤖 *Elliott Scanner iniciado* — revisando cada 4h.")

    while True:
        print(f"\n[SCANNER] --- Nuevo scan ---")
        for cfg in WATCHLIST:
            scan_asset(cfg)
            time.sleep(2)
        print(f"[SCANNER] Esperando {interval_hours}h...")
        time.sleep(interval_hours * 3600)


if __name__ == "__main__":
    run_scanner()
