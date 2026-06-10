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

    # hecho — confirmar compra
    if low in ("hecho", "/hecho", "comprado", "entre", "entré"):
        s = state.load()
        if not s.get("pending_signal"):
            return "No tengo ninguna señal pendiente ahora mismo. Cuando dispare una, responde 'hecho'."
        pos = state.open_position_from_pending()
        if not pos:
            return "No pude registrar la entrada. Intenta de nuevo."
        return (
            f"📍 Registrado. *{pos['name']}* abierto a {messages.fmt_price(pos['entry'])}.\n"
            f"Target {messages.fmt_price(pos['target'])} | Stop {messages.fmt_price(pos['stop'])}\n"
            f"Lo vigilo 24/7 y te aviso cuando salir. 🦅"
        )

    # vendido — confirmar cierre manual
    if low in ("vendido", "/vendido", "cerre", "cerré", "sali", "salí"):
        s = state.load()
        pos = s.get("open_position")
        if not pos:
            return "No tengo posicion abierta registrada."
        price = get_price(pos["product"]) or pos["entry"]
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
        if s.get("open_position"):
            price = get_price(s["open_position"]["product"])
        return messages.status(s, price)

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
