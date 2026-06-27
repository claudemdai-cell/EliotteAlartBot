"""
Plantillas de mensajes para Telegram.
Formato visual mejorado con barras, emojis y narrativa.
"""

import datetime

TREND_ICON = {"alcista": "📈", "bajista": "📉", "lateral": "↔️"}
TREND_TXT  = {
    "alcista": "Alcista — compradores dominan",
    "bajista": "Bajista — vendedores dominan",
    "lateral": "Lateral — sin dirección clara",
}
ASSET_ICON = {
    "BTC": "₿", "ETH": "Ξ", "LINK": "⬡", "SOL": "◎",
    "JASMY": "✧",
}


def fmt_price(price: float) -> str:
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


def _score_bar(score: float, total: int = 5) -> str:
    filled = int(score)
    half   = 1 if (score - filled) >= 0.5 else 0
    empty  = total - filled - half
    return "█" * filled + ("▒" if half else "") + "░" * empty


def _asset_name(raw: str) -> str:
    return raw.replace("USD", "").replace("USDT", "").replace("_", "")


def _icon(name: str) -> str:
    return ASSET_ICON.get(name.upper(), "◆")


# ─── ESTADO INDIVIDUAL ────────────────────────────────────────────────────────

def cmd_asset_status(name: str, s: dict, proj: dict = None) -> str:
    """
    Estado completo de un activo.
    Si proj viene con datos (solo BTC/ETH/LINK/SOL), incluye proyecciones.
    """
    price  = fmt_price(s["price"])
    score  = s["score"]
    bar    = _score_bar(score)
    trend  = s.get("trend", "?")
    icon   = _icon(name)

    if s["in_zone"]:
        zona = "⚡ EN GOLDEN ZONE — máxima atención"
    elif s["dist_pct"] < 0:
        zona = f"Falta {abs(s['dist_pct']):.0f}% para entrar en zona"
    else:
        zona = f"{s['dist_pct']:.0f}% por encima de la zona"

    if score >= 4:
        estado = "🔥 SETUP ACTIVO — revisa el gráfico ahora"
    elif score == 3:
        estado = "⚠️ Calentando — ponle ojo"
    else:
        estado = "⏳ Esperando — mercado en corrección"

    lines = [
        f"*{icon} {name}* · {price}",
        "─────────────────────",
        f"📊 Score:     [{bar}] {score}/5",
        f"{TREND_ICON.get(trend,'?')} Tendencia: {TREND_TXT.get(trend, trend)}",
        f"📡 RSI:       {s['rsi']:.0f}",
        f"📍 Zona:      {zona}",
        "",
        f"🎯 Target: {fmt_price(s['target'])}",
        f"🛑 Stop:   {fmt_price(s['stop'])}",
    ]

    if proj:
        lines += [
            "",
            "─────────────────────",
            "*📅 PROYECCIÓN HOY*",
            f"   Rango esperado: {fmt_price(proj['day_low'])} — {fmt_price(proj['day_high'])}",
            f"   Cierre estimado: ≈{fmt_price(proj['day_close'])}",
            f"   Confianza: {proj['confidence']}%",
            "",
            "*📆 ESTA SEMANA*",
            f"   Target: {fmt_price(proj['week_target'])} ({TREND_TXT.get(trend,'?').split(' —')[0].lower()})",
            f"   Soporte: {fmt_price(proj['week_support'])}",
            "",
            "*⏳ DISTANCIA AL ATH*",
            f"   ATH: {fmt_price(proj['ath'])} (+{proj['pct_to_ath']}%)",
            f"   Estimado: ~{proj['days_to_ath']} días a velocidad actual",
            "",
            "*📌 POR QUÉ*",
        ]
        for r in proj.get("reasons", []):
            lines.append(f"   • {r}")

    lines += ["", f"_{estado}_"]
    return "\n".join(lines)


# ─── RESUMEN DIARIO ───────────────────────────────────────────────────────────

def daily_summary(assets: list[dict], date_str: str) -> str:
    hour = datetime.datetime.utcnow().hour
    if 5 <= hour < 12:
        saludo = "Buenos días"
    elif 12 <= hour < 19:
        saludo = "Buenas tardes"
    else:
        saludo = "Buenas noches"

    hot = [a for a in assets if a["score"] >= 3]
    if any(a["score"] >= 4 for a in assets):
        intro = "🔥 Hay un setup activo. Revisa la alerta."
    elif hot:
        names = ", ".join(_asset_name(a["asset"]) for a in hot)
        intro = f"⚠️ {names} se está calentando. Ponle ojo."
    else:
        intro = "⏳ Todo tranquilo. Mercado aún en corrección."

    lines = [
        f"*{saludo} — {date_str}*",
        f"_{intro}_",
        "",
        "─────────────────────",
    ]

    for a in assets:
        score = a["score"]
        name  = _asset_name(a["asset"])
        icon  = _icon(name)
        bar   = _score_bar(score)
        trend = a.get("trend", "")
        ti    = TREND_ICON.get(trend, "?")

        if a["in_zone"]:
            zona = "⚡ En zona"
        elif a["dist_pct"] < 0:
            zona = f"−{abs(a['dist_pct']):.0f}% a zona"
        else:
            zona = f"+{a['dist_pct']:.0f}% sobre zona"

        lines.append(
            f"{icon} *{name}* [{bar}] {score}/5 {ti}\n"
            f"   {fmt_price(a['price'])} · RSI {a['rsi']:.0f} · {zona}"
        )

    lines += [
        "─────────────────────",
        "_Scan cada 4h · Gem scan diario · Análisis semanal_",
    ]
    return "\n".join(lines)


# ─── GEMS ────────────────────────────────────────────────────────────────────

def gem_report(gems: list[dict], new_gems: list[dict] = None) -> list[str]:
    if not gems:
        return ["*💎 Gem Hunter*\n\nNada destacado ahora. El mercado no tiene setups claros.\n_Seguimos escaneando cada día._"]

    msgs = []
    total = len(gems)
    fuego = sum(1 for g in gems if g["emoji"] in ("💎", "🔥"))

    lines = [
        "*💎 Gem Hunter — Reporte*",
        f"_{total} oportunidades · {fuego} de alta prioridad_",
        "─────────────────────",
        "",
    ]

    if new_gems:
        lines.append("*🆕 NUEVAS desde el último scan:*")
        for g in new_gems[:4]:
            lines.append(f"  {g['emoji']} *{g['asset']}* — {g['label']}")
        lines.append("")

    order = [("💎", "GEM MÁXIMA"), ("🔥", "FUEGO"), ("⭐", "ALTA OPORT"), ("👀", "EN RADAR")]
    for emoji, label in order:
        group = [g for g in gems if g["emoji"] == emoji]
        if not group:
            continue
        lines.append(f"*{emoji} {label}*")
        for g in group[:5]:
            name  = g["asset"]
            price = fmt_price(g["price"])
            wl    = " ✅WL" if g.get("in_watchlist") else ""
            dist  = g.get("dist_pct", g.get("dist_to_zone", 0))
            zona  = "EN ZONA" if g["in_zone"] else (f"falta {abs(dist):.0f}%" if dist < 0 else f"+{dist:.0f}% sobre zona")
            lines.append(
                f"  *{name}*{wl}  {price}  RSI {g['rsi']:.0f}  {g['score']}/5  {zona}"
            )
        lines.append("")

    lines.append("_Las 💎 y 🔥 se agregan al watchlist automáticamente._")

    msg = "\n".join(lines)
    if len(msg) > 4000:
        half = len(lines) // 2
        msgs.append("\n".join(lines[:half]))
        msgs.append("\n".join(lines[half:]))
    else:
        msgs.append(msg)
    return msgs


# ─── CAMBIO DE PANORAMA ───────────────────────────────────────────────────────

def analysis_update(asset: str, levels: dict, changes: list) -> str:
    name  = _asset_name(asset)
    icon  = _icon(name)
    price = fmt_price(levels["last_price"])
    trend = levels.get("trend", "?")
    ti    = TREND_ICON.get(trend, "?")

    dist = ((levels["last_price"] - levels["gz_low"]) / levels["gz_low"]) * 100
    if dist < 0:
        zona_txt = f"falta {abs(dist):.0f}% para entrar"
    elif levels["last_price"] <= levels["gz_high"]:
        zona_txt = "⚡ EN ZONA AHORA"
    else:
        zona_txt = f"{dist:.0f}% sobre la zona"

    lines = [
        f"*{icon} {name} — Actualización de panorama*",
        "─────────────────────",
    ]

    if changes:
        lines.append("*¿Qué cambió?*")
        for c in changes:
            lines.append(f"  • {c}")
        lines.append("")

    lines += [
        f"{ti} Tendencia: {TREND_TXT.get(trend, trend)}",
        f"💰 Precio: {price} · RSI: {levels['rsi']:.0f}",
        f"📏 Rango 90d: {fmt_price(levels['min_90d'])} — {fmt_price(levels['max_90d'])}",
        f"🌟 Golden zone: {fmt_price(levels['gz_low'])} — {fmt_price(levels['gz_high'])}",
        f"📍 Estado: {zona_txt}",
        f"🎯 Target: {fmt_price(levels['target'])} · 🛑 Stop: {fmt_price(levels['stop'])}",
    ]
    return "\n".join(lines)


# ─── AYUDA ────────────────────────────────────────────────────────────────────

def cmd_help() -> str:
    return (
        "*Elliott Alert Bot*\n"
        "─────────────────────\n"
        "*Análisis por activo*\n"
        "  /btc · /eth · /link · /sol · /jasmy\n\n"
        "*Proyecciones detalladas*\n"
        "  /proyeccion btc · /proyeccion eth\n"
        "  /proyeccion link · /proyeccion sol\n\n"
        "*General*\n"
        "  /estado — resumen de todos los activos\n"
        "  /gems — oportunidades del mercado\n"
        "  /scan — forzar scan ahora\n"
        "  /ayuda — este menú\n\n"
        "─────────────────────\n"
        "_También puedes escribir el nombre de cualquier crypto que monitoreo._"
    )


# ─── BOTONES ─────────────────────────────────────────────────────────────────

def asset_buttons(asset_code: str) -> list:
    """Botones de acción rápida después de ver un activo."""
    a = _asset_name(asset_code).lower()
    return [
        [(f"📊 Proy. {a.upper()}", f"proy:{asset_code}"), ("📈 Estado general", "estado")],
        [("💎 Gems", "gems"), ("⚡ Forzar scan", "scan")],
    ]


def summary_buttons() -> list:
    """Botones del resumen diario para ir a cada activo."""
    return [
        [("₿ BTC", "proy:BTCUSD"), ("Ξ ETH", "proy:ETHUSD")],
        [("⬡ LINK", "proy:LINKUSD"), ("◎ SOL", "proy:SOLUSD")],
        [("💎 Gems", "gems"), ("⚡ Scan ahora", "scan")],
    ]
