"""
Elliott Alert Bot — Servidor Flask.
- Recibe webhooks de TradingView
- Responde comandos de Telegram (/estado, /btc, /gems, etc.)
- Lanza scanner y keep-alive en background
"""

import os
import threading
from flask import Flask, request, jsonify
from layers import WebhookPayload, evaluate_layers, format_alert_text, alert_buttons
from alerts import send_telegram, send_telegram_photo, logo_url
from log import log_alert

app = Flask(__name__)
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "elliott2026")

# Referencia al estado dinamico del scanner (se llena cuando arranca)
_scanner_state = {}


# ─── THREADS ──────────────────────────────────────────────────────────────────

def start_scanner_thread():
    try:
        from scanner import run_scanner, DYNAMIC_STATE
        _scanner_state["ref"] = DYNAMIC_STATE
        t = threading.Thread(target=run_scanner, daemon=True)
        t.start()
        print("[MAIN] Scanner iniciado.")
    except Exception as e:
        print(f"[MAIN] Error scanner: {e}")


def start_growth_thread():
    """Lanza el scanner del Reto 100->1000 con watchdog que lo reinicia si muere."""
    def supervised():
        import time
        from growth.scanner import run_growth_scanner
        while True:
            try:
                run_growth_scanner()
            except Exception as e:
                print(f"[GROWTH] Scanner cayo: {e}. Reiniciando en 30s...")
                time.sleep(30)
    try:
        t = threading.Thread(target=supervised, daemon=True)
        t.start()
        print("[MAIN] Growth scanner (Reto 100->1000) iniciado.")
    except Exception as e:
        print(f"[MAIN] Error growth: {e}")


def start_keepalive_thread():
    """
    Auto-ping cada 5 min para evitar que Render free se duerma (limite 15 min).
    Cubre ambos bots (comparten /health). Como respaldo extra se recomienda
    un monitor externo (UptimeRobot/cron-job.org) pegandole a /health.
    """
    import time, requests as req
    def ping():
        url = os.getenv("BOT_URL", "https://eliottealartbot.onrender.com").rstrip("/") + "/health"
        while True:
            try:
                req.get(url, timeout=10)
                print("[KEEPALIVE] ok")
            except Exception as e:
                print(f"[KEEPALIVE] error: {e}")
            time.sleep(300)  # 5 min, holgado bajo el limite de 15
    t = threading.Thread(target=ping, daemon=True)
    t.start()
    print("[MAIN] Keep-alive iniciado (cada 5 min).")


# ─── COMANDOS TELEGRAM ────────────────────────────────────────────────────────

PROJECTION_ALIAS = {
    "btcusd": "BTCUSD", "ethusd": "ETHUSD",
    "linkusd": "LINKUSD", "solusd": "SOLUSD",
    "btc": "BTCUSD", "eth": "ETHUSD",
    "link": "LINKUSD", "sol": "SOLUSD",
}

ASSET_ALIAS = {
    "/btc": "BTCUSD", "btc": "BTCUSD", "bitcoin": "BTCUSD",
    "/eth": "ETHUSD", "eth": "ETHUSD", "ethereum": "ETHUSD",
    "/link": "LINKUSD", "link": "LINKUSD", "chainlink": "LINKUSD",
    "/sol": "SOLUSD", "sol": "SOLUSD", "solana": "SOLUSD",
    "/jasmy": "JASMYUSD", "jasmy": "JASMYUSD",
}


def _get_asset_data(asset_code: str):
    """Retorna (s, state) para un activo, o (None, None) si falla."""
    from scanner import WATCHLIST, DYNAMIC_STATE, get_asset_status
    cfg = next((c for c in WATCHLIST if c["asset"] == asset_code), None)
    if not cfg:
        return None, None
    state = DYNAMIC_STATE.get(asset_code, {})
    s = get_asset_status(cfg)
    if not s:
        return None, None
    s["trend"]  = state.get("trend", "?")
    s["target"] = state.get("target", s["target"])
    s["stop"]   = state.get("stop",   s["stop"])
    return s, state


def _build_projection(asset_code: str, state: dict) -> dict:
    """Obtiene proyección para un activo principal."""
    from projections import project, PROJECTION_ASSETS
    from scanner import get_ohlcv
    from scanner import WATCHLIST
    if asset_code not in PROJECTION_ASSETS:
        return {}
    cfg = next((c for c in WATCHLIST if c["asset"] == asset_code), None)
    if not cfg:
        return {}
    candles_1d = get_ohlcv(cfg["symbol"], "1D", 90)
    return project(asset_code, candles_1d, state)


def handle_projection_cmd(asset_code: str) -> tuple:
    """Retorna (texto, botones) con proyección detallada."""
    from messages import cmd_asset_status, asset_buttons
    s, state = _get_asset_data(asset_code)
    if not s:
        return ("No pude obtener datos ahora. Intenta en un momento.", None)
    proj  = _build_projection(asset_code, state)
    name  = asset_code.replace("USD", "")
    text  = cmd_asset_status(name, s, proj=proj)
    btns  = asset_buttons(asset_code)
    return (text, btns)


def handle_telegram_command(text: str):
    """Procesa comando/mensaje. Retorna str o (str, buttons)."""
    from messages import cmd_help, cmd_asset_status, daily_summary, summary_buttons, asset_buttons
    from scanner import WATCHLIST, DYNAMIC_STATE, get_asset_status

    text = text.strip().lower()

    # /proyeccion btc | /proyeccion eth ...
    if text.startswith("/proyeccion") or text.startswith("proyeccion"):
        parts = text.split()
        key   = parts[1] if len(parts) > 1 else ""
        code  = PROJECTION_ALIAS.get(key, "")
        if not code:
            return "Uso: /proyeccion btc | eth | link | sol"
        return handle_projection_cmd(code)

    # Activo específico — incluye proyección para los 4 principales
    if text in ASSET_ALIAS:
        asset_code = ASSET_ALIAS[text]
        s, state = _get_asset_data(asset_code)
        if not s:
            return "No pude obtener datos ahora. Intenta en un momento."
        from projections import PROJECTION_ASSETS
        proj = _build_projection(asset_code, state) if asset_code in PROJECTION_ASSETS else {}
        name = asset_code.replace("USD", "")
        text_resp = cmd_asset_status(name, s, proj=proj)
        btns = asset_buttons(asset_code)
        return (text_resp, btns)

    # Estado general
    if text in ("/estado", "/resumen", "estado", "resumen", "/start"):
        import datetime
        assets_data = []
        for cfg in WATCHLIST:
            state = DYNAMIC_STATE.get(cfg["asset"], {})
            s = get_asset_status(cfg)
            if s:
                s["trend"]  = state.get("trend", "?")
                s["target"] = state.get("target", s["target"])
                s["stop"]   = state.get("stop",   s["stop"])
                assets_data.append(s)
        utc_offset = int(os.getenv("UTC_OFFSET_HOURS", -5))
        local = datetime.datetime.utcnow() + datetime.timedelta(hours=utc_offset)
        date_str = local.strftime("%d %b %Y")
        return (daily_summary(assets_data, date_str), summary_buttons())

    # Gems
    if text in ("/gems", "gems", "/gemas", "gemas"):
        from scanner import _prev_gems
        if not _prev_gems:
            return "Todavía no he hecho el primer gem scan. Se ejecuta diariamente. Espera al próximo ciclo."
        gems = sorted(_prev_gems.values(),
                      key=lambda x: ({"💎": 0, "🔥": 1, "⭐": 2, "👀": 3, "📊": 4}.get(x["emoji"], 5), -x["score"]))
        from messages import gem_report
        msgs = gem_report(gems[:20])
        return msgs[0]

    # Forzar scan
    if text in ("/scan", "scan", "/escanear"):
        def run_now():
            from scanner import WATCHLIST as WL, scan_asset
            for cfg in WL:
                scan_asset(cfg)
        threading.Thread(target=run_now, daemon=True).start()
        return "⚡ Scan iniciado. En unos segundos te aviso si hay algo."

    # Modo silencioso
    if text in ("/silenciar", "silenciar", "/mute", "mute"):
        from messages import silence_buttons
        return ("¿Cuánto tiempo quieres silenciar las alertas del scanner?", silence_buttons())

    if text in ("/reactivar", "reactivar", "/unmute", "unmute"):
        from alerts import clear_silent
        return clear_silent()

    # Ayuda
    if text in ("/ayuda", "/help", "ayuda", "help", "hola", "menu"):
        return cmd_help()

    return (
        "No entendí ese comando.\n\n"
        "Escribe /ayuda para ver todo lo que puedo hacer.\n\n"
        "Comandos: /estado /btc /eth /sol /link /gems /scan /proyeccion btc /silenciar"
    )


def handle_elliott_callback(cb_data: str):
    """Maneja clics de botones inline del bot Elliott."""
    if cb_data.startswith("proy:"):
        asset_code = cb_data.split(":", 1)[1]
        return handle_projection_cmd(asset_code)
    if cb_data in ("estado", "resumen"):
        return handle_telegram_command("/estado")
    if cb_data == "gems":
        return handle_telegram_command("/gems")
    if cb_data == "scan":
        return handle_telegram_command("/scan")
    if cb_data.startswith("silent:"):
        from alerts import set_silent, clear_silent
        hours_str = cb_data.split(":", 1)[1]
        if hours_str == "0":
            return clear_silent()
        try:
            return set_silent(float(hours_str))
        except ValueError:
            return "Valor inválido."
    return None


def _send_elliott_response(response) -> None:
    """Envía respuesta str o (str, buttons)."""
    if isinstance(response, tuple):
        text, buttons = response
        send_telegram(text, buttons=buttons)
    elif response:
        send_telegram(response)


@app.route("/telegram", methods=["POST"])
def telegram_webhook():
    """Recibe updates de Telegram y responde comandos y botones inline."""
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({"ok": True})

    expected = os.getenv("TELEGRAM_CHAT_ID", "")

    # Clic en botón inline
    cb = data.get("callback_query")
    if cb:
        from alerts import answer_callback
        chat_id = (cb.get("message") or {}).get("chat", {}).get("id")
        cb_data = cb.get("data", "")
        answer_callback(cb.get("id", ""))
        if not expected or str(chat_id) != str(expected):
            return jsonify({"ok": True})
        print(f"[TELEGRAM] Botón: {cb_data}")
        response = handle_elliott_callback(cb_data)
        _send_elliott_response(response)
        return jsonify({"ok": True})

    # Mensaje de texto
    msg = data.get("message") or data.get("edited_message")
    if not msg:
        return jsonify({"ok": True})

    if not expected or str(msg.get("chat", {}).get("id")) != str(expected):
        print("[TELEGRAM] Mensaje de chat desconocido, ignorado")
        return jsonify({"ok": True})

    text = msg.get("text", "")
    if not text:
        return jsonify({"ok": True})

    print(f"[TELEGRAM] Mensaje: {text}")
    _send_elliott_response(handle_telegram_command(text))
    return jsonify({"ok": True})


# ─── ENDPOINTS GROWTH (Reto 100->1000) ───────────────────────────────────────

# Botones validos del bot growth (whitelist de callback_data)
_GROWTH_CALLBACKS = {"entre", "paso", "vendi", "revisar", "update", "posiciones"}


def _growth_callback_ok(cb_data: str) -> bool:
    """Acepta los callbacks exactos y los patrones 'revisar:<PRODUCTO>' / 'vendi:<PRODUCTO>'."""
    if cb_data in _GROWTH_CALLBACKS:
        return True
    for prefix in ("revisar:", "vendi:", "entre:", "paso:"):
        if cb_data.startswith(prefix):
            product = cb_data.split(":", 1)[1]
            return product.replace("-", "").replace("_", "").isalnum() and len(product) <= 20
    return False


def _growth_chat_ok(chat_id) -> bool:
    """Solo procesar mensajes/clics que vengan del chat configurado."""
    expected = os.getenv("GROWTH_TELEGRAM_CHAT_ID", "")
    return bool(expected) and str(chat_id) == str(expected)


def _send_growth_response(response) -> None:
    """handle_growth_command puede retornar str o (str, buttons)."""
    from growth.alerts import send_growth_telegram
    if isinstance(response, tuple):
        text, buttons = response
        send_growth_telegram(text, buttons=buttons)
    elif response:
        send_growth_telegram(response)


@app.route("/growth-telegram", methods=["POST"])
def growth_telegram_webhook():
    """Recibe updates del bot de crecimiento: comandos de texto y clics de botones."""
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({"ok": True})

    try:
        from growth.commands import handle_growth_command
        from growth.alerts import answer_callback

        # Clic en un boton inline (Entré / Paso / Vendí / Revisar)
        cb = data.get("callback_query")
        if cb:
            chat_id = (cb.get("message") or {}).get("chat", {}).get("id")
            cb_data = cb.get("data", "")
            answer_callback(cb.get("id", ""))
            if not _growth_chat_ok(chat_id) or not _growth_callback_ok(cb_data):
                print(f"[GROWTH TG] Callback rechazado (chat {chat_id}, data {cb_data!r})")
                return jsonify({"ok": True})
            print(f"[GROWTH TG] Boton: {cb_data}")
            _send_growth_response(handle_growth_command(cb_data))
            return jsonify({"ok": True})

        # Mensaje de texto o foto normal
        msg = data.get("message") or data.get("edited_message")
        if not msg:
            return jsonify({"ok": True})
        if not _growth_chat_ok(msg.get("chat", {}).get("id")):
            print("[GROWTH TG] Mensaje de chat desconocido, ignorado")
            return jsonify({"ok": True})

        # Foto enviada por el usuario (captura de orden de Coinbase)
        photo = msg.get("photo")
        if photo:
            from growth.commands import handle_growth_photo
            caption = msg.get("caption", "")
            print(f"[GROWTH TG] Foto recibida. Caption: {caption!r}")
            _send_growth_response(handle_growth_photo(photo, caption))
            return jsonify({"ok": True})

        text = msg.get("text", "")
        if not text:
            return jsonify({"ok": True})

        print(f"[GROWTH TG] Mensaje: {text}")
        _send_growth_response(handle_growth_command(text))
    except Exception as e:
        print(f"[GROWTH TG] Error: {e}")
    return jsonify({"ok": True})


@app.route("/setup-growth-webhook", methods=["GET"])
def setup_growth_webhook():
    """Registra el webhook del bot de crecimiento."""
    import requests
    token = os.getenv("GROWTH_TELEGRAM_TOKEN")
    if not token:
        return jsonify({"error": "falta GROWTH_TELEGRAM_TOKEN"}), 400
    url = f"https://api.telegram.org/bot{token}/setWebhook"
    bot_url = os.getenv("BOT_URL", "https://eliottealartbot.onrender.com")
    r = requests.post(url, json={"url": f"{bot_url}/growth-telegram"}, timeout=10)
    return jsonify(r.json())


# ─── ENDPOINTS ────────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    info = {"status": "ok", "bot": "Elliott Alert Bot"}
    try:
        from growth import state as growth_state
        gs = growth_state.load()
        positions = gs.get("open_positions", {})
        info["growth"] = {
            "balance": gs.get("balance"),
            "last_scan_ts": gs.get("last_scan_ts"),
            "open_positions": list(positions.keys()) if positions else [],
        }
    except Exception:
        pass
    return jsonify(info)


@app.route("/webhook", methods=["POST"])
def webhook():
    secret = request.headers.get("X-Webhook-Secret") or request.args.get("secret")
    if secret != WEBHOOK_SECRET:
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "no JSON payload"}), 400

    try:
        payload = WebhookPayload(
            asset           = data["asset"],
            price           = float(data["price"]),
            open_4h         = float(data["open_4h"]),
            close_4h        = float(data["close_4h"]),
            high_4h         = float(data["high_4h"]),
            low_4h          = float(data["low_4h"]),
            rsi_4h          = float(data["rsi_4h"]),
            volume_avg5     = float(data["volume_avg5"]),
            volume_avg20    = float(data["volume_avg20"]),
            ema21_4h        = float(data["ema21_4h"]),
            in_elliott_zone = bool(data.get("in_elliott_zone", False)),
            wave_start      = float(data.get("wave_start", 0)),
            wave_end        = float(data.get("wave_end", 0)),
        )
    except (KeyError, ValueError) as e:
        return jsonify({"error": f"payload invalido: {e}"}), 422

    stop   = float(data.get("stop",   payload.low_4h * 0.99))
    target = float(data.get("target", payload.price  * 1.06))

    result = evaluate_layers(payload)
    score  = result["score"]
    layers_passed = [k for k, v in result["layers"].items() if v.passed]

    sent = False
    if score >= 4:
        text = format_alert_text(payload, result, stop, target)
        sent = send_telegram_photo(logo_url(payload.asset), text, buttons=alert_buttons(stop, target))

    log_alert(payload.asset, score, payload.price, stop, target, layers_passed, sent)

    return jsonify({
        "asset": payload.asset, "score": score, "alert_sent": sent,
        "layers": {k: v.passed for k, v in result["layers"].items()},
    })


@app.route("/setup-telegram-webhook", methods=["GET"])
def setup_webhook():
    """Registra el webhook de Telegram apuntando a este servidor."""
    import requests
    token = os.getenv("TELEGRAM_TOKEN")
    url   = f"https://api.telegram.org/bot{token}/setWebhook"
    bot_url = os.getenv("BOT_URL", "https://eliottealartbot.onrender.com")
    r = requests.post(url, json={"url": f"{bot_url}/telegram"}, timeout=10)
    return jsonify(r.json())


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"Elliott Alert Bot en puerto {port}")
    start_scanner_thread()
    start_growth_thread()
    start_keepalive_thread()
    app.run(host="0.0.0.0", port=port, debug=False)
