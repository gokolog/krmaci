"""Ana döngü.  python main.py --mode paper|testnet [--once]"""
import argparse
import time
from datetime import datetime, timezone

import desk
import journal
import risk
import scanner
from agents import LLM
from binance_client import BinanceTestnet
from config import Config, env
from executor import Executor


def _day(state: dict, now: datetime) -> dict:
    return state["days"].setdefault(now.strftime("%Y-%m-%d"), {"trades": 0, "pnl": 0.0})


def manage_positions(cfg: Config, client, ex: Executor, state: dict, now: datetime) -> None:
    """Açık pozisyonlarda stop/hedef kontrolü. (Bot kapalıyken stop çalışmaz -> sadece testnet için kabul edilebilir.)"""
    for sym, p in list(state["positions"].items()):
        px = client.price(sym)
        reason = "STOP" if px <= p["stop"] else "HEDEF" if px >= p["target"] else None
        if not reason:
            continue
        c = ex.close_long(sym, p["qty"], px)
        gross = (c["price"] - p["entry_price"]) * p["qty"]
        fees = p["fee_open"] + c["fee_usdt"]
        net = gross - fees
        state["total_pnl"] += net
        _day(state, now)["pnl"] += net
        del state["positions"][sym]
        state["last_trade_ts"][sym] = now.timestamp()
        journal.log(cfg.journal_path, "close", symbol=sym, reason=reason, entry=p["entry_price"],
                    exit=c["price"], gross=round(gross, 4), fees=round(fees, 4), net=round(net, 4),
                    total_pnl=round(state["total_pnl"], 4))
        if state["total_pnl"] <= -cfg.kill_switch_loss_usdt:
            state["killed"] = True
            journal.log(cfg.journal_path, "kill_switch", total_pnl=state["total_pnl"])


def balance(cfg: Config, client, mode: str, state: dict) -> float:
    if mode == "paper":
        locked = sum(p["quote"] for p in state["positions"].values())
        return cfg.start_balance_usdt + state["total_pnl"] - locked
    return client.balance("USDT")


def cycle(cfg: Config, client, llm, ex: Executor, mode: str, state: dict, now: datetime | None = None) -> None:
    now = now or datetime.now(timezone.utc)
    manage_positions(cfg, client, ex, state, now)
    if state["killed"] or state["positions"]:
        return

    anomalies = []
    for sym in cfg.symbols:
        if not risk.pre_check(cfg, sym, state, now)[0]:
            continue
        ks = client.klines(sym, cfg.interval, cfg.vol_lookback + 5)
        a = scanner.detect(sym, ks, cfg.vol_lookback, cfg.vol_z_threshold, cfg.price_move_pct)
        if a:
            anomalies.append((a, ks))
    if not anomalies:
        return
    anomalies.sort(key=lambda x: x[0].vol_z, reverse=True)
    an, ks = anomalies[0]   # döngü başına en güçlü tek anomali (maliyet/gürültü kontrolü)

    v = desk.run(llm, an, ks, cfg.max_debate_rounds, cfg.use_web_search)
    if cfg.log_agents:
        journal.log(cfg.journal_path, "debate", symbol=an.symbol, decision=v.decision,
                    reason=v.reason, transcript=v.transcript)
    if v.decision != "LONG" and v.decision != "SHORT":
        return

    plan = risk.Plan(an.symbol, v.decision, float(v.plan["entry"]), float(v.plan["stop"]), float(v.plan["target"]))
    bal = balance(cfg, client, mode, state)
    ok, why = risk.check(cfg, plan, state, bal, now)
    journal.log(cfg.journal_path, "risk", symbol=an.symbol, side=plan.side, ok=ok, why=why, balance=bal)
    if not ok:
        return

    quote = risk.position_size(cfg, bal)
    live = client.price(an.symbol)   # giriş fiyatı olarak güncel fiyat; planın girişinden çok saptıysa girme
    if abs(live - plan.entry) / plan.entry * 100 > 0.5:
        journal.log(cfg.journal_path, "skip", symbol=an.symbol, why="fiyat plandan %0.5'ten fazla saptı")
        return
    o = ex.open_long(an.symbol, quote, live)
    state["positions"][an.symbol] = {"qty": o["qty"], "entry_price": o["price"], "stop": plan.stop,
                                    "target": plan.target, "fee_open": o["fee_usdt"], "quote": quote,
                                    "opened_ts": now.timestamp()}
    _day(state, now)["trades"] += 1
    journal.log(cfg.journal_path, "open", symbol=an.symbol, qty=o["qty"], price=o["price"],
                stop=plan.stop, target=plan.target, quote=quote, fee=o["fee_usdt"], mode=mode)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["paper", "testnet"], default="paper")
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()
    cfg = Config()
    if args.mode == "testnet":
        client = BinanceTestnet(cfg.base_url, env("BINANCE_TESTNET_API_KEY"), env("BINANCE_TESTNET_API_SECRET"))
    else:
        client = BinanceTestnet(cfg.base_url)   # sadece public veri
    llm = LLM(cfg.model, env("ANTHROPIC_API_KEY"))
    ex = Executor(cfg, client, args.mode)
    state = journal.load_state(cfg.state_path)
    print(f"[{args.mode}] başladı. Semboller: {cfg.symbols}")
    while True:
        try:
            cycle(cfg, client, llm, ex, args.mode, state)
            journal.save_state(cfg.state_path, state)
        except Exception as e:  # tek hata botu öldürmesin ama kaydedilsin
            journal.log(cfg.journal_path, "error", error=repr(e))
            print("hata:", repr(e))
        if args.once or state["killed"]:
            break
        time.sleep(cfg.scan_every_sec)


if __name__ == "__main__":
    main()
