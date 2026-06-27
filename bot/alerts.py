"""
Telegram notifications via Bot API.
Soporta texto, foto (logo de la crypto) y botones inline (callback + copy_text).
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID        = os.getenv("TELEGRAM_CHAT_ID")


def logo_url(asset: str) -> str:
    """Logo de la crypto (CoinCap). 'BTCUSD' -> btc."""
    sym = asset.replace("USDT", "").replace("USD", "").replace("_", "").lower()
    return f"https://assets.coincap.io/assets/icons/{sym}@2x.png"


def _build_keyboard(buttons: list) -> dict:
    """
    Filas de (texto, data) -> inline_keyboard.
    data: str = callback_data | {"copy": "x"} = copia al portapapeles.
    """
    rows = []
    for row in buttons:
        btn_row = []
        for (t, d) in row:
            if isinstance(d, dict) and "copy" in d:
                btn_row.append({"text": t, "copy_text": {"text": str(d["copy"])}})
            else:
                btn_row.append({"text": t, "callback_data": d})
        rows.append(btn_row)
    return {"inline_keyboard": rows}


def send_telegram(text: str, buttons: list | None = None) -> bool:
    """Envía mensaje Markdown a Telegram. Retorna True si fue exitoso."""
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("[ALERT] TELEGRAM_TOKEN o CHAT_ID no configurados en .env")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    if buttons:
        payload["reply_markup"] = _build_keyboard(buttons)
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        return True
    except requests.RequestException as e:
        print(f"[ALERT ERROR] {e}")
        return False


def send_telegram_photo(photo_url: str, caption: str, buttons: list | None = None) -> bool:
    """Foto (logo) + caption + botones. Si falla, cae a mensaje de texto."""
    if not TELEGRAM_TOKEN or not CHAT_ID:
        return False
    if len(caption) > 1000:  # limite de caption en sendPhoto
        return send_telegram(caption, buttons=buttons)
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    payload = {
        "chat_id": CHAT_ID,
        "photo": photo_url,
        "caption": caption,
        "parse_mode": "Markdown",
    }
    if buttons:
        payload["reply_markup"] = _build_keyboard(buttons)
    try:
        r = requests.post(url, json=payload, timeout=12)
        if r.status_code == 200:
            return True
        print(f"[ALERT PHOTO] {r.status_code}: {r.text[:150]} — fallback a texto")
    except requests.RequestException as e:
        print(f"[ALERT PHOTO] error: {e} — fallback a texto")
    return send_telegram(caption, buttons=buttons)


def answer_callback(callback_id: str) -> None:
    """Confirma recepción de un clic de botón inline."""
    if not TELEGRAM_TOKEN or not callback_id:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery",
            json={"callback_query_id": callback_id},
            timeout=5,
        )
    except Exception:
        pass


def test_connection() -> bool:
    """Envía mensaje de prueba para verificar que el bot funciona."""
    return send_telegram("✅ *Elliott Alert Bot* conectado y funcionando.")
