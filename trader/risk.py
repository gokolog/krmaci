"""Risk Yöneticisi: KOD. LLM'in 'zarar etmeyecek' demesine güvenmeyiz, kural zorlarız. Veto hakkı vardır."""
from dataclasses import dataclass
from datetime import datetime, timezone

from config import Config


@dataclass
class Plan:
    symbol: str
    side: str          # LONG | SHORT
    entry: float
    stop: float
    target: float


def check(cfg: Config, plan: Plan, state: dict, balance: float, now: datetime | None = None) -> tuple[bool, str]:
    now = now or datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")

    if state.get("killed"):
        return False, "kill-switch aktif"
    if state.get("total_pnl", 0.0) <= -cfg.kill_switch_loss_usdt:
        return False, f"toplam zarar limiti ({cfg.kill_switch_loss_usdt}$) aşıldı"
    day = state.get("days", {}).get(today, {"trades": 0, "pnl": 0.0})
    if day["pnl"] <= -cfg.max_daily_loss_usdt:
        return False, "günlük zarar limiti"
    if day["trades"] >= cfg.max_trades_per_day:
        return False, "günlük işlem limiti"
    if len(state.get("positions", {})) >= cfg.max_open_positions:
        return False, "açık pozisyon limiti"

    last = state.get("last_trade_ts", {}).get(plan.symbol)
    if last and (now.timestamp() - last) < cfg.cooldown_min * 60:
        return False, "sembol bekleme süresinde"

    if plan.side != "LONG":
        return False, "spot modda yalnızca LONG yürütülür (SHORT sadece sinyal)"
    if not (plan.stop < plan.entry < plan.target):
        return False, "stop/giriş/hedef sıralaması hatalı"
    stop_pct = (plan.entry - plan.stop) / plan.entry * 100
    if stop_pct > cfg.max_stop_distance_pct:
        return False, f"stop çok uzak (%{stop_pct:.2f})"
    rr = (plan.target - plan.entry) / (plan.entry - plan.stop)
    if rr < cfg.min_reward_risk:
        return False, f"risk/ödül düşük ({rr:.2f})"

    size = position_size(cfg, balance)
    if size < cfg.min_notional_usdt:
        return False, f"bakiye min işlem tutarına yetmiyor ({size:.2f}$)"
    return True, "ok"


def pre_check(cfg: Config, symbol: str, state: dict, now: datetime) -> tuple[bool, str]:
    """LLM çağrısından ÖNCE çalışan ucuz kapı: limitler ve bekleme süresi (boşuna API maliyeti olmasın)."""
    today = now.strftime("%Y-%m-%d")
    day = state.get("days", {}).get(today, {"trades": 0, "pnl": 0.0})
    if state.get("killed") or state.get("total_pnl", 0.0) <= -cfg.kill_switch_loss_usdt:
        return False, "kill-switch"
    if day["pnl"] <= -cfg.max_daily_loss_usdt:
        return False, "günlük zarar limiti"
    if day["trades"] >= cfg.max_trades_per_day:
        return False, "günlük işlem limiti"
    last = state.get("last_trade_ts", {}).get(symbol)
    if last and (now.timestamp() - last) < cfg.cooldown_min * 60:
        return False, "bekleme süresi"
    return True, "ok"


def position_size(cfg: Config, balance: float) -> float:
    return round(min(balance * cfg.max_position_pct, balance), 2)
