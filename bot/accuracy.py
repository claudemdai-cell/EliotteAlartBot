"""
Historial de precisión de proyecciones diarias.
Guarda el cierre estimado de cada activo y lo compara con el precio real al día siguiente.
"""

import datetime
from elliott_store import load, save


def save_projections(projs_by_asset: dict) -> None:
    """
    Persiste las proyecciones del día antes de enviar el resumen matutino.
    projs_by_asset = { "BTCUSD": {"day_close": 34500, "week_target": 31000, ...}, ... }
    """
    state = load()
    today = datetime.date.today().isoformat()
    dp    = state.get("daily_projections", {})
    dp[today] = {
        asset: {"day_close": p.get("day_close"), "week_target": p.get("week_target")}
        for asset, p in projs_by_asset.items()
        if p.get("day_close")
    }
    # Solo últimos 30 días
    if len(dp) > 30:
        del dp[sorted(dp.keys())[0]]
    state["daily_projections"] = dp
    save(state)
    print(f"[ACCURACY] Proyecciones guardadas para {today}: {list(projs_by_asset.keys())}")


def compute_accuracy(actual_prices: dict) -> dict | None:
    """
    Compara proyecciones de ayer con precios reales de hoy.
    actual_prices = { "BTCUSD": 34521.0, "ETHUSD": 1820.0, ... }
    Retorna { results, avg, date } o None si no hay datos.
    """
    state     = load()
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    dp        = state.get("daily_projections", {})
    if yesterday not in dp:
        return None

    results   = {}
    acc_list  = []

    for asset, proj in dp[yesterday].items():
        actual    = actual_prices.get(asset)
        projected = proj.get("day_close")
        if not actual or not projected or projected == 0:
            continue
        error_pct = abs(actual - projected) / projected * 100
        accuracy  = round(max(0, 100 - error_pct), 1)
        results[asset] = {
            "projected": projected,
            "actual":    actual,
            "error_pct": round(error_pct, 1),
            "accuracy":  accuracy,
        }
        acc_list.append(accuracy)

    if not results:
        return None

    avg = round(sum(acc_list) / len(acc_list), 1)

    # Guardar en historial
    hist = state.get("accuracy_history", [])
    hist.append({"date": yesterday, "scores": {k: v["accuracy"] for k, v in results.items()}, "avg": avg})
    state["accuracy_history"] = hist[-30:]
    save(state)

    return {"results": results, "avg": avg, "date": yesterday}


def get_history() -> list:
    return load().get("accuracy_history", [])


def get_monday_projections() -> dict:
    """Retorna las proyecciones del lunes de esta semana (para review de viernes)."""
    state = load()
    dp    = state.get("daily_projections", {})
    today = datetime.date.today()
    # Encontrar el lunes más reciente
    days_since_mon = today.weekday()
    monday = (today - datetime.timedelta(days=days_since_mon)).isoformat()
    return dp.get(monday, {})
