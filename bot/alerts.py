"""
Telegram notifications via Bot API.
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID        = os.getenv("TELEGRAM_CHAT_ID")


def send_telegram(text: str) -> bool:
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
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        return True
    except requests.RequestException as e:
        print(f"[ALERT ERROR] {e}")
        return False


def test_connection() -> bool:
    """Envía mensaje de prueba para verificar que el bot funciona."""
    return send_telegram("✅ *Elliott Alert Bot* conectado y funcionando.")
