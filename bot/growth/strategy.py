"""
Motor de senales — Momentum Breakout para el Reto 100->1000.

Filosofia: esperar el setup correcto, no operar por operar.
Una senal se dispara solo cuando varios factores se alinean:
  1. Breakout: precio rompe el maximo reciente (resistencia local).
  2. Volumen: la vela del breakout trae volumen > 2x el promedio.
  3. Tendencia multi-temporalidad: diario alcista + momentum de corto plazo.
  4. RSI con espacio para correr (no sobrecomprado, no hundido).
  5. No extendido: el precio no esta demasiado lejos de su EMA21.

El riesgo (stop y agresividad) se adapta al balance actual (tramos).
"""

from dataclasses import dataclass, field
from growth.coinbase_data import get_candles, get_price, G_1H, G_6H, G_1D
from growth.indicators import compute_rsi, compute_ema, pct_change


# ─── UNIVERSO ─────────────────────────────────────────────────────────────────
# Alts liquidas y volatiles disponibles en Coinbase. Se cruza con los productos
# realmente operables al momento de escanear.
CURATED = [
    "SOL-USD", "SUI-USD", "INJ-USD", "RENDER-USD", "WLD-USD", "ONDO-USD",
    "LINK-USD", "AVAX-USD", "NEAR-USD", "SEI-USD", "TIA-USD", "JTO-USD",
    "APT-USD", "ARB-USD", "OP-USD", "FET-USD", "AAVE-USD",
    "DOGE-USD", "JASMY-USD", "FIL-USD", "ADA-USD", "DOT-USD", "ATOM-USD",
]


# ─── TRAMOS DE RIESGO ─────────────────────────────────────────────────────────
@dataclass
class RiskTier:
    name: str
    stop_pct: float       # distancia del stop (fraccion, ej 0.07 = 7%)
    target_rr: float      # multiplo R/R del target
    min_score: int        # confirmaciones minimas exigidas (de 5)
    size_pct: float       # fraccion del balance a usar


def risk_tier(balance: float) -> RiskTier:
    """Selecciona el tramo de riesgo segun el balance actual."""
    if balance < 150:
        return RiskTier("Conservador", 0.07, 2.0, 4, 1.00)
    if balance < 300:
        return RiskTier("Normal",      0.09, 2.2, 4, 1.00)
    if balance < 600:
        return RiskTier("Agresivo",    0.11, 2.5, 4, 1.00)
    if balance < 900:
        return RiskTier("Caza final",  0.13, 2.8, 4, 1.00)
    return RiskTier("Proteger",        0.05, 2.0, 5, 0.75)


# ─── SENAL ────────────────────────────────────────────────────────────────────
@dataclass
class Signal:
    product: str
    name: str               # "SUI"
    price: float
    entry_low: float
    entry_high: float
    stop: float
    target: float
    rr: float
    score: int              # confirmaciones cumplidas (0-5)
    rsi: float
    trend: str              # "alcista" / "lateral" / "bajista"
    resistance: float
    reasons: list = field(default_factory=list)
    size_pct: float = 1.0
    kind: str = "breakout"  # "breakout" | "reversion"


# ─── PREPARACION DE DATOS ─────────────────────────────────────────────────────
def _load_series(product: str):
    """
    Descarga y limpia las series. Descarta la vela diaria en formacion
    (el dia de hoy, aun incompleto) para no contaminar estructura/volumen.
    Mide el volumen con velas de 1h (mas responsivo y sin el bug del dia parcial).

    Retorna dict o None si faltan datos:
      { price, d_close, d_high, d_low, d_open, vol_ratio, mom_24h, mom_12h }
    """
    daily = get_candles(product, G_1D, 120)
    if len(daily) < 56:  # necesitamos 55 cerradas + 1 en formacion
        return None
    h1 = get_candles(product, G_1H, 72)
    if len(h1) < 30:
        return None

    # descartar el dia en formacion
    daily_closed = daily[:-1]
    d_close = [c["c"] for c in daily_closed]
    d_high  = [c["h"] for c in daily_closed]
    d_low   = [c["l"] for c in daily_closed]
    d_open  = [c["o"] for c in daily_closed]

    h_close = [c["c"] for c in h1]
    h_vol   = [c["v"] for c in h1]
    price = h_close[-1]
    if price <= 0:
        return None

    # volumen: ultimas 6h vs promedio de bloques de 6h previos
    recent_vol = sum(h_vol[-6:])
    prior = h_vol[-30:-6]
    avg_block = (sum(prior) / len(prior)) * 6 if prior else 0
    vol_ratio = recent_vol / avg_block if avg_block > 0 else 0

    return {
        "price": price,
        "d_close": d_close, "d_high": d_high, "d_low": d_low, "d_open": d_open,
        "h_close": h_close,
        "vol_ratio": round(vol_ratio, 2),
        "mom_24h": pct_change(h_close, 24),
        "mom_12h": pct_change(h_close, 12),
    }


# ─── EVALUACION DE UN ACTIVO ──────────────────────────────────────────────────
def evaluate(product: str, balance: float) -> Signal | None:
    """
    Analiza un par y devuelve una Signal si cumple el setup, o None.
    Usa velas diarias (tendencia + resistencia), 6h y 1h (momentum/breakout).
    """
    tier = risk_tier(balance)
    data = _load_series(product)
    if not data:
        return None

    price   = data["price"]
    d_close = data["d_close"]
    d_high  = data["d_high"]
    h_close = data["h_close"]

    ema21_d = compute_ema(d_close, 21)
    ema50_d = compute_ema(d_close, 50)
    rsi_d   = compute_rsi(d_close)
    ema21_h = compute_ema(h_close, 21)

    # Resistencia local: maximo de las ultimas 20 velas diarias cerradas
    resistance = max(d_high[-20:])

    reasons = []
    score = 0

    # 1. BREAKOUT — precio rompe (o esta rompiendo) la resistencia local
    broke = price >= resistance * 0.995
    if broke:
        score += 1
        days_fighting = sum(1 for x in d_high[-6:] if x >= resistance * 0.97)
        if days_fighting >= 2:
            reasons.append(f"Rompio resistencia de {_fmt(resistance)} (la peleo {days_fighting} dias)")
        else:
            reasons.append(f"Rompio resistencia de {_fmt(resistance)}")

    # 2. VOLUMEN — repunte en las ultimas horas (calculado en 1h)
    vol_ratio = data["vol_ratio"]
    if vol_ratio >= 2.0:
        score += 1
        reasons.append(f"Volumen {vol_ratio:.1f}x el promedio = compradores reales")
    elif vol_ratio >= 1.4:
        reasons.append(f"Volumen subiendo ({vol_ratio:.1f}x el promedio)")

    # 3. TENDENCIA MULTI-TF — diario alcista + momentum corto plazo
    daily_up = price > ema50_d and ema21_d > ema50_d
    mom_1h   = data["mom_24h"] > 0
    if daily_up and mom_1h:
        score += 1
        reasons.append("Tendencia diaria y de corto plazo: alcista")
        trend = "alcista"
    elif daily_up:
        trend = "alcista"
        reasons.append("Tendencia diaria alcista")
    elif price < ema50_d and ema21_d < ema50_d:
        trend = "bajista"
    else:
        trend = "lateral"

    # 4. RSI con espacio para correr
    if 40 <= rsi_d <= 65:
        score += 1
        reasons.append(f"RSI {rsi_d:.0f}, con espacio para correr")
    elif rsi_d > 72:
        reasons.append(f"RSI {rsi_d:.0f} — algo caliente, cuidado")

    # 5. NO EXTENDIDO — precio cerca de su EMA21 (no sobreextendido)
    ext = (price - ema21_h) / ema21_h * 100 if ema21_h > 0 else 0
    if ext <= 12:
        score += 1
        if ext >= 0:
            reasons.append("Precio aun cerca de su media, no sobreextendido")
    else:
        reasons.append(f"Precio {ext:.0f}% sobre su media — ya corrio bastante")

    # ── Filtro: tendencia no bajista y score suficiente para el tramo ──
    if trend == "bajista":
        return None
    if not broke:
        return None
    if score < tier.min_score:
        return None

    # ── Construir niveles ──
    stop   = round(price * (1 - tier.stop_pct), 8)
    risk   = price - stop
    target = round(price + risk * tier.target_rr, 8)
    rr     = round((target - price) / risk, 1) if risk > 0 else 0

    return Signal(
        product=product,
        name=product.replace("-USD", ""),
        price=price,
        entry_low=round(price * 0.997, 8),
        entry_high=round(price * 1.005, 8),
        stop=stop,
        target=target,
        rr=rr,
        score=score,
        rsi=rsi_d,
        trend=trend,
        resistance=resistance,
        reasons=reasons,
        size_pct=tier.size_pct,
    )


# ─── REVERSION DESDE SOBREVENTA ───────────────────────────────────────────────
def evaluate_reversion(product: str, balance: float) -> Signal | None:
    """
    Caza el rebote desde sobreventa profunda (util en correcciones).
    NO atrapa cuchillos: exige vela de confirmacion + repunte de volumen.
      1. RSI diario < 32 (sobreventa real).
      2. Vela diaria de giro: cierre > apertura (compradores aparecen).
      3. Cerca del piso reciente (dentro de ~8% del minimo 30d).
      4. Volumen repuntando en el rebote.
      5. Repunte de corto plazo: ultimas 12h al alza.
    """
    tier = risk_tier(balance)
    data = _load_series(product)
    if not data:
        return None

    price   = data["price"]
    d_close = data["d_close"]
    d_low   = data["d_low"]

    rsi_d = compute_rsi(d_close)
    if rsi_d >= 35:
        return None  # no esta sobrevendido, este detector no aplica

    reasons = []
    score = 1  # la sobreventa ya cuenta
    reasons.append(f"RSI {rsi_d:.0f} — sobreventa profunda, rebote probable")

    # 2. Confirmacion de giro: precio ya rebotando desde el cierre de ayer
    turn = price > d_close[-1] or data["mom_12h"] > 1.0
    if turn:
        score += 1
        reasons.append("Empieza a rebotar: los compradores aparecieron")

    # 3. Cerca del piso reciente
    low30 = min(d_low[-30:])
    dist_low = (price - low30) / low30 * 100 if low30 > 0 else 99
    if dist_low <= 10:
        score += 1
        reasons.append(f"Pegado al piso de {_fmt(low30)} (zona de rebote)")

    # 4. Volumen repuntando (1h)
    vol_ratio = data["vol_ratio"]
    if vol_ratio >= 1.3:
        score += 1
        reasons.append(f"Volumen {vol_ratio:.1f}x = interes comprador real")

    # 5. Repunte de corto plazo
    if data["mom_12h"] > 0:
        score += 1
        reasons.append("Rebotando en las ultimas horas")

    # Exigimos confirmacion: giro obligatorio + score del tramo
    if not turn:
        return None
    if score < tier.min_score:
        return None

    # Niveles: stop bajo el piso reciente, target hacia la EMA21 diaria
    ema21_d = compute_ema(d_close, 21)
    stop = round(min(low30, price * (1 - tier.stop_pct)) * 0.995, 8)
    risk = price - stop
    if risk <= 0:
        return None
    # target: el mayor entre RR del tramo y un acercamiento a la EMA21
    target_rr   = price + risk * tier.target_rr
    target_ema  = max(ema21_d, price * 1.06)
    target = round(max(target_rr, min(target_ema, price * 1.5)), 8)
    rr = round((target - price) / risk, 1)

    if rr < 1.5:
        return None

    return Signal(
        product=product, name=product.replace("-USD", ""), price=price,
        entry_low=round(price * 0.997, 8), entry_high=round(price * 1.008, 8),
        stop=stop, target=target, rr=rr, score=score, rsi=rsi_d,
        trend="rebote", resistance=ema21_d, reasons=reasons,
        size_pct=tier.size_pct, kind="reversion",
    )


# ─── ESCANEO DEL UNIVERSO ─────────────────────────────────────────────────────
def scan_universe(balance: float, available: set[str] | None = None) -> list[Signal]:
    """
    Recorre el universo curado (cruzado con productos disponibles) y
    devuelve las senales validas ordenadas por score y R/R.
    """
    universe = [p for p in CURATED if (available is None or p in available)]
    signals = []
    for product in universe:
        try:
            # 1) Breakout (mejor en tendencia alcista)
            sig = evaluate(product, balance)
            # 2) Si no hay breakout, probar reversion desde sobreventa
            if not sig:
                sig = evaluate_reversion(product, balance)
            if sig:
                signals.append(sig)
        except Exception as e:
            print(f"[STRATEGY] Error {product}: {e}")
            continue
    # breakout tiene prioridad sobre reversion; luego score y rr
    kind_rank = {"breakout": 0, "reversion": 1}
    signals.sort(key=lambda s: (kind_rank.get(s.kind, 2), -s.score, -s.rr))
    return signals


# ─── MARKET REGIME ────────────────────────────────────────────────────────────
def market_too_weak() -> bool:
    """True si BTC cayo mas de 15% en la ultima semana (pausamos)."""
    daily = get_candles("BTC-USD", G_1D, 10)
    if len(daily) < 8:
        return False
    week_ago = daily[-8]["c"]
    now = daily[-1]["c"]
    if week_ago <= 0:
        return False
    return (now - week_ago) / week_ago * 100 < -15


def _fmt(p: float) -> str:
    if p >= 1000:
        return f"${p:,.2f}"
    if p >= 1:
        return f"${p:.3f}"
    if p >= 0.01:
        return f"${p:.5f}"
    return f"${p:.7f}"
