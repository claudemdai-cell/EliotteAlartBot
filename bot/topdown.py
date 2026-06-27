"""
Motor de análisis Top-Down multi-timeframe.
Flujo: 1M → 1W → 1D → 4H → 1H → 30m → 15m
Calcula tendencia, RSI, EMAs, patrón de vela y sesgo Elliott por cada TF.
"""

import requests
from candle_patterns import detect as detect_candle, fmt_pattern

CRYPTO_API = "https://api.crypto.com/exchange/v1/public"

# Timeframes en orden macro → micro
TIMEFRAMES = [
    {"tf": "1M",  "label": "Mensual",  "limit": 24,  "weight": 3.0,  "group": "MACRO"},
    {"tf": "7D",  "label": "Semanal",  "limit": 26,  "weight": 2.0,  "group": "MACRO"},
    {"tf": "1D",  "label": "Diario",   "limit": 90,  "weight": 2.0,  "group": "MACRO"},
    {"tf": "4h",  "label": "4H",       "limit": 50,  "weight": 1.5,  "group": "ESTRUCTURA"},
    {"tf": "1h",  "label": "1H",       "limit": 50,  "weight": 1.0,  "group": "ESTRUCTURA"},
    {"tf": "30m", "label": "30m",      "limit": 50,  "weight": 0.5,  "group": "TIMING"},
    {"tf": "15m", "label": "15m",      "limit": 50,  "weight": 0.5,  "group": "TIMING"},
]

TREND_ICON = {"alcista": "📈", "bajista": "📉", "lateral": "↔️"}
TOTAL_WEIGHT = sum(t["weight"] for t in TIMEFRAMES)


def _get_ohlcv(symbol: str, tf: str, limit: int) -> list:
    try:
        r = requests.get(
            f"{CRYPTO_API}/get-candlestick",
            params={"instrument_name": symbol, "timeframe": tf, "count": limit},
            timeout=12,
        )
        r.raise_for_status()
        return r.json().get("result", {}).get("data", [])
    except Exception as e:
        print(f"[TOPDOWN] {symbol} {tf}: {e}")
        return []


def _compute_rsi(closes: list, period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains  = [d for d in deltas[-period:] if d > 0]
    losses = [-d for d in deltas[-period:] if d < 0]
    ag = sum(gains) / period if gains else 0.001
    al = sum(losses) / period if losses else 0.001
    return round(100 - 100 / (1 + ag / al), 1)


def _compute_ema(closes: list, period: int) -> float:
    n = min(period, len(closes))
    if n < 2:
        return closes[-1] if closes else 0.0
    k   = 2 / (n + 1)
    ema = sum(closes[:n]) / n
    for p in closes[n:]:
        ema = p * k + ema * (1 - k)
    return round(ema, 8)


def _elliott_bias(trend: str, rsi: float, pos_pct: float, tf_group: str) -> str:
    """Interpreta el sesgo de onda Elliott según el contexto del TF."""
    if tf_group == "MACRO":
        if trend == "bajista":
            if rsi < 30:
                return "Fin de onda C probable — vigilar"
            return "Onda bajista mayor (3 o C)"
        elif trend == "alcista":
            if rsi > 70:
                return "Posible fin de onda 5 — cuidado"
            return "Impulso alcista (onda 3 o 5)"
        return "Corrección lateral (onda 4 o B)"

    if tf_group == "ESTRUCTURA":
        if trend == "bajista" and rsi < 40:
            return "Sub-onda bajista — espera agotamiento"
        if trend == "alcista" and pos_pct > 60:
            return "Sub-onda alcista en desarrollo"
        if rsi < 35:
            return "Oversold — posible inicio de rebote"
        return "En transición"

    # TIMING
    if trend == "alcista":
        return "Micro impulso — timing de entrada"
    if trend == "bajista":
        return "Micro corrección — espera"
    return "Consolidación"


def analyze_tf(symbol: str, tf_cfg: dict, state: dict) -> dict | None:
    """Analiza un solo timeframe. Retorna dict o None si hay datos insuficientes."""
    candles = _get_ohlcv(symbol, tf_cfg["tf"], tf_cfg["limit"])
    if len(candles) < 10:
        return None

    opens   = [float(c["o"]) for c in candles]
    highs   = [float(c["h"]) for c in candles]
    lows    = [float(c["l"]) for c in candles]
    closes  = [float(c["c"]) for c in candles]

    price  = closes[-1]
    rsi    = _compute_rsi(closes)
    ema20  = _compute_ema(closes, 20)
    ema50  = _compute_ema(closes, min(50, len(closes)))
    ema200 = _compute_ema(closes, min(200, len(closes)))

    # Tendencia por EMA
    if price > ema50 and ema20 > ema50:
        trend = "alcista"
    elif price < ema50 and ema20 < ema50:
        trend = "bajista"
    else:
        trend = "lateral"

    # Posición en rango de las últimas 20 velas
    h20 = max(highs[-20:])
    l20 = min(lows[-20:])
    rng = h20 - l20
    pos_pct = round((price - l20) / rng * 100, 1) if rng > 0 else 50.0

    # Patrón de vela (últimas 3 velas)
    pattern = detect_candle(opens, highs, lows, closes)

    # Sesgo Elliott
    elliott = _elliott_bias(trend, rsi, pos_pct, tf_cfg["group"])

    return {
        "tf":      tf_cfg["tf"],
        "label":   tf_cfg["label"],
        "weight":  tf_cfg["weight"],
        "group":   tf_cfg["group"],
        "trend":   trend,
        "rsi":     rsi,
        "ema20":   ema20,
        "ema50":   ema50,
        "ema200":  ema200,
        "price":   price,
        "pos_pct": pos_pct,
        "elliott": elliott,
        "pattern": pattern,
        "h20":     round(h20, 8),
        "l20":     round(l20, 8),
    }


def full_topdown(symbol: str, state: dict) -> list[dict]:
    """
    Corre el análisis completo para todos los timeframes.
    Retorna lista de dicts ordenada macro → micro.
    """
    results = []
    import time
    for cfg in TIMEFRAMES:
        r = analyze_tf(symbol, cfg, state)
        if r:
            results.append(r)
        time.sleep(0.3)   # rate-limiting suave
    return results


def topdown_score(analyses: list[dict]) -> dict:
    """
    Calcula el score de alineación entre timeframes.
    Retorna { score_pct, bullish_tfs, bearish_tfs, neutral_tfs, alignment, direction }
    """
    direction_map = {"alcista": 1, "bajista": -1, "lateral": 0}
    weighted_sum  = 0.0
    total_weight  = 0.0
    bull, bear, neutral = 0, 0, 0

    for a in analyses:
        d = direction_map.get(a["trend"], 0)
        w = a["weight"]
        weighted_sum  += d * w
        total_weight  += w
        if d > 0: bull += 1
        elif d < 0: bear += 1
        else: neutral += 1

    if total_weight == 0:
        return {}

    normalized   = weighted_sum / total_weight          # -1 a +1
    score_pct    = round((normalized + 1) / 2 * 100, 1) # 0=fully bearish, 100=fully bullish

    if score_pct >= 75:
        alignment = "Alcista fuerte"
    elif score_pct >= 60:
        alignment = "Sesgo alcista"
    elif score_pct >= 45:
        alignment = "Mixto"
    elif score_pct >= 30:
        alignment = "Sesgo bajista"
    else:
        alignment = "Bajista fuerte"

    direction = "alcista" if score_pct > 55 else ("bajista" if score_pct < 45 else "lateral")

    return {
        "score_pct":   score_pct,
        "bullish_tfs": bull,
        "bearish_tfs": bear,
        "neutral_tfs": neutral,
        "alignment":   alignment,
        "direction":   direction,
    }


def elliott_conclusion(analyses: list[dict], state: dict) -> str:
    """
    Genera la conclusión Elliott narrativa para el mensaje.
    Integra macro + estructura + timing en 2-3 oraciones.
    """
    macro   = [a for a in analyses if a["group"] == "MACRO"]
    struct  = [a for a in analyses if a["group"] == "ESTRUCTURA"]
    timing  = [a for a in analyses if a["group"] == "TIMING"]

    m_bear  = sum(1 for a in macro  if a["trend"] == "bajista")
    m_bull  = sum(1 for a in macro  if a["trend"] == "alcista")
    t_bull  = sum(1 for a in timing if a["trend"] == "alcista")
    t_bear  = sum(1 for a in timing if a["trend"] == "bajista")

    rsi_d   = next((a["rsi"] for a in analyses if a["tf"] == "1D"), 50)
    rsi_4h  = next((a["rsi"] for a in analyses if a["tf"] == "4h"), 50)
    rsi_1h  = next((a["rsi"] for a in analyses if a["tf"] == "1h"), 50)

    gz_low  = state.get("gz_low", 0)
    gz_high = state.get("gz_high", 0)
    stop    = state.get("stop", 0)
    target  = state.get("target", 0)

    parts = []

    # Contexto macro
    if m_bear >= 2:
        parts.append("Estructura macro bajista dominante.")
        if rsi_d < 30:
            parts.append(f"RSI diario en sobreventa ({rsi_d:.0f}) — posible fin de onda C, busca señal de reversión.")
        else:
            parts.append("El mercado sigue en corrección de largo plazo.")
    elif m_bull >= 2:
        parts.append("Estructura macro alcista.")
        if rsi_d > 70:
            parts.append(f"RSI diario sobrecomprado ({rsi_d:.0f}) — posible consolidación antes de continuar.")
    else:
        parts.append("Mercado en transición — macro sin consenso claro.")

    # Divergencia timing vs macro
    if m_bear >= 2 and t_bull >= 1:
        parts.append(
            "Rebote en TFs bajos = corrección menor (onda 2 o B). "
            "NO entrar largo hasta que 1D confirme giro."
        )
        if gz_low > 0:
            from messages import fmt_price
            parts.append(f"Zona ideal para corto: {fmt_price(gz_low)}–{fmt_price(gz_high)}.")
    elif m_bull >= 2 and t_bear >= 1:
        parts.append("Pullback en TFs bajos sobre tendencia alcista mayor — posible zona de entrada largo.")

    # Oversold en estructura
    if rsi_4h < 35:
        parts.append(f"4H en oversold ({rsi_4h:.0f}) — espera patrón de vela alcista antes de entrar.")
    elif rsi_1h < 35:
        parts.append(f"1H en oversold ({rsi_1h:.0f}) — timing potencial, confirma en 30m.")

    return " ".join(parts)
