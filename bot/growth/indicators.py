"""
Indicadores tecnicos para el bot de crecimiento.
Funciones puras sobre listas de precios de cierre.
"""


def compute_rsi(closes: list, period: int = 14) -> float:
    """RSI clasico (0-100). Retorna 50 si no hay datos suficientes."""
    if len(closes) < period + 1:
        return 50.0
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains  = [d for d in deltas[-period:] if d > 0]
    losses = [-d for d in deltas[-period:] if d < 0]
    avg_gain = sum(gains) / period if gains else 0.001
    avg_loss = sum(losses) / period if losses else 0.001
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def compute_ema(closes: list, period: int = 21) -> float:
    """EMA del ultimo valor. Retorna el ultimo close si faltan datos."""
    if len(closes) < period:
        return closes[-1] if closes else 0.0
    k = 2 / (period + 1)
    ema = sum(closes[:period]) / period
    for price in closes[period:]:
        ema = price * k + ema * (1 - k)
    return round(ema, 6)


def ema_series(closes: list, period: int = 21) -> list:
    """Serie completa de EMA, alineada al final de closes."""
    if len(closes) < period:
        return []
    k = 2 / (period + 1)
    ema = sum(closes[:period]) / period
    out = [ema]
    for price in closes[period:]:
        ema = price * k + ema * (1 - k)
        out.append(ema)
    return out


def pct_change(closes: list, lookback: int) -> float:
    """Cambio porcentual entre el cierre actual y hace `lookback` velas."""
    if len(closes) <= lookback or closes[-1 - lookback] == 0:
        return 0.0
    return round((closes[-1] - closes[-1 - lookback]) / closes[-1 - lookback] * 100, 2)
