"""Günlükçü: her karar, her konuşma ve her işlem (brüt VE net) kaydedilir."""
import json
import os
import time


def log(path: str, kind: str, **data) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.time(), "kind": kind, **data}, ensure_ascii=False) + "\n")


def load_state(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"positions": {}, "days": {}, "last_trade_ts": {}, "total_pnl": 0.0, "killed": False}


def save_state(path: str, state: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
