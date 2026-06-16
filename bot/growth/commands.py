"""
Manejador de comandos de Telegram para el bot de crecimiento.
Comandos: /estado, /balance <monto>, hecho, vendido, /pausa, /reanudar, /ayuda.
"""

from growth import state, messages
from growth.coinbase_data import get_price


def _ask_fill_price(sig: dict, prefill: float | None = None) -> str:
    """Guarda estado 'esperando precio de llenado' y devuelve la pregunta."""
    s = state.load()
    s["awaiting_fill_price"]   = True
    s["awaiting_entry_confirm"] = False
    s["awaiting_order_photo"]  = False
    s["pending_fill_price"]    = prefill
    state.save(s)
    return messages.ask_fill_price(sig, prefill)


def handle_growth_photo(photo_list: list, caption: str | None) -> str:
    """Fotos ya no son necesarias — pedimos el precio en texto."""
    s = state.load()
    if s.get("awaiting_fill_price") and s.get("pending_signal"):
        sig = s["pending_signal"]
        name = sig.get("name", sig.get("product", "").replace("-USD", ""))
        return (
            f"📝 Ya no necesito la captura. Solo escribe el precio al que\n"
            f"te llenó Coinbase para *{name}*.\n\n"
            f"Ejemplo: `{messages._raw_num(sig.get('price', 0), sig.get('product'))}`"
        )
    return (
        "📸 Recibí tu foto, pero ahora registro las entradas con texto.\n\n"
        "Cuando llegue una señal toca ✅ *Entré* y te pregunto el precio exacto."
    )


def handle_growth_command(text: str) -> str:
    raw = text.strip()
    low = raw.lower()

    # /update — progreso completo del reto en tiempo real
    if low in ("update", "/update", "actualizacion", "actualización", "actualizar", "/actualizar"):
        s = state.load()
        price = None
        if s.get("open_position"):
            price = get_price(s["open_position"]["product"])
        text = messages.update_message(s, price)
        return (text, [[("🔄 Actualizar", "update")]])

    # ── Precio de llenado esperado ────────────────────────────────────────────
    _s = state.load()
    if _s.get("awaiting_fill_price") and _s.get("pending_signal"):
        sig = _s["pending_signal"]

        # Cancelar explícito
        if low in ("cancelar", "cancel", "salir"):
            _s["awaiting_fill_price"] = False
            _s["pending_fill_price"]  = None
            state.save(_s)
            return "Cancelado. La señal sigue pendiente — escribe *hecho* cuando quieras confirmar."

        # Confirmar el precio pre-ingresado ("sí")
        if low in ("sí", "si", "yes", "ok") and _s.get("pending_fill_price"):
            fill_price = float(_s["pending_fill_price"])
            _s["awaiting_fill_price"] = False
            _s["pending_fill_price"]  = None
            state.save(_s)
            pos = state.open_position_from_pending(entry_override=fill_price)
            if not pos:
                return "No pude registrar. Intenta de nuevo."
            breakeven = round(fill_price * (1 + 2 * state.COINBASE_FEE), 8)
            return messages.fill_price_confirmed(pos, breakeven, get_price(pos["product"]))

        # Intentar parsear como precio
        price_text = raw.replace("$", "").replace(",", ".").strip()
        try:
            fill_price = float(price_text)
            if 0 < fill_price < 1_000_000:
                _s["awaiting_fill_price"] = False
                _s["pending_fill_price"]  = None
                state.save(_s)
                pos = state.open_position_from_pending(entry_override=fill_price)
                if not pos:
                    return "No pude registrar. Intenta de nuevo."
                breakeven = round(fill_price * (1 + 2 * state.COINBASE_FEE), 8)
                return messages.fill_price_confirmed(pos, breakeven, get_price(pos["product"]))
        except (ValueError, TypeError):
            pass

        # No es número ni comando conocido — re-preguntar
        known_cmds = ("/estado", "estado", "/balance", "balance", "vendido", "vendi",
                      "paso", "/pausa", "/reanudar", "/ayuda", "ayuda", "update", "/update")
        if not any(low.startswith(c) for c in known_cmds):
            example = messages._raw_num(sig.get("price", 0), sig.get("product"))
            return (
                f"No reconocí ese precio. Escribe solo el número de tu orden.\n"
                f"Ejemplo: `{example}`\n\n"
                f"_O escribe *cancelar* para volver._"
            )

    # /balance <monto>
    if low.startswith("/balance") or low.startswith("balance"):
        parts = raw.split()
        if len(parts) >= 2:
            try:
                amount = float(parts[1].replace("$", "").replace(",", ""))
                state.set_balance(amount)
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
    first_base = first_word.split(":")[0]   # "entre:ARB-USD" → "entre"

    # Producto incluido en el callback del botón: "entre:ARB-USD"
    _callback_product = None
    if ":" in first_word and first_base in ("entre", "entré", "paso"):
        _callback_product = first_word.split(":", 1)[1].upper()

    # sí / si — confirmar entrada cuando el bot pidió confirmación explícita
    if low in ("sí", "si", "yes", "correcto", "confirmo"):
        _s = state.load()
        if _s.get("awaiting_entry_confirm"):
            sig = _s.get("pending_signal")
            _s["awaiting_entry_confirm"] = False
            if not sig:
                state.save(_s)
                return "Ya no hay señal pendiente para registrar. Escribe /estado para ver cómo vamos."
            age = state.pending_age_minutes()
            if age is not None and age > 240:
                state.set_pending(None)
                state.save(_s)
                return messages.signal_expired(sig.get("name", "?"), age / 60)
            if age is not None and age > 30:
                price_now = get_price(sig["product"])
                now_txt = f" Ahora está en {messages.fmt_price(price_now)}." if price_now else ""
                state.save(_s)
                return (
                    f"⏱️ Esa señal tiene {age:.0f} min.{now_txt}\n"
                    f"¿A qué precio entraste? Responde: *hecho {messages._raw_num(price_now or sig['price'], sig.get('product'))}*"
                )
            state.save(_s)
            return _ask_fill_price(sig)

    if first_base in ("hecho", "/hecho", "comprado", "entre", "entré"):
        s = state.load()
        sig = s.get("pending_signal")
        if not sig:
            return "No tengo ninguna señal pendiente ahora mismo. Cuando dispare una, responde 'hecho'."

        if _callback_product and sig.get("product") and _callback_product != sig["product"]:
            pending_name = sig.get("name", sig["product"])
            callback_name = _callback_product.replace("-USD", "")
            return (
                f"⚠️ *Espera — moneda incorrecta.*\n\n"
                f"Tocaste ✅ Entré en *{callback_name}*, pero la señal "
                f"que tengo pendiente es de *{pending_name}*.\n\n"
                f"¿En cuál de las dos entraste realmente?\n"
                f"• Si en *{pending_name}*: escribe *hecho*\n"
                f"• Si en *{callback_name}*: escribe *hecho {callback_name}*"
            )

        # Sin callback de botón (texto plano): pedir confirmación antes de registrar
        if _callback_product is None:
            pending_name = sig.get("name", sig["product"].replace("-USD", ""))
            s["awaiting_entry_confirm"] = True
            state.save(s)
            return (
                f"⚠️ *¿Estamos en la misma página?* · {messages.SELLO}\n\n"
                f"La señal que tengo pendiente es de *{pending_name}*.\n"
                f"¿Entraste en *{pending_name}*?\n\n"
                f"• ✅ Si sí → escribe *sí*\n"
                f"• ❌ Si fue otra moneda → escribe *hecho [MONEDA]* (ej: *hecho ARB*)"
            )

        age = state.pending_age_minutes()
        if age is not None and age > 240:
            state.set_pending(None)
            return messages.signal_expired(sig.get("name", "?"), age / 60)

        entry_override = None
        parts = raw.split()
        if len(parts) >= 2:
            try:
                entry_override = float(parts[1].replace("$", "").replace(",", ""))
            except ValueError:
                return "No entendí el precio. Ejemplo: hecho 3.45"

        if entry_override is None and age is not None and age > 30:
            price_now = get_price(sig["product"])
            now_txt = f" Ahora está en {messages.fmt_price(price_now)}." if price_now else ""
            return (
                f"⏱️ Esa señal tiene {age:.0f} min.{now_txt}\n"
                f"¿A qué precio entraste? Responde: *hecho {messages._raw_num(price_now or sig['price'], sig.get('product'))}*\n"
                f"(o solo toca 🔄 ¿Sigue válida? para revisar antes)"
            )

        return _ask_fill_price(sig, prefill=entry_override)

    # revisar [producto]
    if first_word.split(":")[0] in ("revisar", "/revisar") or low in ("sigue valida", "sigue válida", "¿sigue válida?"):
        product = None
        if ":" in raw:
            product = raw.split(":", 1)[1].strip().upper()
        elif len(raw.split()) >= 2:
            product = raw.split()[1].strip().upper()
            if product and "-" not in product:
                product = f"{product}-USD"

        s = state.load()
        sig = s.get("pending_signal")

        if not sig or (product and sig.get("product") != product):
            if not product:
                return "No hay señal pendiente que revisar. Cuando dispare una, ahí estará el botón. 👍"
            from growth.strategy import evaluate, evaluate_reversion
            fresh = None
            try:
                fresh = evaluate(product, s["balance"]) or evaluate_reversion(product, s["balance"])
            except Exception as e:
                print(f"[GROWTH] Error re-evaluando {product}: {e}")
            name = product.replace("-USD", "")
            if fresh:
                from dataclasses import asdict
                sig_dict = asdict(fresh)
                state.set_pending(sig_dict)
                size_usd = round(s["balance"] * fresh.size_pct, 2)
                text = (
                    f"🔄 Re-analicé *{name}* desde cero y...\n"
                    f"¡el setup SIGUE VIVO! Jugada actualizada: 👇\n\n"
                ) + messages.buy_signal(sig_dict, s["balance"], size_usd)
                return (text, messages.signal_buttons(sig_dict))
            return (
                f"🔄 Re-analicé *{name}* con datos frescos.\n\n"
                f"❌ Ya no hay setup válido ahí. El momento pasó\n"
                f"o las condiciones cambiaron. No entres tarde —\n"
                f"sigo escaneando y te aviso con la próxima. 🦅"
            )

        from growth.strategy import revalidate_signal
        age = state.pending_age_minutes()
        res = revalidate_signal(sig, s["balance"])
        verdict = res["verdict"]
        text = messages.revalidation(verdict, res["sig"], res["price_now"], res["drift_pct"], age)
        if verdict == "expirada":
            state.set_pending(None)
            return text
        if verdict == "ajustada":
            new_sig = res["sig"]
            new_sig["created_at"] = sig.get("created_at")
            st = state.load()
            st["pending_signal"] = new_sig
            state.save(st, important=True)
            return (text, messages.signal_buttons(new_sig))
        return (text, messages.signal_buttons(res["sig"]))

    # paso — descartar la señal pendiente
    if first_base in ("paso", "/paso") or low in ("paso", "/paso", "no", "skip"):
        s = state.load()
        if not s.get("pending_signal"):
            return "No hay señal pendiente. Todo en orden. 👍"
        name = s["pending_signal"].get("name", "")
        state.set_pending(None)
        return f"Entendido, pasamos de {name}. Sigo buscando el próximo setup. 🦅"

    # vendido [precio] — confirmar cierre manual
    if first_word in ("vendido", "/vendido", "vendi", "vendí", "cerre", "cerré", "sali", "salí"):
        s = state.load()
        pos = s.get("open_position")
        if not pos:
            return "No tengo posicion abierta registrada."
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
        breakdown = messages.fmt_pnl_breakdown(res)
        return (
            f"Registrado {emoji}. *{res['name']}* cerrado.\n"
            f"{breakdown}\n"
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
