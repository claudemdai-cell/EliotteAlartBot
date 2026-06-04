"""
Registro de alertas generadas.
Guarda en logs/alerts.jsonl (una línea JSON por alerta).
"""

import json
import os
from datetime import datetime, timezone


LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "logs", "alerts.jsonl")


def log_alert(asset: str, score: int, price: float, stop: float,
              target: float, layers_passed: list[str], sent: bool) -> None:
    entry = {
        "ts":      datetime.now(timezone.utc).isoformat(),
        "asset":   asset,
        "score":   score,
        "price":   price,
        "stop":    stop,
        "target":  target,
        "layers":  layers_passed,
        "sent":    sent,
    }
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"[LOG] {entry['ts']} | {asset} {score}/5 | sent={sent}")
