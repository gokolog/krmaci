"""Hacim Tarayıcı: LLM değil, istatistik. Olağandışı hacim + fiyat hareketini yakalar."""
import statistics
from dataclasses import dataclass


@dataclass
class Anomaly:
    symbol: str
    price: float
    vol_z: float
    move_pct: float   # son kapanmış mumda %
    direction: str    # UP / DOWN


def detect(symbol: str, klines: list[dict], lookback: int, z_thr: float, move_thr: float) -> Anomaly | None:
    # son mum henüz kapanmamış olabilir -> kapanmış son mumu (-2) kullan
    if len(klines) < lookback + 2:
        return None
    last = klines[-2]
    hist = [k["qv"] for k in klines[-lookback - 2:-2]]
    sd = statistics.pstdev(hist)
    if sd == 0:
        return None
    z = (last["qv"] - statistics.mean(hist)) / sd
    move = (last["c"] - last["o"]) / last["o"] * 100
    if z >= z_thr and abs(move) >= move_thr:
        return Anomaly(symbol, klines[-1]["c"], round(z, 2), round(move, 2), "UP" if move > 0 else "DOWN")
    return None
