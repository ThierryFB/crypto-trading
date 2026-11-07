"""Offline test of the wake's order path: fake candles, fake Demo venue, fake Crypto Book and Paperclip.
Checks per-slice sizing, the risk refusals, the slice ledgers, the shadow books, per-slice overlay, idempotency,
the cross-slice coin cap, the v1 state migration and the Crypto Book rows.
Run: python3 test_wake.py
"""
import json, os, sys, tempfile, types
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
        FakeDemo.orders.append(dict(id=oid, sym=sym, side=side, qty=q, price=p, fill=fill, px=px, link=link))
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


def run_wake(cfg=None, **kw):
    a = types.SimpleNamespace(dry_run=False, skip=kw.get("skip", []), exit_early=kw.get("exit_early", []))
    cfg = cfg or runner.load_cfg(); st = runner.load_state(cfg); st["log_issue"] = "THE-TEST"
    rc = runner.wake(cfg, st, a)
    return rc, runner.load_state(cfg)


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        sys.exit(1)


SL = list(engine.SLICES)
SLICE_USDT = 2000 / 3


def by_slice(sl, sym=None, side=None):
    return [o for o in FakeDemo.orders if f"-{sl}-" in o["link"] and (sym is None or o["sym"] == sym) and (side is None or o["side"] == side)]


if __name__ == "__main__":
    FakeDemo.bal = {"USDT": 50000.0, "BTC": 1.0}; FakeDemo.fill_ratio = 1.0
    T0 = 1794096000 + 300  # 2026-11-08 00:05Z
    # wake 1: BTC, ETH, SOL, XRP, DOGE break out in every slice; SOL skipped in med only; 4 slots per slice
    CLOCK[0] = T0; setup({"BTCUSDT": 6, "ETHUSDT": 8, "SOLUSDT": 10, "XRPUSDT": 7, "DOGEUSDT": 5})
    rc, st = run_wake(skip=["med:SOLUSDT=test skip"])
    R, S = st["real"], st["shadow"]
    check(rc == 0, f"wake 1 rc 0 (got {rc})")
    top4 = {"SOLUSDT", "ETHUSDT", "XRPUSDT", "BTCUSDT"}
    check(all(set(S[sl]["pos"]) == top4 for sl in SL), "every shadow slice takes the 4 strongest")
    check(set(R["fast"]["pos"]) == top4 and set(R["slow"]["pos"]) == top4, "fast and slow take the 4 strongest")
    check(set(R["med"]["pos"]) == {"ETHUSDT", "XRPUSDT", "BTCUSDT"}, f"med skips SOL and does not promote DOGE: {sorted(R['med']['pos'])}")
    check(all("BTCUSDT" in R[sl]["pos"] for sl in SL) and len({R[sl]["pos"]["BTCUSDT"]["link_id"] for sl in SL}) == 3,
          "BTC held by all three slices as three separate positions")
    for sl in SL:
        for s, p in R[sl]["pos"].items():
            risk = (p["entry_px"] - p["stop"]) * p["qty"] / 0.999  # gross qty
            check(risk <= SLICE_USDT * 0.01 + 1e-4 and p["qty"] * p["entry_px"] <= SLICE_USDT * 0.25 + 1e-4,
                  f"{sl} {s}: risk ${risk:.2f} ≤ $6.67, value ${p['qty'] * p['entry_px']:.2f} ≤ $166.67")
        spent = sum(o["fill"] * o["px"] for o in by_slice(sl))
        check(abs(R[sl]["cash"] - (SLICE_USDT - spent)) < 1e-6, f"{sl} cash ledger {R[sl]['cash']:.2f} = $666.67 − its own fills")
    ent = [c for c in CB if c["side"] == "entry"]
    check(len(ent) == 11 and all(c["reason"].startswith(("[fast]", "[med]", "[slow]")) and c["book"] == "majors-breakout" for c in ent),
          f"11 Crypto Book entries, each tagged with its slice (got {len(ent)})")
    check(len(POSTS) == 1 and POSTS[0][0] == "/api/issues/THE-TEST/comments", "decision log posted")
    check(st["bh"] and st["overlay"][0] == {**st["overlay"][0], "slice": "med", "sym": "SOLUSDT", "kind": "skip"}, "benchmark started, overlay recorded with its slice")
    check("every coin covered" in POSTS[0][1]["body"], "demo balances reconciled to the sum of the slices")
    # same bar again: nothing
    n = len(FakeDemo.orders); rc, st = run_wake()
    check(len(FakeDemo.orders) == n and len(POSTS) == 1, "re-run of the same close places and posts nothing")
    # wake 2: BTC breaks down (exit in every slice), ETH early exit in fast only, 30% partial fills
    CLOCK[0] = T0 + 28800; setup({"BTCUSDT": -12, "ETHUSDT": 8.2, "XRPUSDT": 7.1, "SOLUSDT": 10.1, "DOGEUSDT": 5})
    FakeDemo.fill_ratio = 0.3
    rc, st = run_wake(exit_early=["fast:ETHUSDT=test early exit"])
    R = st["real"]
    check(all(R[sl]["pos"]["BTCUSDT"].get("exit_pending") for sl in SL), "BTC partial exits flagged for retry in every slice")
    check(R["fast"]["pos"]["ETHUSDT"].get("exit_pending") and not R["med"]["pos"]["ETHUSDT"].get("exit_pending")
          and not R["slow"]["pos"]["ETHUSDT"].get("exit_pending"), "fast's early exit leaves med's and slow's ETH alone")
    check("SOLUSDT" in R["med"]["pos"] and all("DOGEUSDT" not in R[sl]["pos"] and len(R[sl]["pos"]) == 4 for sl in SL),
          f"med fills its free slot with SOL; DOGE refused while exits incomplete: {[sorted(R[sl]['pos']) for sl in SL]}")
    check(all("ETHUSDT" in st["shadow"][sl]["pos"] and "BTCUSDT" not in st["shadow"][sl]["pos"] for sl in SL), "shadows keep ETH, exit BTC")
    # wake 3: full fills; the pending exits go out even though BTC no longer signals
    CLOCK[0] = T0 + 2 * 28800; setup({"BTCUSDT": 3, "ETHUSDT": 8.3, "XRPUSDT": 7.2, "SOLUSDT": 10.2})
    FakeDemo.fill_ratio = 1.0
    rc, st = run_wake(); R = st["real"]
    check(all("BTCUSDT" not in R[sl]["pos"] for sl in SL) and "ETHUSDT" not in R["fast"]["pos"] and "ETHUSDT" in R["med"]["pos"],
          f"pending exits completed per slice (open: {[sorted(R[sl]['pos']) for sl in SL]})")
    check([len(R[sl]["closed"]) for sl in SL] == [2, 1, 1], "closed: fast BTC+ETH, med BTC, slow BTC")
    ex = [c for c in CB if c["side"] == "exit"]
    check(len(ex) == 4 and all(c.get("entry_trade_id") for c in ex), "4 Crypto Book exits linked to entries")
    links = {c["entry_trade_id"] for c in ex}
    check(len(links) == 4, "each exit closes its own slice's entry")
    for sl in SL:
        btc = next(c for c in R[sl]["closed"] if c["sym"] == "BTCUSDT")
        xs = [o for o in by_slice(sl, "BTCUSDT", "Sell") if o["fill"]]
        vwap = sum(o["fill"] * o["px"] for o in xs) / sum(o["fill"] for o in xs)
        check(abs(btc["exit_px"] - vwap) < 1e-6, f"{sl} BTC exit price = VWAP of its own exit fills across wakes ({btc['exit_px']:.2f})")
    # wake 4: halt blocks everything
    st["halted"] = {"by": "Ingrid", "ref": "THE-TEST"}; runner.save_state(st)
    CLOCK[0] = T0 + 3 * 28800; setup({"XRPUSDT": -15}); n = len(FakeDemo.orders)
    rc, st = run_wake()
    check(len(FakeDemo.orders) == n and all("XRPUSDT" in st["real"][sl]["pos"] for sl in SL), "halted: XRP exits not placed in any slice")
    print(POSTS[-1][1]["body"])
    print()

    # cross-slice coin cap (if risk-policy.md sets one): at 15% of the sleeve, the third BTC position is refused
    runner.STATE_DIR = tempfile.mkdtemp(); CB.clear(); n = len(FakeDemo.orders)
    cfg = runner.load_cfg(); cfg["limits"]["max_coin_sleeve_nav"] = 0.15
    CLOCK[0] = T0 + 4 * 28800; setup({"BTCUSDT": 6})
    rc, st = run_wake(cfg)
    held = [sl for sl in SL if "BTCUSDT" in st["real"][sl]["pos"]]
    check(held == ["fast", "med"] and "across slices" in POSTS[-1][1]["body"], f"cross-slice BTC cap: held by {held}, slow refused")

    # v1 state: an idle single-speed ledger migrates; one with activity refuses to run
    runner.STATE_DIR = tempfile.mkdtemp(); cfg = runner.load_cfg()
    v1 = {"version": 1, "started": None, "real": runner.new_book(2000), "shadow": runner.new_book(2000), "bh": None, "last_bar": None,
          "day": None, "failed_wakes": 0, "halted": None, "log_issue": "THE-322", "cb_pending": [], "overlay": [], "test_orders": [], "wakes": 0}
    json.dump(v1, open(os.path.join(runner.STATE_DIR, "state.json"), "w"))
    m = runner.load_state(cfg)
    check(m["version"] == 2 and set(m["real"]) == set(SL) and abs(sum(b["cash"] for b in m["real"].values()) - 2000) < 1e-9
          and m["log_issue"] == "THE-322", "idle v1 state migrates to three $666.67 slices, keeps the log issue")
    v1["wakes"] = 1; json.dump(v1, open(os.path.join(runner.STATE_DIR, "state.json"), "w"))
    try:
        runner.load_state(cfg); check(False, "v1 with activity should refuse")
    except SystemExit:
        check(True, "v1 state with activity refuses to run")
