"""
Motor de proyecciones para BTC, ETH, LINK, SOL.
Calcula targets diarios/semanales y estimado de días al ATH.
"""

ATH = {
    "BTCUSD":  108_786.0,
    "ETHUSD":    4_878.0,
    "LINKUSD":      52.70,
    "SOLUSD":      293.31,
}

PROJECTION_ASSETS = frozenset(ATH.keys())


def _atr(highs: list, lows: list, closes: list, period: int = 14) -> float:
    trs = []
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        trs.append(tr)
    window = trs[-period:] if len(trs) >= period else trs
    return sum(window) / len(window) if window else 0.0


def project(asset: str, candles_1d: list, state: dict) -> dict:
    """
    Proyecciones de hoy y la semana + estimado días al ATH.
    state = DYNAMIC_STATE[asset]
    """
    if len(candles_1d) < 20:
        return {}

    closes = [float(c["c"]) for c in candles_1d]
    highs  = [float(c["h"]) for c in candles_1d]
    lows   = [float(c["l"]) for c in candles_1d]

    price   = closes[-1]
    ath     = ATH.get(asset, price * 5)
    trend   = state.get("trend", "bajista")
    rsi     = state.get("rsi", 50.0)
    pos     = state.get("position_pct", 50.0)
    gz_low  = state.get("gz_low", price * 0.95)
    gz_high = state.get("gz_high", price)
    min_90  = state.get("min_90d", min(lows))

    atr14 = _atr(highs, lows, closes, 14)

    # Proyección diaria — magnitud según RSI
    rsi_factor = 0.4 if rsi < 30 else (0.7 if rsi < 40 else 1.0)

    if trend == "bajista":
        day_low   = round(price - atr14 * rsi_factor, 6)
        day_high  = round(price + atr14 * 0.25, 6)
        day_close = day_low
    elif trend == "alcista":
        day_high  = round(price + atr14 * rsi_factor, 6)
        day_low   = round(price - atr14 * 0.25, 6)
        day_close = day_high
    else:
        day_high  = round(price + atr14 * 0.5, 6)
        day_low   = round(price - atr14 * 0.5, 6)
        day_close = price

    # Proyección semanal
    weekly_mult = 3.5 if trend == "bajista" else 4.5
    if trend == "bajista":
        week_target = round(price - atr14 * weekly_mult * rsi_factor, 6)
    elif trend == "alcista":
        week_target = round(price + atr14 * weekly_mult, 6)
    else:
        week_target = round(price + atr14 * 1.5, 6)

    week_support = round(min_90 * 1.01, 6)

    # Estimado días al ATH
    pct_to_ath  = round((ath - price) / price * 100, 1) if ath > price else 0.0
    daily_speed = atr14 * (1.0 if trend == "alcista" else 0.4)
    days_to_ath = int((ath - price) / daily_speed) if daily_speed > 0 and ath > price else 0

    # Confianza 0-85%
    conf = 35
    if trend != "lateral": conf += 15
    if rsi < 35 and trend == "bajista": conf += 15
    if rsi > 60 and trend == "alcista": conf += 15
    if gz_low <= price <= gz_high: conf += 12
    if pos < 20 or pos > 80: conf += 8
    conf = min(conf, 85)

    # Razonamiento
    reasons = []
    if trend == "bajista":
        reasons.append("EMA20 < EMA50 — vendedores en control")
    elif trend == "alcista":
        reasons.append("EMA20 > EMA50 — compradores en control")
    else:
        reasons.append("EMAs convergiendo — mercado lateral")

    if rsi < 30:
        reasons.append(f"RSI {rsi:.0f} — sobreventa extrema, rebote estadísticamente probable")
    elif rsi < 40:
        reasons.append(f"RSI {rsi:.0f} — zona de sobreventa, aún con presión")
    elif rsi > 70:
        reasons.append(f"RSI {rsi:.0f} — sobrecompra, posible corrección")
    else:
        reasons.append(f"RSI {rsi:.0f} — zona neutral")

    if pos < 20:
        reasons.append(f"Precio en el {pos:.0f}% del rango 90d — zona de acumulación histórica")
    elif pos > 75:
        reasons.append(f"Precio en el {pos:.0f}% del rango 90d — zona de distribución")
    else:
        reasons.append(f"Precio en el {pos:.0f}% del rango 90d — zona media")

    if gz_low <= price <= gz_high:
        reasons.append("Dentro de la golden zone Fibonacci 50-61.8%")
    elif price < gz_low:
        dist = (gz_low - price) / price * 100
        reasons.append(f"Bajo la golden zone — zona clave a +{dist:.0f}% de aquí")

    return {
        "day_low":      day_low,
        "day_high":     day_high,
        "day_close":    day_close,
        "week_target":  week_target,
        "week_support": week_support,
        "ath":          ath,
        "pct_to_ath":   pct_to_ath,
        "days_to_ath":  days_to_ath,
        "atr14":        round(atr14, 6),
        "confidence":   conf,
        "trend":        trend,
        "reasons":      reasons[:4],
    }
