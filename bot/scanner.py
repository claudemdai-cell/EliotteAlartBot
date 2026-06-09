"""
Scanner autónomo — corre cada 4 horas sin TradingView.
Obtiene datos OHLCV de Crypto.com y evalúa las 5 capas.
"""

import time
import datetime
import requests
from layers import WebhookPayload, evaluate_layers, format_alert_text
from fibonacci import in_golden_zone
from alerts import send_telegram
from log import log_alert

# Timezone offset UTC-5 (Colombia, Peru, Ecuador, Mexico CDT)
# Cambiar a -3 para Argentina, -6 para Mexico CST
UTC_OFFSET_HOURS = -5
DAILY_SUMMARY_HOUR = 6  # 6:00 AM hora local

# Activos a monitorear con sus niveles Elliott actuales
# Actualizar wave_start/wave_end manualmente cuando cambie el conteo
WATCHLIST = [
    {
        "asset": "BTCUSD",
        "symbol": "BTC_USDT",
        "wave_start": 60171,   # inicio O1 diario
        "wave_end":   76013,   # fin O1 diario
        "stop":       59800,   # invalidación bajo mínimo
        "target":     95000,   # extensión 161.8%
        "in_elliott_zone": True,
    },
    {
        "asset": "ETHUSD",
        "symbol": "ETH_USDT",
        "wave_start": 1741,    # inicio O1d
        "wave_end":   2460,    # fin O1d
        "stop":       1720,    # invalidación
        "target":     4000,    # target O3
        "in_elliott_zone": True,
    },
    {
        "asset": "LINKUSD",
        "symbol": "LINK_USDT",
        "wave_start": 6.999,   # mínimo 90d — base del impulso
        "wave_end":   10.867,  # máximo 90d — fin O1
        "stop":       6.80,    # invalidación bajo mínimo
        "target":     13.25,   # extensión 161.8% desde wave_start
        "in_elliott_zone": True,
    },
    {
        "asset": "SOLUSD",
        "symbol": "SOL_USDT",
        "wave_start": 60.11,   # mínimo 90d — base del impulso
        "wave_end":   98.40,   # máximo 90d — fin O1
        "stop":       58.50,   # invalidación bajo mínimo
        "target":     122.00,  # extensión 161.8% desde wave_start
        "in_elliott_zone": True,
    },
    {
        "asset": "JASMYUSD",
        "symbol": "JASMY_USDT",
        "wave_start": 0.0043,  # mínimo 90d — base del impulso
        "wave_end":   0.0078,  # máximo 90d — fin O1
        "stop":       0.0041,  # invalidación bajo mínimo
        "target":     0.0100,  # extensión 161.8% desde wave_start
        "in_elliott_zone": True,
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


def get_asset_status(cfg: dict) -> dict | None:
    """Escanea un activo y retorna su estado sin enviar alerta."""
    symbol = cfg["symbol"]
    candles = get_ohlcv(symbol, "4h", 25)
    if len(candles) < 21:
        return None

    opens   = [float(c['o']) for c in candles]
    highs   = [float(c['h']) for c in candles]
    lows    = [float(c['l']) for c in candles]
    closes  = [float(c['c']) for c in candles]
    volumes = [float(c['v']) for c in candles]

    rsi      = compute_rsi(closes)
    ema21    = compute_ema(closes, 21)
    vol_avg5  = sum(volumes[-5:]) / 5
    vol_avg20 = sum(volumes[-20:]) / 20

    payload = WebhookPayload(
        asset=cfg["asset"], price=closes[-1],
        open_4h=opens[-1], close_4h=closes[-1],
        high_4h=highs[-1], low_4h=lows[-1],
        rsi_4h=rsi, volume_avg5=vol_avg5, volume_avg20=vol_avg20,
        ema21_4h=ema21, in_elliott_zone=cfg["in_elliott_zone"],
        wave_start=cfg["wave_start"], wave_end=cfg["wave_end"],
    )
    result = evaluate_layers(payload)

    # Calcular distancia al golden zone
    ws, we = cfg["wave_start"], cfg["wave_end"]
    rng = abs(we - ws)
    gz_low  = we - rng * 0.618
    gz_high = we - rng * 0.500
    dist_pct = ((closes[-1] - gz_low) / gz_low) * 100

    return {
        "asset": cfg["asset"],
        "price": closes[-1],
        "score": result["score"],
        "rsi": rsi,
        "gz_low": gz_low,
        "gz_high": gz_high,
        "dist_pct": dist_pct,
        "in_zone": in_golden_zone(closes[-1], ws, we),
        "target": cfg["target"],
        "stop": cfg["stop"],
        "result": result,
        "payload": payload,
    }


def send_daily_summary() -> None:
    """Envia resumen diario de todos los activos a las 6AM."""
    lines = ["*Resumen Diario Elliott Bot*", f"_{datetime.datetime.utcnow().strftime('%Y-%m-%d')} | 6:00 AM_", ""]

    for cfg in WATCHLIST:
        s = get_asset_status(cfg)
        if not s:
            continue

        score = s["score"]
        # Barra visual del score
        bar = "█" * score + "░" * (5 - score)

        if s["in_zone"]:
            zone_txt = "EN ZONA"
        elif s["dist_pct"] < 0:
            zone_txt = f"Falta {abs(s['dist_pct']):.1f}% para zona"
        else:
            zone_txt = f"Sobre zona +{s['dist_pct']:.1f}%"

        # Emoji segun score
        if score >= 4:
            emoji = "ALERTA"
        elif score == 3:
            emoji = "Calentando"
        else:
            emoji = "Esperando"

        lines.append(
            f"*{s['asset']}* [{bar}] {score}/5 - {emoji}\n"
            f"  Precio: `{s['price']}` | RSI: `{s['rsi']:.0f}`\n"
            f"  Zona: `{s['gz_low']:.4f}` - `{s['gz_high']:.4f}` | {zone_txt}\n"
            f"  Target: `{s['target']}` | Stop: `{s['stop']}`"
        )

    send_telegram("\n".join(lines))


def scan_asset(cfg: dict) -> None:
    symbol = cfg["symbol"]
    candles = get_ohlcv(symbol, "4h", 25)

    if len(candles) < 21:
        print(f"[SCANNER] {symbol}: datos insuficientes")
        return

    # Crypto.com devuelve {"o": open, "h": high, "l": low, "c": close, "v": volume, "t": time}
    opens   = [float(c['o']) for c in candles]
    highs   = [float(c['h']) for c in candles]
    lows    = [float(c['l']) for c in candles]
    closes  = [float(c['c']) for c in candles]
    volumes = [float(c['v']) for c in candles]

    last_open   = opens[-1]
    last_close  = closes[-1]
    last_high   = highs[-1]
    last_low    = lows[-1]

    rsi     = compute_rsi(closes)
    ema21   = compute_ema(closes, 21)
    vol_avg5  = sum(volumes[-5:]) / 5
    vol_avg20 = sum(volumes[-20:]) / 20

    payload = WebhookPayload(
        asset            = cfg["asset"],
        price            = last_close,
        open_4h          = last_open,
        close_4h         = last_close,
        high_4h          = last_high,
        low_4h           = last_low,
        rsi_4h           = rsi,
        volume_avg5      = vol_avg5,
        volume_avg20     = vol_avg20,
        ema21_4h         = ema21,
        in_elliott_zone  = cfg["in_elliott_zone"],
        wave_start       = cfg["wave_start"],
        wave_end         = cfg["wave_end"],
    )

    result = evaluate_layers(payload)
    score  = result["score"]
    layers_passed = [k for k, v in result["layers"].items() if v.passed]

    print(f"[SCANNER] {cfg['asset']} | Score: {score}/5 | RSI: {rsi} | Price: {last_close}")

    sent = False
    if score >= 4:
        text = format_alert_text(payload, result, cfg["stop"], cfg["target"])
        sent = send_telegram(text)

    log_alert(cfg["asset"], score, last_close, cfg["stop"], cfg["target"], layers_passed, sent)


def run_scanner(interval_hours: int = 4) -> None:
    """Loop principal — corre cada 4 horas. Resumen diario a las 6AM."""
    print(f"[SCANNER] Iniciando. Revisando cada {interval_hours}h.")
    send_telegram("*Elliott Scanner iniciado* — revisando cada 4h. Resumen diario a las 6AM.")

    last_summary_day = None  # Evita enviar mas de 1 resumen por dia

    while True:
        # Calcular hora local
        utc_now = datetime.datetime.utcnow()
        local_now = utc_now + datetime.timedelta(hours=UTC_OFFSET_HOURS)
        today = local_now.date()

        # Enviar resumen diario si es hora 6AM y no se envio hoy
        if local_now.hour == DAILY_SUMMARY_HOUR and last_summary_day != today:
            print(f"[SCANNER] Enviando resumen diario ({local_now.strftime('%H:%M')} local)")
            send_daily_summary()
            last_summary_day = today

        print(f"\n[SCANNER] --- Scan {local_now.strftime('%Y-%m-%d %H:%M')} local ---")
        for cfg in WATCHLIST:
            scan_asset(cfg)
            time.sleep(2)
        print(f"[SCANNER] Esperando {interval_hours}h...")
        time.sleep(interval_hours * 3600)


if __name__ == "__main__":
    run_scanner()
