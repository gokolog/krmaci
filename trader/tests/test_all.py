import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import dataclasses

import desk
import journal
import main as m
import risk
import scanner
from config import Config
from executor import Executor


def kl(n=60, spike=False, up=True):
    ks = [{"t": i, "o": 100.0, "h": 100.5, "l": 99.5, "c": 100.0 + (0.01 * (i % 3)), "v": 10, "qv": 1000 + (i % 5) * 10}
          for i in range(n)]
    if spike:   # -2 indeksi kapanmış son mum
        ks[-2] = {"t": 0, "o": 100.0, "h": 102, "l": 99.9, "c": 101.5 if up else 98.5, "v": 99, "qv": 9000}
    return ks


class FakeClient:
    def __init__(self, spike_sym=None, price=101.5):
        self.spike_sym, self._price = spike_sym, price

    def klines(self, sym, interval, limit):
        return kl(spike=(sym == self.spike_sym))

    def price(self, sym):
        return self._price

    def balance(self, a="USDT"):
        return 10.0


class FakeLLM:
    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = 0

    def ask(self, system, user, web_search=False):
        self.calls += 1
        return self.answers.pop(0)


def J(**k):
    return json.dumps(k)


GOOD = [J(reason="listeleme", sources=["http://x"], confidence=.8, is_old_news=False),
        J(side="LONG", entry=101.5, stop=100.5, target=103.5, rationale="r"),
        J(objections=["likidite"], blocking=False),
        J(decision="LONG", reason="ok")]


def cfg(tmp_path):
    return dataclasses.replace(Config(), journal_path=str(tmp_path / "j.jsonl"),
                               state_path=str(tmp_path / "s.json"), symbols=("AAAUSDT",))


def test_scanner_detects_spike_and_ignores_flat():
    assert scanner.detect("X", kl(), 48, 3, 0.8) is None
    a = scanner.detect("X", kl(spike=True), 48, 3, 0.8)
    assert a and a.direction == "UP" and a.vol_z > 3


def test_desk_blocks_without_sources():
    an = scanner.detect("X", kl(spike=True), 48, 3, 0.8)
    llm = FakeLLM([J(reason="bulunamadı", sources=[], confidence=0, is_old_news=False)])
    v = desk.run(llm, an, kl(spike=True), 2, False)
    assert v.decision == "BEKLE" and llm.calls == 1


def test_desk_geç_when_no_plan():
    an = scanner.detect("X", kl(spike=True), 48, 3, 0.8)
    llm = FakeLLM([GOOD[0], J(side="NONE", entry=0, stop=0, target=0, rationale="")])
    assert desk.run(llm, an, kl(spike=True), 2, False).decision == "GEÇ"


def test_desk_happy_path():
    an = scanner.detect("X", kl(spike=True), 48, 3, 0.8)
    v = desk.run(FakeLLM(GOOD), an, kl(spike=True), 2, False)
    assert v.decision == "LONG" and v.plan["stop"] == 100.5 and len(v.transcript) == 5


def test_risk_rules(tmp_path):
    c = cfg(tmp_path)
    st = journal.load_state(str(tmp_path / "none.json"))
    ok = risk.Plan("A", "LONG", 100, 99, 102)
    assert risk.check(c, ok, st, 10.0)[0]
    assert not risk.check(c, risk.Plan("A", "LONG", 100, 99, 100.5), st, 10.0)[0]   # RR düşük
    assert not risk.check(c, risk.Plan("A", "LONG", 100, 90, 120), st, 10.0)[0]     # stop uzak
    assert not risk.check(c, risk.Plan("A", "SHORT", 100, 101, 98), st, 10.0)[0]    # spot short yok
    assert not risk.check(c, ok, st, 6.0)[0]                                        # bakiye yetmez
    st["total_pnl"] = -3.0
    assert not risk.check(c, ok, st, 10.0)[0]                                       # kill-switch


def test_full_cycle_open_then_target_hit_net_includes_fees(tmp_path):
    c = cfg(tmp_path)
    client = FakeClient(spike_sym="AAAUSDT", price=101.5)
    ex = Executor(c, client, "paper")
    st = journal.load_state(str(tmp_path / "none.json"))
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    m.cycle(c, client, FakeLLM(GOOD), ex, "paper", st, now)
    assert "AAAUSDT" in st["positions"]
    client._price = 104.0   # hedef
    m.cycle(c, client, FakeLLM([]), ex, "paper", st, now)
    assert not st["positions"]
    rows = [json.loads(l) for l in open(c.journal_path)]
    close = [r for r in rows if r["kind"] == "close"][0]
    assert close["reason"] == "HEDEF" and close["net"] < close["gross"] and close["fees"] > 0


def test_stop_loss_triggers_and_counts(tmp_path):
    c = cfg(tmp_path)
    client = FakeClient(spike_sym="AAAUSDT", price=101.5)
    ex = Executor(c, client, "paper")
    st = journal.load_state(str(tmp_path / "none.json"))
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    m.cycle(c, client, FakeLLM(GOOD), ex, "paper", st, now)
    client._price = 100.0
    m.cycle(c, client, FakeLLM([]), ex, "paper", st, now)
    assert st["total_pnl"] < 0 and not st["positions"]


def test_price_drift_skips_entry(tmp_path):
    c = cfg(tmp_path)
    client = FakeClient(spike_sym="AAAUSDT", price=103.0)   # plan girişi 101.5, %1.5 saptı
    st = journal.load_state(str(tmp_path / "none.json"))
    m.cycle(c, client, FakeLLM(GOOD), Executor(c, client, "paper"), "paper", st,
            datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert not st["positions"]


def test_client_refuses_non_testnet():
    import pytest
    from binance_client import BinanceTestnet
    with pytest.raises(ValueError):
        BinanceTestnet("https://api.binance.com")


def test_cooldown_prevents_llm_call_after_close(tmp_path):
    c = cfg(tmp_path)
    client = FakeClient(spike_sym="AAAUSDT", price=101.5)
    ex = Executor(c, client, "paper")
    st = journal.load_state(str(tmp_path / "none.json"))
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    m.cycle(c, client, FakeLLM(GOOD), ex, "paper", st, now)
    client._price = 104.0
    llm = FakeLLM([])
    m.cycle(c, client, llm, ex, "paper", st, now)
    assert llm.calls == 0
