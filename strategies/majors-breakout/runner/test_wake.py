"""Offline test of the wake's order path: fake candles, fake Demo venue, fake Crypto Book and Paperclip.
Checks per-slice sizing, the risk refusals, the slice ledgers, the shadow books, per-slice overlay, idempotency,
the cross-slice coin cap (shrink / skip), catastrophe stops per slice-lot, lots-vs-venue reconciliation, the −10% day
halt, the HALT-issue check, failed-wake accounting, the v1 state migration and the Crypto Book rows.
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
    orders, stops = [], {}

    def __init__(self, *a):
        self.bal = FakeDemo.bal

    def balances(self, detail=False):
        return dict(self.bal)

    def stop_sell(self, sym, qty, trigger, link):
        if FakeDemo.reject_stops:
            raise bybit.BybitError("retCode 170130 stop orders not supported")
        oid = f"s{len(FakeDemo.stops)}"
        FakeDemo.stops[oid] = dict(sym=sym, qty=float(qty), trig=float(trigger), status="Untriggered", link=link, px=None)
        return oid

    def cancel(self, sym, oid, stop=False):
        o = FakeDemo.stops[oid]
        if o["status"] != "Untriggered":
            raise bybit.BybitError("retCode 170213 order does not exist")
        o["status"] = "Cancelled"; return {"orderId": oid}

    def stop_status(self, sym, oid):
        return {"orderStatus": FakeDemo.stops[oid]["status"]}

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
        if oid in FakeDemo.stops:
            o = FakeDemo.stops[oid]
            return [(o["qty"], o["px"], o["qty"] * o["px"] * 0.001, "USDT")] if o["status"] == "Filled" else []
        o = next(x for x in FakeDemo.orders if x["id"] == oid)
        if not o["fill"]:
            return []
        fee = o["fill"] * 0.001 if o["side"] == "Buy" else o["fill"] * o["px"] * 0.001
        return [(o["fill"], o["px"], fee, sym[:-4] if o["side"] == "Buy" else "USDT")]


def fire(oid, px):
    """The venue triggers a resting stop between wakes."""
    o = FakeDemo.stops[oid]; o.update(status="Filled", px=px)
    FakeDemo.bal[o["sym"][:-4]] -= o["qty"]; FakeDemo.bal["USDT"] += o["qty"] * px * 0.999


def live_stops(sym=None):
    return [o for o in FakeDemo.stops.values() if o["status"] == "Untriggered" and (sym is None or o["sym"] == sym)]


CB, POSTS, HALTS = [], [], []


def setup(breakout):
    runner.time = types.SimpleNamespace(time=lambda: CLOCK[0], sleep=lambda s: None)
    bybit.klines4h = lambda s, **k: candles(s, CLOCK[0], breakout)
    bybit.touch = lambda s, base=None: (PX[s] * 0.9999, PX[s] * 1.0001)
    bybit.instrument = lambda s, base=None: dict(base=s[:-4], tick="0.0000001", step="0.000001", min_qty=0.000001, min_amt=5.0, status="Trading")
    bybit.Demo = FakeDemo
    runner.creds = lambda cfg: ("k", "s")
    runner.merged_on_master = lambda: []
    runner.cb_post = lambda cfg, body: (CB.append(body), f"cb{len(CB)}")[1]
    runner.pc = fake_pc
    os.environ.setdefault("PAPERCLIP_COMPANY_ID", "test")


def fake_pc(m, p, b=None):
    if m == "GET":
        if HALTS == ["down"]:
            raise OSError("paperclip unreachable")
        return [dict(identifier="THE-X", title=h, status="todo") for h in HALTS]
    if POST_FAIL:
        raise OSError("paperclip unreachable")
    POSTS.append((p, b))


POST_FAIL = False


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
    FakeDemo.bal = {"USDT": 50000.0, "BTC": 1.0}; FakeDemo.fill_ratio = 1.0; FakeDemo.reject_stops = False
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
            check(risk <= SLICE_USDT * 0.0075 + 1e-4 and p["qty"] * p["entry_px"] <= SLICE_USDT * 0.25 + 1e-4,
                  f"{sl} {s}: risk ${risk:.2f} ≤ $5.00 (0.75% of slice), value ${p['qty'] * p['entry_px']:.2f} ≤ $166.67")
            c = p.get("cat") or {}
            check(c.get("id") in FakeDemo.stops and abs(c["qty"] - p["qty"]) < 1e-5 and abs(c["px"] - (p["entry_px"] - 4 * p["atr14"])) < 1e-6,
                  f"{sl} {s}: own resting stop {c.get('id')} for its lot at entry − 4×ATR")
        spent = sum(o["fill"] * o["px"] for o in by_slice(sl))
        check(abs(R[sl]["cash"] - (SLICE_USDT - spent)) < 1e-6, f"{sl} cash ledger {R[sl]['cash']:.2f} = $666.67 − its own fills")
    ent = [c for c in CB if c["side"] == "entry"]
    check(len(ent) == 11 and all(c["reason"].startswith(("[fast]", "[med]", "[slow]")) and c["book"] == "majors-breakout" for c in ent),
          f"11 Crypto Book entries, each tagged with its slice (got {len(ent)})")
    check(len(POSTS) == 1 and POSTS[0][0] == "/api/issues/THE-TEST/comments", "decision log posted")
    check(st["bh"] and st["overlay"][0] == {**st["overlay"][0], "slice": "med", "sym": "SOLUSDT", "kind": "skip"}, "benchmark started, overlay recorded with its slice")
    check("every coin adds up" in POSTS[0][1]["body"] and st["venue_base"]["BTC"] == 1.0, "baseline captured; venue = baseline + slice-lots")
    check(len(live_stops()) == 11 and len(live_stops("BTCUSDT")) == 3, "11 resting stops, 3 of them on BTC (one per slice-lot)")
    check(all(f"**Decision [{sl}]:**" in POSTS[0][1]["body"] for sl in SL), "the log has a decision line for every slice")
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
    eth = [R[sl]["pos"]["ETHUSDT"]["cat"]["id"] for sl in SL]
    check(FakeDemo.stops[eth[1]]["status"] == FakeDemo.stops[eth[2]]["status"] == "Untriggered" and R["fast"]["pos"]["ETHUSDT"]["cat"]["id"] not in eth[1:]
          and FakeDemo.stops[next(o for o in FakeDemo.stops if FakeDemo.stops[o]["link"].endswith("-fast-ETHUSDT-c"))]["status"] == "Cancelled",
          "fast cancels only its own ETH stop; med's and slow's stay resting")
    check(all(abs(R[sl]["pos"]["BTCUSDT"]["cat"]["qty"] - R[sl]["pos"]["BTCUSDT"]["qty"]) < 1e-5 for sl in SL),
          "after a partial exit each BTC lot gets a fresh stop for what is left")
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

    # a stop fires between wakes: that lot closes at the stop fill, the others on the coin are untouched, no re-entry
    xrp = {sl: st["real"][sl]["pos"]["XRPUSDT"]["cat"]["id"] for sl in SL}
    st["halted"] = None; runner.save_state(st)
    fill_px = PX["XRPUSDT"] * 0.85; fire(xrp["med"], fill_px)
    CLOCK[0] = T0 + 4 * 28800; setup({"XRPUSDT": 7.3, "ETHUSDT": 8.4, "SOLUSDT": 10.3}); n_cb = len(CB)
    rc, st = run_wake(); R = st["real"]
    check("XRPUSDT" not in R["med"]["pos"] and "XRPUSDT" in R["fast"]["pos"] and "XRPUSDT" in R["slow"]["pos"]
          and FakeDemo.stops[xrp["fast"]]["status"] == "Untriggered", "med's XRP lot closed by its stop; fast's and slow's XRP lots and stops untouched")
    xc = next(c for c in R["med"]["closed"] if c["sym"] == "XRPUSDT")
    check(abs(xc["exit_px"] - fill_px) < 1e-9 and "catastrophe" in xc["exit_why"]
          and any(c["side"] == "exit" and c["token_symbol"] == "XRP" for c in CB[n_cb:]), "exit at the stop fill, Crypto Book exit queued")
    check("every coin adds up" in POSTS[-1][1]["body"] and not st["halted"], "ledger still adds up to the venue after the stop fill")

    # lots vs venue mismatch is a halt
    FakeDemo.bal["ETH"] -= 0.01
    CLOCK[0] = T0 + 5 * 28800; setup({"ADAUSDT": 9}); n = len(FakeDemo.orders)
    rc, st = run_wake()
    check(st["halted"] and st["halted"]["by"] == "runner" and len(FakeDemo.orders) == n and "ETH venue" in POSTS[-1][1]["body"],
          "venue ≠ baseline + slice-lots: runner halts, nothing placed")
    FakeDemo.bal["ETH"] += 0.01

    def fresh(bal=None):
        runner.STATE_DIR = tempfile.mkdtemp(); FakeDemo.bal = dict(bal or {"USDT": 50000.0, "BTC": 1.0}); CB.clear()
        return runner.load_cfg()

    # cross-slice coin cap: shrink to fit, skip below 2% of sleeve NAV
    def btc_vals(st):
        return [st["real"][sl]["pos"]["BTCUSDT"]["qty"] * st["real"][sl]["pos"]["BTCUSDT"]["entry_px"] for sl in SL if "BTCUSDT" in st["real"][sl]["pos"]]
    cfg = fresh(); CLOCK[0] = T0 + 6 * 28800; setup({"BTCUSDT": 6}); rc, st = run_wake(cfg)
    v = btc_vals(st); one = v[0]
    check(len(v) == 3 and sum(v) <= 500 + 1e-6, f"default 25% cap: 3 BTC lots worth ${sum(v):.2f} ≤ $500")
    cfg = fresh(); cfg["limits"]["max_coin_sleeve_nav"] = (2 * one + 60) / 2000; rc, st = run_wake(cfg); v = btc_vals(st)
    check(len(v) == 3 and abs(v[2] - 60) < 1 and "shrunk" in POSTS[-1][1]["body"], f"cap leaves $60 for slow: shrunk to ${v[2]:.2f}")
    cfg = fresh(); cfg["limits"]["max_coin_sleeve_nav"] = (2 * one + 30) / 2000; rc, st = run_wake(cfg); v = btc_vals(st)
    check(len(v) == 2 and "SKIPPED by the coin cap" in POSTS[-1][1]["body"] and rc == 0, "cap leaves $30 < $40 (2% sleeve): slow skips, wake not failed")

    # open HALT issue: nothing placed; Paperclip down: no entries
    for h, what in ((["HALT — desk"], "open HALT — desk issue"), (["down"], "HALT check unreachable")):
        cfg = fresh(); HALTS[:] = h; n = len(FakeDemo.orders); rc, st = run_wake(cfg)
        check(len(FakeDemo.orders) == n and not any(b["pos"] for b in st["real"].values()), f"{what}: no buy placed")
    HALTS.clear()

    # −10% sleeve day: hard halt
    cfg = fresh(); CLOCK[0] = T0 + 7 * 28800; setup({"BTCUSDT": 6, "ETHUSDT": 8}); rc, st = run_wake(cfg)
    st["day"] = {"date": st["day"]["date"], "nav": 2400}; runner.save_state(st)
    CLOCK[0] = T0 + 8 * 28800; setup({"BTCUSDT": 6.1, "ETHUSDT": 8.1, "SOLUSDT": 9}); n = len(FakeDemo.orders)
    rc, st = run_wake(cfg)
    same_day = runner.utc(T0 + 8 * 28800 + 28800)[:10] == runner.utc(T0 + 7 * 28800 + 28800)[:10]
    check(not same_day or (st["halted"] and "hard halt" in st["halted"]["ref"] and len(FakeDemo.orders) == n), "sleeve ≥10% down on the day: runner halts")

    # Bybit rejects stops: the lot is flagged unprotected and the wake fails
    cfg = fresh(); FakeDemo.reject_stops = True; CLOCK[0] = T0 + 9 * 28800; setup({"BTCUSDT": 6}); rc, st = run_wake(cfg)
    check(rc == 1 and "catastrophe stop NOT placed" in POSTS[-1][1]["body"], "rejected stop: flagged, wake counted as failed")
    FakeDemo.reject_stops = False

    # a decision log that can't be posted counts as a failed wake
    cfg = fresh(); CLOCK[0] = T0 + 10 * 28800; setup({}); POST_FAIL = True; rc, st = run_wake(cfg); POST_FAIL = False
    check(rc == 2 and st["failed_wakes"] == 1, "log not posted: failed wake counted")

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
