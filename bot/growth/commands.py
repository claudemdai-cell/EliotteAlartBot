"""
Manejador de comandos de Telegram para el bot de crecimiento.
Comandos: /estado, /balance <monto>, hecho, vendido, /pausa, /reanudar, /ayuda.
"""

import re
import requests as _requests

from growth import state, messages
from growth.coinbase_data import get_price


# ─── HELPERS DE FOTO / OCR ────────────────────────────────────────────────────

def _download_telegram_photo(file_id: str) -> bytes | None:
    """Descarga una foto de Telegram usando su file_id. Retorna bytes o None."""
    from growth.alerts import TOKEN
    if not TOKEN:
        return None
    try:
        r = _requests.get(
            f"https://api.telegram.org/bot{TOKEN}/getFile",
            params={"file_id": file_id}, timeout=10,
        )
        if r.status_code != 200:
            return None
        file_path = r.json().get("result", {}).get("file_path", "")
        if not file_path:
            return None
        dl = _requests.get(
            f"https://api.telegram.org/file/bot{TOKEN}/{file_path}", timeout=20
        )
        return dl.content if dl.status_code == 200 else None
    except Exception as e:
        print(f"[GROWTH] Error descargando foto: {e}")
        return None


def _ocr_photo(img_bytes: bytes) -> str | None:
    """
    Intenta OCR con pytesseract. Retorna texto o None si no está disponible.
    """
    try:
        import pytesseract
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(img_bytes))
        text = pytesseract.image_to_string(img, lang="eng")
        return text
    except ImportError:
        return None
    except Exception as e:
        print(f"[GROWTH] OCR error: {e}")
        return None


def _parse_coinbase_screenshot(text: str) -> dict:
    """
    Parsea texto OCR de un screenshot de Coinbase Advanced Trade.
    Retorna dict con price, asset, total, fee (los que pueda encontrar).
    """
    result = {}

    # Asset: "ARB-USD", "ARB-USDC", "JTO-USDC", etc.
    m = re.search(r'\b([A-Z]{2,10})[/-](?:USD|USDC|USDT)\b', text)
    if m:
        result["asset"] = m.group(1)

    # Precio: "Price $0.4230" / "Avg price $0.4230" / "Filled at $0.4230"
    m = re.search(
        r'(?:price|avg\.?\s*price|filled\s*at|precio|ejecuci[oó]n)[\s:$]*([0-9,]+\.[0-9]+)',
        text, re.IGNORECASE,
    )
    if m:
        try:
            result["price"] = float(m.group(1).replace(",", ""))
        except ValueError:
            pass

    # Si no encontramos precio etiquetado, buscar el primer número razonable tras "$"
    if "price" not in result:
        for m in re.finditer(r'\$([0-9,]+\.[0-9]{2,8})', text):
            try:
                v = float(m.group(1).replace(",", ""))
                if 0.0001 <= v <= 1_000_000:
                    result.setdefault("price", v)
                    break
            except ValueError:
                pass

    # Total pagado (incluyendo fee)
    m = re.search(
        r'(?:total|subtotal|paid|amount)[\s:$]*([0-9,]+\.[0-9]{2})',
        text, re.IGNORECASE,
    )
    if m:
        try:
            result["total"] = float(m.group(1).replace(",", ""))
        except ValueError:
            pass

    # Fee / comisión
    m = re.search(
        r'(?:fee|fees|commission|comisi[oó]n)[\s:$]*([0-9,]+\.[0-9]{2,4})',
        text, re.IGNORECASE,
    )
    if m:
        try:
            result["fee"] = float(m.group(1).replace(",", ""))
        except ValueError:
            pass

    return result


def _ask_for_order_photo(sig: dict, entry_override: float | None = None) -> str:
    """
    Guarda el estado 'esperando captura de orden' y retorna mensaje al usuario.
    No abre la posición aún — eso lo hace cuando llegue la foto (o fallback manual).
    """
    s = state.load()
    s["awaiting_order_photo"] = True
    s["pending_entry_override"] = entry_override  # precio si ya lo conocemos
    # Mantener awaiting_entry_confirm = False
    s["awaiting_entry_confirm"] = False
    state.save(s)
    name = sig.get("name", sig.get("product", "").replace("-USD", ""))
    price_hint = (
        f" (precio señal: {messages.fmt_price(sig.get('price', 0))})"
        if not entry_override else
        f" (precio: {messages.fmt_price(entry_override)})"
    )
    return (
        f"📸 *Perfecto.* Mándame la captura de la orden de Coinbase "
        f"para registrar los datos exactos{price_hint}.\n\n"
        f"_Si no tienes la foto a mano, escribe *manual* y registro "
        f"con los datos del alert._"
    )


def handle_growth_photo(photo_list: list, caption: str | None) -> str:
    """
    Maneja fotos enviadas al bot.
    Flujo:
    1. Si awaiting_order_photo → parsear y abrir posición
    2. Si caption tiene 'entrada [MONEDA] [precio]' → confirmar señal pendiente
    3. Fallback: instrucciones
    """
    cap = (caption or "").strip()
    cap_low = cap.lower()
    s = state.load()

    # ── Caso A: esperando foto de orden (Feature 3) ──
    if s.get("awaiting_order_photo") and s.get("pending_signal"):
        sig = s["pending_signal"]
        entry_override = s.get("pending_entry_override")
        parsed = {}

        # Intentar OCR si hay foto
        if photo_list:
            # Tomar la foto de mayor resolución (último elemento)
            file_id = photo_list[-1].get("file_id") if isinstance(photo_list[-1], dict) else None
            if file_id:
                img_bytes = _download_telegram_photo(file_id)
                if img_bytes:
                    ocr_text = _ocr_photo(img_bytes)
                    if ocr_text:
                        parsed = _parse_coinbase_screenshot(ocr_text)
                        print(f"[GROWTH] OCR parseado: {parsed}")

        # Si OCR encontró precio, usarlo; si no, usar el override guardado o señal
        if parsed.get("price"):
            entry_override = parsed["price"]
            print(f"[GROWTH] Precio desde captura: {entry_override}")

        # Verificar consistencia de activo si OCR encontró uno
        ocr_asset = parsed.get("asset", "").upper()
        sig_asset = sig.get("product", "").replace("-USD", "").replace("-USDC", "").upper()
        if ocr_asset and ocr_asset != sig_asset:
            print(f"[GROWTH] OCR asset {ocr_asset} vs señal {sig_asset} — usando señal")

        # Registrar la posición
        pos = state.open_position_from_pending(entry_override=entry_override)
        if not pos:
            return "No pude registrar la entrada. Intenta de nuevo o escribe *manual*."

        price_now = get_price(pos["product"])
        pnl_txt = ""
        if price_now:
            pnl = (price_now - pos["entry"]) / pos["entry"] * 100
            pnl_txt = f"\nAhora: {messages.fmt_price(price_now)} ({pnl:+.1f}%)"

        # Info de comisión real si vino de OCR
        fee_txt = ""
        if parsed.get("fee"):
            fee_txt = f"\nComisión Coinbase: {messages.fmt_usd(parsed['fee'])} (desde captura)"
        elif parsed.get("total") and entry_override:
            coinbase_fee = round(parsed["total"] * 0.006, 2)
            fee_txt = f"\nComisión est.: ~{messages.fmt_usd(coinbase_fee)}"

        source = "captura 📸" if parsed.get("price") or parsed.get("total") else "alert (sin OCR)"
        return (
            f"✅ *¡Registrado! {pos['name']}* desde {source} · {messages.SELLO}\n\n"
            f"Entrada: {messages.fmt_price(pos['entry'])}"
            + pnl_txt
            + fee_txt
            + f"\nTarget: {messages.fmt_price(pos['target'])}\n"
            + f"Stop:   {messages.fmt_price(pos['stop'])}\n\n"
            + f"Lo vigilo 24/7 y te aviso cuando salir. 🦅"
        )

    # ── Caso B: caption con "entrada [MONEDA] [precio]" ──
    if cap_low.startswith(("entrada ", "entre ", "compre ", "compré ")):
        parts = cap.split()
        moneda = parts[1].upper() if len(parts) >= 2 else None
        precio = None
        if len(parts) >= 3:
            try:
                precio = float(parts[2].replace("$", "").replace(",", ""))
            except ValueError:
                pass

        if moneda:
            product = f"{moneda}-USD"
            sig = s.get("pending_signal")
            pos = s.get("open_position")

            if pos:
                return f"Ya tienes una posición abierta en *{pos['name']}*. Ciérrala primero con *vendido*."

            if sig and sig.get("product", "").upper() == product:
                pos_result = state.open_position_from_pending(entry_override=precio)
                if not pos_result:
                    return "No pude registrar la entrada. Intenta de nuevo."
                return (
                    f"📸✅ *Registrado desde caption.* *{pos_result['name']}* "
                    f"abierto a {messages.fmt_price(pos_result['entry'])}.\n"
                    f"Target {messages.fmt_price(pos_result['target'])} | Stop {messages.fmt_price(pos_result['stop'])}\n"
                    f"Lo vigilo 24/7 y te aviso cuando salir. 🦅"
                )
            elif not sig:
                return (
                    f"📸 No tengo señal pendiente para *{moneda}*.\n"
                    f"El bot genera señales automáticamente. Cuando dispare una, "
                    f"manda la captura o escribe *hecho*."
                )
            else:
                pending_name = sig.get("name", sig["product"].replace("-USD", ""))
                return (
                    f"📸 La captura es de *{moneda}* pero la señal pendiente es de *{pending_name}*.\n"
                    f"¿Cuál es la correcta?\n"
                    f"• Si {pending_name}: escribe *hecho*\n"
                    f"• Si {moneda}: escribe *hecho {moneda}*"
                )

    # ── Caso C: foto sin contexto suficiente ──
    return (
        "📸 *Vi tu foto.*\n\n"
        "Para registrar una entrada desde una captura, agrega un caption:\n"
        "• *entrada ARB* — registra con el precio del alert\n"
        "• *entrada ARB 0.423* — registra con precio específico\n\n"
        "O cuando llegue una señal, presiona ✅ Entré y luego mándame la captura."
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

    # ── Fallback manual mientras esperamos foto de orden ─────────────────────
    if low in ("manual", "saltar", "skip", "sin foto"):
        _s = state.load()
        if _s.get("awaiting_order_photo") and _s.get("pending_signal"):
            entry_override = _s.get("pending_entry_override")
            _s["awaiting_order_photo"] = False
            _s["pending_entry_override"] = None
            state.save(_s)
            pos = state.open_position_from_pending(entry_override=entry_override)
            if not pos:
                return "No pude registrar la entrada. Intenta de nuevo."
            price_now = get_price(pos["product"])
            pnl_txt = ""
            if price_now:
                pnl = (price_now - pos["entry"]) / pos["entry"] * 100
                pnl_txt = f"\nAhora: {messages.fmt_price(price_now)} ({pnl:+.1f}%)"
            return (
                f"✅ *¡Registrado!* {pos['name']} abierto a {messages.fmt_price(pos['entry'])}."
                + pnl_txt
                + f"\nTarget {messages.fmt_price(pos['target'])} | Stop {messages.fmt_price(pos['stop'])}\n"
                + "Lo vigilo 24/7 y te aviso cuando salir. 🦅"
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
            # Feature 3: pedir captura antes de abrir la posición
            state.save(_s)
            return _ask_for_order_photo(sig)

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

        # Feature 3: pedir captura antes de abrir la posición
        return _ask_for_order_photo(sig, entry_override=entry_override)

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
