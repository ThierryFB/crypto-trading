"""Minimal Bybit V5 client: public market data (keyless) and signed spot orders on Bybit Demo.
Credentials are read by the caller and passed in; this module never prints or stores them.
"""
import hashlib, hmac, json, time, urllib.parse, urllib.request

MAINNET = "https://api.bybit.com"
DEMO = "https://api-demo.bybit.com"


class BybitError(Exception):
    pass


def _req(url, data=None, headers=None, timeout=20):
    r = urllib.request.Request(url, data=data, headers={"User-Agent": "majors-breakout-runner", **(headers or {})})
    with urllib.request.urlopen(r, timeout=timeout) as f:
        d = json.load(f)
    if d.get("retCode") != 0:
        raise BybitError(f"{url.split('?')[0]}: retCode {d.get('retCode')} {d.get('retMsg')}")
    return d["result"]


def public(path, base=MAINNET, **q):
    return _req(f"{base}{path}?{urllib.parse.urlencode(q)}")


def klines4h(sym, base=MAINNET, limit=1000):
    """[(start_s, o, h, l, c)] oldest first, forming candle included (engine.bars8h drops it)."""
    L = public("/v5/market/kline", base, category="spot", symbol=sym, interval="240", limit=limit)["list"]
    return sorted((int(r[0]) // 1000, *map(float, r[1:5])) for r in L)


def touch(sym, base=DEMO):
    t = public("/v5/market/tickers", base, category="spot", symbol=sym)["list"][0]
    return float(t["bid1Price"]), float(t["ask1Price"])


def instrument(sym, base=DEMO):
    L = public("/v5/market/instruments-info", base, category="spot", symbol=sym)["list"]
    if not L:
        raise BybitError(f"{sym} is not a spot instrument on {base}")
    i = L[0]
    f = i["lotSizeFilter"]
    return dict(base=i["baseCoin"], tick=i["priceFilter"]["tickSize"], step=f["basePrecision"],
                min_qty=float(f["minOrderQty"]), min_amt=float(f["minOrderAmt"]), status=i["status"])


class Demo:
    def __init__(self, key, secret, base=DEMO, recv=5000):
        self._k, self._s, self.base, self.recv = key, secret, base, str(recv)

    def _signed(self, method, path, params):
        ts = str(int(time.time() * 1000))
        if method == "GET":
            payload = urllib.parse.urlencode(params); url = f"{self.base}{path}?{payload}"; data = None
        else:
            payload = json.dumps(params, separators=(",", ":")); url = f"{self.base}{path}"; data = payload.encode()
        sign = hmac.new(self._s.encode(), (ts + self._k + self.recv + payload).encode(), hashlib.sha256).hexdigest()
        h = {"X-BAPI-API-KEY": self._k, "X-BAPI-TIMESTAMP": ts, "X-BAPI-RECV-WINDOW": self.recv,
             "X-BAPI-SIGN": sign, "Content-Type": "application/json"}
        return _req(url, data, h)

    def balances(self, detail=False):
        """{coin: walletBalance} of the unified demo account; detail=True gives {coin: {wallet, locked}}."""
        r = self._signed("GET", "/v5/account/wallet-balance", {"accountType": "UNIFIED"})
        out = {}
        for a in r.get("list", []):
            for c in a.get("coin", []):
                w = float(c.get("walletBalance") or 0)
                out[c["coin"]] = dict(wallet=w, locked=float(c.get("locked") or 0)) if detail else w
        return out

    def stop_sell(self, sym, qty, trigger, link_id):
        """Resting spot conditional order: market sell of qty (base coin) once the price trades at or below trigger."""
        r = self._signed("POST", "/v5/order/create", {
            "category": "spot", "symbol": sym, "side": "Sell", "orderType": "Market", "qty": qty,
            "marketUnit": "baseCoin", "triggerPrice": trigger, "orderFilter": "StopOrder", "orderLinkId": link_id})
        return r["orderId"]

    def cancel(self, sym, order_id, stop=False):
        p = {"category": "spot", "symbol": sym, "orderId": order_id}
        if stop:
            p["orderFilter"] = "StopOrder"
        return self._signed("POST", "/v5/order/cancel", p)

    def stop_status(self, sym, order_id):
        """Current record of a conditional order (untriggered, triggered or done), or None if Bybit has no record."""
        for path, extra in (("/v5/order/realtime", {"orderFilter": "StopOrder"}), ("/v5/order/realtime", {}), ("/v5/order/history", {})):
            L = self._signed("GET", path, {"category": "spot", "symbol": sym, "orderId": order_id, **extra}).get("list", [])
            if L:
                return L[0]
        return None

    def query_api(self):
        """Read-only: the key's own record (permissions, readOnly flag). Callers must not print the key.
        Not served on Bybit EU Demo (404): use account_info there."""
        return self._signed("GET", "/v5/user/query-api", {})

    def account_info(self):
        """Read-only signed check that works on Bybit EU Demo: the account's margin mode and status."""
        return self._signed("GET", "/v5/account/info", {})

    def executions(self, start_ms, end_ms, category="spot"):
        """Every execution on the account in [start_ms, end_ms], oldest window first. Bybit allows 7 days per query, so
        the range is walked in 7-day windows, each paged by cursor. Raises on any error (callers fail closed)."""
        out, week = [], 7 * 86400 * 1000 - 1
        t = start_ms
        while t <= end_ms:
            e, cur = min(t + week, end_ms), None
            while True:
                q = {"category": category, "startTime": str(t), "endTime": str(e), "limit": "100"}
                if cur:
                    q["cursor"] = cur
                r = self._signed("GET", "/v5/execution/list", q)
                out += r.get("list", [])
                cur = r.get("nextPageCursor")
                if not cur or not r.get("list"):
                    break
            t = e + 1
        return out

    def cash_balance(self, coin):
        """The coin's balance after its latest entry in the unified transaction log, or None if the log has no entry.
        Read-only. Bybit EU Demo serves no wallet-balance route; whether it fills this log is what test-order finds out."""
        L = self._signed("GET", "/v5/account/transaction-log", {"accountType": "UNIFIED", "currency": coin, "limit": "1"}).get("list", [])
        return float(L[0]["cashBalance"]) if L and L[0].get("cashBalance") not in (None, "") else None

    def amend_stop(self, sym, order_id, trigger):
        """Move a resting conditional order's trigger price."""
        return self._signed("POST", "/v5/order/amend", {"category": "spot", "symbol": sym, "orderId": order_id,
                                                        "triggerPrice": trigger, "orderFilter": "StopOrder"})

    def limit_sell(self, sym, qty, price, link_id):
        """Resting GTC limit sell (a ticket's target), post-only so it never takes."""
        r = self._signed("POST", "/v5/order/create", {
            "category": "spot", "symbol": sym, "side": "Sell", "orderType": "Limit", "qty": qty,
            "price": price, "timeInForce": "PostOnly", "orderLinkId": link_id})
        return r["orderId"]

    def ioc_limit(self, sym, side, qty, price, link_id):
        r = self._signed("POST", "/v5/order/create", {
            "category": "spot", "symbol": sym, "side": side, "orderType": "Limit", "qty": qty,
            "price": price, "timeInForce": "IOC", "orderLinkId": link_id})
        return r["orderId"]

    def order(self, sym, order_id, tries=6):
        """Final state of an order: realtime first (recent closed orders), then history."""
        for i in range(tries):
            for path in ("/v5/order/realtime", "/v5/order/history"):
                L = self._signed("GET", path, {"category": "spot", "symbol": sym, "orderId": order_id}).get("list", [])
                if L and L[0]["orderStatus"] not in ("New", "PartiallyFilled", "Untriggered", "Created"):
                    return L[0]
            time.sleep(0.5 * (i + 1))
        raise BybitError(f"order {order_id} not final after {tries} polls")

    def fills(self, sym, order_id):
        """[(qty, price, fee, fee_coin, execId)] for an order; falls back to the order's cum fields if executions are empty."""
        try:
            L = self._signed("GET", "/v5/execution/list", {"category": "spot", "symbol": sym, "orderId": order_id}).get("list", [])
        except BybitError:
            L = []
        return [(float(e["execQty"]), float(e["execPrice"]), float(e["execFee"] or 0), e.get("feeCurrency", ""), e.get("execId", "")) for e in L]
