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
    if s.get("open_positions"):
        return  # ya hay posiciones abiertas

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


# ─── MONITOR DE POSICIONES ────────────────────────────────────────────────────
def _monitor_one(pos: dict) -> None:
    """Monitorea una posición individual: target, stop, trailing, progreso."""
    from growth.coinbase_data import snap_price
    product = pos["product"]
    price   = get_price(product)
    if price is None:
        return

    s       = state.load()
    old_bal = s["balance"]
    logo    = messages.logo_url(product)
    price_txt = messages._raw_num(price, product)
    sell_btn  = [
        [("💰 Vendí " + pos["name"], f"vendi:{product}")],
        [(f"📋 Precio {price_txt}", {"copy": price_txt})],
    ]

    if price >= pos["target"]:
        if not pos.get("partial_tp_done"):
            # Primera vez en target: cerrar 50% y dejar correr el resto
            res = state.partial_close_position(product, price, fraction=0.5)
            # Mover stop a breakeven para el 50% restante
            breakeven = round(pos["entry"] * (1 + 2 * state.COINBASE_FEE), 8)
            s2 = state.load()
            if product in s2.get("open_positions", {}):
                from growth.coinbase_data import snap_price as _snap
                s2["open_positions"][product]["stop"] = _snap(breakeven, product)
                s2["open_positions"][product]["target"] = _snap(
                    pos["target"] * 1.05, product
                )   # target secundario: +5% sobre el primero
                state.save(s2, important=True)
            msg = messages.partial_tp(pos["name"], price, res["pnl_usd"], res["new_balance"], breakeven)
            send_growth_photo(logo, msg, buttons=sell_btn)
            print(f"[GROWTH] PARTIAL TP {pos['name']} +{res['pnl_pct']}% (50%)")
        else:
            # 50% restante llegó a target secundario: cerrar todo
            res = state.close_position(product, price, "target")
            msg = messages.sell_target(res["name"], price, res["pnl_pct"], old_bal, res["new_balance"], close_result=res)
            send_growth_photo(logo, msg, buttons=sell_btn)
            print(f"[GROWTH] TARGET FINAL {pos['name']} +{res['pnl_pct']}%")
        return

    if price <= pos["stop"]:
        res = state.close_position(product, price, "stop")
        msg = messages.sell_stop(res["name"], price, res["pnl_pct"], old_bal, res["new_balance"], close_result=res)
        send_growth_photo(logo, msg, buttons=sell_btn)
        print(f"[GROWTH] STOP {pos['name']} {res['pnl_pct']}%")
        return

    entry      = pos["entry"]
    pnl        = (price - entry) / entry * 100 if entry else 0
    target_pct = (pos["target"] - entry) / entry * 100 if entry else 0
    level      = pos.get("trail_level", 0)
    new_stop   = None
    new_level  = level

    if level == 0 and pnl >= 10:
        new_stop, new_level = snap_price(entry, product), 1
    elif level == 1 and target_pct > 0 and pnl >= target_pct * 0.6:
        new_stop, new_level = snap_price(entry * 1.05, product), 2

    if new_stop is not None and new_stop > pos["stop"]:
        s2 = state.load()
        if product in s2.get("open_positions", {}):
            s2["open_positions"][product]["stop"]        = new_stop
            s2["open_positions"][product]["trail_level"] = new_level
            state.save(s2, important=True)
        msg      = messages.trailing_update(pos["name"], new_level, new_stop, pnl)
        stop_txt = messages._raw_num(new_stop, product)
        send_growth_telegram(msg, buttons=[[(f"📋 Stop {stop_txt}", {"copy": stop_txt})]])
        print(f"[GROWTH] TRAILING {pos['name']} nivel {new_level} stop {new_stop}")
        return

    last_pnl   = pos.get("last_progress_pnl", 0.0)
    last_ts    = pos.get("last_progress_ts")
    delta      = pnl - last_pnl
    cooldown_ok = True
    if last_ts:
        try:
            elapsed = (datetime.datetime.utcnow() - datetime.datetime.fromisoformat(last_ts)).total_seconds()
            cooldown_ok = elapsed >= 7200
        except Exception:
            pass
    if cooldown_ok and (delta >= 5 or delta <= -3):
        s2 = state.load()
        if product in s2.get("open_positions", {}):
            s2["open_positions"][product]["last_progress_pnl"] = pnl
            s2["open_positions"][product]["last_progress_ts"]  = datetime.datetime.utcnow().isoformat()
            state.save(s2)
        send_growth_telegram(messages.position_progress(pos["name"], pnl, price, pos["target"]))


def monitor_position() -> None:
    """Monitorea todas las posiciones abiertas."""
    s = state.load()
    positions = s.get("open_positions", {})
    if not positions:
        return
    for product, pos in list(positions.items()):
        try:
            _monitor_one(pos)
        except Exception as e:
            print(f"[GROWTH] Error monitoreando {product}: {e}")


# ─── RESUMENES ────────────────────────────────────────────────────────────────
def maybe_send_summaries() -> None:
    s = state.load()
    local = _local_now()
    today = local.date().isoformat()

    positions = s.get("open_positions") or {}
    prices    = {p: get_price(p) for p in positions} if positions else {}

    # Diario a las 7AM
    if local.hour >= DAILY_SUMMARY_HOUR and s.get("last_daily_summary") != today:
        has_signal = bool(s.get("pending_signal") or positions)
        msg = messages.daily_summary(
            s["balance"], s["start_balance"], CURATED, has_signal,
            positions=positions, prices=prices,
        )
        send_growth_telegram(msg)
        s["last_daily_summary"] = today
        state.save(s)

    # Semanal los lunes
    if local.weekday() == 0 and s.get("last_weekly_summary") != today:
        tier = risk_tier(s["balance"])
        msg = messages.weekly_summary(
            s["balance"], s["start_balance"], s.get("trade_log", []),
            _days_left(s), tier.name,
            positions=positions, prices=prices,
        )
        send_growth_telegram(msg)
        s["last_weekly_summary"] = today
        state.save(s)


# ─── LOOP PRINCIPAL ───────────────────────────────────────────────────────────
def run_growth_scanner() -> None:
    print("[GROWTH] Scanner del Reto 100->1000 iniciado.")

    # Cargar estado (dispara la recuperacion desde GitHub si hubo reinicio)
    s = state.load()
    _positions = s.get("open_positions") or {}
    _prices    = {p: get_price(p) for p in _positions} if _positions else {}
    if state.RECOVERY["recovered"]:
        send_growth_telegram(messages.state_recovered(
            s["balance"], len(s.get("trade_log", [])),
            positions=_positions, prices=_prices,
        ))
    elif state.RECOVERY["failed"]:
        send_growth_telegram(messages.state_lost())
    else:
        send_growth_telegram(messages.welcome(positions=_positions, prices=_prices))

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
