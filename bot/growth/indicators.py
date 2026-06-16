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


def compute_atr(highs: list, lows: list, closes: list, period: int = 14) -> float:
    """
    Average True Range (14 velas diarias por defecto).
    Mide la volatilidad real: el mayor de (H-L, |H-Cprev|, |L-Cprev|).
    Retorna 0.0 si no hay datos suficientes.
    """
    n = min(len(highs), len(lows), len(closes))
    if n < period + 1:
        return 0.0
    trs = []
    for i in range(1, n):
        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i - 1])
        lc = abs(lows[i] - closes[i - 1])
        trs.append(max(hl, hc, lc))
    return round(sum(trs[-period:]) / period, 8)


def compute_macd(closes: list, fast: int = 12, slow: int = 26, signal_period: int = 9):
    """
    MACD clásico sobre velas diarias.
    Retorna (macd_line, signal_line, histogram) del último punto.
    (0.0, 0.0, 0.0) si no hay datos suficientes.
    """
    if len(closes) < slow + signal_period:
        return 0.0, 0.0, 0.0
    ema_f = ema_series(closes, fast)
    ema_s = ema_series(closes, slow)
    n = min(len(ema_f), len(ema_s))
    if n == 0:
        return 0.0, 0.0, 0.0
    macd_vals = [ef - es for ef, es in zip(ema_f[-n:], ema_s[-n:])]
    sig_series = ema_series(macd_vals, signal_period)
    if not sig_series:
        return 0.0, 0.0, 0.0
    macd_val = macd_vals[-1]
    sig_val  = sig_series[-1]
    return round(macd_val, 8), round(sig_val, 8), round(macd_val - sig_val, 8)
