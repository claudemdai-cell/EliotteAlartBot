"""
Cliente Telegram del bot de crecimiento — token y chat propios.
Variables de entorno:
  GROWTH_TELEGRAM_TOKEN   — token del bot nuevo (BotFather)
  GROWTH_TELEGRAM_CHAT_ID — chat destino
"""

import os
import time
import requests

TOKEN   = os.getenv("GROWTH_TELEGRAM_TOKEN")
CHAT_ID = os.getenv("GROWTH_TELEGRAM_CHAT_ID")


def send_growth_telegram(text: str, buttons: list | None = None) -> bool:
    """
    Envia mensaje Markdown al chat del Reto. True si exitoso.
    buttons: lista de filas de botones [[(texto, data), ...], ...] para teclado inline.
    Reintenta hasta 3 veces para no perder una alerta por un fallo de red.
    """
    if not TOKEN or not CHAT_ID:
        print("[GROWTH] Falta GROWTH_TELEGRAM_TOKEN o GROWTH_TELEGRAM_CHAT_ID")
        return False
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    if buttons:
        payload["reply_markup"] = {
            "inline_keyboard": [
                [{"text": t, "callback_data": d} for (t, d) in row]
                for row in buttons
            ]
        }
    for attempt in range(3):
        try:
            r = requests.post(url, json=payload, timeout=10)
            if r.status_code == 200:
                return True
            print(f"[GROWTH ALERT ERROR] {r.status_code}: {r.text[:200]}")
        except requests.RequestException as e:
            print(f"[GROWTH ALERT ERROR] intento {attempt+1}: {e}")
        time.sleep(1.5 * (attempt + 1))
    return False


def send_growth_photo(photo_url: str, caption: str, buttons: list | None = None) -> bool:
    """
    Envia una foto (logo de la crypto) con caption y botones.
    Si falla (logo no existe, etc.), cae de vuelta a un mensaje de texto.
    """
    if not TOKEN or not CHAT_ID:
        print("[GROWTH] Falta token/chat para enviar foto")
        return False
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    payload = {
        "chat_id": CHAT_ID,
        "photo": photo_url,
        "caption": caption,
        "parse_mode": "Markdown",
    }
    if buttons:
        payload["reply_markup"] = {
            "inline_keyboard": [
                [{"text": t, "callback_data": d} for (t, d) in row]
                for row in buttons
            ]
        }
    try:
        r = requests.post(url, json=payload, timeout=12)
        if r.status_code == 200:
            return True
        print(f"[GROWTH PHOTO] {r.status_code}: {r.text[:150]} — fallback a texto")
    except requests.RequestException as e:
        print(f"[GROWTH PHOTO] error: {e} — fallback a texto")
    # Fallback: mensaje de texto normal
    return send_growth_telegram(caption, buttons=buttons)


def answer_callback(callback_id: str, text: str = "") -> None:
    """Responde el 'loading' de un boton inline para que no quede girando."""
    if not TOKEN:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/answerCallbackQuery",
            json={"callback_query_id": callback_id, "text": text},
            timeout=8,
        )
    except requests.RequestException:
        pass
