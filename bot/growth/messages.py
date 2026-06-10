"""
Plantillas de mensajes del Reto 100->1000.
Estilo: divertido, serio pero emocionante, con detalle tecnico.
Todas llevan el sello 🚀 "Reto 100->1000" para distinguirlas del bot Elliott.
"""

SELLO = "Reto 100→1000"


def fmt_price(p: float) -> str:
    """Formato para precios de activos (mantiene decimales segun magnitud)."""
    if p >= 1000:
        return f"${p:,.2f}"
    if p >= 1:
        return f"${p:.3f}"
    if p >= 0.01:
        return f"${p:.5f}"
    return f"${p:.7f}"


def fmt_usd(amount: float) -> str:
    """Formato para montos de dinero (balance, tamano): dolares limpios."""
    if amount >= 100:
        return f"${amount:,.0f}"
    return f"${amount:,.2f}"


def _pct(a: float, b: float) -> float:
    """Cambio porcentual de a hacia b."""
    return (b - a) / a * 100 if a else 0


def buy_signal(sig: dict, balance: float, size_usd: float) -> str:
    """
    sig: dict con product, name, price, stop, target, rr, rsi, trend, reasons[]
    """
    name   = sig["name"]
    price  = sig["price"]
    target = sig["target"]
    stop   = sig["stop"]
    rr     = sig["rr"]

    tgt_pct  = _pct(price, target)
    stop_pct = _pct(price, stop)

    goal = 1000
    next_balance = round(balance + size_usd * tgt_pct / 100)

    reasons = "\n".join(f"• {r}" for r in sig.get("reasons", [])[:4])

    kind = sig.get("kind", "breakout")
    if kind == "reversion":
        titulo = "👀 *¡REBOTE A LA VISTA!*"
        gancho = f"{name} tocó fondo y empieza a rebotar."
    else:
        titulo = "🚀 *¡SEÑAL CALIENTE!*"
        gancho = f"Esto es lo que esperábamos. {name} rompió."

    return (
        f"{titulo} · {SELLO}\n\n"
        f"🎯 *{name}/USD* · {fmt_price(price)}\n"
        f"{gancho}\n\n"
        f"📈 *LA JUGADA*\n"
        f"💵 Entra con: *{fmt_usd(size_usd)}*\n"
        f"🎯 Target: {fmt_price(target)} ({tgt_pct:+.0f}%)\n"
        f"🛑 Stop: {fmt_price(stop)} ({stop_pct:.0f}%)\n"
        f"⚖️ R/R 1:{rr} — ganas {rr:.1f}x lo que arriesgas\n\n"
        f"🔍 *POR QUÉ AHORA*\n{reasons}\n\n"
        f"🏆 Vamos {fmt_usd(balance)} de ${goal:,}. Si pega,\n"
        f"saltamos a ~{fmt_usd(next_balance)}. Paso a paso.\n\n"
        f'Responde *"hecho"* y lo vigilo 24/7.'
    )


def sell_target(name: str, exit_price: float, pnl_pct: float, old_bal: float, new_bal: float) -> str:
    return (
        f"✅ *VENDE {name}* · {SELLO}\n\n"
        f"Llegó al target: {fmt_price(exit_price)}\n"
        f"Ganancia: *{pnl_pct:+.1f}%* 🎉\n\n"
        f"Balance: {fmt_usd(old_bal)} → *{fmt_usd(new_bal)}*\n"
        f"Vende todo y esperamos la próxima.\n\n"
        f'Responde *"vendido"* para registrarlo.'
    )


def sell_stop(name: str, exit_price: float, pnl_pct: float, old_bal: float, new_bal: float) -> str:
    return (
        f"⚠️ *SAL DE {name}* · {SELLO}\n\n"
        f"Tocó el stop: {fmt_price(exit_price)}\n"
        f"Pérdida: *{pnl_pct:.1f}%*\n\n"
        f"Balance: {fmt_usd(old_bal)} → *{fmt_usd(new_bal)}*\n"
        f"Cortamos aquí. Cuidamos el capital,\n"
        f"el próximo setup llega pronto. 💪\n\n"
        f'Responde *"vendido"* para registrarlo.'
    )


def daily_summary(balance: float, start: float, watching: list[str], has_signal: bool) -> str:
    growth = _pct(start, balance)
    watch = ", ".join(w.replace("-USD", "") for w in watching[:6])
    if has_signal:
        estado = "Hay una señal activa, revísala arriba."
    else:
        estado = "Hoy sin señal clara, mercado sin breakout limpio."
    return (
        f"🌙 *{SELLO} · Resumen*\n\n"
        f"Balance: *{fmt_usd(balance)}* ({growth:+.0f}% desde el inicio)\n"
        f"{estado}\n\n"
        f"Vigilando: {watch}\n"
        f"Te aviso apenas algo rompa con fuerza."
    )


def weekly_summary(balance: float, start: float, trade_log: list, days_left: int, tier_name: str) -> str:
    growth = _pct(start, balance)
    wins = sum(1 for t in trade_log if t.get("pnl_pct", 0) > 0)
    losses = sum(1 for t in trade_log if t.get("pnl_pct", 0) <= 0)
    return (
        f"📊 *{SELLO} · Cómo vamos*\n\n"
        f"Empezaste: {fmt_usd(start)}\n"
        f"Ahora: *{fmt_usd(balance)}* ({growth:+.0f}%)\n"
        f"Trades: {wins} ganados, {losses} perdidos\n"
        f"Faltan: {days_left} días para la meta\n"
        f"Modo de riesgo actual: {tier_name}\n\n"
        f"{_weekly_note(growth, days_left)}"
    )


def _weekly_note(growth: float, days_left: int) -> str:
    if growth >= 100:
        return "Vamos adelantados. Aprovecho el ritmo con setups más ambiciosos. 🔥"
    if growth >= 30:
        return "Buen avance. Mantengo la disciplina, sin apurar trades. 👌"
    if growth >= 0:
        return "Vamos lento pero vivos. Esperamos el setup correcto. 🧘"
    return "Semana dura. Protejo el capital y espero mejores condiciones. 🛡️"


def position_open(pos: dict, current_price: float) -> str:
    name = pos["name"]
    entry = pos["entry"]
    pnl = _pct(entry, current_price)
    return (
        f"📍 *{name}* abierto · {SELLO}\n\n"
        f"Entrada: {fmt_price(entry)}\n"
        f"Ahora: {fmt_price(current_price)} ({pnl:+.1f}%)\n"
        f"Target: {fmt_price(pos['target'])}\n"
        f"Stop: {fmt_price(pos['stop'])}\n"
        f"Invertido: {fmt_usd(pos['size_usd'])}"
    )


def status(s: dict, current_price: float | None = None) -> str:
    balance = s["balance"]
    start = s["start_balance"]
    growth = _pct(start, balance)
    lines = [
        f"🚀 *{SELLO} · Estado*\n",
        f"Balance: *{fmt_usd(balance)}* ({growth:+.0f}%)",
        f"Meta: $1,000",
    ]
    pos = s.get("open_position")
    if pos:
        if current_price:
            pnl = _pct(pos["entry"], current_price)
            lines.append(f"\nPosición abierta: *{pos['name']}* ({pnl:+.1f}%)")
            lines.append(f"  Ahora {fmt_price(current_price)} | Target {fmt_price(pos['target'])} | Stop {fmt_price(pos['stop'])}")
        else:
            lines.append(f"\nPosición abierta: *{pos['name']}*")
            lines.append(f"  Target {fmt_price(pos['target'])} | Stop {fmt_price(pos['stop'])}")
    elif s.get("pending_signal"):
        lines.append(f"\nSeñal pendiente: *{s['pending_signal']['name']}* — responde 'hecho' si entraste.")
    else:
        lines.append("\nSin posición abierta. Escaneando el mercado.")

    if s.get("paused"):
        lines.append("\n⏸️ Bot en *pausa*. Escribe /reanudar para seguir.")
    if s.get("cooldown_until"):
        import datetime
        try:
            if datetime.datetime.utcnow() < datetime.datetime.fromisoformat(s["cooldown_until"]):
                lines.append("\n🧊 En enfriamiento tras 2 pérdidas. Espero mejor momento.")
        except Exception:
            pass
    return "\n".join(lines)


def help_text() -> str:
    return (
        f"🚀 *{SELLO} — Comandos*\n\n"
        "/estado — balance, posición y progreso\n"
        "/balance <monto> — fijar/ajustar tu capital\n"
        "*hecho* — confirmar que compraste la señal\n"
        "*vendido* — confirmar que cerraste\n"
        "/pausa — el bot deja de mandar señales\n"
        "/reanudar — reactivar señales\n"
        "/ayuda — ver este menú\n\n"
        "_Yo busco el setup y te explico el porqué.\n"
        "Tú pones la orden en Coinbase. Equipo._"
    )


def welcome() -> str:
    return (
        f"🚀 *{SELLO} — Activado*\n\n"
        "Voy a cazar setups de momentum en Coinbase 24/7.\n"
        "Cuando algo rompa con fuerza, te aviso con la jugada\n"
        "completa: cuánto poner, target, stop y el porqué.\n\n"
        "Para empezar, dime tu capital con */balance 100*\n"
        "Escribe /ayuda para ver todo lo que puedo hacer.\n\n"
        "_Meta: llevar $100 a $1,000. Sin apuro, con cabeza._"
    )
