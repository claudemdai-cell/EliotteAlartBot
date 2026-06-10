"""
Manejador de comandos de Telegram para el bot de crecimiento.
Comandos: /estado, /balance <monto>, hecho, vendido, /pausa, /reanudar, /ayuda.
"""

from growth import state, messages
from growth.coinbase_data import get_price


def handle_growth_command(text: str) -> str:
    raw = text.strip()
    low = raw.lower()

    # /balance <monto>
    if low.startswith("/balance") or low.startswith("balance"):
        parts = raw.split()
        if len(parts) >= 2:
            try:
                amount = float(parts[1].replace("$", "").replace(",", ""))
                s = state.set_balance(amount)
                return (
                    f"💵 Capital fijado en {messages.fmt_usd(amount)}.\n"
                    f"Listo, a cazar setups. 🚀"
                )
            except ValueError:
                return "Dame un numero. Ejemplo: /balance 100"
        s = state.load()
        return f"Tu balance actual es {messages.fmt_usd(s['balance'])}.\nPara cambiarlo: /balance 100"

    # hecho [precio] — confirmar compra (acepta el precio real de entrada)
    first_word = low.split()[0] if low.split() else ""
    if first_word in ("hecho", "/hecho", "comprado", "entre", "entré"):
        s = state.load()
        sig = s.get("pending_signal")
        if not sig:
            return "No tengo ninguna señal pendiente ahora mismo. Cuando dispare una, responde 'hecho'."

        # Senal demasiado vieja: expirar en vez de abrir con precio fantasma
        age = state.pending_age_minutes()
        if age is not None and age > 240:  # 4 horas
            state.set_pending(None)
            return messages.signal_expired(sig.get("name", "?"), age / 60)

        # Precio real de entrada si lo dio: "hecho 3.45"
        entry_override = None
        parts = raw.split()
        if len(parts) >= 2:
            try:
                entry_override = float(parts[1].replace("$", "").replace(",", ""))
            except ValueError:
                return "No entendí el precio. Ejemplo: hecho 3.45"

        # Senal con mas de 30 min y sin precio: pedir el precio real
        if entry_override is None and age is not None and age > 30:
            from growth.coinbase_data import get_price
            price_now = get_price(sig["product"])
            now_txt = f" Ahora está en {messages.fmt_price(price_now)}." if price_now else ""
            return (
                f"⏱️ Esa señal tiene {age:.0f} min.{now_txt}\n"
                f"¿A qué precio entraste? Responde: *hecho {messages._raw_num(price_now or sig['price'], sig.get('product'))}*\n"
                f"(o solo toca 🔄 ¿Sigue válida? para revisar antes)"
            )

        pos = state.open_position_from_pending(entry_override=entry_override)
        if not pos:
            return "No pude registrar la entrada. Intenta de nuevo."
        return (
            f"📍 Registrado. *{pos['name']}* abierto a {messages.fmt_price(pos['entry'])}.\n"
            f"Target {messages.fmt_price(pos['target'])} | Stop {messages.fmt_price(pos['stop'])}\n"
            f"Lo vigilo 24/7 y te aviso cuando salir. 🦅"
        )

    # revisar — ¿la señal pendiente sigue siendo valida?
    if low in ("revisar", "/revisar", "sigue valida", "sigue válida", "¿sigue válida?"):
        s = state.load()
        sig = s.get("pending_signal")
        if not sig:
            return "No hay señal pendiente que revisar. Cuando dispare una, ahí estará el botón. 👍"
        from growth.strategy import revalidate_signal
        age = state.pending_age_minutes()
        res = revalidate_signal(sig, s["balance"])
        verdict = res["verdict"]
        text = messages.revalidation(verdict, res["sig"], res["price_now"], res["drift_pct"], age)
        if verdict == "expirada":
            state.set_pending(None)
            return text
        if verdict == "ajustada":
            # Actualizar la senal pendiente con los niveles nuevos
            new_sig = res["sig"]
            new_sig["created_at"] = sig.get("created_at")
            st = state.load()
            st["pending_signal"] = new_sig
            state.save(st, important=True)
            return (text, messages.signal_buttons(new_sig))
        # valida: re-ofrecer los botones con los niveles vigentes
        return (text, messages.signal_buttons(res["sig"]))

    # paso — descartar la señal pendiente (no entré)
    if low in ("paso", "/paso", "no", "skip"):
        s = state.load()
        if not s.get("pending_signal"):
            return "No hay señal pendiente. Todo en orden. 👍"
        name = s["pending_signal"].get("name", "")
        state.set_pending(None)
        return f"Entendido, pasamos de {name}. Sigo buscando el próximo setup. 🦅"

    # vendido [precio] — confirmar cierre manual (acepta el precio real de venta)
    if first_word in ("vendido", "/vendido", "vendi", "vendí", "cerre", "cerré", "sali", "salí"):
        s = state.load()
        pos = s.get("open_position")
        if not pos:
            return "No tengo posicion abierta registrada."
        # Precio real de venta si lo dio: "vendido 3.45"
        exit_override = None
        parts = raw.split()
        if len(parts) >= 2:
            try:
                exit_override = float(parts[1].replace("$", "").replace(",", ""))
            except ValueError:
                return "No entendí el precio. Ejemplo: vendido 3.45"
        price = exit_override or get_price(pos["product"])
        if price is None:
            return (
                f"⚠️ No pude leer el precio de {pos['name']} ahora.\n"
                f"Dime a qué precio vendiste: *vendido 3.45*"
            )
        res = state.close_position(price, "manual")
        emoji = "🎉" if res["pnl_pct"] >= 0 else "💪"
        return (
            f"Registrado {emoji}. {res['name']} cerrado.\n"
            f"Resultado: {res['pnl_pct']:+.1f}% ({messages.fmt_usd(res['pnl_usd'])})\n"
            f"Balance: *{messages.fmt_usd(res['new_balance'])}*"
        )

    # /estado
    if low in ("/estado", "estado", "/start", "status"):
        s = state.load()
        price = None
        warn = ""
        if s.get("open_position"):
            price = get_price(s["open_position"]["product"])
            if price is None:
                warn = "\n\n⚠️ No pude leer el precio actual; la posición sigue vigilada."
        return messages.status(s, price) + warn

    # /pausa
    if low in ("/pausa", "pausa", "/pause"):
        s = state.load()
        s["paused"] = True
        state.save(s)
        return "⏸️ Bot en pausa. No mandaré señales hasta que escribas /reanudar."

    # /reanudar
    if low in ("/reanudar", "reanudar", "/resume"):
        s = state.load()
        s["paused"] = False
        state.save(s)
        return "▶️ Reactivado. Volviendo a cazar setups. 🚀"

    # /ayuda
    if low in ("/ayuda", "ayuda", "/help", "help", "menu", "hola"):
        return messages.help_text()

    return (
        "No entendí eso.\n\n"
        "Escribe /ayuda para ver los comandos.\n"
        "Rápidos: /estado · /balance 100 · hecho · vendido"
    )
