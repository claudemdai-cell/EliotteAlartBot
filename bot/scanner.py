"""
Scanner autónomo — corre cada 4 horas sin TradingView.
- Analiza niveles Elliott dinamicamente con datos reales (90d)
- Detecta cambios de panorama y envia alertas
- Resumen diario a las 6AM
"""

import time
import datetime
import requests
from layers import WebhookPayload, evaluate_layers, format_alert_text
from fibonacci import in_golden_zone
from alerts import send_telegram
from log import log_alert
from gem_hunter import run_gem_scan, send_gem_report

# Timezone offset — cambia segun tu pais
# -5 = Colombia, Peru, Ecuador | -3 = Argentina | -6 = Mexico CST
UTC_OFFSET_HOURS = -5
DAILY_SUMMARY_HOUR = 6   # 6:00 AM hora local
ANALYSIS_INTERVAL_DAYS = 7   # Re-analizar niveles cada 7 dias
GEM_SCAN_INTERVAL_DAYS = 3   # Gem scan cada 3 dias

# Cache de gems previas para detectar novedades
_prev_gems: dict = {}  # { symbol: gem_data }

CRYPTO_API = "https://api.crypto.com/exchange/v1/public"

# Watchlist base — los niveles se actualizan automaticamente
WATCHLIST = [
    {"asset": "BTCUSD",   "symbol": "BTC_USDT"},
    {"asset": "ETHUSD",   "symbol": "ETH_USDT"},
    {"asset": "LINKUSD",  "symbol": "LINK_USDT"},
    {"asset": "SOLUSD",   "symbol": "SOL_USDT"},
    {"asset": "JASMYUSD", "symbol": "JASMY_USDT"},
]

# Estado dinamico — se actualiza con cada analisis
# { "BTCUSD": { wave_start, wave_end, stop, target, trend, last_analyzed } }
DYNAMIC_STATE = {}


# ─── DATA ────────────────────────────────────────────────────────────────────

def get_ohlcv(symbol: str, timeframe: str = "4h", limit: int = 100) -> list:
    url = f"{CRYPTO_API}/get-candlestick"
    params = {"instrument_name": symbol, "timeframe": timeframe, "count": limit}
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        return r.json().get("result", {}).get("data", [])
    except Exception as e:
        print(f"[SCANNER] Error {symbol}: {e}")
        return []


def compute_rsi(closes: list, period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gains  = [d for d in deltas[-period:] if d > 0]
    losses = [-d for d in deltas[-period:] if d < 0]
    avg_gain = sum(gains) / period if gains else 0.001
    avg_loss = sum(losses) / period if losses else 0.001
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def compute_ema(closes: list, period: int = 21) -> float:
    if len(closes) < period:
        return closes[-1] if closes else 0.0
    k = 2 / (period + 1)
    ema = sum(closes[:period]) / period
    for price in closes[period:]:
        ema = price * k + ema * (1 - k)
    return round(ema, 4)


# ─── ANALISIS DINAMICO ────────────────────────────────────────────────────────

def analyze_levels(symbol: str, asset: str) -> dict:
    """
    Calcula automaticamente los niveles Elliott desde datos reales.
    Usa velas diarias de los ultimos 90 dias para identificar:
    - wave_start: minimo del periodo (soporte estructural)
    - wave_end: maximo del periodo (resistencia / fin de impulso)
    - trend: alcista / bajista / lateral
    - stop, target con Fibonacci
    """
    candles_1d = get_ohlcv(symbol, "1D", 90)
    if len(candles_1d) < 30:
        return {}

    highs  = [float(c['h']) for c in candles_1d]
    lows   = [float(c['l']) for c in candles_1d]
    closes = [float(c['c']) for c in candles_1d]

    max_high = max(highs)
    min_low  = min(lows)
    last_price = closes[-1]

    # Determinar tendencia con EMA50 diaria
    ema50 = compute_ema(closes, 50) if len(closes) >= 50 else compute_ema(closes, len(closes))
    ema20 = compute_ema(closes, 20)

    # Posicion del precio relativa al rango
    rng = max_high - min_low
    position_pct = (last_price - min_low) / rng * 100 if rng > 0 else 50

    # Tendencia
    if last_price > ema50 and ema20 > ema50:
        trend = "alcista"
    elif last_price < ema50 and ema20 < ema50:
        trend = "bajista"
    else:
        trend = "lateral"

    # En tendencia alcista: wave_start = minimo, wave_end = maximo
    # En bajista: invertimos para buscar rebote desde soporte
    wave_start = min_low
    wave_end   = max_high

    # Calcular golden zone (retroceso desde max al min)
    gz_low  = wave_end - rng * 0.618
    gz_high = wave_end - rng * 0.500

    # Stop: 2% bajo el minimo
    stop   = round(min_low * 0.98, 6)
    # Target: extension 161.8% desde el minimo
    target = round(min_low + rng * 1.618, 6)

    # RSI actual
    rsi_4h_candles = get_ohlcv(symbol, "4h", 25)
    rsi = 50.0
    if rsi_4h_candles:
        closes_4h = [float(c['c']) for c in rsi_4h_candles]
        rsi = compute_rsi(closes_4h)

    return {
        "wave_start":    round(wave_start, 6),
        "wave_end":      round(wave_end, 6),
        "stop":          stop,
        "target":        target,
        "gz_low":        round(gz_low, 6),
        "gz_high":       round(gz_high, 6),
        "trend":         trend,
        "position_pct":  round(position_pct, 1),
        "rsi":           rsi,
        "last_price":    last_price,
        "max_90d":       round(max_high, 6),
        "min_90d":       round(min_low, 6),
        "last_analyzed": datetime.datetime.utcnow().isoformat(),
    }


def detect_panorama_change(asset: str, old: dict, new: dict) -> list:
    """
    Compara analisis anterior con el nuevo.
    Retorna lista de cambios importantes detectados.
    """
    changes = []
    if not old:
        return changes

    price = new["last_price"]

    # 1. Nuevo minimo historico (invalidacion)
    if new["min_90d"] < old["min_90d"] * 0.97:
        pct = ((new["min_90d"] - old["min_90d"]) / old["min_90d"]) * 100
        changes.append(f"NUEVO MINIMO 90d: {new['min_90d']} (cambio {pct:.1f}%)")

    # 2. Nuevo maximo historico (momentum alcista)
    if new["max_90d"] > old["max_90d"] * 1.03:
        pct = ((new["max_90d"] - old["max_90d"]) / old["max_90d"]) * 100
        changes.append(f"NUEVO MAXIMO 90d: {new['max_90d']} (+{pct:.1f}%)")

    # 3. Cambio de tendencia
    if old.get("trend") and new["trend"] != old["trend"]:
        changes.append(f"CAMBIO DE TENDENCIA: {old['trend']} -> {new['trend']}")

    # 4. Precio entro en golden zone
    was_in_zone = in_golden_zone(old["last_price"], old["wave_start"], old["wave_end"])
    now_in_zone = in_golden_zone(price, new["wave_start"], new["wave_end"])
    if now_in_zone and not was_in_zone:
        changes.append(f"ENTRO EN GOLDEN ZONE ({new['gz_low']:.4f} - {new['gz_high']:.4f})")

    # 5. Precio rompio soporte (bajo wave_start)
    if price < new["wave_start"]:
        changes.append(f"ROMPIO SOPORTE: precio {price} bajo minimo {new['wave_start']}")

    # 6. Precio rompio resistencia (sobre wave_end)
    if price > new["wave_end"]:
        changes.append(f"ROMPIO RESISTENCIA: precio {price} sobre maximo {new['wave_end']}")

    return changes


def send_analysis_update(asset: str, levels: dict, changes: list) -> None:
    """Envia alerta de cambio de panorama al Telegram."""
    trend_emoji = {"alcista": "Alcista", "bajista": "Bajista", "lateral": "Lateral"}.get(levels["trend"], "?")
    gz_dist = ((levels["last_price"] - levels["gz_low"]) / levels["gz_low"]) * 100

    if gz_dist < 0:
        zona_txt = f"Falta {abs(gz_dist):.1f}% para entrar"
    elif in_golden_zone(levels["last_price"], levels["wave_start"], levels["wave_end"]):
        zona_txt = "EN ZONA AHORA"
    else:
        zona_txt = f"Sobre zona +{gz_dist:.1f}%"

    lines = [
        f"*Actualizacion de Analisis: {asset}*",
        "",
    ]

    if changes:
        lines.append("*Cambios detectados:*")
        for c in changes:
            lines.append(f"  - {c}")
        lines.append("")

    lines += [
        f"*Panorama actual:* {trend_emoji}",
        f"Precio: `{levels['last_price']}` | RSI: `{levels['rsi']:.0f}`",
        f"Rango 90d: `{levels['min_90d']}` - `{levels['max_90d']}`",
        f"Golden Zone: `{levels['gz_low']:.4f}` - `{levels['gz_high']:.4f}`",
        f"Estado: {zona_txt}",
        f"Stop: `{levels['stop']}` | Target: `{levels['target']}`",
    ]

    send_telegram("\n".join(lines))


# ─── SCAN ─────────────────────────────────────────────────────────────────────

def scan_asset(cfg: dict) -> None:
    asset  = cfg["asset"]
    symbol = cfg["symbol"]
    state  = DYNAMIC_STATE.get(asset, {})

    candles = get_ohlcv(symbol, "4h", 25)
    if len(candles) < 21:
        print(f"[SCANNER] {symbol}: datos insuficientes")
        return

    opens   = [float(c['o']) for c in candles]
    highs   = [float(c['h']) for c in candles]
    lows    = [float(c['l']) for c in candles]
    closes  = [float(c['c']) for c in candles]
    volumes = [float(c['v']) for c in candles]

    rsi       = compute_rsi(closes)
    ema21     = compute_ema(closes, 21)
    vol_avg5  = sum(volumes[-5:]) / 5
    vol_avg20 = sum(volumes[-20:]) / 20

    # Usar niveles dinamicos si existen, si no usar defaults del 90d
    wave_start = state.get("wave_start", min(lows))
    wave_end   = state.get("wave_end",   max(highs))
    stop       = state.get("stop",       min(lows) * 0.98)
    target     = state.get("target",     max(highs) * 1.5)

    payload = WebhookPayload(
        asset=asset, price=closes[-1],
        open_4h=opens[-1], close_4h=closes[-1],
        high_4h=highs[-1], low_4h=lows[-1],
        rsi_4h=rsi, volume_avg5=vol_avg5, volume_avg20=vol_avg20,
        ema21_4h=ema21, in_elliott_zone=True,
        wave_start=wave_start, wave_end=wave_end,
    )

    result = evaluate_layers(payload)
    score  = result["score"]
    layers_passed = [k for k, v in result["layers"].items() if v.passed]

    print(f"[SCANNER] {asset} | Score: {score}/5 | RSI: {rsi:.1f} | Price: {closes[-1]}")

    sent = False
    if score >= 4:
        text = format_alert_text(payload, result, stop, target)
        sent = send_telegram(text)

    log_alert(asset, score, closes[-1], stop, target, layers_passed, sent)


# ─── RESUMEN DIARIO ───────────────────────────────────────────────────────────

def send_daily_summary() -> None:
    """Envia resumen diario de todos los activos a las 6AM."""
    date_str = (datetime.datetime.utcnow() + datetime.timedelta(hours=UTC_OFFSET_HOURS)).strftime("%Y-%m-%d")
    lines = [f"*Resumen Diario Elliott Bot*", f"_{date_str} | 6:00 AM_", ""]

    for cfg in WATCHLIST:
        asset  = cfg["asset"]
        symbol = cfg["symbol"]
        state  = DYNAMIC_STATE.get(asset, {})

        candles = get_ohlcv(symbol, "4h", 25)
        if len(candles) < 21:
            continue

        closes  = [float(c['c']) for c in candles]
        volumes = [float(c['v']) for c in candles]
        rsi = compute_rsi(closes)
        vol5 = sum(volumes[-5:]) / 5
        vol20 = sum(volumes[-20:]) / 20

        price      = closes[-1]
        wave_start = state.get("wave_start", min([float(c['l']) for c in candles]))
        wave_end   = state.get("wave_end",   max([float(c['h']) for c in candles]))
        target     = state.get("target", wave_end * 1.5)
        stop       = state.get("stop", wave_start * 0.98)
        trend      = state.get("trend", "?")
        gz_low     = wave_end - abs(wave_end - wave_start) * 0.618
        gz_high    = wave_end - abs(wave_end - wave_start) * 0.500
        dist_pct   = ((price - gz_low) / gz_low) * 100

        # Score rapido
        ema21 = compute_ema(closes, 21)
        payload = WebhookPayload(
            asset=asset, price=price,
            open_4h=float(candles[-1]['o']), close_4h=price,
            high_4h=float(candles[-1]['h']), low_4h=float(candles[-1]['l']),
            rsi_4h=rsi, volume_avg5=vol5, volume_avg20=vol20,
            ema21_4h=ema21, in_elliott_zone=True,
            wave_start=wave_start, wave_end=wave_end,
        )
        score = evaluate_layers(payload)["score"]
        bar   = chr(9608) * score + chr(9617) * (5 - score)

        if in_golden_zone(price, wave_start, wave_end):
            zona_txt = "EN ZONA"
        elif dist_pct < 0:
            zona_txt = f"Falta {abs(dist_pct):.1f}% para zona"
        else:
            zona_txt = f"Sobre zona +{dist_pct:.1f}%"

        estado = "ALERTA" if score >= 4 else ("Calentando" if score == 3 else "Esperando")
        trend_txt = f" | {trend}" if trend != "?" else ""

        lines.append(
            f"*{asset}* [{bar}] {score}/5 - {estado}{trend_txt}\n"
            f"  Precio: `{price}` | RSI: `{rsi:.0f}`\n"
            f"  Zona: `{gz_low:.4f}` - `{gz_high:.4f}` | {zona_txt}\n"
            f"  Target: `{target}` | Stop: `{stop}`"
        )

    send_telegram("\n".join(lines))


# ─── ANALISIS SEMANAL ─────────────────────────────────────────────────────────

def run_weekly_analysis(force: bool = False) -> None:
    """
    Re-analiza todos los activos con datos reales de 90 dias.
    Detecta cambios de panorama y actualiza DYNAMIC_STATE.
    Se ejecuta cada 7 dias (o al inicio).
    """
    print("[ANALYSIS] Ejecutando analisis semanal...")

    for cfg in WATCHLIST:
        asset  = cfg["asset"]
        symbol = cfg["symbol"]
        old    = DYNAMIC_STATE.get(asset, {})

        new = analyze_levels(symbol, asset)
        if not new:
            print(f"[ANALYSIS] {asset}: sin datos")
            continue

        changes = detect_panorama_change(asset, old, new)
        DYNAMIC_STATE[asset] = new

        print(f"[ANALYSIS] {asset}: trend={new['trend']} | pos={new['position_pct']}% del rango | cambios={len(changes)}")

        # Notificar si hay cambios importantes O si es el primer analisis
        if changes or not old:
            send_analysis_update(asset, new, changes)
            time.sleep(1)

    print("[ANALYSIS] Analisis completado.")


# ─── LOOP PRINCIPAL ───────────────────────────────────────────────────────────

def run_scanner(interval_hours: int = 4) -> None:
    """Loop principal — corre cada 4 horas."""
    print(f"[SCANNER] Iniciando. Scan cada {interval_hours}h | Resumen 6AM | Analisis semanal.")
    send_telegram("*Elliott Scanner iniciado*\nScan cada 4h | Resumen 6AM | Analisis semanal automatico.")

    last_summary_day  = None
    last_analysis_day = None
    last_gem_day      = None

    # Analisis inicial al arrancar
    run_weekly_analysis(force=True)

    while True:
        utc_now   = datetime.datetime.utcnow()
        local_now = utc_now + datetime.timedelta(hours=UTC_OFFSET_HOURS)
        today     = local_now.date()

        # Resumen diario a las 6AM
        if local_now.hour == DAILY_SUMMARY_HOUR and last_summary_day != today:
            print(f"[SCANNER] Resumen diario ({local_now.strftime('%H:%M')} local)")
            send_daily_summary()
            last_summary_day = today

        # Analisis semanal de niveles Elliott
        days_since_analysis = (today - last_analysis_day).days if last_analysis_day else 999
        if days_since_analysis >= ANALYSIS_INTERVAL_DAYS:
            run_weekly_analysis()
            last_analysis_day = today

        # Gem scan cada 3 dias
        days_since_gem = (today - last_gem_day).days if last_gem_day else 999
        if days_since_gem >= GEM_SCAN_INTERVAL_DAYS:
            print("[SCANNER] Iniciando Gem Scan...")
            watchlist_set = {cfg["asset"] for cfg in WATCHLIST}
            gems = run_gem_scan(watchlist_assets=watchlist_set)
            # Detectar nuevas gems vs scan anterior
            new_gems = [g for g in gems if g["symbol"] not in _prev_gems]
            # Auto-agregar gems 💎 y 🔥 al watchlist si no estan
            for g in gems:
                if g["emoji"] in ("💎", "🔥") and not g.get("in_watchlist"):
                    asset_name = g["asset"] + "USD"
                    if not any(c["asset"] == asset_name for c in WATCHLIST):
                        WATCHLIST.append({
                            "asset":  asset_name,
                            "symbol": g["symbol"],
                        })
                        print(f"[GEM] {g['emoji']} {asset_name} agregado al watchlist automaticamente")
            send_gem_report(gems, new_gems=new_gems if new_gems else None)
            _prev_gems.update({g["symbol"]: g for g in gems})
            last_gem_day = today

        # Scan normal cada 4h
        print(f"\n[SCANNER] --- Scan {local_now.strftime('%Y-%m-%d %H:%M')} ---")
        for cfg in WATCHLIST:
            scan_asset(cfg)
            time.sleep(2)

        print(f"[SCANNER] Esperando {interval_hours}h...")
        time.sleep(interval_hours * 3600)


if __name__ == "__main__":
    run_scanner()
