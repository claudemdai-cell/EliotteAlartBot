"""
Detección de patrones de vela japonesa.
Cubre patrones de 1, 2 y 3 velas — alcistas, bajistas y neutros.
"""


def detect(opens: list, highs: list, lows: list, closes: list) -> dict | None:
    """
    Analiza las últimas 3 velas y retorna el patrón más significativo.
    Retorna { name, bias, strength } o None.
    """
    if len(opens) < 3:
        return None

    o1, h1, l1, c1 = opens[-1], highs[-1], lows[-1], closes[-1]
    o2, h2, l2, c2 = opens[-2], highs[-2], lows[-2], closes[-2]
    o3, h3, l3, c3 = opens[-3], highs[-3], lows[-3], closes[-3]

    body1  = abs(c1 - o1)
    range1 = h1 - l1 if (h1 - l1) > 0 else 0.0001
    lower1 = min(o1, c1) - l1
    upper1 = h1 - max(o1, c1)

    body2  = abs(c2 - o2)
    range2 = h2 - l2 if (h2 - l2) > 0 else 0.0001
    lower2 = min(o2, c2) - l2
    upper2 = h2 - max(o2, c2)

    bull1 = c1 > o1
    bear1 = c1 < o1
    bull2 = c2 > o2
    bear2 = c2 < o2
    bull3 = c3 > o3
    bear3 = c3 < o3

    # ── PATRONES DE 3 VELAS (más fuertes — evaluar primero) ───────────────────

    # Estrella de la Mañana (Morning Star) — alcista fuerte
    mid_body2 = abs(c2 - o2) < 0.3 * range2
    if bear3 and mid_body2 and bull1 and c1 > (o3 + c3) / 2:
        return {"name": "Estrella de la Mañana", "bias": "alcista", "strength": "fuerte"}

    # Estrella Vespertina (Evening Star) — bajista fuerte
    if bull3 and mid_body2 and bear1 and c1 < (o3 + c3) / 2:
        return {"name": "Estrella Vespertina", "bias": "bajista", "strength": "fuerte"}

    # Tres Soldados Blancos — alcista fuerte
    if bull1 and bull2 and bull3 and c1 > c2 > c3 and body1 > 0.5 * range1:
        return {"name": "Tres Soldados Blancos", "bias": "alcista", "strength": "fuerte"}

    # Tres Cuervos Negros — bajista fuerte
    if bear1 and bear2 and bear3 and c1 < c2 < c3 and body1 > 0.5 * range1:
        return {"name": "Tres Cuervos Negros", "bias": "bajista", "strength": "fuerte"}

    # Bebé Abandonado Alcista (Abandoned Baby) — muy raro, muy fuerte
    gap_down = h2 < min(l1, l3)
    if bear3 and body2 < 0.1 * range2 and bull1 and gap_down:
        return {"name": "Bebé Abandonado Alcista", "bias": "alcista", "strength": "fuerte"}

    # ── PATRONES DE 2 VELAS ───────────────────────────────────────────────────

    # Engulfing Alcista
    if bear2 and bull1 and body1 > body2 and c1 > o2 and o1 < c2:
        strength = "fuerte" if body1 > 1.5 * body2 else "medio"
        return {"name": "Engulfing Alcista", "bias": "alcista", "strength": strength}

    # Engulfing Bajista
    if bull2 and bear1 and body1 > body2 and c1 < o2 and o1 > c2:
        strength = "fuerte" if body1 > 1.5 * body2 else "medio"
        return {"name": "Engulfing Bajista", "bias": "bajista", "strength": strength}

    # Harami Alcista (inversión de tendencia bajista)
    if bear2 and bull1 and c1 <= o2 and o1 >= c2 and body1 < body2:
        return {"name": "Harami Alcista", "bias": "alcista", "strength": "débil"}

    # Harami Bajista
    if bull2 and bear1 and c1 >= o2 and o1 <= c2 and body1 < body2:
        return {"name": "Harami Bajista", "bias": "bajista", "strength": "débil"}

    # Dark Cloud Cover (nube oscura) — bajista medio
    if bull2 and bear1 and o1 > h2 and c1 < (o2 + c2) / 2:
        return {"name": "Nube Oscura", "bias": "bajista", "strength": "medio"}

    # Piercing Pattern (penetración) — alcista medio
    if bear2 and bull1 and o1 < l2 and c1 > (o2 + c2) / 2:
        return {"name": "Patrón de Penetración", "bias": "alcista", "strength": "medio"}

    # ── PATRONES DE 1 VELA ────────────────────────────────────────────────────

    # Doji (cuerpo < 10% del rango)
    if body1 < 0.1 * range1:
        if lower1 > 2 * upper1:
            return {"name": "Doji de Libélula", "bias": "alcista", "strength": "medio"}
        elif upper1 > 2 * lower1:
            return {"name": "Doji de Lápida", "bias": "bajista", "strength": "medio"}
        return {"name": "Doji", "bias": "neutral", "strength": "débil"}

    # Martillo (Hammer) — alcista
    if lower1 >= 2 * body1 and upper1 <= 0.5 * body1 and bear2:
        return {"name": "Martillo", "bias": "alcista", "strength": "medio"}

    # Martillo Invertido (Inverted Hammer) — alcista potencial
    if upper1 >= 2 * body1 and lower1 <= 0.5 * body1 and bull1:
        return {"name": "Martillo Invertido", "bias": "alcista", "strength": "débil"}

    # Shooting Star — bajista
    if upper1 >= 2 * body1 and lower1 <= 0.5 * body1 and bear1:
        return {"name": "Shooting Star", "bias": "bajista", "strength": "medio"}

    # Hanging Man — bajista (igual forma que martillo pero en alza)
    if lower1 >= 2 * body1 and upper1 <= 0.5 * body1 and bull2:
        return {"name": "Hanging Man", "bias": "bajista", "strength": "débil"}

    # Pin Bar Alcista (cola larga abajo)
    if body1 < 0.3 * range1 and lower1 > 0.55 * range1:
        return {"name": "Pin Bar Alcista", "bias": "alcista", "strength": "medio"}

    # Pin Bar Bajista (cola larga arriba)
    if body1 < 0.3 * range1 and upper1 > 0.55 * range1:
        return {"name": "Pin Bar Bajista", "bias": "bajista", "strength": "medio"}

    # Vela alcista fuerte (marubozu verde)
    if bull1 and body1 > 0.8 * range1:
        return {"name": "Vela Alcista Fuerte", "bias": "alcista", "strength": "medio"}

    # Vela bajista fuerte (marubozu rojo)
    if bear1 and body1 > 0.8 * range1:
        return {"name": "Vela Bajista Fuerte", "bias": "bajista", "strength": "medio"}

    return None


BIAS_ICON = {"alcista": "🟢", "bajista": "🔴", "neutral": "⚪"}
STRENGTH_ICON = {"fuerte": "⚡", "medio": "◆", "débil": "·"}


def fmt_pattern(p: dict | None) -> str:
    if not p:
        return ""
    bi = BIAS_ICON.get(p["bias"], "")
    si = STRENGTH_ICON.get(p["strength"], "")
    return f"{bi}{si} {p['name']}"
