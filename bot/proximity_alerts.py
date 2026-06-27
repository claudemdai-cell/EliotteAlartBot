"""
Alertas de proximidad a niveles clave y detección de volumen anómalo.
Anti-spam: una alerta por nivel por día.
"""

import datetime

# "asset:nivel:fecha" — evita repetir la misma alerta en el mismo día
_alerted: set = set()

PROXIMITY_THRESHOLD = 0.025   # 2.5%
VOLUME_SPIKE_RATIO  = 2.5     # 2.5x el promedio → anómalo


def _key(asset: str, level: str) -> str:
    return f"{asset}:{level}:{datetime.date.today().isoformat()}"


def check_proximity(asset: str, price: float, state: dict) -> list[str]:
    """
    Retorna lista de textos de alerta si el precio toca un nivel clave.
    Un nivel = dentro del 2.5% de distancia.
    """
    alerts = []
    levels = {
        "soporte_90d":       (state.get("min_90d", 0),  "⬇️ Soporte 90d"),
        "resistencia_90d":   (state.get("max_90d", 0),  "⬆️ Resistencia 90d"),
        "golden_zone_low":   (state.get("gz_low", 0),   "🌟 Borde inferior Golden Zone"),
        "golden_zone_high":  (state.get("gz_high", 0),  "🌟 Borde superior Golden Zone"),
    }

    name = asset.replace("USD", "").replace("USDT", "")
    for level_key, (level_price, label) in levels.items():
        if level_price <= 0:
            continue
        k = _key(asset, level_key)
        if k in _alerted:
            continue
        dist = abs(price - level_price) / level_price
        if dist <= PROXIMITY_THRESHOLD:
            direction = "encima de" if price > level_price else "bajo"
            pct = round(dist * 100, 1)
            alerts.append(
                f"📍 *{name}* a {pct}% del {label}\n"
                f"   Precio: ${price:,.4f} · Nivel: ${level_price:,.4f} ({direction})"
            )
            _alerted.add(k)

    return alerts


def check_volume_anomaly(asset: str, price: float, current_vol: float,
                          avg20: float, trend: str) -> str | None:
    """
    Retorna mensaje de alerta si hay un spike de volumen ≥ 2.5x el promedio 20.
    """
    if avg20 <= 0 or current_vol <= 0:
        return None
    ratio = current_vol / avg20
    if ratio < VOLUME_SPIKE_RATIO:
        return None
    k = _key(asset, "vol_anomaly")
    if k in _alerted:
        return None
    _alerted.add(k)

    name     = asset.replace("USD", "").replace("USDT", "")
    trend_tx = {"alcista": "📈 Alcista", "bajista": "📉 Bajista"}.get(trend, "↔️ Lateral")
    implication = (
        "Podría ser una vela de reversión al alza." if trend == "bajista"
        else "Confirma momentum alcista — atención a continuación."
        if trend == "alcista"
        else "Sin tendencia clara — espera confirmación."
    )

    return (
        f"⚡ *Volumen anómalo — {name}*\n\n"
        f"📊 Volumen actual: *{ratio:.1f}x* el promedio 20 velas\n"
        f"💰 Precio: ${price:,.4f}\n"
        f"{trend_tx}\n\n"
        f"_{implication}_\n"
        f"_Vigila las próximas 2-4 horas._"
    )
