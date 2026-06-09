"""
Gem Hunter — Escanea todo el mercado de Crypto.com buscando oportunidades.

Criterios de seleccion:
- RSI < 45 (zona de sobreventa o aproximandose)
- Precio en el 30% inferior de su rango 90d (acumulacion)
- Volumen decreciente (corrección saludable, no capitulacion)
- Score Elliott >= 2 (al menos 2 capas alineadas)
- Volumen minimo para evitar illiquidos

Clasificacion por potencial (emojis):
  💎 GEM MAXIMA  — RSI < 30, en golden zone, score 4-5
  🔥 FUEGO       — RSI < 35, posicion < 15% del rango, score 3+
  ⭐ ALTA OPORT  — RSI < 40, posicion < 25%, score 2+
  👀 EN RADAR    — RSI < 45, posicion < 35%, score 2+
  📊 SEGUIMIENTO — cambio estructural detectado
"""

import time
import requests
from layers import WebhookPayload, evaluate_layers
from fibonacci import in_golden_zone
from alerts import send_telegram

CRYPTO_API = "https://api.crypto.com/exchange/v1/public"

# Excluir stablecoins y tokens poco relevantes
EXCLUDE = {
    "USDC_USDT", "TUSD_USDT", "USDP_USDT", "BUSD_USDT", "USDD_USDT",
    "DAI_USDT", "FRAX_USDT", "GUSD_USDT", "HUSD_USDT", "PAX_USDT",
    "WBTC_USDT", "STETH_USDT", "WETH_USDT",
}

# Minimo volumen 24h en USDT para considerar el activo (evitar illiquidos)
MIN_VOLUME_24H = 500_000


def get_all_spot_symbols() -> list[str]:
    """Retorna todos los pares USDT spot tradables de Crypto.com."""
    url = f"{CRYPTO_API}/get-instruments"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        instruments = r.json().get("result", {}).get("data", [])
        return [
            i["symbol"] for i in instruments
            if i.get("inst_type") == "CCY_PAIR"
            and i.get("quote_ccy") == "USDT"
            and i.get("tradable")
            and i["symbol"] not in EXCLUDE
        ]
    except Exception as e:
        print(f"[GEM] Error obteniendo instrumentos: {e}")
        return []


def get_ohlcv(symbol: str, timeframe: str = "1D", limit: int = 90) -> list:
    url = f"{CRYPTO_API}/get-candlestick"
    try:
        r = requests.get(url, params={"instrument_name": symbol, "timeframe": timeframe, "count": limit}, timeout=10)
        r.raise_for_status()
        return r.json().get("result", {}).get("data", [])
    except Exception:
        return []


def compute_rsi(closes: list, period: int = 14) -> float:
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
    if len(closes) < period:
        return closes[-1] if closes else 0.0
    k = 2 / (period + 1)
    ema = sum(closes[:period]) / period
    for price in closes[period:]:
        ema = price * k + ema * (1 - k)
    return round(ema, 4)


def classify_gem(score: int, rsi: float, position_pct: float, in_zone: bool) -> tuple[str, str]:
    """
    Retorna (emoji, label) segun el potencial del activo.
    """
    if in_zone and score >= 4:
        return "💎", "GEM MAXIMA"
    if in_zone and score >= 3:
        return "🔥", "FUEGO"
    if rsi < 30 and position_pct < 15:
        return "🔥", "FUEGO"
    if rsi < 35 and position_pct < 20 and score >= 2:
        return "⭐", "ALTA OPORT"
    if rsi < 40 and position_pct < 25 and score >= 2:
        return "⭐", "ALTA OPORT"
    if rsi < 45 and position_pct < 35 and score >= 2:
        return "👀", "EN RADAR"
    return "📊", "SEGUIMIENTO"


def scan_gem(symbol: str) -> dict | None:
    """
    Analiza un activo. Retorna datos si tiene potencial, None si no.
    """
    # Datos diarios para estructura y volumen
    candles_1d = get_ohlcv(symbol, "1D", 90)
    if len(candles_1d) < 20:
        return None

    closes_1d  = [float(c['c']) for c in candles_1d]
    highs_1d   = [float(c['h']) for c in candles_1d]
    lows_1d    = [float(c['l']) for c in candles_1d]
    volumes_1d = [float(c['v']) for c in candles_1d]

    # Filtro de volumen minimo (promedio 7d)
    vol_7d_avg = sum(volumes_1d[-7:]) / 7 * closes_1d[-1]
    if vol_7d_avg < MIN_VOLUME_24H:
        return None

    max_high   = max(highs_1d)
    min_low    = min(lows_1d)
    last_price = closes_1d[-1]
    rng        = max_high - min_low
    if rng == 0:
        return None

    position_pct = (last_price - min_low) / rng * 100

    # Solo analizar activos en el 40% inferior del rango
    if position_pct > 40:
        return None

    # Datos 4H para RSI y capas Elliott
    candles_4h = get_ohlcv(symbol, "4h", 25)
    if len(candles_4h) < 21:
        return None

    opens_4h   = [float(c['o']) for c in candles_4h]
    closes_4h  = [float(c['c']) for c in candles_4h]
    highs_4h   = [float(c['h']) for c in candles_4h]
    lows_4h    = [float(c['l']) for c in candles_4h]
    vols_4h    = [float(c['v']) for c in candles_4h]

    rsi_4h = compute_rsi(closes_4h)
    rsi_1d = compute_rsi(closes_1d)
    ema21  = compute_ema(closes_4h, 21)
    vol5   = sum(vols_4h[-5:]) / 5
    vol20  = sum(vols_4h[-20:]) / 20

    # Usar RSI diario para el filtro de oversold (mas confiable para gems)
    rsi = rsi_1d

    # Solo activos con RSI diario < 50 (zona de oportunidad)
    if rsi_1d > 50:
        return None

    # Golden zone
    gz_low  = max_high - rng * 0.618
    gz_low  = max(gz_low, min_low)  # no puede estar bajo el minimo
    gz_high = max_high - rng * 0.500
    in_zone = in_golden_zone(last_price, min_low, max_high)

    # Score Elliott (usando min/max como wave_start/end)
    payload = WebhookPayload(
        asset=symbol, price=last_price,
        open_4h=opens_4h[-1], close_4h=closes_4h[-1],
        high_4h=highs_4h[-1], low_4h=lows_4h[-1],
        rsi_4h=rsi_4h, volume_avg5=vol5, volume_avg20=vol20,
        ema21_4h=ema21, in_elliott_zone=True,
        wave_start=min_low, wave_end=max_high,
    )
    result = evaluate_layers(payload)
    score  = result["score"]

    # Solo reportar si score >= 2
    if score < 2:
        return None

    # Calcular target (extension 161.8%) y stop (2% bajo minimo)
    target = round(min_low + rng * 1.618, 8)
    stop   = round(min_low * 0.98, 8)
    dist_to_zone = ((last_price - gz_low) / gz_low) * 100

    emoji, label = classify_gem(score, rsi, position_pct, in_zone)

    # Tendencia con EMA50
    ema50 = compute_ema(closes_1d, 50) if len(closes_1d) >= 50 else compute_ema(closes_1d, len(closes_1d))
    trend = "alcista" if last_price > ema50 else "bajista"

    asset_name = symbol.replace("_USDT", "")

    return {
        "symbol":       symbol,
        "asset":        asset_name,
        "price":        last_price,
        "rsi":          rsi,
        "score":        score,
        "position_pct": round(position_pct, 1),
        "in_zone":      in_zone,
        "gz_low":       round(gz_low, 8),
        "gz_high":      round(gz_high, 8),
        "dist_to_zone": round(dist_to_zone, 1),
        "target":       target,
        "stop":         stop,
        "max_90d":      round(max_high, 8),
        "min_90d":      round(min_low, 8),
        "trend":        trend,
        "vol_7d_usd":   round(vol_7d_avg, 0),
        "emoji":        emoji,
        "label":        label,
    }


def run_gem_scan(watchlist_assets: set = None) -> list[dict]:
    """
    Escanea todos los pares USDT buscando oportunidades.
    Retorna lista de gems ordenada por potencial.
    """
    print("[GEM] Iniciando escaneo de mercado...")
    symbols = get_all_spot_symbols()
    print(f"[GEM] Escaneando {len(symbols)} pares USDT...")

    gems = []
    for i, symbol in enumerate(symbols):
        try:
            result = scan_gem(symbol)
            if result:
                # Marcar si ya esta en watchlist
                result["in_watchlist"] = watchlist_assets and result["asset"] + "USD" in watchlist_assets
                gems.append(result)
                print(f"[GEM] {result['emoji']} {symbol}: score={result['score']}/5 RSI={result['rsi']:.0f} pos={result['position_pct']}%")
        except Exception as e:
            pass
        # Rate limiting — pausa breve cada 10 requests
        if i % 10 == 0:
            time.sleep(0.5)

    # Ordenar: primero por score desc, luego por rsi asc (más oversold primero)
    priority = {"💎": 0, "🔥": 1, "⭐": 2, "👀": 3, "📊": 4}
    gems.sort(key=lambda x: (priority.get(x["emoji"], 5), -x["score"], x["rsi"]))

    print(f"[GEM] Scan completado. {len(gems)} oportunidades encontradas.")
    return gems


def send_gem_report(gems: list[dict], new_gems: list[dict] = None) -> None:
    """Envia reporte de gems al Telegram."""
    if not gems:
        send_telegram("*Gem Hunter* — Sin oportunidades destacadas ahora. Mercado sin setups claros.")
        return

    # Agrupar por categoria
    by_emoji = {}
    for g in gems:
        by_emoji.setdefault(g["emoji"], []).append(g)

    lines = ["*GEM HUNTER — Reporte de Mercado*", ""]

    # Nuevas gems (no estaban antes)
    if new_gems:
        lines.append(f"*NUEVAS OPORTUNIDADES DETECTADAS ({len(new_gems)}):*")
        for g in new_gems[:5]:
            lines.append(f"{g['emoji']} *{g['asset']}* — {g['label']}")
        lines.append("")

    # Reporte por categoria
    order = ["💎", "🔥", "⭐", "👀"]
    for emoji in order:
        group = by_emoji.get(emoji, [])
        if not group:
            continue
        label = group[0]["label"]
        lines.append(f"*{emoji} {label} ({len(group)}):*")
        for g in group[:6]:  # max 6 por categoria
            wl = " [WL]" if g.get("in_watchlist") else ""
            if g["in_zone"]:
                zona = "EN ZONA"
            elif g["dist_to_zone"] < 0:
                zona = f"Falta {abs(g['dist_to_zone']):.0f}%"
            else:
                zona = f"+{g['dist_to_zone']:.0f}% sobre zona"
            lines.append(
                f"  *{g['asset']}*{wl} | `{g['price']}` | RSI `{g['rsi']:.0f}` | {g['score']}/5 | {zona}"
            )
        lines.append("")

    lines.append(f"_Total: {len(gems)} activos con potencial | Actualizado automaticamente_")

    # Telegram tiene limite de 4096 chars — dividir si es necesario
    msg = "\n".join(lines)
    if len(msg) > 4000:
        # Enviar en dos partes
        send_telegram("\n".join(lines[:len(lines)//2]))
        time.sleep(1)
        send_telegram("\n".join(lines[len(lines)//2:]))
    else:
        send_telegram(msg)
