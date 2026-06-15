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


def logo_url(product: str) -> str:
    """
    URL del logo de la crypto (CoinCap). product = 'OP-USD' -> simbolo 'op'.
    Si no existe, Telegram simplemente no adjunta la foto.
    """
    sym = product.replace("-USD", "").replace("-USDT", "").lower()
    return f"https://assets.coincap.io/assets/icons/{sym}@2x.png"


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

    product = sig.get("product", f"{name}-USD")

    # Números crudos para copiar directamente en Coinbase (sin $, sin comas)
    target_raw = _raw_num(target, product)
    stop_raw   = _raw_num(stop, product)

    # Coinbase cobra ~0.60% taker en la entrada
    fee_usd  = round(size_usd * 0.006, 2)
    net_usd  = round(size_usd - fee_usd, 2)

    return (
        f"{titulo} · {SELLO}\n\n"
        f"🎯 *{name}/USD* · {fmt_price(price)}\n"
        f"🆔 Búscalo en Coinbase como: `{product}`\n"
        f"{gancho}\n\n"
        f"📈 *LA JUGADA*\n"
        f"💵 Entra con: *{fmt_usd(size_usd)}* (neto ~{fmt_usd(net_usd)} tras fee)\n"
        f"🎯 Target: {fmt_price(target)} ({tgt_pct:+.0f}%) → copia: `{target_raw}`\n"
        f"🛑 Stop:   {fmt_price(stop)} ({stop_pct:.0f}%) → copia: `{stop_raw}`\n"
        f"⚖️ R/R 1:{rr} — ganas {rr:.1f}x lo que arriesgas\n\n"
        f"🔍 *POR QUÉ AHORA*\n{reasons}\n\n"
        f"🏆 Vamos {fmt_usd(balance)} de ${goal:,}. Si pega,\n"
        f"saltamos a ~{fmt_usd(next_balance)}. Paso a paso.\n\n"
        f'Toca ✅ *Entré* (o escribe "hecho") y lo vigilo 24/7.'
    )


def fmt_pnl_breakdown(close_result: dict) -> str:
    """
    Formatea el desglose de P&L con comisiones.
    Retorna string multi-línea para usar en mensajes de cierre.
    """
    gross = close_result.get("gross_pnl_usd")
    fee_t = close_result.get("fee_total_usd")
    net   = close_result.get("pnl_usd")
    net_pct = close_result.get("pnl_pct", 0)
    if gross is None or fee_t is None:
        # Sin datos de desglose (retrocompat)
        return f"Resultado: *{net_pct:+.1f}%* ({fmt_usd(net)})"
    sign = "+" if gross >= 0 else ""
    return (
        f"P&L bruto:  {sign}{fmt_usd(gross)}\n"
        f"Comisiones: -{fmt_usd(fee_t)} (entrada + salida)\n"
        f"*P&L neto:  {'+' if net >= 0 else ''}{fmt_usd(net)} ({net_pct:+.1f}%)*"
    )


def sell_target(name: str, exit_price: float, pnl_pct: float, old_bal: float, new_bal: float,
                close_result: dict | None = None) -> str:
    breakdown = fmt_pnl_breakdown(close_result) if close_result else f"Ganancia: *{pnl_pct:+.1f}%* 🎉"
    return (
        f"✅ *VENDE {name}* · {SELLO}\n\n"
        f"Llegó al target: {fmt_price(exit_price)}\n"
        f"{breakdown}\n\n"
        f"Balance: {fmt_usd(old_bal)} → *{fmt_usd(new_bal)}*\n"
        f"Vende todo y esperamos la próxima.\n\n"
        f'Responde *"vendido"* para registrarlo.'
    )


def sell_stop(name: str, exit_price: float, pnl_pct: float, old_bal: float, new_bal: float,
              close_result: dict | None = None) -> str:
    breakdown = fmt_pnl_breakdown(close_result) if close_result else None
    # Stop trailing con ganancia: no es una perdida, es una salida protegida
    if pnl_pct >= 0:
        result_line = breakdown or f"Resultado: *{pnl_pct:+.1f}%* — el trailing funcionó. 😎"
        return (
            f"🔒 *VENDE {name} — ganancia protegida* · {SELLO}\n\n"
            f"Tocó el stop que subimos: {fmt_price(exit_price)}\n"
            f"{result_line}\n\n"
            f"Balance: {fmt_usd(old_bal)} → *{fmt_usd(new_bal)}*\n"
            f"Vende todo y vamos por la próxima.\n\n"
            f'Responde *"vendido"* para registrarlo.'
        )
    result_line = breakdown or f"Pérdida: *{pnl_pct:.1f}%*"
    return (
        f"⚠️ *SAL DE {name}* · {SELLO}\n\n"
        f"Tocó el stop: {fmt_price(exit_price)}\n"
        f"{result_line}\n\n"
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
        f"{_alive_line(s)}",
        f"Balance: *{fmt_usd(balance)}* ({growth:+.0f}%)",
        f"Meta: $1,000",
    ]
    pos = s.get("open_position")
    if pos:
        if current_price:
            gross_pct = _pct(pos["entry"], current_price)
            size_usd  = pos.get("size_usd", pos.get("size_gross", 0))
            size_gross = pos.get("size_gross", size_usd)
            # Estimar comisiones para dar P&L neto aproximado
            fee_entry = pos.get("fee_entry", round(size_gross * 0.006, 2))
            exit_gross_est = size_usd * (1 + gross_pct / 100)
            fee_exit_est = round(exit_gross_est * 0.006, 2)
            fee_total_est = round(fee_entry + fee_exit_est, 2)
            gross_pnl_est = round(size_usd * gross_pct / 100, 2)
            net_pnl_est = round(gross_pnl_est - fee_entry - fee_exit_est, 2)
            net_pct_est = net_pnl_est / size_gross * 100 if size_gross else 0
            lines.append(f"\nPosición abierta: *{pos['name']}*")
            lines.append(
                f"  {fmt_price(current_price)} · bruto {gross_pct:+.1f}% | neto ~{net_pct_est:+.1f}% (fees ~{fmt_usd(fee_total_est)})"
            )
            lines.append(f"  Target {fmt_price(pos['target'])} | Stop {fmt_price(pos['stop'])}")
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


def _alive_line(s: dict) -> str:
    """Indicador de vida basado en last_scan_ts."""
    import datetime
    ts = s.get("last_scan_ts")
    if not ts:
        return "🟢 Activo, arrancando…"
    try:
        last = datetime.datetime.fromisoformat(ts)
        mins = (datetime.datetime.utcnow() - last).total_seconds() / 60
        if mins < 10:
            return f"🟢 Activo · última revisión hace {int(mins)} min"
        if mins < 60:
            return f"🟡 Última revisión hace {int(mins)} min"
        return f"🔴 Sin revisar hace {int(mins/60)}h — puede estar dormido"
    except Exception:
        return "🟢 Activo"


def help_text() -> str:
    return (
        f"🚀 *{SELLO} — Comandos*\n\n"
        "/estado — balance, posición y si estoy vivo\n"
        "/balance <monto> — fijar/ajustar tu capital\n"
        "/pausa — el bot deja de mandar señales\n"
        "/reanudar — reactivar señales\n"
        "/ayuda — ver este menú\n\n"
        "Cuando llegue una señal, te saldrán botones:\n"
        "✅ *Entré* · 🚫 *Paso* · 💰 *Vendí*\n"
        "(o escríbelos a mano si prefieres)\n\n"
        "_Yo busco el setup y te explico el porqué.\n"
        "Tú pones la orden en Coinbase. Equipo._"
    )


def signal_buttons(sig: dict) -> list:
    """
    Botonera estandar de una senal de compra:
      [✅ Entré] [🚫 Paso]
      [🔄 ¿Sigue válida?]
      [📋 Target ...] [📋 Stop ...]
    Los botones 📋 copian el numero con los decimales exactos que acepta Coinbase.
    """
    product = sig.get("product")
    t = _raw_num(sig["target"], product)
    s = _raw_num(sig["stop"], product)
    # El boton lleva la moneda dentro: aunque la senal haya expirado o el bot
    # se haya reiniciado, siempre puede re-analizar ese par al instante.
    revisar_data = f"revisar:{product}" if product else "revisar"
    entre_data = f"entre:{product}" if product else "entre"
    paso_data  = f"paso:{product}"  if product else "paso"
    return [
        [("✅ Entré", entre_data), ("🚫 Paso", paso_data)],
        [("🔄 ¿Sigue válida?", revisar_data)],
        [(f"📋 Target {t}", {"copy": t}),
         (f"📋 Stop {s}",   {"copy": s})],
    ]


def _raw_num(p: float, product: str | None = None) -> str:
    """
    Numero crudo sin $ ni comas, listo para pegar en Coinbase.
    Si se conoce el par, usa exactamente los decimales que Coinbase acepta
    (quote_increment) — ni uno mas.
    """
    if product:
        try:
            from growth.coinbase_data import increment_decimals
            d = increment_decimals(product)
            if d is not None:
                return f"{p:.{d}f}"
        except Exception:
            pass
    if p >= 1000:
        return f"{p:.2f}"
    if p >= 1:
        return f"{p:.3f}"
    if p >= 0.01:
        return f"{p:.5f}"
    return f"{p:.8f}"


def revalidation(verdict: str, sig: dict, price_now: float | None, drift_pct: float, age_min: float | None) -> str:
    """Respuesta del boton '¿Sigue válida?'."""
    name = sig.get("name", "?")
    age_txt = ""
    if age_min is not None:
        if age_min >= 60:
            age_txt = f" (señal de hace {age_min/60:.1f}h)"
        else:
            age_txt = f" (señal de hace {age_min:.0f} min)"

    if verdict == "error":
        return f"⚠️ No pude leer el precio de {name} ahora mismo. Intenta de nuevo en un momento."

    header = f"🔄 *Revisión de {name}*{age_txt}\n\n"
    drift_txt = f"{drift_pct:+.1f}%"

    if verdict == "valida":
        extra = "Incluso un poco más barato que la señal. 😎" if drift_pct < -0.3 else ""
        return (
            header +
            f"Precio ahora: {fmt_price(price_now)} ({drift_txt} vs la señal)\n\n"
            f"✅ *AÚN ESTÁS A TIEMPO.* La jugada sigue en pie\n"
            f"con los mismos niveles. {extra}\n\n"
            f"🎯 Target: {fmt_price(sig['target'])}\n"
            f"🛑 Stop: {fmt_price(sig['stop'])}"
        )
    if verdict == "ajustada":
        return (
            header +
            f"Precio ahora: {fmt_price(price_now)} ({drift_txt} vs la señal)\n\n"
            f"⚠️ *Se movió a favor, pero aún hay jugada.*\n"
            f"Ajusté los niveles al precio actual:\n\n"
            f"💵 Entrada: {fmt_price(sig['price'])}\n"
            f"🎯 Target nuevo: {fmt_price(sig['target'])}\n"
            f"🛑 Stop nuevo: {fmt_price(sig['stop'])}\n"
            f"⚖️ R/R 1:{sig.get('rr', '?')}\n\n"
            f"Si entras, usa ESTOS niveles."
        )
    # expirada
    return (
        header +
        f"Precio ahora: {fmt_price(price_now)} ({drift_txt} vs la señal)\n\n"
        f"❌ *YA PASÓ.* El tren se fue o el setup se rompió.\n"
        f"No entres tarde — perseguir trades es la forma\n"
        f"más rápida de regalar dinero. La próxima llega. 🧘"
    )


def signal_expired(name: str, age_hours: float) -> str:
    return (
        f"⏰ La señal de *{name}* expiró (tenía {age_hours:.1f}h).\n"
        f"El mercado ya es otro. Sigo buscando la próxima. 🦅"
    )


def trailing_update(name: str, level: int, new_stop: float, pnl_pct: float) -> str:
    if level == 1:
        return (
            f"🔒 *{name}: stop subido a breakeven* · {SELLO}\n\n"
            f"Vas {pnl_pct:+.1f}%. Mueve tu stop a *{fmt_price(new_stop)}*\n"
            f"(tu precio de entrada). A partir de aquí,\n"
            f"*este trade ya no puede hacerte perder.* 😤\n\n"
                   f"📋 Stop nuevo abajo para copiar."
        )
    return (
        f"🔒 *{name}: asegurando ganancia* · {SELLO}\n\n"
        f"Vas {pnl_pct:+.1f}%. Sube tu stop a *{fmt_price(new_stop)}*.\n"
        f"Pase lo que pase, ya ganas en este trade. 💰\n\n"
        f"📋 Stop nuevo abajo para copiar."
    )


def position_progress(name: str, pnl_pct: float, price: float, target: float) -> str:
    if pnl_pct >= 0:
        dist = (target - price) / price * 100 if price else 0
        return (
            f"📈 *{name}* va {pnl_pct:+.1f}% · {SELLO}\n"
            f"Precio: {fmt_price(price)} | Falta {dist:.1f}% para el target.\n"
            f"Aguanta, lo estamos logrando. 🚀"
        )
    return (
        f"📉 *{name}* va {pnl_pct:+.1f}% · {SELLO}\n"
        f"Precio: {fmt_price(price)}. Respira — el stop está puesto\n"
        f"por algo. O rebota, o salimos con pérdida controlada."
    )


def state_recovered(balance: float, trades: int) -> str:
    return (
        f"♻️ *Me reinicié y recuperé todo* · {SELLO}\n\n"
        f"Balance: *{fmt_usd(balance)}* | Trades registrados: {trades}\n"
        f"Backup de GitHub funcionando. Seguimos. 💪"
    )


def state_lost() -> str:
    return (
        f"⚠️ *Me reinicié y no pude recuperar el estado* · {SELLO}\n\n"
        f"Confirma tu balance actual con */balance <monto>*\n"
        f"y si tienes una posición abierta, avísame."
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
 a $1,000. Sin apuro, con cabeza._"
    )
