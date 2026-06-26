"""
Evaluación de las 5 capas del Protocolo de Entrada.

Capa 1 — ELLIOTT  : zona correcta (manual / Pine Script)
Capa 2 — FIBONACCI: precio entre 50-61.8% de retroceso
Capa 3 — VOLUMEN  : A) corrección con volumen decreciente + B) spike en vela de reversión ≥1.5×
Capa 4 — RSI 4H   : RSI < 40 Y ya subiendo (mínimo 1 vela al alza desde el fondo)
Capa 5 — VELA 4H  : martillo / engulfing alcista / pin bar (vela cerrada)
BONUS  — EMAs     : precio > EMA21 en 4H
"""

from dataclasses import dataclass, field
from fibonacci import in_golden_zone


@dataclass
class WebhookPayload:
    """Datos que envía TradingView vía webhook."""
    asset: str
    price: float
    open_4h: float
    close_4h: float
    high_4h: float
    low_4h: float
    rsi_4h: float
    volume_avg5: float   # avg últimas 5 velas (sin incluir la actual)
    volume_avg20: float  # avg últimas 20 velas
    current_volume: float = 0.0  # volumen de la vela actual
    ema21_4h: float = 0.0
    in_elliott_zone: bool = True
    wave_start: float = 0.0
    wave_end: float = 0.0
    # Vela anterior (para engulfing)
    prev_open_4h: float = 0.0
    prev_close_4h: float = 0.0
    prev_high_4h: float = 0.0
    prev_low_4h: float = 0.0
    # RSI anterior (para confirmar que está girando al alza)
    rsi_prev_4h: float = 50.0


@dataclass
class LayerResult:
    passed: bool
    detail: str
    partial: bool = False  # C3 puede ser parcial (0.5 pts)


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def _is_hammer(o: float, h: float, l: float, c: float) -> bool:
    body = abs(c - o)
    if body == 0:
        return False
    lower_wick = min(o, c) - l
    upper_wick = h - max(o, c)
    return lower_wick >= 2 * body and upper_wick <= 0.5 * body


def _is_engulfing(o: float, c: float, prev_o: float, prev_c: float) -> bool:
    prev_bearish = prev_c < prev_o
    curr_bullish = c > o
    curr_body = abs(c - o)
    prev_body = abs(prev_c - prev_o)
    return prev_bearish and curr_bullish and curr_body > prev_body


def _is_pin_bar(o: float, h: float, l: float, c: float) -> bool:
    total = h - l
    if total == 0:
        return False
    body = abs(c - o)
    lower_wick = min(o, c) - l
    return body < 0.3 * total and lower_wick > 0.5 * total


# ─── CAPAS ────────────────────────────────────────────────────────────────────

def evaluate_layers(p: WebhookPayload) -> dict:
    """Evalúa las 5 capas. Score puede ser float por C3 parcial."""

    # C1 — Elliott
    c1 = LayerResult(
        passed=p.in_elliott_zone,
        detail="Zona Elliott confirmada" if p.in_elliott_zone else "Fuera de zona Elliott"
    )

    # C2 — Fibonacci 50-61.8%
    golden = in_golden_zone(p.price, p.wave_start, p.wave_end)
    c2 = LayerResult(
        passed=golden,
        detail=f"Precio {p.price} {'EN zona dorada ✓' if golden else 'FUERA de zona dorada ✗'} "
               f"50-61.8% ({p.wave_start}→{p.wave_end})"
    )

    # C3 — Volumen: A) decreciente + B) spike ≥1.5×
    vol_trend_ok = p.volume_avg5 < p.volume_avg20  # A: corrección con menor volumen
    spike_ok = (p.current_volume >= 1.5 * p.volume_avg5
                if p.current_volume > 0 and p.volume_avg5 > 0 else False)  # B: spike en reversión

    if vol_trend_ok and spike_ok:
        c3 = LayerResult(passed=True, partial=False,
                         detail=f"Volumen decreciente ✓ + Spike {p.current_volume:.0f} ≥1.5×avg5 {p.volume_avg5:.0f} ✓")
    elif vol_trend_ok:
        c3 = LayerResult(passed=False, partial=True,
                         detail=f"Volumen decreciente ✓ pero sin spike de reversión (vol={p.current_volume:.0f} vs 1.5×avg5={p.volume_avg5*1.5:.0f})")
    else:
        c3 = LayerResult(passed=False, partial=False,
                         detail=f"Volumen NO decreciente ✗ (avg5={p.volume_avg5:.0f} vs avg20={p.volume_avg20:.0f})")

    # C4 — RSI: < 40 Y girando al alza
    rsi_oversold = p.rsi_4h < 40
    rsi_rising = p.rsi_4h > p.rsi_prev_4h  # RSI subió respecto a la vela anterior
    if rsi_oversold and rsi_rising:
        c4 = LayerResult(passed=True,
                         detail=f"RSI {p.rsi_4h:.1f} < 40 ✓ + girando al alza ({p.rsi_prev_4h:.1f}→{p.rsi_4h:.1f}) ✓")
    elif rsi_oversold:
        c4 = LayerResult(passed=False,
                         detail=f"RSI {p.rsi_4h:.1f} < 40 ✓ pero aún bajando ({p.rsi_prev_4h:.1f}→{p.rsi_4h:.1f}) — esperar giro")
    else:
        c4 = LayerResult(passed=False,
                         detail=f"RSI {p.rsi_4h:.1f} ≥ 40 ✗ (no oversold)")

    # C5 — Vela de reversión 4H
    o, h, l, c = p.open_4h, p.high_4h, p.low_4h, p.close_4h
    hammer   = _is_hammer(o, h, l, c)
    engulf   = _is_engulfing(o, c, p.prev_open_4h, p.prev_close_4h)
    pin_bar  = _is_pin_bar(o, h, l, c)

    if hammer:
        pattern = "Martillo ✓"
    elif engulf:
        pattern = "Engulfing alcista ✓"
    elif pin_bar:
        pattern = "Pin bar ✓"
    else:
        pattern = None

    c5 = LayerResult(
        passed=bool(pattern),
        detail=pattern if pattern else
               f"Sin patrón de reversión ✗ (o={o}, h={h}, l={l}, c={c})"
    )

    # Bonus EMA
    ema_bonus = LayerResult(
        passed=p.price > p.ema21_4h,
        detail=f"Precio {'sobre' if p.price > p.ema21_4h else 'bajo'} EMA21 ({p.ema21_4h})"
    )

    layers = {"C1_Elliott": c1, "C2_Fibonacci": c2, "C3_Volumen": c3,
              "C4_RSI": c4, "C5_Vela": c5}

    # Score: parcial C3 vale 0.5
    score = sum(
        0.5 if l.partial else (1.0 if l.passed else 0.0)
        for l in layers.values()
    )

    return {
        "layers": layers,
        "bonus": ema_bonus,
        "score": score,
        "alert_ready": score >= 4,
    }


def _fmt_price(p: float) -> str:
    if p >= 1000:
        return f"${p:,.2f}"
    if p >= 1:
        return f"${p:.3f}"
    if p >= 0.01:
        return f"${p:.5f}"
    return f"${p:.7f}"


def _raw_num(v: float) -> str:
    """Numero crudo sin $ ni comas, listo para pegar en el exchange."""
    if v >= 1000:
        return f"{v:.2f}"
    if v >= 1:
        return f"{v:.3f}"
    if v >= 0.01:
        return f"{v:.5f}"
    return f"{v:.8f}"


def format_alert_text(p: WebhookPayload, result: dict, stop: float, target: float) -> str:
    """Alerta con la misma estructura visual del bot Reto 100->1000."""
    score  = result["score"]
    layers = result["layers"]
    bonus  = result["bonus"]

    risk   = abs(p.price - stop)
    reward = abs(target - p.price)
    rr     = round(reward / risk, 1) if risk > 0 else 0
    risk_pct   = round(risk / p.price * 100, 1)
    reward_pct = round(reward / p.price * 100, 1)

    name = p.asset.replace("USDT", "").replace("USD", "")

    # Header segun score
    if score >= 5 and bonus.passed:
        titulo = "💎 *¡SETUP PERFECTO!*"
        gancho = f"5/5 capas + EMA confirmada. Esto es lo que esperabas: {name} está listo."
    elif score >= 5:
        titulo = "🔥 *¡SETUP MÁXIMO!*"
        gancho = f"5/5 capas alineadas en {name}. Alta probabilidad."
    elif score >= 4.5:
        titulo = "🚀 *¡SETUP FUERTE!*"
        gancho = f"4.5/5 capas en {name}. Solo falta spike de volumen — revisa."
    else:
        titulo = "🚀 *¡SETUP ACTIVO!*"
        gancho = f"4/5 capas alineadas en {name}. Revisa antes de entrar."

    # Capas en lenguaje simple
    layer_names = {
        "C1_Elliott": "Zona Elliott correcta",
        "C2_Fibonacci": "Fibonacci 50-61.8%",
        "C3_Volumen":   "Volumen (corrección + spike)",
        "C4_RSI":       f"RSI oversold + girando ({p.rsi_4h:.0f})",
        "C5_Vela":      "Martillo / Engulfing / Pin bar",
    }

    def _capa_icon(k: str, v: LayerResult) -> str:
        if v.passed:
            return "✅"
        if v.partial:
            return "⚠️"  # C3 parcial
        return "❌"

    capas = "\n".join(
        f"{_capa_icon(k, v)} {layer_names[k]}"
        for k, v in layers.items()
    )
    bonus_line = f"{'✅' if bonus.passed else '⚪'} EMA21 a favor (bonus)"

    cierre = ("La mejor combinación posible. Gestiona bien el riesgo. 😤"
              if (score == 5 and bonus.passed)
              else "Revisa el gráfico antes de entrar. Tú decides. 🧠")

    return (
        f"{titulo} · Elliott Bot\n\n"
        f"🎯 *{name}/USD* · {_fmt_price(p.price)}\n"
        f"{gancho}\n\n"
        f"📈 *LA JUGADA*\n"
        f"🎯 Target: {_fmt_price(target)} (+{reward_pct}%)\n"
        f"🛑 Stop: {_fmt_price(stop)} (-{risk_pct}%)\n"
        f"⚖️ R/R 1:{rr} — ganas {rr}x lo que arriesgas\n\n"
        f"🔍 *LAS 5 CAPAS*\n{capas}\n{bonus_line}\n\n"
        f"{cierre}"
    )


def alert_buttons(stop: float, target: float) -> list:
    """Botones 📋 de copiar target/stop para la alerta Elliott."""
    t, s = _raw_num(target), _raw_num(stop)
    return [[(f"📋 Target {t}", {"copy": t}), (f"📋 Stop {s}", {"copy": s})]]
