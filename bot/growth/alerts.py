"""
Cliente Telegram del bot de crecimiento — token y chat propios.
Variables de entorno:
  GROWTH_TELEGRAM_TOKEN   — token del bot nuevo (BotFather)
  GROWTH_TELEGRAM_CHAT_ID — chat destino
"""

import os
import requests

TOKEN   = os.getenv("GROWTH_TELEGRAM_TOKEN")
CHAT_ID = os.getenv("GROWTH_TELEGRAM_CHAT_ID")


def send_growth_telegram(text: str) -> bool:
    """Envia mensaje Markdown al chat del Reto. True si exitoso."""
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
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code != 200:
            print(f"[GROWTH ALERT ERROR] {r.status_code}: {r.text[:200]}")
            return False
        return True
    except requests.RequestException as e:
        print(f"[GROWTH ALERT ERROR] {e}")
        return False
