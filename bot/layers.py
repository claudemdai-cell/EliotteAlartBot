"""
Evaluación de las 5 capas del Protocolo de Entrada.

Capa 1 — ELLIOTT  : zona correcta (viene del webhook de TradingView)
Capa 2 — FIBONACCI: precio entre 50-61.8% de retroceso
Capa 3 — VOLUMEN  : volumen decrece en onda C (avg5 < avg20)
Capa 4 — RSI 4H   : RSI < 40 (zona oversold / divergencia alcista)
Capa 5 — VELA 4H  : cierre > apertura (vela alcista de reversión)
BONUS  — EMAs     : precio > EMA21 en 4H
"""

from dataclasses import dataclass
from fibonacci import in_golden_zone


@dataclass
class WebhookPayload:
    """Datos que envía TradingView vía webhook."""
    asset: str          # "BTCUSDT", "ETHUSDT", etc.
    price: float        # precio actual (close 4H)
    open_4h: float
    close_4h: float
    high_4h: float
    low_4h: float
    rsi_4h: float
    volume_avg5: float  # promedio volumen últimas 5 velas 4H
    volume_avg20: float # promedio volumen últimas 20 velas 4H
    ema21_4h: float
    # Datos del conteo Elliott (cargados manualmente o por Pine Script)
    in_elliott_zone: bool
    wave_start: float   # inicio de la onda que se está retrocediendo
    wave_end: float     # fin de esa onda (techo/piso)


@dataclass
class LayerResult:
    passed: bool
    detail: str


def evaluate_layers(p: WebhookPayload) -> dict:
    """Evalúa las 5 capas. Devuelve resultado por capa y puntuación total."""

    c1 = LayerResult(
        passed=p.in_elliott_zone,
        detail="Zona Elliott confirmada por Pine Script" if p.in_elliott_zone
               else "Precio fuera de zona Elliott"
    )

    golden = in_golden_zone(p.price, p.wave_start, p.wave_end)
    c2 = LayerResult(
        passed=golden,
        detail=f"Precio {p.price} {'en' if golden else 'fuera de'} zona dorada "
               f"50-61.8% ({p.wave_start}→{p.wave_end})"
    )

    vol_ok = p.volume_avg5 < p.volume_avg20
    c3 = LayerResult(
        passed=vol_ok,
        detail=f"Volumen {'decreciente ✓' if vol_ok else 'NO decreciente ✗'} "
               f"(avg5={p.volume_avg5:.0f} vs avg20={p.volume_avg20:.0f})"
    )

    rsi_ok = p.rsi_4h < 40
    c4 = LayerResult(
        passed=rsi_ok,
        detail=f"RSI 4H = {p.rsi_4h:.1f} {'< 40 ✓' if rsi_ok else '>= 40 ✗'}"
    )

    candle_ok = p.close_4h > p.open_4h
    c5 = LayerResult(
        passed=candle_ok,
        detail=f"Vela 4H {'alcista ✓' if candle_ok else 'bajista ✗'} "
               f"(open={p.open_4h}, close={p.close_4h})"
    )

    ema_bonus = p.price > p.ema21_4h
    bonus = LayerResult(
        passed=ema_bonus,
        detail=f"Precio {'sobre' if ema_bonus else 'bajo'} EMA21 ({p.ema21_4h})"
    )

    layers = {"C1_Elliott": c1, "C2_Fibonacci": c2, "C3_Volumen": c3,
              "C4_RSI": c4, "C5_Vela": c5}
    score = sum(1 for l in layers.values() if l.passed)

    return {
        "layers": layers,
        "bonus": bonus,
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
    if score == 5 and bonus.passed:
        titulo = "💎 *¡SETUP PERFECTO!*"
        gancho = f"5/5 capas + EMA confirmada. Esto es lo que esperabas: {name} está listo."
    elif score == 5:
        titulo = "🔥 *¡SETUP MÁXIMO!*"
        gancho = f"5/5 capas alineadas en {name}. Alta probabilidad."
    else:
        titulo = "🚀 *¡SETUP ACTIVO!*"
        gancho = f"4/5 capas alineadas en {name}. Revisa antes de entrar."

    # Capas en lenguaje simple
    layer_names = {
        "C1_Elliott": "Zona Elliott correcta",
        "C2_Fibonacci": "Fibonacci 50-61.8%",
        "C3_Volumen":   "Volumen bajando (sano)",
        "C4_RSI":       f"RSI oversold ({p.rsi_4h:.0f})",
        "C5_Vela":      "Vela de reversal alcista",
    }
    capas = "\n".join(
        f"{'✅' if v.passed else '❌'} {layer_names[k]}"
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
