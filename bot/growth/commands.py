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
        prices = {p: get_price(p) for p in s.get("open_positions", {}) if get_price(p)}
        txt = messages.update_message(s, prices)
        return (txt, [
            [("📍 Posiciones", "posiciones"), ("🔄 Actualizar", "update")],
        ])

    # /posiciones — resumen rápido de inversiones abiertas y su P&L
    if low in ("posiciones", "/posiciones", "cartera", "/cartera",
               "inversiones", "/inversiones", "portfolio"):
        s = state.load()
        prices = {p: get_price(p) for p in s.get("open_positions", {}) if get_price(p)}
        txt = messages.positions_summary(s, prices)
        return (txt, [[("🔄 Actualizar", "posiciones")]])

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

    # /abrir COIN entrada target stop monto — registrar posición abierta manualmente
    if low.startswith(("/abrir ", "abrir ")):
        parts = raw.split()
        if len(parts) < 6:
            return (
                "Para registrar una posición que ya tienes abierta:\n"
                "*/abrir COIN entrada target stop monto*\n\n"
                "Ejemplo:\n"
                "`/abrir JTO 0.75340 0.85880 0.70070 119`\n"
                "`/abrir ARB 0.0804 0.0951 0.0737 100`"
            )
        try:
            coin   = parts[1].upper().replace("-USD", "")
            entry  = float(parts[2].replace(",", "."))
            target = float(parts[3].replace(",", "."))
            stop   = float(parts[4].replace(",", "."))
            amount = float(parts[5].replace(",", "."))
        except (ValueError, IndexError):
            return "No entendí los valores.\nEjemplo: `/abrir JTO 0.75340 0.85880 0.70070 119`"
        product   = f"{coin}-USD"
        pos       = state.register_external_position(product, entry, stop, target, amount)
        price_now = get_price(product)
        pnl_txt   = ""
        if price_now:
            pnl = (price_now - entry) / entry * 100
            pnl_txt = f"\nAhora: {messages.fmt_price(price_now)} ({pnl:+.1f}%)"
        breakeven = round(entry * (1 + 2 * state.COINBASE_FEE), 8)
        return (
            f"✅ *{coin}* registrado · {messages.SELLO}\n\n"
            f"Entrada:   {messages.fmt_price(entry)}"
            + pnl_txt + "\n"
            f"Target:    {messages.fmt_price(target)}\n"
            f"Stop:      {messages.fmt_price(stop)}\n"
            f"Invertido: {messages.fmt_usd(amount)}\n"
            f"Breakeven: {messages.fmt_price(breakeven)}\n\n"
            f"Lo vigilo ahora. 🦅"
        )

    # vendido [COIN] [precio] — confirmar cierre (soporta múltiples posiciones)
    if first_word in ("vendido", "/vendido", "vendi", "vendí", "cerre", "cerré", "sali", "salí") \
            or (first_word.startswith("vendi:") and ":" in first_word):
        s = state.load()
        positions = s.get("open_positions", {})
        if not positions:
            return "No tengo posición abierta registrada."

        # Callback de botón: "vendi:JTO-USD"
        product = None
        if ":" in first_word:
            product = first_word.split(":", 1)[1].upper()

        parts = raw.split()
        exit_override = None

        if not product:
            # Intentar extraer coin del texto: "vendido JTO 0.75" o "vendido 0.75"
            if len(parts) >= 2:
                maybe_coin = parts[1].upper().replace("-USD", "")
                maybe_product = f"{maybe_coin}-USD"
                if maybe_product in positions:
                    product = maybe_product
                    if len(parts) >= 3:
                        try:
                            exit_override = float(parts[2].replace("$", "").replace(",", "."))
                        except ValueError:
                            pass
                else:
                    try:
                        exit_override = float(parts[1].replace("$", "").replace(",", "."))
                    except ValueError:
                        pass

        # Si hay múltiples posiciones y no especificaron cuál
        if not product and len(positions) > 1:
            names = " · ".join(p.replace("-USD", "") for p in positions)
            return (
                f"Tienes varias posiciones abiertas: *{names}*\n"
                f"Especifica cuál: *vendido JTO* o *vendido ARB*"
            )
        if not product:
            product = list(positions.keys())[0]

        pos = positions.get(product)
        if not pos:
            return f"No tengo {product.replace('-USD','')} registrado."

        price = exit_override or get_price(product)
        if price is None:
            return (
                f"⚠️ No pude leer el precio de {pos['name']}.\n"
                f"Dime a cuánto vendiste: *vendido {pos['name']} {messages._raw_num(pos['entry'], product)}*"
            )
        old_bal = s["balance"]
        res     = state.close_position(product, price, "manual")
        emoji   = "🎉" if res["pnl_pct"] >= 0 else "💪"
        return (
            f"Registrado {emoji}. *{res['name']}* cerrado.\n"
            f"{messages.fmt_pnl_breakdown(res)}\n"
            f"Balance: *{messages.fmt_usd(res['new_balance'])}*"
        )

    # /estado
    if low in ("/estado", "estado", "/start", "status"):
        s = state.load()
        prices = {p: get_price(p) for p in s.get("open_positions", {}) if get_price(p)}
        warn = ""
        if s.get("open_positions") and not prices:
            warn = "\n\n⚠️ No pude leer precios ahora; las posiciones siguen vigiladas."
        return messages.status(s, prices) + warn

    # /precio COIN — precio spot inmediato
    if low.startswith(("/precio", "precio", "/price", "price")):
        parts = raw.split()
        if len(parts) < 2:
            return "Dime qué moneda. Ejemplo: `/precio SOL`"
        coin    = parts[1].upper().replace("-USD", "")
        product = f"{coin}-USD"
        price   = get_price(product)
        if price is None:
            return f"⚠️ No pude leer el precio de *{coin}* ahora. Inténtalo en un momento."
        return f"💰 *{coin}/USD* ahora: `{messages.fmt_price(price)}`"

    # /historial — resumen de los últimos trades
    if low in ("/historial", "historial", "/trades", "trades", "resultados"):
        s = state.load()
        log = s.get("trade_log", [])
        if not log:
            return "Aún no hay trades cerrados registrados. 🦅"
        lines = [f"📋 *{messages.SELLO} — Historial*\n"]
        for t in log[-8:][::-1]:
            emoji  = "✅" if t.get("pnl_pct", 0) > 0 else "❌"
            name   = t.get("name", t.get("product", "?"))
            pnl    = t.get("pnl_pct", 0)
            pnl_u  = t.get("pnl_usd", 0)
            sign   = "+" if pnl_u >= 0 else ""
            lines.append(f"{emoji} *{name}*  {pnl:+.1f}%  ({sign}{messages.fmt_usd(pnl_u)})")
        total = sum(t.get("pnl_usd", 0) for t in log)
        sign  = "+" if total >= 0 else ""
        lines.append(f"\nTotal acumulado: *{sign}{messages.fmt_usd(total)}*")
        return "\n".join(lines)

    # Lenguaje natural — "qué tal", "cómo vas", "cómo va JTO", etc.
    _natural_global = (
        "qué tal", "que tal", "como vamos", "cómo vamos", "como van",
        "cómo van", "como estas", "cómo estás", "como va el reto",
        "como va", "cómo va", "como estamos", "cómo estamos", "hay algo",
    )
    _is_natural = any(low.startswith(p) or low == p for p in _natural_global)

    if _is_natural:
        # Intentar extraer una coin del texto ("cómo va JTO")
        words = low.split()
        coin_hint = None
        for w in words:
            candidate = w.upper().replace("-USD", "")
            if len(candidate) >= 2 and candidate.isalpha():
                product_try = f"{candidate}-USD"
                s2 = state.load()
                if product_try in s2.get("open_positions", {}):
                    coin_hint = product_try
                    break

        s = state.load()
        positions = s.get("open_positions", {})
        if coin_hint:
            pos   = positions.get(coin_hint, {})
            price = get_price(coin_hint)
            if not price:
                return f"No pude leer el precio de *{coin_hint.replace('-USD','')}* ahora. Está vigilado. 👁️"
            pnl   = (price - pos["entry"]) / pos["entry"] * 100 if pos.get("entry") else 0
            dist  = (pos["target"] - price) / price * 100 if pos.get("target") and price else 0
            emoji = "📈" if pnl >= 0 else "📉"
            return (
                f"{emoji} *{pos['name']}* va {pnl:+.1f}%\n"
                f"Ahora: {messages.fmt_price(price)}\n"
                f"Falta {dist:.1f}% para target · Stop: {messages.fmt_price(pos['stop'])}"
            )

        if positions:
            prices = {p: get_price(p) for p in positions if get_price(p)}
            lines  = [f"📊 *{messages.SELLO} — Resumen rápido*\n"]
            for product, pos in positions.items():
                price = prices.get(product)
                if price:
                    pnl   = (price - pos["entry"]) / pos["entry"] * 100 if pos.get("entry") else 0
                    emoji = "📈" if pnl >= 0 else "📉"
                    lines.append(f"{emoji} *{pos['name']}*: {pnl:+.1f}% · {messages.fmt_price(price)}")
                else:
                    lines.append(f"❓ *{pos['name']}*: sin precio ahora")
            lines.append(f"\nBalance: {messages.fmt_usd(s['balance'])}")
            return "\n".join(lines)

        sig = s.get("pending_signal")
        if sig:
            return (
                f"🎯 Tengo una señal pendiente de *{sig.get('name','?')}*.\n"
                f"Toca ✅ *Entré* si entraste, o 🚫 *Paso* si no."
            )
        return (
            f"Todo tranquilo. 🦅 Sin posición abierta ahora.\n"
            f"Escaneando el mercado cada 30 min.\n"
            f"Balance: {messages.fmt_usd(s['balance'])}"
        )

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
