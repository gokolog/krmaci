"""Yürütücü: paper (sahte dolum) ya da testnet (gerçek testnet emri). Çıkışları (stop/hedef) döngü izler."""
from config import Config


class Executor:
    def __init__(self, cfg: Config, client, mode: str):
        assert mode in ("paper", "testnet")
        self.cfg, self.client, self.mode = cfg, client, mode

    def open_long(self, symbol: str, quote_usdt: float, ref_price: float) -> dict:
        """Dönen: {qty, price, fee_usdt}"""
        if self.mode == "paper":
            px = ref_price * (1 + self.cfg.slippage_pct / 100)
            qty = (quote_usdt / px)
            return {"qty": qty, "price": px, "fee_usdt": quote_usdt * self.cfg.fee_rate}
        o = self.client.market_buy_quote(symbol, quote_usdt)
        qty = float(o["executedQty"])
        spent = float(o["cummulativeQuoteQty"])
        fee = sum(_fee_usdt(f, symbol, spent / qty) for f in o.get("fills", []))
        return {"qty": qty, "price": spent / qty, "fee_usdt": fee}

    def close_long(self, symbol: str, qty: float, ref_price: float) -> dict:
        if self.mode == "paper":
            px = ref_price * (1 - self.cfg.slippage_pct / 100)
            return {"price": px, "fee_usdt": qty * px * self.cfg.fee_rate}
        o = self.client.market_sell_qty(symbol, qty)
        got = float(o["cummulativeQuoteQty"])
        eq = float(o["executedQty"])
        fee = sum(_fee_usdt(f, symbol, got / eq) for f in o.get("fills", []))
        return {"price": got / eq, "fee_usdt": fee}


def _fee_usdt(fill: dict, symbol: str, px: float) -> float:
    c, asset = float(fill["commission"]), fill["commissionAsset"]
    if asset == "USDT":
        return c
    if symbol.startswith(asset):      # base asset ile ödenmiş
        return c * px
    return c * float(fill.get("price", px)) if asset != "BNB" else 0.0  # BNB: yaklaşık, ihmal
