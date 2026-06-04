"""
Fibonacci calculations for Elliott Wave analysis.
Retrocesos, extensiones y zonas de confluencia.
"""

FIB_RETRACEMENTS = [0.236, 0.382, 0.500, 0.618, 0.786]
FIB_EXTENSIONS   = [1.000, 1.272, 1.414, 1.618, 2.000, 2.618]


def retracement_levels(wave_start: float, wave_end: float) -> dict:
    """Niveles de retroceso desde wave_start hasta wave_end."""
    rango = wave_end - wave_start
    return {
        f"{int(r*100)}%": round(wave_end - rango * r, 4)
        for r in FIB_RETRACEMENTS
    }


def extension_levels(wave_start: float, wave_end: float, correction_end: float) -> dict:
    """Extensiones proyectadas desde correction_end."""
    rango = wave_end - wave_start
    return {
        f"{int(r*100)}%": round(correction_end + rango * r, 4)
        for r in FIB_EXTENSIONS
    }


def in_golden_zone(price: float, wave_start: float, wave_end: float) -> bool:
    """True si price está entre 50% y 61.8% de retroceso (zona dorada)."""
    rango = wave_end - wave_start
    fib_50  = wave_end - rango * 0.500
    fib_618 = wave_end - rango * 0.618

    low  = min(fib_50, fib_618)
    high = max(fib_50, fib_618)
    return low <= price <= high


def retracement_pct(wave_start: float, wave_end: float, current: float) -> float:
    """Porcentaje de retroceso actual. Fórmula: retroceso / recorrido."""
    rango = abs(wave_end - wave_start)
    if rango == 0:
        return 0.0
    retroceso = abs(wave_end - current)
    return round(retroceso / rango, 4)
