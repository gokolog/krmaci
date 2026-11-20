"""Masa: Tarayıcı tetikler -> Haberci -> Stratejist <-> Şüpheci (en çok N tur) -> Karar Masası."""
from dataclasses import dataclass

import agents
from scanner import Anomaly


@dataclass
class Verdict:
    decision: str            # LONG | SHORT | BEKLE | GEÇ
    reason: str
    plan: dict | None
    transcript: list[dict]


def _fmt(transcript: list[dict]) -> str:
    return "\n".join(f"[{t['role']}] {t['content']}" for t in transcript)


def run(llm, an: Anomaly, klines: list[dict], max_rounds: int, web_search: bool) -> Verdict:
    tr: list[dict] = []

    def say(role, obj):
        tr.append({"role": role, "content": obj if isinstance(obj, str) else __import__("json").dumps(obj, ensure_ascii=False)})

    recent = [{"o": k["o"], "c": k["c"], "qv": round(k["qv"])} for k in klines[-12:]]
    say("TARAYICI", {"symbol": an.symbol, "price": an.price, "vol_z": an.vol_z,
                     "move_pct": an.move_pct, "direction": an.direction, "recent_candles": recent})

    # Haberci
    news = agents.parse_json(llm.ask(agents.HABERCI, _fmt(tr), web_search=web_search))
    say("HABERCİ", news)
    if not news.get("sources"):
        return Verdict("BEKLE", "Haberci kaynak gösteremedi", None, tr)

    # Stratejist <-> Şüpheci
    plan = None
    for _ in range(max_rounds):
        plan = agents.parse_json(llm.ask(agents.STRATEJIST, _fmt(tr)))
        say("STRATEJİST", plan)
        if plan.get("side", "NONE") == "NONE":
            return Verdict("GEÇ", "Stratejist plan çıkarmadı", None, tr)
        obj = agents.parse_json(llm.ask(agents.SUPHECI, _fmt(tr)))
        say("ŞÜPHECİ", obj)
        if not obj.get("blocking"):
            break

    final = agents.parse_json(llm.ask(agents.MASA, _fmt(tr)))
    say("MASA", final)
    decision = final.get("decision", "GEÇ")
    if decision not in ("LONG", "SHORT", "BEKLE", "GEÇ"):
        decision = "GEÇ"
    return Verdict(decision, final.get("reason", ""), plan if decision in ("LONG", "SHORT") else None, tr)
