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


def format_alert_text(p: WebhookPayload, result: dict, stop: float, target: float) -> str:
    """Genera el texto de la alerta para Telegram."""
    score = result["score"]
    layers = result["layers"]
    bonus = result["bonus"]

    risk   = abs(p.price - stop)
    reward = abs(target - p.price)
    rb     = round(reward / risk, 2) if risk > 0 else 0

    emojis = {True: "✅", False: "❌"}
    lines = [
        f"🚨 *ALERT {p.asset}* — {score}/5 capas",
        f"",
        f"💰 Precio: `{p.price}`",
        f"🛑 Stop: `{stop}` | 🎯 Target: `{target}` | R/B: `1:{rb}`",
        f"",
        f"{emojis[layers['C1_Elliott'].passed]} C1 Elliott: {layers['C1_Elliott'].detail}",
        f"{emojis[layers['C2_Fibonacci'].passed]} C2 Fib: {layers['C2_Fibonacci'].detail}",
        f"{emojis[layers['C3_Volumen'].passed]} C3 Vol: {layers['C3_Volumen'].detail}",
        f"{emojis[layers['C4_RSI'].passed]} C4 RSI: {layers['C4_RSI'].detail}",
        f"{emojis[layers['C5_Vela'].passed]} C5 Vela: {layers['C5_Vela'].detail}",
        f"{'✅' if bonus.passed else '⚪'} BONUS EMA21: {bonus.detail}",
    ]

    if score < 4:
        lines.append(f"\n⚠️ Solo {score}/5 — NO entrar aún. Esperar confirmación.")
    elif score == 5 and bonus.passed:
        lines.append(f"\n🔥 5/5 + BONUS — Setup ideal. Revisar y decidir.")
    else:
        lines.append(f"\n⚡ {score}/5 — Setup válido. Revisar antes de entrar.")

    return "\n".join(lines)
