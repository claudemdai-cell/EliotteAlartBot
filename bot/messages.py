"""
Plantillas de mensajes para Telegram.
Mensajes claros, directos y sin ruido tecnico.
"""

import datetime


def fmt_price(price: float) -> str:
    """Formatea precio segun su magnitud."""
    if price >= 1000:
        return f"${price:,.2f}"
    elif price >= 1:
        return f"${price:.3f}"
    elif price >= 0.01:
        return f"${price:.5f}"
    else:
        return f"${price:.7f}"


def fmt_pct(pct: float) -> str:
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.1f}%"


def daily_summary(assets: list[dict], date_str: str) -> str:
    """
    Resumen diario limpio.
    assets = [{ asset, price, score, rsi, dist_pct, in_zone, trend, gz_low, gz_high }]
    """
    hour = datetime.datetime.utcnow().hour

    if 5 <= hour < 12:
        saludo = "Buenos dias"
    elif 12 <= hour < 19:
        saludo = "Buenas tardes"
    else:
        saludo = "Buenas noches"

    # Ver si hay algo urgente
    hot = [a for a in assets if a["score"] >= 3]

    if any(a["score"] >= 4 for a in assets):
        intro = "Hay un setup activo. Revisa la alerta."
    elif hot:
        names = ", ".join(a["asset"].replace("USD","") for a in hot)
        intro = f"{names} se esta calentando. Ojo."
    else:
        intro = "Todo tranquilo. Mercado aun en correccion."

    lines = [
        f"*{saludo} — {date_str}*",
        f"_{intro}_",
        "",
    ]

    for a in assets:
        score = a["score"]
        price = fmt_price(a["price"])
        rsi   = a["rsi"]
        trend = a.get("trend", "")
        name  = a["asset"].replace("USD","").replace("USDT","")

        # Icono de estado
        if score >= 4:
            icon = "ALERTA"
        elif score == 3:
            icon = "Calentando"
        elif a["in_zone"]:
            icon = "En zona"
        else:
            icon = "Esperando"

        # Distancia a la zona
        if a["in_zone"]:
            zona = "en golden zone ahora"
        elif a["dist_pct"] < 0:
            zona = f"falta {abs(a['dist_pct']):.0f}% para la zona"
        else:
            zona = f"{a['dist_pct']:.0f}% sobre la zona"

        # Barra de score
        bar = "I" * score + "." * (5 - score)

        lines.append(
            f"*{name}* [{bar}] {score}/5 — {icon}\n"
            f"  {price} | RSI {rsi:.0f} | {zona}"
        )

    lines += ["", "_El scanner revisa cada 4h. Te aviso si algo cambia._"]
    return "\n".join(lines)


def gem_report(gems: list[dict], new_gems: list[dict] = None) -> list[str]:
    """
    Reporte de gems. Retorna lista de mensajes (puede ser mas de uno).
    """
    if not gems:
        return ["*Gem Hunter*\n\nNada destacado ahora. El mercado no tiene setups claros. Seguimos escaneando."]

    msgs = []

    # Header
    total = len(gems)
    fuego = sum(1 for g in gems if g["emoji"] in ("💎","🔥"))
    lines = [
        "*Gem Hunter — Reporte*",
        f"_{total} oportunidades encontradas, {fuego} de alta prioridad_",
        "",
    ]

    # Nuevas
    if new_gems:
        lines.append(f"*NUEVAS desde el ultimo scan:*")
        for g in new_gems[:4]:
            lines.append(f"{g['emoji']} {g['asset']} — {g['label']}")
        lines.append("")

    # Por categoria
    order = [("💎","GEM MAXIMA"), ("🔥","FUEGO"), ("⭐","ALTA OPORT"), ("👀","EN RADAR")]
    for emoji, label in order:
        group = [g for g in gems if g["emoji"] == emoji]
        if not group:
            continue
        lines.append(f"*{emoji} {label}*")
        for g in group[:5]:
            name = g["asset"]
            price = fmt_price(g["price"])
            rsi = g["rsi"]
            score = g["score"]
            wl = " [WL]" if g.get("in_watchlist") else ""

            dist = g.get("dist_pct", g.get("dist_to_zone", 0))
            if g["in_zone"]:
                zona = "EN ZONA"
            elif dist < 0:
                zona = f"falta {abs(dist):.0f}%"
            else:
                zona = f"+{dist:.0f}% sobre zona"

            lines.append(f"  *{name}*{wl}  {price}  RSI {rsi:.0f}  {score}/5  {zona}")
        lines.append("")

    lines.append("_Las 💎 y 🔥 se agregan al watchlist automaticamente._")

    msg = "\n".join(lines)
    # Dividir si pasa los 4000 chars
    if len(msg) > 4000:
        half = len(lines) // 2
        msgs.append("\n".join(lines[:half]))
        msgs.append("\n".join(lines[half:]))
    else:
        msgs.append(msg)

    return msgs


def analysis_update(asset: str, levels: dict, changes: list) -> str:
    """Notificacion de cambio de panorama."""
    name = asset.replace("USD","").replace("USDT","")
    price = fmt_price(levels["last_price"])
    trend = levels.get("trend","?")

    trend_txt = {"alcista": "Alcista — compradores en control",
                 "bajista": "Bajista — vendedores en control",
                 "lateral": "Lateral — sin direccion clara"}.get(trend, trend)

    gz_low  = fmt_price(levels["gz_low"])
    gz_high = fmt_price(levels["gz_high"])

    dist = ((levels["last_price"] - levels["gz_low"]) / levels["gz_low"]) * 100
    if dist < 0:
        zona_txt = f"falta {abs(dist):.0f}% para entrar"
    elif levels["last_price"] <= levels["gz_high"]:
        zona_txt = "EN ZONA AHORA"
    else:
        zona_txt = f"{dist:.0f}% sobre la zona"

    lines = [f"*Actualizacion — {name}*", ""]

    if changes:
        lines.append("*Que cambio:*")
        for c in changes:
            lines.append(f"  - {c}")
        lines.append("")

    lines += [
        f"Tendencia: {trend_txt}",
        f"Precio: {price} | RSI: {levels['rsi']:.0f}",
        f"Rango 90d: {fmt_price(levels['min_90d'])} — {fmt_price(levels['max_90d'])}",
        f"Golden zone: {gz_low} — {gz_high}",
        f"Estado: {zona_txt}",
        f"Stop: {fmt_price(levels['stop'])} | Target: {fmt_price(levels['target'])}",
    ]

    return "\n".join(lines)


def cmd_help() -> str:
    return (
        "*Elliott Alert Bot*\n"
        "_Comandos disponibles:_\n\n"
        "/estado — resumen rapido de todos los activos\n"
        "/btc — estado de Bitcoin\n"
        "/eth — estado de Ethereum\n"
        "/link — estado de Chainlink\n"
        "/sol — estado de Solana\n"
        "/jasmy — estado de Jasmy\n"
        "/gems — ultimas gems encontradas\n"
        "/scan — forzar scan ahora\n"
        "/ayuda — ver este menu\n\n"
        "_Tambien puedes escribir el nombre de cualquier crypto que monitoreo._"
    )


def cmd_asset_status(name: str, s: dict) -> str:
    """Estado individual de un activo."""
    price = fmt_price(s["price"])
    score = s["score"]
    bar   = "I" * score + "." * (5 - score)

    if s["in_zone"]:
        zona = "EN GOLDEN ZONE — alta atencion"
    elif s["dist_pct"] < 0:
        zona = f"falta {abs(s['dist_pct']):.0f}% para entrar en zona"
    else:
        zona = f"{s['dist_pct']:.0f}% sobre la zona"

    trend = s.get("trend", "?")
    trend_icon = {"alcista": "Alcista", "bajista": "Bajista", "lateral": "Lateral"}.get(trend, "?")

    if score >= 4:
        estado = "SETUP ACTIVO — revisa el grafico"
    elif score == 3:
        estado = "Calentando — ponle ojo"
    else:
        estado = "Esperando — mercado en correccion"

    return (
        f"*{name}*\n\n"
        f"Precio: {price}\n"
        f"Score:  [{bar}] {score}/5\n"
        f"RSI:    {s['rsi']:.0f}\n"
        f"Trend:  {trend_icon}\n"
        f"Zona:   {zona}\n"
        f"Target: {fmt_price(s['target'])}\n"
        f"Stop:   {fmt_price(s['stop'])}\n\n"
        f"_{estado}_"
    )
