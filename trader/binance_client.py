"""Binance Spot Testnet REST istemcisi. Para çekme endpoint'i YOK (bilerek)."""
import hashlib
import hmac
import time
from urllib.parse import urlencode

import requests


class BinanceTestnet:
    def __init__(self, base_url: str, api_key: str = "", api_secret: str = ""):
        if "testnet" not in base_url:
            raise ValueError("Güvenlik: yalnızca testnet URL'sine izin verilir.")
        self.base = base_url.rstrip("/")
        self.key = api_key
        self.secret = api_secret.encode()
        self.s = requests.Session()
        if api_key:
            self.s.headers["X-MBX-APIKEY"] = api_key

    # ---- public ----
    def klines(self, symbol: str, interval: str, limit: int = 100) -> list[dict]:
        r = self.s.get(f"{self.base}/api/v3/klines",
                       params={"symbol": symbol, "interval": interval, "limit": limit}, timeout=10)
        r.raise_for_status()
        return [{"t": k[0], "o": float(k[1]), "h": float(k[2]), "l": float(k[3]),
                 "c": float(k[4]), "v": float(k[5]), "qv": float(k[7])} for k in r.json()]

    def price(self, symbol: str) -> float:
        r = self.s.get(f"{self.base}/api/v3/ticker/price", params={"symbol": symbol}, timeout=10)
        r.raise_for_status()
        return float(r.json()["price"])

    # ---- signed ----
    def _signed(self, method: str, path: str, params: dict):
        params = {**params, "timestamp": int(time.time() * 1000), "recvWindow": 5000}
        q = urlencode(params)
        sig = hmac.new(self.secret, q.encode(), hashlib.sha256).hexdigest()
        r = self.s.request(method, f"{self.base}{path}?{q}&signature={sig}", timeout=10)
        r.raise_for_status()
        return r.json()

    def balance(self, asset: str = "USDT") -> float:
        acc = self._signed("GET", "/api/v3/account", {})
        for b in acc["balances"]:
            if b["asset"] == asset:
                return float(b["free"])
        return 0.0

    def market_buy_quote(self, symbol: str, quote_usdt: float) -> dict:
        return self._signed("POST", "/api/v3/order", {
            "symbol": symbol, "side": "BUY", "type": "MARKET",
            "quoteOrderQty": f"{quote_usdt:.2f}", "newOrderRespType": "FULL"})

    def market_sell_qty(self, symbol: str, qty: float) -> dict:
        return self._signed("POST", "/api/v3/order", {
            "symbol": symbol, "side": "SELL", "type": "MARKET",
            "quantity": f"{qty:.8f}".rstrip("0").rstrip("."), "newOrderRespType": "FULL"})
