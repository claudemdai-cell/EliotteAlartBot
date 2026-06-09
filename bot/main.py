"""
Elliott Alert Bot — Servidor Flask.

Recibe webhooks de TradingView, evalúa las 5 capas
y manda alerta a Telegram si score >= 4.

Endpoint: POST /webhook
"""

import os
import threading
from flask import Flask, request, jsonify
from layers import WebhookPayload, evaluate_layers, format_alert_text
from alerts import send_telegram
from log import log_alert

app = Flask(__name__)


def start_scanner_thread():
    """Lanza el scanner autónomo en un thread background."""
    try:
        from scanner import run_scanner
        t = threading.Thread(target=run_scanner, daemon=True)
        t.start()
        print("[MAIN] Scanner background thread iniciado.")
    except Exception as e:
        print(f"[MAIN] Error iniciando scanner: {e}")


def start_keepalive_thread():
    """Hace ping a si mismo cada 10 min para evitar que Render duerma el servicio."""
    import time, requests as req
    def ping():
        url = "https://eliottealartbot.onrender.com/health"
        while True:
            time.sleep(600)  # 10 minutos
            try:
                req.get(url, timeout=10)
                print("[KEEPALIVE] ping ok")
            except Exception as e:
                print(f"[KEEPALIVE] error: {e}")
    t = threading.Thread(target=ping, daemon=True)
    t.start()
    print("[MAIN] Keep-alive thread iniciado (ping cada 10 min).")

# Clave secreta para validar que el webhook viene de TradingView
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "elliott2026")


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "bot": "Elliott Alert Bot"})


@app.route("/webhook", methods=["POST"])
def webhook():
    # Validación básica de seguridad
    secret = request.headers.get("X-Webhook-Secret") or request.args.get("secret")
    if secret != WEBHOOK_SECRET:
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "no JSON payload"}), 400

    try:
        payload = WebhookPayload(
            asset            = data["asset"],
            price            = float(data["price"]),
            open_4h          = float(data["open_4h"]),
            close_4h         = float(data["close_4h"]),
            high_4h          = float(data["high_4h"]),
            low_4h           = float(data["low_4h"]),
            rsi_4h           = float(data["rsi_4h"]),
            volume_avg5      = float(data["volume_avg5"]),
            volume_avg20     = float(data["volume_avg20"]),
            ema21_4h         = float(data["ema21_4h"]),
            in_elliott_zone  = bool(data.get("in_elliott_zone", False)),
            wave_start       = float(data.get("wave_start", 0)),
            wave_end         = float(data.get("wave_end", 0)),
        )
    except (KeyError, ValueError) as e:
        return jsonify({"error": f"payload inválido: {e}"}), 422

    stop   = float(data.get("stop",   payload.low_4h * 0.99))
    target = float(data.get("target", payload.price  * 1.06))

    result = evaluate_layers(payload)
    score  = result["score"]

    layers_passed = [k for k, v in result["layers"].items() if v.passed]

    sent = False
    if score >= 4:
        text = format_alert_text(payload, result, stop, target)
        sent = send_telegram(text)

    log_alert(payload.asset, score, payload.price, stop, target, layers_passed, sent)

    return jsonify({
        "asset":       payload.asset,
        "score":       score,
        "alert_sent":  sent,
        "layers":      {k: v.passed for k, v in result["layers"].items()},
        "bonus":       result["bonus"].passed,
    })


@app.route("/test-telegram", methods=["GET"])
def test_telegram():
    secret = request.args.get("secret")
    if secret != WEBHOOK_SECRET:
        return jsonify({"error": "unauthorized"}), 401
    from alerts import test_connection
    ok = test_connection()
    return jsonify({"telegram_ok": ok})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"Elliott Alert Bot corriendo en puerto {port}")
    start_scanner_thread()
    start_keepalive_thread()
    app.run(host="0.0.0.0", port=port, debug=False)
