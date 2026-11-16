#!/usr/bin/env python3
"""Offline checks of the ticket-driven runner (post → execute) against a fake Bybit Demo and a fake Paperclip:
L3, L9, L10, O1, O2, O3, O5, the order gate, halts, the Crypto Book rows and the shadow book. No network."""
import copy, json, os, sys, tempfile, types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ["MD_STATE_DIR"] = tempfile.mkdtemp()
os.environ.setdefault("PAPERCLIP_COMPANY_ID", "test")
import mdisc, execute as ex, tickets, shadow, inputs  # noqa: E402
from inputs import bybit, engine  # noqa: E402
import runner as mb  # noqa: E402

MERGED = ex.merged_gate  # the real one, before setup() fakes it

CLOCK = [tickets.ts("2026-11-16T08:06Z")]
PX = {"BTC": 64000.0, "ETH": 1800.0, "SOL": 70.0, "XRP": 0.9, "DOGE": 0.057, "ADA": 0.147}
F6 = {"BTC": 0.48, "ETH": 0.47, "SOL": 0.6, "XRP": 0.46, "DOGE": 0.47, "ADA": 0.46}


class Venue:
    def __init__(self, *a):
        pass

    def reset(self):
        self.bal = {"USDT": 50000.0, "DOGE": 3.0}
        self.orders, self.cond, self.reject_stop, self.reject_amend, self.fill_ratio = {}, {}, False, False, 1.0

    def query_api(self):
        return {"readOnly": 0, "permissions": {"Spot": ["SpotTrade"]}}

    def balances(self, detail=False):
        return dict(V.bal)

    def ioc_limit(self, sym, side, qty, price, link):
        c, q, p = sym[:-4], float(qty), float(price)
        bid, ask = bybit.touch(sym)
        fill = q * V.fill_ratio if (side == "Buy" and p >= ask) or (side == "Sell" and p <= bid) else 0.0
        px = ask if side == "Buy" else bid
        if side == "Buy":
            V.bal["USDT"] -= fill * px; V.bal[c] = V.bal.get(c, 0) + fill * 0.999
        else:
            V.bal[c] -= fill; V.bal["USDT"] += fill * px * 0.999
        oid = f"o{len(V.orders)}"
        V.orders[oid] = dict(sym=sym, side=side, qty=q, fill=fill, px=px, status="Filled" if fill == q else "Cancelled" if not fill else "PartiallyFilledCanceled")
        return oid

    def order(self, sym, oid):
        o = V.orders[oid]
        return {"orderStatus": o["status"], "cumExecQty": str(o["fill"]), "cumExecValue": str(o["fill"] * o["px"]), "cumExecFee": "0"}

    def fills(self, sym, oid):
        o = V.orders.get(oid) or V.cond.get(oid)
        if not o or not o["fill"]:
            return []
        fee, cur = (o["fill"] * 0.001, sym[:-4]) if o["side"] == "Buy" else (o["fill"] * o["px"] * 0.001, "USDT")
        return [(o["fill"], o["px"], fee, cur)]

    def stop_sell(self, sym, qty, trigger, link):
        if V.reject_stop:
            raise bybit.BybitError("retCode 170130 not supported")
        oid = f"s{len(V.cond)}"
        V.cond[oid] = dict(sym=sym, side="Sell", qty=float(qty), trig=float(trigger), status="Untriggered", fill=0.0, px=None, stop=True)
        return oid

    def limit_sell(self, sym, qty, price, link):
        oid = f"t{len(V.cond)}"
        V.cond[oid] = dict(sym=sym, side="Sell", qty=float(qty), trig=float(price), status="New", fill=0.0, px=None, stop=False)
        return oid

    def amend_stop(self, sym, oid, trigger):
        if V.reject_amend:
            raise bybit.BybitError("retCode 170213 amend not supported")
        V.cond[oid]["trig"] = float(trigger)

    def cancel(self, sym, oid, stop=False):
        o = V.cond[oid]
        if o["status"] not in ("Untriggered", "New"):
            raise bybit.BybitError("retCode 170213 order does not exist")
        o["status"] = "Cancelled"

    def stop_status(self, sym, oid):
        o = V.cond.get(oid)
        return {"orderStatus": o["status"]} if o else None


V = Venue()


def fire(oid, px):
    o = V.cond[oid]; o.update(status="Filled" if o["stop"] else "Filled", fill=o["qty"], px=px)
    c = o["sym"][:-4]; V.bal[c] -= o["qty"]; V.bal["USDT"] += o["qty"] * px * 0.999


def live(coin=None):
    return [o for o in V.cond.values() if o["status"] in ("Untriggered", "New") and (coin is None or o["sym"][:-4] == coin)]


COMMENTS, POSTS, CB, ISSUES = {}, [], [], {}
LEO, NADIA, INGRID = "leo-id", "61d8dff6-02c6-4a36-b985-22a5ffb4d96d", "20e2608c-49d2-407a-97f1-47280f505ea6"
PC_DOWN = [False]


def fake_pc(m, path, body=None):
    """Fake Paperclip: comments on any issue, issue create / read / search. PC_DOWN makes every call fail."""
    if PC_DOWN[0]:
        raise OSError("Paperclip unreachable")
    t = mdisc.ex.iso(CLOCK[0]).replace("+00:00", ".000Z")
    if m == "POST" and path.endswith("/issues"):
        iid = f"i{len(ISSUES)}"
        ISSUES[iid] = dict(dict(status="todo"), **body, id=iid, identifier=f"THE-{900 + len(ISSUES)}")
        return ISSUES[iid]
    if m == "POST":
        return comment(path.split("/")[3], body["body"], LEO)
    if "/issues?q=" in path:  # paged like Paperclip: limit / offset
        q = dict(x.split("=") for x in path.split("?")[1].split("&"))
        o, n = int(q.get("offset", 0)), int(q.get("limit", 10 ** 6))
        return [dict(i) for i in ISSUES.values()][o:o + n]
    if "/comments?" in path:  # oldest first; after includes the cursor comment, as the real API does
        q = dict(x.split("=") for x in path.split("?")[1].split("&"))
        cs = [c for c in COMMENTS.values() if c["issueId"] == path.split("/")[3]]
        o = next((k for k, c in enumerate(cs) if c["id"] == q.get("after")), 0)
        return cs[o:o + int(q.get("limit", 10 ** 6))]
    if "/comments/" in path:
        cid = path.rsplit("/", 1)[1]
        if cid not in COMMENTS:
            raise OSError("404")
        return COMMENTS[cid]
    return ISSUES[path.rsplit("/", 1)[1]]


def comment(issue, text, author):
    cid = f"c{len(COMMENTS)}"
    t = mdisc.ex.iso(CLOCK[0]).replace("+00:00", ".000Z")
    COMMENTS[cid] = dict(id=cid, issueId=issue if issue in ISSUES else None, body=text, createdAt=t, updatedAt=t, authorAgentId=author)
    if issue == "THE-334":
        POSTS.append(text)
    return COMMENTS[cid]


def halt_issue(title="HALT — desk"):
    iid = f"i{len(ISSUES)}"
    ISSUES[iid] = dict(id=iid, identifier=f"THE-{900 + len(ISSUES)}", title=title, status="todo")
    return iid


def candles(sym, now):
    """Flat 4h history around PX with a small wiggle: enough for engine.levels, no breakout."""
    p, out = PX[sym[:-4]], []
    t0 = int(now // 14400) * 14400 - 999 * 14400
    for i in range(1000):
        w = p * (1 + 0.01 * ((i % 7) - 3) / 3)
        out.append((t0 + i * 14400, w, w * 1.005, w * 0.995, w))
    return out


def setup():
    V.reset()
    mdisc.time = ex.time = types.SimpleNamespace(time=lambda: CLOCK[0], sleep=lambda s: None)
    mb.time = types.SimpleNamespace(time=lambda: CLOCK[0], sleep=lambda s: None)
    bybit.touch = lambda s, base=None: (PX[s[:-4]] * 0.9999, PX[s[:-4]] * 1.0001)
    bybit.instrument = lambda s, base=None: dict(base=s[:-4], tick="0.0000001", step="0.000001", min_qty=0.000001, min_amt=5.0, status="Trading")
    bybit.klines4h = lambda s, **k: candles(s, CLOCK[0])
    bybit.Demo = Venue
    mb.creds = lambda cfg: ("k", "s")
    mb.pc = fake_pc
    mb.cb_post = lambda cfg, body: (CB.append(body), f"cb{len(CB)}")[1]
    ex.merged_gate = lambda: []
    inputs.collect = lambda U, now=None: dict(t=CLOCK[0], coins={c: dict(mid=PX[c], up24_90d=0.5) for c in PX}, perp={}, hist={}, errors=[])
    inputs.render = lambda D: "(inputs)"
    for f in os.listdir(os.environ["MD_STATE_DIR"]):
        os.remove(os.path.join(os.environ["MD_STATE_DIR"], f))
    COMMENTS.clear(); POSTS.clear(); CB.clear(); ISSUES.clear(); PC_DOWN[0] = False
    json.dump({"stop_test": {"ok": True}}, open(os.path.join(os.environ["MD_STATE_DIR"], "state.json"), "w"))


def entry(**kw):
    t = {"type": "entry", "coin": "SOL", "risk_usd": 12.0, "entry": "touch", "stop": 66.0, "target": 76.0, "forecast_24h": 0.6,
         "thesis": {"why_now": "w", "invalidated_if": "i", "sources": [{"what": "a", "url": "u", "at": ex.iso(CLOCK[0] - 600)}]}}
    t.update(kw)
    return t


def wake(tickets_=None, review=None, no_trade="nothing to do", forecasts_=None):
    p = os.path.join(os.environ["MD_STATE_DIR"], "wake.json")
    json.dump({"read": "r", "forecasts": forecasts_ or F6, "review": review or {}, "tickets": tickets_ or [],
               "no_trade": no_trade if not tickets_ else ""}, open(p, "w"))
    return p


def run(cmd, path=None, expect_exit=False):
    a = types.SimpleNamespace(wake=path, dry_run=False, no_post=False)
    cfg = mdisc.load_cfg(); st = mdisc.load_state(cfg)
    try:
        rc = {"post": mdisc.cmd_post, "execute": mdisc.cmd_execute}[cmd](cfg, st, a)
    except SystemExit as e:
        assert expect_exit, f"unexpected exit: {e}"
        return str(e), mdisc.load_state(cfg)
    assert not expect_exit, "expected the command to refuse"
    return rc, mdisc.load_state(cfg)


N = [0]


def check(cond, msg):
    assert cond, msg
    N[0] += 1


def at(s):
    CLOCK[0] = tickets.ts(s)


def main():
    # 1. post then execute an entry: ticket in the log first, IOC at the touch, resting stop, Crypto Book row
    setup(); at("2026-11-16T08:06Z")
    rc, st = run("post", wake([entry()]))
    t_id = "T-20261116-0805-1"
    check(t_id in st["tickets"] and st["tickets"][t_id]["status"] == "pending", "ticket recorded as pending")
    check(len(st["forecasts"]) == 6, "six forecasts recorded at post")
    check(ex.tickets_in(POSTS[-1])[t_id]["coin"] == "SOL" and "Pre-check: OK" in POSTS[-1], "ticket JSON + pre-check in the log")
    at("2026-11-16T08:07Z")
    rc, st = run("execute")
    lot = st["lots"].get("L-0001")
    check(lot and 11.5 < lot["qty"] * (lot["entry_px"] - lot["stop"]) <= 12, "sized from the stop at the limit: ≤ $12 at risk")
    check(st["tickets"][t_id]["status"] == "placed" and V.orders["o0"]["side"] == "Buy", "IOC buy placed")
    check(len(live("SOL")) == 1 and 0 <= lot["qty"] - live("SOL")[0]["qty"] < 1e-6 + 1e-12, "L3: one resting stop for the lot")
    check(CB and CB[0]["side"] == "entry" and CB[0]["book"] == "majors-discretionary" and lot["cb_id"] == "cb1", "Crypto Book entry")
    check(st["started"] and st["shadow"] and st["bh"], "paper clock, shadow book and BTC benchmark start at the first order")
    check("bought" in POSTS[-1] and "resting stop-market" in POSTS[-1], "fills comment posted")
    check(st["week"]["cost"] > 0, "L8: fee and slippage counted")

    # 2. the resting stop fires between wakes: the lot closes at its fill, exit row links to the entry
    sid = lot["stop_order"]["id"]
    fire(sid, 65.9)
    at("2026-11-16T14:36Z")
    rc, st = run("post", wake())
    rc, st = run("execute")
    check("L-0001" not in st["lots"] and st["closed"][-1]["exit_why"].startswith("stop"), "stop fill closes the lot")
    check(CB[-1]["side"] == "exit" and CB[-1]["entry_trade_id"] == "cb1", "Crypto Book exit linked to its entry")
    check(not live(), "nothing left resting")

    # 3. exit ticket: the lot's own stop is cancelled first, then the IOC sell
    setup(); at("2026-11-16T08:06Z"); run("post", wake([entry()])); at("2026-11-16T08:07Z"); run("execute")
    at("2026-11-16T14:36Z")
    rc, st = run("post", wake([{"type": "exit", "coin": "SOL", "lot": "L-0001", "fraction": 1.0, "reason": "thesis broken"}],
                              review={"L-0001": "exit"}))
    rc, st = run("execute")
    check(not st["lots"] and not live() and V.bal["SOL"] < 1e-5, "exit: stop cancelled, lot sold, no stop left")
    check(st["closed"][-1]["exit_why"] == "thesis broken" and CB[-1]["side"] == "exit", "exit recorded")

    # 4. a review is required for every open lot
    setup(); at("2026-11-16T08:06Z"); run("post", wake([entry()])); at("2026-11-16T08:07Z"); run("execute")
    at("2026-11-16T14:36Z")
    msg, _ = run("post", wake(), expect_exit=True)
    check("no review for L-0001" in msg, "post refused without a position review")

    # 5. adjust: amend the stop up; when amend is refused, the new stop goes in before the old is cancelled
    rc, st = run("post", wake([{"type": "adjust", "coin": "SOL", "lot": "L-0001", "stop": 68.0, "reason": "trail"}], review={"L-0001": "hold"}))
    rc, st = run("execute")
    check(st["lots"]["L-0001"]["stop"] == 68.0 and abs(live("SOL")[0]["trig"] - 68.0) < 1e-6 and len(live("SOL")) == 1, "stop amended up")
    V.reject_amend = True
    at("2026-11-17T00:06Z")
    run("post", wake([{"type": "adjust", "coin": "SOL", "lot": "L-0001", "stop": 69.0, "reason": "trail"}], review={"L-0001": "hold"}))
    rc, st = run("execute")
    check(len(live("SOL")) == 1 and abs(live("SOL")[0]["trig"] - 69.0) < 1e-6, "amend refused: replaced, still exactly one stop")

    # 6. O3: an edited log comment is refused and halts; a changed ticket is refused
    setup(); at("2026-11-16T08:06Z"); run("post", wake([entry()]))
    cid = next(iter(COMMENTS)); COMMENTS[cid]["updatedAt"] = "2026-11-16T08:06:30.000Z"
    rc, st = run("execute")
    check(not st["lots"] and "edited" in st["tickets"]["T-20261116-0805-1"]["result"] and st["halted"], "O3 edit: refused and halted")
    setup(); at("2026-11-16T08:06Z"); run("post", wake([entry()]))
    cid = next(iter(COMMENTS)); COMMENTS[cid]["body"] = COMMENTS[cid]["body"].replace('"risk_usd": 12.0', '"risk_usd": 15.0')
    rc, st = run("execute")
    check(not st["lots"] and "differs" in st["tickets"]["T-20261116-0805-1"]["result"], "O3 content change: refused")

    # 7. order gate not met: nothing placed, the reason logged
    setup(); ex.merged_gate = lambda: ["strategies/majors-discretionary/runner/execute.py not on master"]
    at("2026-11-16T08:06Z"); run("post", wake([entry()]))
    check("Order gate:** not met" in POSTS[-1] and "definition (forecast-only)" in POSTS[-1], "post shows the gate")
    rc, st = run("execute")
    check(not st["lots"] and not V.orders and "order gate not met" in st["tickets"]["T-20261116-0805-1"]["result"], "gate: no order")
    setup()
    at("2026-11-16T08:06Z"); run("post", wake([entry()]))
    st = mdisc.load_state(mdisc.load_cfg()); st["stop_test"] = None; mdisc.save_state(st)
    rc, st = run("execute")
    check(not V.orders and "stop-market test" in st["tickets"]["T-20261116-0805-1"]["result"], "gate: stop test required")

    # 8. a ticket placed more than 60 min after its log expires
    setup(); at("2026-11-16T08:06Z"); run("post", wake([entry()])); at("2026-11-16T09:07Z")
    rc, st = run("execute")
    check(st["tickets"]["T-20261116-0805-1"]["status"] == "expired" and not V.orders, "ticket expires after 60 min")

    # 9. HALT issue: entries refused; a discretionary exit needs Nadia's or Ingrid's request
    setup(); at("2026-11-16T08:06Z"); run("post", wake([entry()])); at("2026-11-16T08:07Z"); run("execute")
    desk = halt_issue()
    at("2026-11-16T14:36Z")
    run("post", wake([entry(coin="BTC", stop=62000.0, target=70000.0, forecast_24h=0.55),
                      {"type": "exit", "coin": "SOL", "lot": "L-0001", "reason": "r"}], review={"L-0001": "x"},
                     forecasts_=dict(F6, BTC=0.55)))
    rc, st = run("execute")
    check("halted" in st["tickets"]["T-20261116-1435-1"]["result"], "halt: entry refused")
    check("request_ref" in st["tickets"]["T-20261116-1435-2"]["result"] and "L-0001" in st["lots"], "halt: exit needs a request")
    check(len(live("SOL")) == 1, "halt: the resting stop stays")
    leo_c = comment(desk, "please let me exit", LEO)["id"]
    at("2026-11-17T00:06Z")
    run("post", wake([{"type": "exit", "coin": "SOL", "lot": "L-0001", "reason": "r", "requested_by": "Nadia", "request_ref": leo_c}],
                     review={"L-0001": "x"}))
    rc, st = run("execute")
    check("not a comment by Nadia or Ingrid" in st["tickets"]["T-20261117-0005-1"]["result"] and "L-0001" in st["lots"],
          "halt: an exit request has to be Nadia's or Ingrid's comment on the HALT issue")
    nadia_c = comment(desk, "exit SOL", NADIA)["id"]
    at("2026-11-17T08:06Z")
    run("post", wake([{"type": "exit", "coin": "SOL", "lot": "L-0001", "reason": "r", "requested_by": "Nadia", "request_ref": nadia_c}],
                     review={"L-0001": "x"}))
    rc, st = run("execute")
    check(not st["lots"] and not live(), "halt: an exit Nadia asked for on the HALT issue runs")

    # 10. O2: a balance that doesn't add up halts the runner
    setup(); at("2026-11-16T08:06Z"); run("post", wake([entry()])); at("2026-11-16T08:07Z"); run("execute")
    V.bal["SOL"] += 0.5
    at("2026-11-16T14:36Z"); run("post", wake(review={"L-0001": "hold"}))
    rc, st = run("execute")
    check(st["halted"] and "O2" in st["halted"]["ref"], "O2 mismatch halts")

    # 11. O5: a refused stop leaves the lot flagged and the wake failed
    setup(); V.reject_stop = True
    at("2026-11-16T08:06Z"); run("post", wake([entry()])); at("2026-11-16T08:07Z")
    rc, st = run("execute")
    check(rc == 1 and st["wakes"][-1]["failed"] and "NO resting stop" in POSTS[-1], "O5: unprotected lot fails the wake")
    check(st["halted"] and st["halted"]["code"].startswith("O5") and "L-0001" in st["halted"]["ref"], "O5: no stop after the retry halts")
    hi = st["halted"]["issue"]
    check(hi and ISSUES[hi["id"]]["title"].startswith("HALT — majors-discretionary") and ISSUES[hi["id"]]["assigneeAgentId"] == NADIA
          and "NO resting stop" in ISSUES[hi["id"]]["description"], "O5: HALT issue opened, assigned to Nadia, with the evidence")
    check("L-0001" in POSTS[-1] and hi["identifier"] in POSTS[-1], "O5: the fills comment names the lot and the halt issue")

    # 12. O1: a missed wake then an on-time one resets; a missed wake then a late one is two in a row: halt
    setup(); at("2026-11-16T08:06Z"); run("post", wake())
    at("2026-11-17T00:06Z"); run("post", wake())  # the 14:35 wake was missed
    st = mdisc.load_state(mdisc.load_cfg())
    check(st["wakes"][-2].get("missed") and mdisc.streak(st) == 0 and not st["halted"], "missed then on time: streak reset")
    at("2026-11-17T15:41Z"); run("post", wake())  # 08:05 missed, 14:35 posted 66 min late
    st = mdisc.load_state(mdisc.load_cfg())
    check(mdisc.streak(st) == 2 and st["halted"] and "O1" in st["halted"]["ref"], "O1: two failed wakes in a row halt")
    check("LATE" in POSTS[-1] and "Missed wakes" in POSTS[-1], "late and missed wakes are said in the log")

    # 13. one post per wake
    msg, _ = run("post", wake(), expect_exit=True)
    check("already posted" in msg, "a wake posts once")

    # 14. the shadow book acts on 8h closes after it starts and never touches the venue
    sh = shadow.new(2000, 0, "t")
    bars = {s: engine.bars8h(candles(s, CLOCK[0]), CLOCK[0]) for s in ("BTCUSDT", "SOLUSDT")}
    k = sorted(bars["BTCUSDT"])
    bars["SOLUSDT"][k[-1]] = [72.0, 80.0, 72.0, 80.0]  # a breakout on the last close
    sh["last_bar"] = k[-2]
    n0 = len(V.orders)
    moves = shadow.step(sh, bars, 0.0015)
    check(any("buy SOL" in m for m in moves) and len(V.orders) == n0 and sh["last_bar"] == k[-1], "shadow: buys the breakout, no order")

    # 16. D3 latches: it holds after NAV recovers and after the day rolls over
    setup(); at("2026-11-16T08:06Z"); run("post", wake([entry()])); at("2026-11-16T08:07Z"); run("execute")
    st = mdisc.load_state(mdisc.load_cfg()); st["cash"] -= 450; st["venue_base"]["USDT"] += 450; mdisc.save_state(st)  # NAV ≈ $1,550
    at("2026-11-16T14:36Z"); run("post", wake(review={"L-0001": "hold"})); rc, st = run("execute")
    check(st["halted"] and st["halted"]["code"] == "D3" and st["halted"]["issue"], "D3: NAV ≤ $1,600 halts and opens the issue")
    st["cash"] += 450; st["venue_base"]["USDT"] -= 450; mdisc.save_state(st)  # NAV back near $2,000
    at("2026-11-17T00:06Z"); run("post", wake([entry(coin="BTC", stop=62000.0, target=70000.0, forecast_24h=0.55)], review={"L-0001": "hold"},
                                               forecasts_=dict(F6, BTC=0.55)))
    rc, st = run("execute")
    check(st["halted"]["code"] == "D3" and "D3" in st["tickets"]["T-20261117-0005-1"]["result"] and len(ISSUES) == 1,
          "D3: still halted after NAV recovers and the day rolls; one issue, not a new one per run")

    # 17. D2 latches: a ≥ 10% day loss holds into the next day
    setup(); at("2026-11-16T08:06Z"); run("post", wake([entry()])); at("2026-11-16T08:07Z"); run("execute")
    st = mdisc.load_state(mdisc.load_cfg()); st["day"]["nav"] = 2300.0; mdisc.save_state(st)  # as if NAV had been $2,300 at 00:00
    at("2026-11-16T14:36Z"); run("post", wake(review={"L-0001": "hold"})); rc, st = run("execute")
    check(st["halted"] and st["halted"]["code"] == "D2", "D2: day loss ≥ 10% halts")
    at("2026-11-17T00:06Z"); run("post", wake(review={"L-0001": "hold"})); rc, st = run("execute")
    check(st["halted"]["code"] == "D2" and st["day"]["date"] == "2026-11-17", "D2: still halted on the next UTC day")

    # 18. resume: refused while a HALT issue is open, refused on anyone's comment but Nadia's, then allowed
    cfg = mdisc.load_cfg()
    hid = st["halted"]["issue"]["id"]

    def resume(ref):
        st_ = mdisc.load_state(cfg)
        try:
            mdisc.cmd_resume(cfg, st_, types.SimpleNamespace(ref=ref, rebaseline=False))
        except SystemExit as e:
            return str(e)
        return None
    msg = resume(comment(hid, "I resume", LEO)["id"])
    check(msg and "not Nadia's comment" in msg, "resume: Leo's own comment is refused")
    ISSUES[hid]["status"] = "done"
    at("2026-11-17T00:10Z"); early = comment(hid, "ack, waiting for Ingrid", NADIA)["id"]
    msg = resume(early)
    check(msg and "no written review by Ingrid" in msg and mdisc.load_state(cfg)["halted"],
          "resume: Nadia's comment with no review by Ingrid is refused, even with the issue closed")
    at("2026-11-17T00:20Z"); comment(hid, "Review: cause found, fixed; OK to resume", INGRID)
    msg = resume(early)
    check(msg and "no written review by Ingrid" in msg, "resume: Nadia's comment posted before Ingrid's review is refused")
    ISSUES[hid]["status"] = "todo"
    at("2026-11-17T00:30Z"); msg = resume(comment(hid, "Resumed after Ingrid's review", NADIA)["id"])
    check(msg and "still open" in msg and mdisc.load_state(cfg)["halted"], "resume: refused while the HALT issue is open")
    other = halt_issue("HALT — majors-discretionary: other"); ok_elsewhere = comment(other, "Resumed", NADIA)["id"]
    msg = resume(ok_elsewhere)
    check(msg and "not Nadia's comment on" in msg, "resume: Nadia's comment on a different issue is refused")
    ISSUES[other]["status"] = "done"
    ISSUES[hid]["status"] = "done"; desk = halt_issue()
    msg = resume(comment(hid, "Resumed", NADIA)["id"])
    check(msg and "THE-" in msg and "still open" in msg, "resume: refused while HALT — desk is open")
    ISSUES[desk]["status"] = "done"
    for k in range(150):  # more than a page of HALT search results and of comments: both are read to the end
        ISSUES[f"x{k}"] = dict(id=f"x{k}", identifier=f"THE-{2000 + k}", title=f"old {k}", status="done")
        comment(hid, f"noise {k}", LEO)
    desk2 = halt_issue()
    msg = resume(comment(hid, "Resumed", NADIA)["id"])
    check(msg and ISSUES[desk2]["identifier"] in msg, "halt_issues: a HALT — desk issue past the first page of the search is found")
    ISSUES[desk2]["status"] = "done"
    check(resume(comment(hid, "Resumed", NADIA)["id"]) is None and not mdisc.load_state(cfg)["halted"],
          "resume: Ingrid's review, then Nadia's comment, issues closed; more than a page of comments is read")
    PC_DOWN[0] = True
    st = mdisc.load_state(cfg); mdisc.latch(cfg, st, "manual:x", "manual halt by Ingrid: x", "x", CLOCK[0]); mdisc.save_state(st)
    PC_DOWN[0] = False
    check(resume("whatever") and "no HALT issue yet" not in (resume("whatever") or "") and mdisc.load_state(cfg)["halted"]["issue"],
          "a halt issue that couldn't be opened is opened at the next try, and resume still refuses")

    # 18b. no Demo credentials while a lot is open: its stop can't be checked, so O5 halts
    setup(); at("2026-11-16T08:06Z"); run("post", wake([entry()])); at("2026-11-16T08:07Z"); run("execute")
    mb.creds = lambda cfg_: None
    at("2026-11-16T14:36Z"); run("post", wake(review={"L-0001": "hold"})); rc, st = run("execute")
    mb.creds = lambda cfg_: ("k", "s")
    check(st["halted"] and st["halted"]["code"] == "O5-creds" and st["halted"]["issue"], "O5: no credentials with a lot open halts")

    # 19. O2 cash: a USDT balance that doesn't add up halts
    setup(); at("2026-11-16T08:06Z"); run("post", wake([entry()])); at("2026-11-16T08:07Z"); run("execute")
    V.bal["USDT"] += 5.0
    at("2026-11-16T14:36Z"); run("post", wake(review={"L-0001": "hold"})); rc, st = run("execute")
    check(st["halted"] and st["halted"]["code"] == "O2" and "USDT" in st["halted"]["evidence"], "O2: a USDT mismatch halts")

    # 20. a held coin with no price: NAV unknown, entries refused, O2 halt
    setup(); at("2026-11-16T08:06Z"); run("post", wake([entry()])); at("2026-11-16T08:07Z"); run("execute")
    at("2026-11-16T14:36Z")
    run("post", wake([entry(coin="BTC", stop=62000.0, target=70000.0, forecast_24h=0.55)], review={"L-0001": "hold"}, forecasts_=dict(F6, BTC=0.55)))
    good = bybit.touch
    bybit.touch = lambda s_, base=None: (_ for _ in ()).throw(OSError("timeout")) if s_ == "SOLUSDT" else good(s_)
    rc, st = run("execute")
    bybit.touch = good
    check(mdisc.nav(st, {"BTC": 1.0}) is None and st["halted"]["code"] == "O2-nav", "missing mid: NAV unknown is an O2 halt")
    check("BTC" not in {l["coin"] for l in st["lots"].values()} and "NAV can't be computed" in st["tickets"]["T-20261116-1435-1"]["result"],
          "missing mid: the entry is refused")

    # 21. the day's NAV is the 00:00 book at the 00:00 candle opens, even when the first run of the day is the 08:05 wake
    th = {"why_now": "w", "invalidated_if": "i", "sources": [{"what": "a", "url": "u", "at": "2026-11-15T14:00Z"}]}
    setup(); at("2026-11-15T14:36Z"); run("post", wake([entry(thesis=th)])); at("2026-11-15T14:37Z"); run("execute")
    t00, o = tickets.ts("2026-11-16T00:00Z"), 66.5  # SOL opened the day at 66.5; the 08:06 mid is 70
    bybit.klines4h = lambda s_, **k: [(t, o, h, l, c) if t == t00 and s_ == "SOLUSDT" else (t, o_, h, l, c)
                                      for t, o_, h, l, c in candles(s_, CLOCK[0])]
    at("2026-11-16T08:06Z"); rc, st0 = run("post", wake(review={"L-0001": "hold"}))  # the 00:05 wake was missed
    lot = st0["lots"]["L-0001"]
    check(abs(st0["day"]["nav"] - (st0["cash"] + lot["qty"] * o)) < 1e-9 and st0["day"]["how"] == "00:00 UTC marks" and o != PX["SOL"],
          "day NAV marked at the 00:00 open, not the first NAV seen")

    # 22. test-order: refused under a halt, when Paperclip can't be read, and from unmerged code
    def test_order():
        st_ = mdisc.load_state(cfg)
        try:
            mdisc.cmd_test_order(cfg, st_, types.SimpleNamespace(usdt=18, symbol="DOGEUSDT"))
        except SystemExit as e:
            return str(e)
    setup(); halt_issue()
    check("refused" in test_order() and not V.orders, "test-order: refused while HALT — desk is open")
    setup(); PC_DOWN[0] = True
    check("could not check for HALT" in test_order() and not V.orders, "test-order: refused if Paperclip can't be read")
    setup(); ex.merged_gate = lambda: ["O7: runner differs from origin/master"]
    check("O7" in test_order() and not V.orders, "test-order: refused from unmerged code")

    # 23. the HALT issues are re-read before every buy: a halt opened after the first entry stops the second
    setup(); at("2026-11-16T08:06Z")
    run("post", wake([entry(), entry(coin="BTC", stop=62000.0, target=70000.0, forecast_24h=0.55)], forecasts_=dict(F6, BTC=0.55)))
    orig = ex.do_entry
    ex.do_entry = lambda *a_: (halt_issue(), orig(*a_))[1]
    at("2026-11-16T08:07Z"); rc, st = run("execute")
    ex.do_entry = orig
    check("L-0001" in st["lots"] and "halted" in st["tickets"]["T-20261116-0805-2"]["result"], "halt check before each buy")

    # 24. O7: a failed git fetch refuses instead of comparing with a stale origin/master
    sub = ex.subprocess
    ex.subprocess = types.SimpleNamespace(run=lambda c, **k: types.SimpleNamespace(returncode=1 if "fetch" in c else 0, stdout="/r\n", stderr="no network"))
    miss = MERGED()
    ex.subprocess = sub
    check(len(miss) == 1 and "fetch" in miss[0], "O7: stale master refused")

    # 15. backfill parses a hand-posted wake log
    body = ("## Wake Sun 15 Nov 00:05Z: Majors Discretionary, definition phase (forecast-only)\n\n"
            "| Coin | Bybit mid | 24h | Up-24h 90d |\n|---|---|---|---|\n| BTC | 64,047.6 | −6.1% | 51% |\n| ETH | 1,766.82 | −8% | 50% |\n"
            "| SOL | 70.235 | x | 49% |\n| XRP | 0.91765 | x | 45% |\n| DOGE | 0.057255 | x | 50% |\n| ADA | 0.1473 | x | 49% |\n\n"
            "### Forecasts\n| BTC | ETH | SOL | XRP | DOGE | ADA |\n|---|---|---|---|---|---|\n| 0.48 | 0.47 | 0.47 | 0.46 | 0.47 | 0.46 |\n")
    t, F, mids, base = mdisc.parse_wake(body, "2026")
    check(t == tickets.ts("2026-11-15T00:05Z") and F["BTC"] == 0.48 and mids["BTC"] == 64047.6 and base["XRP"] == 0.45, "backfill parse")
    print(f"{N[0]} execution checks pass")


if __name__ == "__main__":
    main()
