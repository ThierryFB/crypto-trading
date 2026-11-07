"""Offline test of the wake's order path: fake candles, fake Demo venue, fake Crypto Book and Paperclip.
Checks sizing, the risk refusals, the ledger, the shadow book, overlay, idempotency and the Crypto Book rows.
Run: python3 test_wake.py
"""
import os, sys, tempfile, types
os.environ["MB_STATE_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bybit, engine, runner

U = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT"]
CLOCK = [0.0]
PX = {}  # sym -> last price


def candles(sym, now, breakout):
    """180 flat-ish 4h candles at 100 (sym-scaled), ending at the last closed bar; optional breakout/breakdown on the last bar."""
    scale = {"BTCUSDT": 1000, "ETHUSDT": 50, "SOLUSDT": 2, "XRPUSDT": 0.02, "DOGEUSDT": 0.002, "ADAUSDT": 0.005}[sym]
    last = int(now // 14400 * 14400) - 14400
    rows = []
    for i in range(400):
        t = last - (399 - i) * 14400
        c = 100 + (i % 7) * 0.5
        rows.append((t, c, c + 1, c - 1, c))
    m = breakout.get(sym, 0)
    if m:
        t = rows[-1][0]; c = 100 + m
        rows[-1] = (t, rows[-2][4], max(c, rows[-2][4]) + 0.5, min(c, rows[-2][4]) - 0.5, c)
    PX[sym] = rows[-1][4] * scale
    return [(t, o * scale, h * scale, l * scale, c * scale) for t, o, h, l, c in rows]


class FakeDemo:
    orders = []

    def __init__(self, *a):
        self.bal = FakeDemo.bal

    def balances(self):
        return dict(self.bal)

    def ioc_limit(self, sym, side, qty, price, link):
        bid, ask = PX[sym] * 0.9999, PX[sym] * 1.0001
        q, p = float(qty), float(price)
        fill = q * FakeDemo.fill_ratio if (side == "Buy" and p >= ask) or (side == "Sell" and p <= bid) else 0.0
        px = ask if side == "Buy" else bid
        base = sym[:-4]
        if side == "Buy":
            self.bal["USDT"] -= fill * px; self.bal[base] = self.bal.get(base, 0) + fill * 0.999
        else:
            self.bal[base] -= fill; self.bal["USDT"] += fill * px * 0.999
        oid = f"o{len(FakeDemo.orders)}"
        FakeDemo.orders.append(dict(id=oid, sym=sym, side=side, qty=q, price=p, fill=fill, px=px))
        return oid

    def order(self, sym, oid):
        o = next(x for x in FakeDemo.orders if x["id"] == oid)
        return {"orderStatus": "Filled" if o["fill"] == o["qty"] else "PartiallyFilledCanceled" if o["fill"] else "Cancelled",
                "cumExecQty": str(o["fill"]), "cumExecValue": str(o["fill"] * o["px"]), "cumExecFee": "0"}

    def fills(self, sym, oid):
        o = next(x for x in FakeDemo.orders if x["id"] == oid)
        if not o["fill"]:
            return []
        fee = o["fill"] * 0.001 if o["side"] == "Buy" else o["fill"] * o["px"] * 0.001
        return [(o["fill"], o["px"], fee, sym[:-4] if o["side"] == "Buy" else "USDT")]


CB, POSTS = [], []


def setup(breakout):
    runner.time = types.SimpleNamespace(time=lambda: CLOCK[0], sleep=lambda s: None)
    bybit.klines4h = lambda s, **k: candles(s, CLOCK[0], breakout)
    bybit.touch = lambda s, base=None: (PX[s] * 0.9999, PX[s] * 1.0001)
    bybit.instrument = lambda s, base=None: dict(base=s[:-4], tick="0.0000001", step="0.000001", min_qty=0.000001, min_amt=5.0, status="Trading")
    bybit.Demo = FakeDemo
    runner.creds = lambda cfg: ("k", "s")
    runner.merged_on_master = lambda: []
    runner.cb_post = lambda cfg, body: (CB.append(body), f"cb{len(CB)}")[1]
    runner.pc = lambda m, p, b=None: POSTS.append((p, b))


def run_wake(**kw):
    a = types.SimpleNamespace(dry_run=False, skip=kw.get("skip", []), exit_early=kw.get("exit_early", []))
    cfg = runner.load_cfg(); st = runner.load_state(cfg); st["log_issue"] = "THE-TEST"
    rc = runner.wake(cfg, st, a)
    return rc, runner.load_state(cfg)


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        sys.exit(1)


if __name__ == "__main__":
    FakeDemo.bal = {"USDT": 50000.0, "BTC": 1.0}; FakeDemo.fill_ratio = 1.0
    T0 = 1794096000 + 300  # 2026-11-08 00:05Z
    # wake 1: BTC, ETH, SOL, XRP, DOGE break out; SOL skipped by overlay; only 4 slots
    CLOCK[0] = T0; setup({"BTCUSDT": 6, "ETHUSDT": 8, "SOLUSDT": 10, "XRPUSDT": 7, "DOGEUSDT": 5})
    rc, st = run_wake(skip=["SOLUSDT=test skip"])
    r, sh = st["real"], st["shadow"]
    check(rc == 0, f"wake 1 rc 0 (got {rc})")
    check(set(sh["pos"]) == {"SOLUSDT", "ETHUSDT", "XRPUSDT", "BTCUSDT"}, f"shadow takes 4 strongest: {sorted(sh['pos'])}")
    check(set(r["pos"]) == {"ETHUSDT", "XRPUSDT", "BTCUSDT"}, f"real skips SOL and does not promote DOGE: {sorted(r['pos'])}")
    nav = 2000
    for s, p in r["pos"].items():
        risk = (p["entry_px"] - p["stop"]) * p["qty"] / 0.999  # gross qty
        check(risk <= 20.0001 and p["qty"] * p["entry_px"] <= 500.0001, f"{s}: risk ${risk:.2f} ≤ $20, value ${p['qty'] * p['entry_px']:.2f} ≤ $500")
    check(abs(r["cash"] - (2000 - sum(o["fill"] * o["px"] for o in FakeDemo.orders))) < 1e-6, f"cash ledger {r['cash']:.2f}")
    check(len([c for c in CB if c["side"] == "entry"]) == 3, "3 Crypto Book entries")
    check(len(POSTS) == 1 and POSTS[0][0] == "/api/issues/THE-TEST/comments", "decision log posted")
    check(st["bh"] and st["overlay"][0]["sym"] == "SOLUSDT", "benchmark started, overlay recorded")
    # same bar again: nothing
    n = len(FakeDemo.orders); rc, st = run_wake()
    check(len(FakeDemo.orders) == n and len(POSTS) == 1, "re-run of the same close places and posts nothing")
    # wake 2: BTC breaks down (exit), ETH early exit by overlay, 30% partial fills
    CLOCK[0] = T0 + 28800; setup({"BTCUSDT": -12, "ETHUSDT": 8.2, "XRPUSDT": 7.1, "SOLUSDT": 10.1, "DOGEUSDT": 5})
    FakeDemo.fill_ratio = 0.3
    rc, st = run_wake(exit_early=["ETHUSDT=test early exit"])
    r = st["real"]
    check(r["pos"]["BTCUSDT"].get("exit_pending") and r["pos"]["ETHUSDT"].get("exit_pending"), "3 partial IOCs: BTC and ETH remainders flagged for retry")
    check("DOGEUSDT" not in r["pos"] and len(r["pos"]) == 4, f"DOGE refused while exits incomplete (4-position limit): {sorted(r['pos'])}")
    check("ETHUSDT" in st["shadow"]["pos"] and "BTCUSDT" not in st["shadow"]["pos"], "shadow keeps ETH, exits BTC")
    # wake 3: full fills; the pending exits go out even though BTC no longer signals
    CLOCK[0] = T0 + 2 * 28800; setup({"BTCUSDT": 3, "ETHUSDT": 8.3, "XRPUSDT": 7.2, "SOLUSDT": 10.2})
    FakeDemo.fill_ratio = 1.0
    rc, st = run_wake(); r = st["real"]
    check("BTCUSDT" not in r["pos"] and "ETHUSDT" not in r["pos"] and len(r["closed"]) == 2, f"pending exits completed (open: {sorted(r['pos'])})")
    check(len([c for c in CB if c["side"] == "exit"]) == 2 and all(c.get("entry_trade_id") for c in CB if c["side"] == "exit"), "2 Crypto Book exits linked to entries")
    btc = next(c for c in r["closed"] if c["sym"] == "BTCUSDT")
    xs = [o for o in FakeDemo.orders if o["sym"] == "BTCUSDT" and o["side"] == "Sell" and o["fill"]]
    vwap = sum(o["fill"] * o["px"] for o in xs) / sum(o["fill"] for o in xs)
    check(abs(btc["exit_px"] - vwap) < 1e-6, f"BTC exit price = VWAP of all its exit fills across wakes ({btc['exit_px']:.2f})")
    navs = runner.book_nav(r, {s: p["mark"] for s, p in r["pos"].items()})
    print(f"real NAV {navs:.2f}, cash {r['cash']:.2f}, dust {r['dust']}")
    # wake 3: halt blocks everything
    st["halted"] = {"by": "Ingrid", "ref": "THE-TEST"}; runner.save_state(st)
    CLOCK[0] = T0 + 3 * 28800; setup({"XRPUSDT": -15}); n = len(FakeDemo.orders)
    rc, st = run_wake()
    check(len(FakeDemo.orders) == n and "XRPUSDT" in st["real"]["pos"], "halted: XRP exit signal not placed")
    print(POSTS[-1][1]["body"])
