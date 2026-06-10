"""
Estado persistente del bot de crecimiento.
Se guarda en logs/growth_state.json para sobrevivir reinicios de Render.

Estructura:
{
  "balance": 100.0,
  "start_balance": 100.0,
  "started_at": "2026-06-09T...",
  "open_position": null | { product, name, entry, stop, target, size_usd, opened_at },
  "pending_signal": null | { ...signal dict, created_at },
  "trade_log": [ { product, entry, exit, pnl_pct, pnl_usd, result, closed_at } ],
  "loss_streak": 0,
  "cooldown_until": null | iso,
  "paused": false,
  "last_signal_day": null | "YYYY-MM-DD",
  "signals_today": 0,
  "last_scan_ts": null | iso,
  "last_daily_summary": null | "YYYY-MM-DD",
  "last_weekly_summary": null | "YYYY-MM-DD"
}
"""

import os
import json
import datetime
import threading

_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "logs")
_PATH = os.path.join(_DIR, "growth_state.json")
_LOCK = threading.Lock()

_DEFAULT = {
    "balance": 100.0,
    "start_balance": 100.0,
    "started_at": None,
    "open_position": None,
    "pending_signal": None,
    "trade_log": [],
    "loss_streak": 0,
    "cooldown_until": None,
    "paused": False,
    "last_signal_day": None,
    "signals_today": 0,
    "last_scan_ts": None,
    "last_daily_summary": None,
    "last_weekly_summary": None,
}


def _now_iso() -> str:
    return datetime.datetime.utcnow().isoformat()


def load() -> dict:
    """Carga el estado desde disco (o defaults)."""
    with _LOCK:
        if not os.path.exists(_PATH):
            return dict(_DEFAULT)
        try:
            with open(_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            merged = dict(_DEFAULT)
            merged.update(data)
            return merged
        except Exception as e:
            print(f"[STATE] Error leyendo estado: {e}")
            return dict(_DEFAULT)


def save(state: dict) -> None:
    """Guarda el estado a disco de forma atomica."""
    with _LOCK:
        try:
            os.makedirs(_DIR, exist_ok=True)
            tmp = _PATH + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            try:
                os.replace(tmp, _PATH)
            except OSError:
                # OneDrive/Windows puede bloquear el rename: escribir directo
                with open(_PATH, "w", encoding="utf-8") as f:
                    json.dump(state, f, indent=2, ensure_ascii=False)
                try:
                    os.remove(tmp)
                except OSError:
                    pass
        except Exception as e:
            print(f"[STATE] Error guardando estado: {e}")


# ─── OPERACIONES DE ALTO NIVEL ────────────────────────────────────────────────

def set_balance(amount: float) -> dict:
    s = load()
    s["balance"] = round(float(amount), 2)
    if not s["started_at"]:
        s["started_at"] = _now_iso()
        s["start_balance"] = round(float(amount), 2)
    save(s)
    return s


def set_pending(signal_dict: dict | None) -> dict:
    s = load()
    if signal_dict is not None:
        signal_dict = dict(signal_dict)
        signal_dict["created_at"] = _now_iso()
    s["pending_signal"] = signal_dict
    save(s)
    return s


def open_position_from_pending() -> dict | None:
    """Convierte la senal pendiente en posicion abierta (cuando el user dice 'hecho')."""
    s = load()
    sig = s.get("pending_signal")
    if not sig:
        return None
    size_usd = round(s["balance"] * sig.get("size_pct", 1.0), 2)
    s["open_position"] = {
        "product":  sig["product"],
        "name":     sig["name"],
        "entry":    sig["price"],
        "stop":     sig["stop"],
        "target":   sig["target"],
        "size_usd": size_usd,
        "opened_at": _now_iso(),
    }
    s["pending_signal"] = None
    # registrar conteo de senales del dia
    today = datetime.date.today().isoformat()
    if s.get("last_signal_day") != today:
        s["last_signal_day"] = today
        s["signals_today"] = 0
    s["signals_today"] = s.get("signals_today", 0) + 1
    save(s)
    return s["open_position"]


def close_position(exit_price: float, result: str) -> dict:
    """
    Cierra la posicion abierta, actualiza balance y trade_log.
    result: 'target' | 'stop' | 'manual'
    Retorna { pnl_pct, pnl_usd, new_balance, name }.
    """
    s = load()
    pos = s.get("open_position")
    if not pos:
        return {}
    entry = pos["entry"]
    pnl_pct = (exit_price - entry) / entry * 100 if entry else 0
    size_usd = pos["size_usd"]
    pnl_usd = size_usd * pnl_pct / 100
    new_balance = round(s["balance"] + pnl_usd, 2)

    s["trade_log"].append({
        "product":   pos["product"],
        "name":      pos["name"],
        "entry":     entry,
        "exit":      exit_price,
        "pnl_pct":   round(pnl_pct, 2),
        "pnl_usd":   round(pnl_usd, 2),
        "result":    result,
        "closed_at": _now_iso(),
    })
    s["balance"] = new_balance
    s["open_position"] = None

    # racha de perdidas / enfriamiento
    if pnl_pct < 0:
        s["loss_streak"] = s.get("loss_streak", 0) + 1
        if s["loss_streak"] >= 2:
            until = datetime.datetime.utcnow() + datetime.timedelta(hours=48)
            s["cooldown_until"] = until.isoformat()
    else:
        s["loss_streak"] = 0

    save(s)
    return {
        "pnl_pct": round(pnl_pct, 2),
        "pnl_usd": round(pnl_usd, 2),
        "new_balance": new_balance,
        "name": pos["name"],
        "result": result,
    }


def in_cooldown() -> bool:
    s = load()
    cu = s.get("cooldown_until")
    if not cu:
        return False
    try:
        return datetime.datetime.utcnow() < datetime.datetime.fromisoformat(cu)
    except Exception:
        return False


def heartbeat() -> None:
    s = load()
    s["last_scan_ts"] = _now_iso()
    save(s)
