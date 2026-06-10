"""
Scanner principal del Reto 100->1000.

Loop 24/7:
- Cada SCAN_INTERVAL min: escanea el universo buscando setups (si no hay posicion abierta).
- Cada MONITOR_INTERVAL min: vigila la posicion abierta (target / stop).
- Resumen diario (🌙) a las 7AM hora local.
- Resumen semanal (📊) los lunes.

Robustez: cada iteracion va en try/except; un error no tumba el loop.
El estado vive en disco (growth/state.py), asi sobrevive reinicios.
"""

import os
import time
import datetime
from dataclasses import asdict

from growth import state, messages
from growth.alerts import send_growth_telegram, send_growth_photo
from growth.coinbase_data import get_price, list_usd_products
from growth.strategy import scan_universe, market_too_weak, risk_tier, CURATED

UTC_OFFSET_HOURS  = int(os.getenv("UTC_OFFSET_HOURS", "-5"))
DAILY_SUMMARY_HOUR = 7
SCAN_INTERVAL_MIN  = 30     # buscar nuevos setups
MONITOR_INTERVAL_SEC = 180  # vigilar posicion abierta (3 min)
GOAL_DAYS = 30


def _local_now() -> datetime.datetime:
    return datetime.datetime.utcnow() + datetime.timedelta(hours=UTC_OFFSET_HOURS)


def _days_left(s: dict) -> int:
    started = s.get("started_at")
    if not started:
        return GOAL_DAYS
    try:
        d0 = datetime.datetime.fromisoformat(started)
        elapsed = (datetime.datetime.utcnow() - d0).days
        return max(0, GOAL_DAYS - elapsed)
    except Exception:
        return GOAL_DAYS


# ─── BUSQUEDA DE SETUPS ───────────────────────────────────────────────────────
def look_for_setup(available: set[str]) -> None:
    s = state.load()

    if s.get("paused"):
        return
    if s.get("open_position"):
        return  # ya hay algo en juego

    # Senal pendiente: si tiene >4h, expirarla y avisar; si no, esperar
    if s.get("pending_signal"):
        age = state.pending_age_minutes()
        if age is not None and age > 240:
            name = s["pending_signal"].get("name", "?")
            state.set_pending(None)
            send_growth_telegram(messages.signal_expired(name, age / 60))
        else:
            return

    if state.in_cooldown():
        return

    # limite de senales por dia
    today = datetime.date.today().isoformat()
    if s.get("last_signal_day") == today and s.get("signals_today", 0) >= 2:
        return

    # regimen de mercado
    if market_too_weak():
        print("[GROWTH] Mercado debil (BTC -15% semana). Pausando busqueda.")
        return

    balance = s["balance"]
    signals = scan_universe(balance, available=available)
    if not signals:
        print("[GROWTH] Sin setups validos este ciclo.")
        return

    best = signals[0]
    sig_dict = asdict(best)
    size_usd = round(balance * best.size_pct, 2)

    state.set_pending(sig_dict)
    msg = messages.buy_signal(sig_dict, balance, size_usd)
    buttons = messages.signal_buttons(sig_dict)
    logo = messages.logo_url(best.product)
    send_growth_photo(logo, msg, buttons=buttons)
    print(f"[GROWTH] Señal enviada: {best.name} score={best.score} rr={best.rr}")


# ─── MONITOR DE POSICION ──────────────────────────────────────────────────────
def monitor_position() -> None:
    s = state.load()
    pos = s.get("open_position")
    if not pos:
        return

    price = get_price(pos["product"])
    if price is None:
        return

    old_bal = s["balance"]

    price_txt = messages._raw_num(price, pos["product"])
    sell_btn = [
        [("💰 Vendí", "vendi")],
        [(f"📋 Precio {price_txt}", {"copy": price_txt})],
    ]
    logo = messages.logo_url(pos["product"])

    # Target alcanzado
    if price >= pos["target"]:
        res = state.close_position(price, "target")
        msg = messages.sell_target(res["name"], price, res["pnl_pct"], old_bal, res["new_balance"])
        send_growth_photo(logo, msg, buttons=sell_btn)
        print(f"[GROWTH] TARGET {pos['name']} +{res['pnl_pct']}%")
        return

    # Stop tocado
    if price <= pos["stop"]:
        res = state.close_position(price, "stop")
        msg = messages.sell_stop(res["name"], price, res["pnl_pct"], old_bal, res["new_balance"])
        send_growth_photo(logo, msg, buttons=sell_btn)
        print(f"[GROWTH] STOP {pos['name']} {res['pnl_pct']}%")
        return

    # ── Trailing stop: proteger ganancias sin cortar el recorrido ──
    entry = pos["entry"]
    pnl = (price - entry) / entry * 100 if entry else 0
    target_pct = (pos["target"] - entry) / entry * 100 if entry else 0
    level = pos.get("trail_level", 0)

    from growth.coinbase_data import snap_price
    new_stop = None
    new_level = level
    if level == 0 and pnl >= 10:
        new_stop, new_level = snap_price(entry, pos["product"]), 1            # breakeven
    elif level == 1 and target_pct > 0 and pnl >= target_pct * 0.6:
        new_stop, new_level = snap_price(entry * 1.05, pos["product"]), 2     # asegurar +5%

    if new_stop is not None and new_stop > pos["stop"]:
        pos["stop"] = new_stop
        pos["trail_level"] = new_level
        s["open_position"] = pos
        state.save(s, important=True)
        msg = messages.trailing_update(pos["name"], new_level, new_stop, pnl)
        stop_txt = messages._raw_num(new_stop, pos["product"])
        copy_btn = [[(f"📋 Stop {stop_txt}", {"copy": stop_txt})]]
        send_growth_telegram(msg, buttons=copy_btn)
        print(f"[GROWTH] TRAILING {pos['name']} nivel {new_level} stop {new_stop}")
        return

    # ── Aviso de progreso (max 1 cada 2h, al cruzar +5% o -3% desde el ultimo) ──
    last_pnl = pos.get("last_progress_pnl", 0.0)
    last_ts  = pos.get("last_progress_ts")
    delta = pnl - last_pnl
    cooldown_ok = True
    if last_ts:
        try:
            elapsed = (datetime.datetime.utcnow() - datetime.datetime.fromisoformat(last_ts)).total_seconds()
            cooldown_ok = elapsed >= 7200
        except Exception:
            pass
    if cooldown_ok and (delta >= 5 or delta <= -3):
        pos["last_progress_pnl"] = pnl
        pos["last_progress_ts"] = datetime.datetime.utcnow().isoformat()
        s["open_position"] = pos
        state.save(s)
        send_growth_telegram(messages.position_progress(pos["name"], pnl, price, pos["target"]))


# ─── RESUMENES ────────────────────────────────────────────────────────────────
def maybe_send_summaries() -> None:
    s = state.load()
    local = _local_now()
    today = local.date().isoformat()

    # Diario a las 7AM
    if local.hour >= DAILY_SUMMARY_HOUR and s.get("last_daily_summary") != today:
        has_signal = bool(s.get("pending_signal") or s.get("open_position"))
        msg = messages.daily_summary(s["balance"], s["start_balance"], CURATED, has_signal)
        send_growth_telegram(msg)
        s["last_daily_summary"] = today
        state.save(s)

    # Semanal los lunes
    if local.weekday() == 0 and s.get("last_weekly_summary") != today:
        tier = risk_tier(s["balance"])
        msg = messages.weekly_summary(
            s["balance"], s["start_balance"], s.get("trade_log", []),
            _days_left(s), tier.name,
        )
        send_growth_telegram(msg)
        s["last_weekly_summary"] = today
        state.save(s)


# ─── LOOP PRINCIPAL ───────────────────────────────────────────────────────────
def run_growth_scanner() -> None:
    print("[GROWTH] Scanner del Reto 100->1000 iniciado.")

    # Cargar estado (dispara la recuperacion desde GitHub si hubo reinicio)
    s = state.load()
    if state.RECOVERY["recovered"]:
        send_growth_telegram(messages.state_recovered(s["balance"], len(s.get("trade_log", []))))
    elif state.RECOVERY["failed"]:
        send_growth_telegram(messages.state_lost())
    else:
        send_growth_telegram(messages.welcome())

    # productos disponibles en Coinbase (cache, refrescado cada hora)
    available = set(list_usd_products()) or set(CURATED)
    last_products_refresh = time.time()
    last_scan = 0.0

    while True:
        try:
            state.heartbeat()
            now = time.time()

            # refrescar lista de productos cada hora
            if now - last_products_refresh > 3600:
                prods = list_usd_products()
                if prods:
                    available = set(prods)
                last_products_refresh = now

            # resumenes
            maybe_send_summaries()

            # monitor de posicion (siempre)
            monitor_position()

            # busqueda de setups cada SCAN_INTERVAL_MIN
            if now - last_scan > SCAN_INTERVAL_MIN * 60:
                look_for_setup(available)
                last_scan = now

        except Exception as e:
            print(f"[GROWTH] Error en loop: {e}")

        time.sleep(MONITOR_INTERVAL_SEC)


if __name__ == "__main__":
    run_growth_scanner()
