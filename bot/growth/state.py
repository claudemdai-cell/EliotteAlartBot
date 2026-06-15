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
import time
import datetime
import threading

from growth import gh_store

_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "logs")
_PATH = os.path.join(_DIR, "growth_state.json")
_LOCK = threading.Lock()

# Rate limit del backup a GitHub: max 1 push cada 30s (salvo eventos importantes)
_BACKUP_MIN_INTERVAL = 30
_last_backup = {"ts": 0.0}

# Flag: el estado se recupero de GitHub tras un reinicio (para avisar por Telegram)
RECOVERY = {"recovered": False, "failed": False, "checked": False}

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
    "awaiting_entry_confirm": False,
}


def _now_iso() -> str:
    return datetime.datetime.utcnow().isoformat()


def load() -> dict:
    """
    Carga el estado desde disco. Si no existe (reinicio de Render con disco
    efimero), intenta recuperarlo del backup en GitHub.
    """
    with _LOCK:
        if not os.path.exists(_PATH):
            # Posible reinicio: intentar recuperar de GitHub (solo la primera vez)
            if not RECOVERY["checked"]:
                RECOVERY["checked"] = True
                if gh_store.enabled():
                    remote = gh_store.download()
                    if remote:
                        merged = dict(_DEFAULT)
                        merged.update(remote)
                        _write_local(merged)
                        RECOVERY["recovered"] = True
                        print("[STATE] Estado recuperado desde GitHub.")
                        return merged
                    RECOVERY["failed"] = True
                    print("[STATE] Sin backup en GitHub; arrancando con defaults.")
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


def _write_local(state: dict) -> None:
    """Escribe el estado a disco local (sin lock; el caller debe tenerlo)."""
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


def save(state: dict, important: bool = False) -> None:
    """
    Guarda el estado a disco y lo respalda en GitHub.
    important=True fuerza el backup inmediato (abrir/cerrar posicion, balance);
    si no, respeta el rate limit de 30s para no saturar la API.
    """
    with _LOCK:
        try:
            _write_local(state)
        except Exception as e:
            print(f"[STATE] Error guardando estado: {e}")

    if not gh_store.enabled():
        return
    now = time.time()
    if important or (now - _last_backup["ts"]) >= _BACKUP_MIN_INTERVAL:
        if gh_store.upload(state):
            _last_backup["ts"] = now


# ─── OPERACIONES DE ALTO NIVEL ────────────────────────────────────────────────

def set_balance(amount: float) -> dict:
    s = load()
    s["balance"] = round(float(amount), 2)
    if not s["started_at"]:
        s["started_at"] = _now_iso()
        s["start_balance"] = round(float(amount), 2)
    save(s, important=True)
    return s


def set_pending(signal_dict: dict | None) -> dict:
    s = load()
    if signal_dict is not None:
        signal_dict = dict(signal_dict)
        signal_dict.setdefault("created_at", _now_iso())
    s["pending_signal"] = signal_dict
    save(s, important=True)
    return s


def pending_age_minutes() -> float | None:
    """Minutos desde que se creo la senal pendiente. None si no hay senal."""
    s = load()
    sig = s.get("pending_signal")
    if not sig or not sig.get("created_at"):
        return None
    try:
        created = datetime.datetime.fromisoformat(sig["created_at"])
        return (datetime.datetime.utcnow() - created).total_seconds() / 60
    except Exception:
        return None


# Fee de Coinbase Advanced Trade: 0.60% taker (cuentas < $10K volumen/mes)
# Se descuenta en la entrada y en la salida para calcular P&L real.
COINBASE_FEE = 0.006


def open_position_from_pending(entry_override: float | None = None) -> dict | None:
    """
    Convierte la senal pendiente en posicion abierta (cuando el user dice 'hecho').
    entry_override: precio real al que entro el usuario (si lo da); el stop/target
    se mantienen porque son niveles de estructura del mercado.
    """
    s = load()
    sig = s.get("pending_signal")
    if not sig:
        return None
    size_gross = round(s["balance"] * sig.get("size_pct", 1.0), 2)
    fee_entry  = round(size_gross * COINBASE_FEE, 2)
    # size_usd = capital real expuesto al mercado (tras pagar fee de entrada)
    size_usd   = round(size_gross - fee_entry, 2)
    entry = float(entry_override) if entry_override else sig["price"]
    s["open_position"] = {
        "product":   sig["product"],
        "name":      sig["name"],
        "entry":     entry,
        "stop":      sig["stop"],
        "target":    sig["target"],
        "size_gross": size_gross,  # lo que sacaste del balance
        "size_usd":  size_usd,     # expuesto al mercado (tras fee de entrada)
        "opened_at": _now_iso(),
        "kind":     sig.get("kind", "breakout"),
        "score":    sig.get("score", 0),
        "trail_level": 0,         # 0=stop original, 1=breakeven, 2=asegurando ganancia
        "last_progress_pnl": 0.0, # ultimo % notificado en avisos de progreso
        "last_progress_ts": None,
    }
    s["pending_signal"] = None
    # registrar conteo de senales del dia
    today = datetime.date.today().isoformat()
    if s.get("last_signal_day") != today:
        s["last_signal_day"] = today
        s["signals_today"] = 0
    s["signals_today"] = s.get("signals_today", 0) + 1
    save(s, important=True)
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
    entry    = pos["entry"]
    pnl_pct  = (exit_price - entry) / entry * 100 if entry else 0
    size_usd = pos["size_usd"]          # capital expuesto (ya descontó fee entrada)
    size_gross = pos.get("size_gross", size_usd)  # backwards compat

    # Calcular P&L real: ganancias brutas menos fee de salida (0.60%)
    exit_gross = size_usd * (1 + pnl_pct / 100)
    fee_exit   = round(exit_gross * COINBASE_FEE, 4)
    exit_net   = exit_gross - fee_exit
    pnl_usd    = round(exit_net - size_gross, 2)  # vs lo que salió del balance
    new_balance = round(s["balance"] + pnl_usd, 2)

    # pnl_pct real = pnl_usd / size_gross * 100 (incluye fees de entrada y salida)
    real_pnl_pct = pnl_usd / size_gross * 100 if size_gross else 0
    s["trade_log"].append({
        "product":   pos["product"],
        "name":      pos["name"],
        "entry":     entry,
        "exit":      exit_price,
        "pnl_pct":   round(real_pnl_pct, 2),
        "pnl_usd":   round(pnl_usd, 2),
        "result":    result,
        "kind":      pos.get("kind", "?"),
        "score":     pos.get("score", 0),
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

    save(s, important=True)
    return {
        "pnl_pct": round(real_pnl_pct, 2),
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
