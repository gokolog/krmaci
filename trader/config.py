"""Tüm ayarlar ve SERT risk limitleri. Bunlar kodda zorlanır, prompt'a bırakılmaz."""
import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Config:
    # --- Piyasa ---
    base_url: str = "https://testnet.binance.vision"  # SADECE testnet
    symbols: tuple = ("BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT")
    interval: str = "5m"
    scan_every_sec: int = 60

    # --- Tarayıcı (LLM yok, düz kod) ---
    vol_lookback: int = 48          # kaç mum üzerinden ortalama/sapma
    vol_z_threshold: float = 3.0    # hacim z-score eşiği
    price_move_pct: float = 0.8     # son mumda en az %0.8 hareket

    # --- Risk (kod zorlar) ---
    start_balance_usdt: float = 10.0
    max_position_pct: float = 0.50      # tek işlemde bakiyenin en çok %50'si (10$ için min notional yüzünden)
    min_notional_usdt: float = 5.0
    max_open_positions: int = 1
    max_trades_per_day: int = 5
    max_daily_loss_usdt: float = 1.0    # günlük zarar bu kadara ulaşırsa dur
    kill_switch_loss_usdt: float = 3.0  # toplam zarar bu kadara ulaşırsa bot kendini kapatır
    min_reward_risk: float = 1.5
    max_stop_distance_pct: float = 3.0  # stop girişten en fazla %3 uzakta
    fee_rate: float = 0.001             # %0.1 işlem başına
    slippage_pct: float = 0.05          # paper modda varsayılan kayma
    cooldown_min: int = 30              # aynı sembolde işlemden sonra bekleme

    # --- LLM ---
    model: str = "claude-sonnet-5-5"
    max_debate_rounds: int = 2
    use_web_search: bool = True         # Haberci için

    # --- Dosyalar ---
    journal_path: str = "data/journal.jsonl"
    state_path: str = "data/state.json"
    log_agents: bool = True             # her botun konuşmasını logla


def env(name: str) -> str:
    v = os.environ.get(name, "")
    if not v:
        raise RuntimeError(f"Ortam değişkeni eksik: {name}")
    return v
