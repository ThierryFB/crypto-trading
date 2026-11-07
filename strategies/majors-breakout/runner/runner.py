#!/usr/bin/env python3
"""Majors Breakout runner: order placement for this strategy only (strategy.md §3, §6-§9). Three slices
(fast 10/5, med 20/10, slow 40/20), each its own ledger, positions and shadow book; one demo account.

  runner.py wake --dry-run                     compute the wake's decision, place nothing, save nothing
  runner.py wake [--skip [SLICE:]SYM=why] [--exit-early [SLICE:]SYM=why]
                                               act on the candle that just closed: orders on Bybit Demo,
                                               slice ledgers, shadow books, BTC benchmark, decision log, Crypto Book
  runner.py test-order [--symbol DOGEUSDT --usdt 18]
                                               small buy, two resting stops (one cancelled alone), sell-back, probe; outside the sleeve
  runner.py status | halt --by NAME --ref ISSUE | resume --by NAME --ref ISSUE [--rebaseline] | set-log-issue ISSUE

State lives in $MB_STATE_DIR (default: Leo's persistent workspace), never in the repo.
Credentials come from env or Paperclip secrets (config.json "credentials") and are never printed or stored.
"""
import argparse, datetime as dt, fcntl, json, os, subprocess, sys, time, urllib.request
from decimal import Decimal, ROUND_DOWN, ROUND_UP

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import engine, bybit  # noqa: E402

STATE_DIR = os.environ.get("MB_STATE_DIR",
                           "/paperclip/instances/default/workspaces/a3ae5ff4-6eb6-4daa-9169-f2568b7087ba/majors-breakout-state")
MAX_WAKE_DELAY = 2 * 3600  # a wake later than this after its close places no orders (strategy.md §6)
LOG_DEADLINE = 65 * 60  # wakes are scheduled at close + 5 min; no log within 60 min of that = failed wake (THE-320)


# ---------- small helpers ----------

def utc(t):
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d %H:%MZ")


def rnd(x, step, mode):
    s = Decimal(str(step))
    return (Decimal(str(x)) / s).to_integral_value(rounding=mode) * s


def fmt(x, d=6):
    return f"{x:,.{d}g}" if abs(x) < 1000 else f"{x:,.2f}"


def load_cfg():
    return json.load(open(os.path.join(HERE, "config.json")))


def new_book(cash):
    return {"cash": cash, "pos": {}, "dust": {}, "closed": []}


def new_books(cfg):
    """{slice: book}, the sleeve split equally between the slices (strategy.md §3)."""
    return {sl: new_book(cfg["sleeve_usdt"] / len(engine.SLICES)) for sl in engine.SLICES}


def book_nav(b, marks):
    return b["cash"] + sum(p["qty"] * marks[s] for s, p in b["pos"].items()) + \
        sum(q * marks.get(s, 0) for s, q in b["dust"].items())


def books_nav(B, marks):
    return sum(book_nav(b, marks) for b in B.values())


def load_state(cfg):
    p = os.path.join(STATE_DIR, "state.json")
    if os.path.exists(p):
        st = json.load(open(p))
        if st.get("version") == 1:  # single-speed ledger, before the 3-speed change (THE-321)
            idle = st["wakes"] == 0 and not st["cb_pending"] and all(not st[k]["pos"] and not st[k]["closed"] for k in ("real", "shadow"))
            if not idle:
                sys.exit("state.json is a v1 ledger with activity: migrate it by hand before running the 3-speed runner")
            st.update(version=2, real=new_books(cfg), shadow=new_books(cfg))
        return st
    return {"version": 2, "started": None, "real": new_books(cfg), "shadow": new_books(cfg),
            "bh": None, "last_bar": None, "day": None, "failed_wakes": 0, "halted": None, "log_issue": cfg.get("log_issue"),
            "cb_pending": [], "overlay": [], "test_orders": [], "wakes": 0}


def save_state(st):
    os.makedirs(STATE_DIR, exist_ok=True)
    p = os.path.join(STATE_DIR, "state.json")
    with open(p + ".tmp", "w") as f:
        json.dump(st, f, indent=1)
    os.replace(p + ".tmp", p)


def lock():
    os.makedirs(STATE_DIR, exist_ok=True)
    f = open(os.path.join(STATE_DIR, "lock"), "w")
    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)  # raises if another wake is running
    return f


# ---------- Paperclip, Crypto Book, credentials ----------

def pc_base():
    b = os.environ.get("PAPERCLIP_API_URL", "").rstrip("/")
    return b[:-4] if b.endswith("/api") else b


def pc(method, path, body=None):
    h = {"Authorization": f"Bearer {os.environ['PAPERCLIP_API_KEY']}", "Content-Type": "application/json"}
    if os.environ.get("PAPERCLIP_RUN_ID"):
        h["X-Paperclip-Run-Id"] = os.environ["PAPERCLIP_RUN_ID"]
    r = urllib.request.Request(pc_base() + path, data=json.dumps(body).encode() if body is not None else None,
                               headers=h, method=method)
    with urllib.request.urlopen(r, timeout=20) as f:
        return json.load(f)


def creds(cfg):
    c = cfg["credentials"]
    k, s = os.environ.get(c["env_key"]), os.environ.get(c["env_secret"])
    if k and s:
        return k, s
    try:
        k = pc("POST", f"/api/agents/me/secrets/{c['paperclip_secret_key']}/value", {}).get("value")
        s = pc("POST", f"/api/agents/me/secrets/{c['paperclip_secret_secret']}/value", {}).get("value")
        return (k, s) if k and s else None
    except Exception:
        return None


def cb_post(cfg, body):
    r = urllib.request.Request(cfg["crypto_book_url"] + "/api/crypto-book/trades", data=json.dumps(body).encode(),
                               headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(r, timeout=20) as f:
        return json.load(f)["trade"]["id"]


def cb_flush(cfg, st, notes):
    """POST queued Crypto Book rows. Exits wait for their entry's id. Failures stay queued for the next wake."""
    keep = []
    rows = [p for b in st["real"].values() for p in b["closed"] + list(b["pos"].values())]
    for item in st["cb_pending"]:
        body = dict(item["body"])
        if body["side"] == "exit":
            eid = item.get("entry_id") or next((c["cb_id"] for c in rows if c.get("link_id") == item["entry_link"] and c.get("cb_id")), None)
            if not eid:
                keep.append(item); continue
            body["entry_trade_id"] = eid
        try:
            tid = cb_post(cfg, body)
            if body["side"] == "entry":
                for p in rows:
                    if p.get("link_id") == item["link"]:
                        p["cb_id"] = tid
            notes.append(f"Crypto Book [{item.get('slice', '?')}] {body['side']} {body['token_symbol']} recorded (`{tid}`)")
        except Exception as e:
            keep.append(item); notes.append(f"Crypto Book [{item.get('slice', '?')}] {body['side']} {body['token_symbol']} **not recorded** ({e}); retried next wake")
    st["cb_pending"] = keep


def halt_issues(cfg):
    """Open issues titled 'HALT — majors-breakout' / 'HALT — desk' (risk policy: checked before every order).
    Raises if Paperclip can't be read; the caller fails closed."""
    norm = lambda t: " ".join(t.lower().replace("–", "—").replace(" - ", " — ").split())
    want = [norm(t) for t in cfg["limits"]["halt_issue_titles"]]
    d = pc("GET", f"/api/companies/{os.environ['PAPERCLIP_COMPANY_ID']}/issues?q=HALT")
    L = d if isinstance(d, list) else d["issues"]
    return [f"{i['identifier']} {i['title']}" for i in L
            if i.get("status") not in ("done", "cancelled") and any(norm(i["title"]).startswith(w) for w in want)]


def merged_on_master():
    """Tradable only when strategy.md and risk-policy.md are on origin/master (AGENTS.md first rule)."""
    try:
        top = subprocess.run(["git", "-C", HERE, "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True).stdout.strip()
        subprocess.run(["git", "-C", top, "fetch", "-q", "origin", "master"], capture_output=True, timeout=60)
        out = subprocess.run(["git", "-C", top, "ls-tree", "--name-only", "origin/master", "strategies/majors-breakout/"],
                             capture_output=True, text=True).stdout.split()
        return [f for f in ("strategy.md", "risk-policy.md") if f"strategies/majors-breakout/{f}" not in out]
    except Exception as e:
        return [f"git check failed: {e}"]


# ---------- orders ----------

def limit_px(side, bid, ask, inst, off):
    if side == "Buy":
        return max(rnd(ask * (1 + off), inst["tick"], ROUND_DOWN), Decimal(str(ask)))
    return min(rnd(bid * (1 - off), inst["tick"], ROUND_UP), Decimal(str(bid)))


def place(demo, sym, side, qty, px, link):
    """IOC limit; returns dict(filled, avg, fee_usdt, fee_coin_qty, order_id, status, ms)."""
    t0 = time.time()
    oid = demo.ioc_limit(sym, side, format(Decimal(qty), "f"), format(Decimal(px), "f"), link)
    o = demo.order(sym, oid)
    F = demo.fills(sym, oid)
    if F:
        q = sum(f[0] for f in F); cost = sum(f[0] * f[1] for f in F)
        fee_base = sum(f[2] for f in F if f[3] and f[3] != "USDT"); fee_q = sum(f[2] for f in F if f[3] == "USDT")
    else:
        q = float(o.get("cumExecQty") or 0); cost = float(o.get("cumExecValue") or 0); fee = float(o.get("cumExecFee") or 0)
        fee_base, fee_q = (fee, 0.0) if side == "Buy" else (0.0, fee)  # Bybit spot: buy fees in base coin, sell fees in quote
    avg = cost / q if q else 0.0
    return dict(order_id=oid, status=o["orderStatus"], filled=q, avg=avg, cost=cost, fee_base=fee_base, fee_quote=fee_q,
                fee_usdt=fee_q + fee_base * avg, ms=int((time.time() - t0) * 1000), fills=len(F))


def check_entry(cfg, b, sym, qty, px, stop, nav, n_after, usdt_avail, inst, gates, coin_other=0.0, sleeve_nav=None):
    """Every reason this buy would break a limit. Empty list = allowed. b and nav are the slice's;
    coin_other is the value of this coin held by the other slices, sleeve_nav the whole sleeve's NAV."""
    L, v = cfg["limits"], float(qty) * float(px)
    bad = list(gates)
    if sym not in cfg["universe"]: bad.append("not in universe")
    if sym in b["pos"]: bad.append("already held by this slice")
    if n_after > L["max_positions"]: bad.append(f"{n_after} positions in the slice > {L['max_positions']}")
    if float(px) <= stop: bad.append("limit price at or below stop")
    if float(qty) * (float(px) - stop) > L["risk_per_trade_nav"] * nav * (1 + 1e-9): bad.append(f"risk at stop > {L['risk_per_trade_nav']:.0%} slice NAV")
    if v > L["max_position_nav"] * nav * (1 + 1e-9): bad.append(f"position > {L['max_position_nav']:.0%} slice NAV")
    cap = L.get("max_coin_sleeve_nav")
    if cap is not None and sleeve_nav and coin_other + v > cap * sleeve_nav * (1 + 1e-9):
        bad.append(f"{sym[:-4]} across slices ${coin_other + v:.2f} > {cap:.0%} sleeve NAV")
    if v > b["cash"] + 1e-9: bad.append(f"needs ${v:.2f}, slice cash ${b['cash']:.2f}")
    if usdt_avail is not None and v > usdt_avail: bad.append(f"demo USDT {usdt_avail:.2f} < ${v:.2f}")
    if float(qty) < inst["min_qty"] or v < inst["min_amt"]: bad.append(f"below venue minimum (${v:.2f})")
    return bad


def entry_qty(cfg, w, nav, cash, px, stop, inst, coin_other=0.0, sleeve_nav=None):
    """bt_active.py sizing (weight × slice NAV, capped at slice cash), trimmed so the risk and position limits hold at the
    limit price, then shrunk to fit the cross-slice coin cap (THE-320). Returns (qty, note); qty 0 = skipped by the cap."""
    L, px = cfg["limits"], float(px)
    val = min(w * nav, cash)
    q = val / px
    if px > stop:
        q = min(q, L["risk_per_trade_nav"] * nav / (px - stop))
    q = min(q, L["max_position_nav"] * nav / px)
    note, cap = None, L.get("max_coin_sleeve_nav")
    if cap is not None and sleeve_nav and q * px > cap * sleeve_nav - coin_other:
        room, floor = cap * sleeve_nav - coin_other, L.get("min_entry_sleeve_nav", 0) * sleeve_nav
        if room < floor:
            return Decimal(0), f"coin cap: other slices hold ${coin_other:.2f}, room ${max(room, 0):.2f} < ${floor:.2f} ({L.get('min_entry_sleeve_nav', 0):.0%} sleeve NAV): skipped"
        note = f"coin cap: shrunk ${q * px:.2f} → ${room:.2f} to keep the coin ≤ {cap:.0%} of sleeve NAV across slices"
        q = room / px
    return rnd(max(q, 0), inst["step"], ROUND_DOWN), note


STOP_LIVE = ("Untriggered", "New", "Created", "Active")  # a resting conditional order that hasn't fired


def settle(cfg, st, rb, sl, s, p, why, px_ref, inst):
    """After sell fills on a slice-lot: an unsellable remainder becomes dust; a fully sold lot is closed and its
    Crypto Book exit queued. Returns True if the lot closed."""
    if p.get("exit_fills") and 0 < p["qty"] and (p["qty"] * px_ref < inst["min_amt"] or p["qty"] < inst["min_qty"]):
        rb["dust"][s] = rb["dust"].get(s, 0) + p["qty"]; p["qty"] = 0  # still marked in NAV
    if p["qty"] > 0:
        return False
    xf = p.pop("exit_fills"); q = sum(x[0] for x in xf)
    p.pop("exit_pending", None)
    p.update(sym=s, slice=sl, exit_px=sum(x[0] * x[1] for x in xf) / q, exit_t=utc(time.time()), exit_why=why,
             exit_fee_usdt=sum(x[2] for x in xf))
    rb["closed"].append(p); del rb["pos"][s]
    st["cb_pending"].append({"entry_link": p["link_id"], "slice": sl, "body": {
        "side": "exit", "book": cfg["strategy"], "token_symbol": s.replace("USDT", ""), "trader": cfg["trader"],
        "trade_date": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "exit_price": f"{p['exit_px']:.10g}", "reason": f"[{sl}] {why}"}})
    return True


# ---------- the wake ----------

def parse_overlay(kvs, notes, kind):
    """'SLICE:SYM=why' targets one slice; 'SYM=why' every slice where it applies. Returns {(slice, sym): why}."""
    out = {}
    for kv in kvs:
        k, why = kv.split("=", 1)
        sl, _, s = k.rpartition(":")
        if sl and sl not in engine.SLICES:
            notes.append(f"Overlay {kind} {k} ignored: unknown slice {sl!r}"); continue
        for x in ([sl] if sl else engine.SLICES):
            out[(x, s)] = why
    return out


def wake(cfg, st, a):
    U, L, X, SL = cfg["universe"], cfg["limits"], cfg["execution"], list(engine.SLICES)
    now = time.time()
    bar = int(now // engine.BAR * engine.BAR) - engine.BAR
    close_t = bar + engine.BAR
    dry = a.dry_run
    if st["last_bar"] == bar and not dry:
        print(f"Candle closing {utc(close_t)} already acted on; nothing placed."); return 0
    out, notes, fail, orders = [], [], [], []
    late = now - close_t > MAX_WAKE_DELAY

    # 1. data: closed 8h candles from the same feed as the backtest, the touch from Demo
    H, lv, tch, inst = {}, {}, {}, {}
    for s in U:
        try:
            B = engine.bars8h(bybit.klines4h(s), now); ks = sorted(B)
            if not ks or ks[-1] != bar:
                fail.append(f"{s}: last closed 8h candle {utc(ks[-1] + engine.BAR) if ks else 'none'}, expected {utc(close_t)}"); continue
            H[s] = [B[k] for k in ks]; lv[s] = engine.levels(H[s])
            tch[s] = bybit.touch(s); inst[s] = bybit.instrument(s)
        except Exception as e:
            fail.append(f"{s}: {e}")
    data_ok = not fail
    real, sh = st["real"], st["shadow"]  # {slice: book}
    lots = lambda: [(sl, s, p) for sl in SL for s, p in list(real[sl]["pos"].items())]

    # 1b. the venue: balances, catastrophe stops that fired between wakes, then lots vs balances (THE-320)
    demo = bal = None
    if not dry:
        k = creds(cfg)
        if k:
            demo = bybit.Demo(*k)
            try:
                bal = demo.balances()
            except Exception as e:
                fail.append(f"balances: {e}")
        elif lots():
            fail.append("no Bybit Demo credentials while slice-lots are open")
    cat_closed = set()  # (slice, sym) closed by a venue stop this wake: no re-entry on the same close
    for sl, s, p in (lots() if bal is not None else []):
        c = p.get("cat")
        if not c:
            continue
        try:
            o = demo.stop_status(s, c["id"])
            status = o.get("orderStatus") if o else None
            if status in STOP_LIVE:
                continue
            F = demo.fills(s, c["id"]) if o else []
            ins = inst.get(s) or bybit.instrument(s)
        except Exception as e:
            fail.append(f"[{sl}] {s} catastrophe stop check: {e}"); continue
        q = sum(f[0] for f in F)
        p["cat"] = None
        if not q:
            notes.append(f"[{sl}] {s} catastrophe stop `{c['id']}` is {status or 'unknown to Bybit'} with no fill: re-placed below"); continue
        cost = sum(f[0] * f[1] for f in F); fee_q = sum(f[2] for f in F if f[3] == "USDT")
        rb = real[sl]; rb["cash"] += cost - fee_q; p["qty"] -= q
        p.setdefault("exit_fills", []).append([q, cost / q, fee_q])
        why = f"catastrophe stop at {fmt(c['px'])} (resting on the venue, fired between wakes)"
        orders.append(dict(slice=sl, sym=s, side="sell", why=why, filled=q, cost=cost, fee_usdt=fee_q, avg=cost / q, status=status, attempts=0))
        if settle(cfg, st, rb, sl, s, p, why, cost / q, ins):
            cat_closed.add((sl, s))
        else:
            p["exit_pending"] = why
    recon_bad = []
    if bal is not None:
        held_q = {s: sum(b["pos"].get(s, {}).get("qty", 0) + b["dust"].get(s, 0) for b in real.values()) for s in U}
        if st.get("venue_base") is None:  # first read of the account: what it holds outside the sleeve
            if any(held_q.values()):
                recon_bad.append("no venue baseline while slice-lots are open")
            else:
                st["venue_base"] = {s[:-4]: bal.get(s[:-4], 0.0) for s in U}
                notes.append("Venue baseline captured (balances outside the sleeve): " + ", ".join(f"{c} {q:g}" for c, q in st["venue_base"].items()))
        if st.get("venue_base") is not None:
            for s in U:
                c = s[:-4]; want = st["venue_base"].get(c, 0.0) + held_q[s]; got = bal.get(c, 0.0)
                step = float(inst[s]["step"]) if s in inst else 0.0
                if abs(got - want) > max(1e-6 * max(abs(want), abs(got)), step):
                    recon_bad.append(f"{c} venue {got:g} ≠ baseline + slice-lots {want:g}")
        notes.append("Slice-lots vs venue: " + ("; ".join(recon_bad) if recon_bad else "every coin adds up"))

    marks = {s: lv[s]["close"] for s in lv if lv[s]}
    for B in (real, sh):  # a coin we hold but couldn't price this wake keeps its last mark
        for b in B.values():
            for s, p in b["pos"].items():
                marks.setdefault(s, p.get("mark", p["entry_px"]))
    nav_r = books_nav(real, marks)
    day = dt.datetime.fromtimestamp(close_t, dt.timezone.utc).strftime("%Y-%m-%d")
    day_nav = st["day"]["nav"] if st["day"] and st["day"]["date"] == day else nav_r
    day_loss = 1 - nav_r / day_nav if day_nav else 0

    # 2. gates (risk policy; the runner refuses, Ingrid halts). Total sleeve NAV, so they apply to every slice.
    gates_all, gates_in = [], []
    if not st["halted"] and recon_bad:
        st["halted"] = {"by": "runner", "ref": "slice-lots don't add up to the venue balance; reconcile, then Nadia resumes", "t": utc(now)}
    if not st["halted"] and day_loss >= L["day_halt_nav"]:
        st["halted"] = {"by": "runner", "ref": f"sleeve {-day_loss * 100:.1f}% on {day} (≥ {L['day_halt_nav']:.0%} day: hard halt until reconciled)", "t": utc(now)}
    if st["halted"]:
        (gates_in if L["halt_allows_exits"] else gates_all).append(f"halted by {st['halted']['by']} ({st['halted']['ref']})")
    if not data_ok: gates_all.append("data check failed")
    if late: gates_all.append(f"late wake ({(now - close_t) / 60:.0f} min after the close)")
    if st["failed_wakes"] >= L["halt_failed_wakes"]: gates_in.append(f"{st['failed_wakes']} failed wakes in a row: halt condition, Ingrid to review")
    if nav_r <= L["halt_nav_usdt"]: gates_in.append(f"sleeve NAV ${nav_r:.2f} ≤ ${L['halt_nav_usdt']}: halt condition, Ingrid to review")
    if day_loss >= L["daily_loss_nav"]: gates_in.append(f"sleeve day loss {day_loss * 100:.1f}% ≥ {L['daily_loss_nav'] * 100:.0f}%: no entries until next UTC day")

    # 3. decisions per slice: rules for both books, overlay on the real book only
    # The shadow's catastrophe stop fires when the closed candle traded through it (at the stop, or the open on a gap).
    ex_r, en_r, ex_s, en_s, cat_s = {}, {}, {}, {}, {sl: {} for sl in SL}
    for sl in SL:
        for s, p in (sh[sl]["pos"].items() if data_ok else []):
            if p.get("cat_px") and p["bar"] < bar and H[s][-1][2] <= p["cat_px"]:
                cat_s[sl][s] = min(p["cat_px"], H[s][-1][0])
        ex_r[sl], en_r[sl] = engine.decide(lv, {s: p["stop"] for s, p in real[sl]["pos"].items()}, sl) if data_ok else ({}, [])
        ex_s[sl], en_s[sl] = engine.decide(lv, {s: p["stop"] for s, p in sh[sl]["pos"].items() if s not in cat_s[sl]}, sl) if data_ok else ({}, [])
        en_r[sl] = [e for e in en_r[sl] if (sl, e[0]) not in cat_closed]
        en_s[sl] = [e for e in en_s[sl] if e[0] not in cat_s[sl]]
    rules_exit = {(sl, s) for sl in SL for s in ex_r[sl]}
    rules_entry = {(sl, e[0]) for sl in SL for e in en_r[sl]}
    held_before = {(sl, s) for sl in SL for s in real[sl]["pos"]}
    for sl in SL:
        for s, p in real[sl]["pos"].items():
            if p.get("exit_pending") and s not in ex_r[sl] and data_ok:
                ex_r[sl][s] = f"retry of unfilled exit ({p['exit_pending']})"
    skip = parse_overlay(a.skip, notes, "skip")
    early = parse_overlay(a.exit_early, notes, "early exit")
    overlay = []
    used = set()
    for (sl, s), why in early.items():
        if s in real[sl]["pos"] and s not in ex_r[sl]:
            ex_r[sl][s] = f"OVERLAY early exit: {why}"; overlay.append((sl, "exit_early", s, why)); used.add(s)
    for k in {k.split("=", 1)[0] for k in a.exit_early}:
        if k.rpartition(":")[2] not in used:
            notes.append(f"Overlay early exit {k} ignored: not held, or the rules already exit")
    used = set()
    for sl in SL:
        kept = []
        for e in en_r[sl]:
            if (sl, e[0]) in skip:
                overlay.append((sl, "skip", e[0], skip[(sl, e[0])])); used.add((sl, e[0]))
            else:
                kept.append(e)
        en_r[sl] = kept
    for k in {k.split("=", 1)[0] for k in a.skip}:
        sl, _, s = k.rpartition(":")
        if not any((x, s) in used for x in ([sl] if sl else SL)):
            notes.append(f"Overlay skip {k} ignored: no rules entry to skip")

    # 4. execution: exits of every slice first, then entries
    can_trade = not dry and not gates_all
    need_stop = any(not p.get("cat") for _, _, p in lots())
    if can_trade and (any(ex_r.values()) or any(en_r.values()) or need_stop):
        missing = merged_on_master()
        if missing:
            gates_all.append("not tradable: missing on master: " + ", ".join(missing))
        elif demo is None:
            gates_all.append("no Bybit Demo credentials")
        elif bal is None:
            gates_all.append("could not read demo balances")
        else:
            try:
                hi = halt_issues(cfg)
                if hi:
                    (gates_in if L["halt_allows_exits"] else gates_all).append("open halt issue: " + "; ".join(hi))
            except Exception as e:
                gates_in.append(f"could not check for HALT issues ({e}): no entries")
        can_trade = not gates_all
    order_fail = False
    real_px = {}  # (slice, sym, side) -> avg fill, for the shadow books
    for sl in SL:
        rb = real[sl]
        for s, why in ex_r[sl].items():
            p = rb["pos"][s]
            rec = dict(slice=sl, sym=s, side="sell", why=why, filled=0.0, cost=0.0, fee_usdt=0.0, attempts=0)
            if not can_trade:
                rec["result"] = "not placed: " + "; ".join(gates_all or ["dry run"]); orders.append(rec); continue
            base = inst[s]["base"]
            if p.get("cat"):  # this lot's own catastrophe stop goes first; the other slices' stops on the coin stay
                try:
                    demo.cancel(s, p["cat"]["id"], stop=True); p["cat"] = None
                except Exception as e:
                    rec["result"] = f"catastrophe stop `{p['cat']['id']}` not cancelled ({e}); exit not placed, retried next wake"
                    p["exit_pending"] = why; order_fail = True; orders.append(rec); continue
            for i in range(X["exit_attempts"]):
                try:
                    bid, ask = bybit.touch(s)
                    q = rnd(min(p["qty"], bal.get(base, 0)), inst[s]["step"], ROUND_DOWN)
                    if q <= 0 or float(q) < inst[s]["min_qty"]:
                        if i == 0:
                            rec["result"] = f"nothing sellable (ledger {p['qty']:g}, demo {bal.get(base, 0):g}): reconcile"; order_fail = True
                        break
                    px = limit_px("Sell", bid, ask, inst[s], X["touch_offset"])
                    f = place(demo, s, "Sell", q, px, f"mb-{bar}-{sl}-{s}-x{i}")
                except Exception as e:
                    rec["result"] = f"order error: {e}"; order_fail = True; break
                rec["attempts"] += 1; rec.update(bid=bid, ask=ask, limit=float(px), qty=float(q), status=f["status"], ms=f["ms"])
                p["qty"] -= f["filled"]; bal[base] = bal.get(base, 0) - f["filled"]
                rb["cash"] += f["cost"] - f["fee_quote"] - f["fee_base"] * f["avg"]
                rec["filled"] += f["filled"]; rec["cost"] += f["cost"]; rec["fee_usdt"] += f["fee_usdt"]
                if f["filled"]:
                    p.setdefault("exit_fills", []).append([f["filled"], f["avg"], f["fee_usdt"]])
                if p["qty"] * bid < inst[s]["min_amt"] or p["qty"] < inst[s]["min_qty"]:
                    break
            rec["avg"] = rec["cost"] / rec["filled"] if rec["filled"] else 0.0
            orders.append(rec)
            if "bid" in rec and settle(cfg, st, rb, sl, s, p, why, rec["bid"], inst[s]):
                real_px[(sl, s, "sell")] = p["exit_px"]
            else:
                p["exit_pending"] = why
                rec.setdefault("result", f"{'partial; ' if rec['filled'] else 'IOC not filled; '}{p['qty']:g} left, retried next wake")

    bidmark = lambda b: b["cash"] + sum(p["qty"] * tch[s][0] for s, p in b["pos"].items() if s in tch)  # NAV at the bid, for sizing
    sleeve_x = sum(bidmark(b) for b in real.values())
    for sl in SL:
        rb = real[sl]
        navx, n_held = bidmark(rb), len(rb["pos"])
        n_in, n_out = engine.SLICES[sl]
        for s, w, stop, strength in en_r[sl]:
            rec = dict(slice=sl, sym=s, side="buy", stop=stop, weight=w,
                       why=f"close {lv[s]['close']:g} > hi{n_in} {lv[s]['hi'][sl]:g} and > sma90 {lv[s]['sma90']:.6g}; strength {strength:.2f} ATR")
            if not can_trade or gates_in:
                rec["result"] = "not placed: " + "; ".join(gates_all + gates_in or ["dry run"]); orders.append(rec); continue
            try:
                bid, ask = bybit.touch(s)
                px = limit_px("Buy", bid, ask, inst[s], X["touch_offset"])
                other = sum(b["pos"][s]["qty"] * bid for x, b in real.items() if x != sl and s in b["pos"])
                q, capnote = entry_qty(cfg, w, navx, rb["cash"], px, stop, inst[s], other, sleeve_x)
                rec.update(bid=bid, ask=ask, limit=float(px), qty=float(q))
                if capnote:
                    rec["why"] += f"; {capnote}"
                if q <= 0 and capnote:
                    rec["result"] = "SKIPPED by the coin cap (risk policy)"; orders.append(rec); continue
                bad = check_entry(cfg, rb, s, q, px, stop, navx, n_held + 1, bal.get("USDT"), inst[s], [], other, sleeve_x)
                if bad:
                    rec["result"] = "REFUSED: " + "; ".join(bad); orders.append(rec); continue
                link = f"mb-{bar}-{sl}-{s}-e"
                f = place(demo, s, "Buy", q, px, link)
            except Exception as e:
                rec["result"] = f"order error: {e}"; order_fail = True; orders.append(rec); continue
            rec.update(**f); orders.append(rec)
            if f["filled"] <= 0:
                rec["result"] = "IOC not filled; dropped (strategy.md §8)"; continue
            net = f["filled"] - f["fee_base"]
            rb["cash"] -= f["cost"] + f["fee_quote"]; bal["USDT"] = bal.get("USDT", 0) - f["cost"]
            bal[inst[s]["base"]] = bal.get(inst[s]["base"], 0) + net
            rb["pos"][s] = dict(qty=net, entry_px=f["avg"], stop=stop, entry_t=utc(time.time()), bar=bar, link_id=link,
                                order_id=f["order_id"], entry_fee_usdt=f["fee_usdt"], cb_id=None, mark=lv[s]["close"],
                                atr14=lv[s]["atr14"], cat_px=f["avg"] - L["catastrophe_atr"] * lv[s]["atr14"], cat=None)
            n_held += 1; real_px[(sl, s, "buy")] = f["avg"]
            st["cb_pending"].append({"link": link, "slice": sl, "body": {
                "side": "entry", "book": cfg["strategy"], "token_symbol": s.replace("USDT", ""), "trader": cfg["trader"],
                "trade_date": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                "entry_price": f"{f['avg']:.10g}", "position_size": f"{net:.10g}",
                "reason": f"[{sl}] Majors Breakout {sl} {n_in}/{n_out} (paper, Bybit Demo): {rec['why']}",
                "planned_exit": f"[{sl}] 8h close < lo{n_out} (now {lv[s]['lo'][sl]:g}) or < stop {stop:.6g}; "
                                f"venue catastrophe stop {rb['pos'][s]['cat_px']:.6g}"}})

    # 4b. one resting catastrophe stop per slice-lot at entry − N×ATR (THE-320); re-placed if it vanished or the lot shrank
    for sl, s, p in (lots() if can_trade else []):
        if p.get("cat"):
            continue
        if not p.get("cat_px") or s not in inst:
            notes.append(f"**[{sl}] {s} has no catastrophe stop** (no level or no instrument data): Ingrid's fallback needed"); order_fail = True; continue
        q = rnd(p["qty"], inst[s]["step"], ROUND_DOWN); trig = rnd(p["cat_px"], inst[s]["tick"], ROUND_DOWN)
        if float(q) < inst[s]["min_qty"] or float(q) * float(trig) < inst[s]["min_amt"]:
            notes.append(f"[{sl}] {s}: {q} is below the venue minimum at the stop, no catastrophe stop"); continue
        try:
            oid = demo.stop_sell(s, format(q, "f"), format(trig, "f"), f"mb-{bar}-{sl}-{s}-c")
            p["cat"] = dict(id=oid, px=float(trig), qty=float(q))
            notes.append(f"[{sl}] {s} catastrophe stop: sell {q} if ≤ {fmt(float(trig))} (`{oid}`)")
        except Exception as e:
            order_fail = True
            notes.append(f"**[{sl}] {s} catastrophe stop NOT placed** ({e}): unprotected between wakes, Ingrid's fallback needed")
    if not can_trade and any(not p.get("cat") for _, _, p in lots()):
        notes.append("Slice-lots without a catastrophe stop, not placed (" + "; ".join(gates_all or ["dry run"]) + "): "
                     + ", ".join(f"[{sl}] {s[:-4]}" for sl, s, p in lots() if not p.get("cat")))

    # 5. shadow books (rules only, one per slice, same gates and data as the real book; strategy.md §7)
    shadow_moves = []
    if data_ok and not gates_all and not dry:
        fee = X["shadow_fee"]
        for sl in SL:
            sb = sh[sl]
            for s, why in [(s, f"catastrophe stop at {cat_s[sl][s]:g}") for s in cat_s[sl]] + list(ex_s[sl].items()):
                p = sb["pos"].pop(s); px = cat_s[sl].get(s) or real_px.get((sl, s, "sell"), tch[s][0])
                sb["cash"] += p["qty"] * px * (1 - fee); p.update(sym=s, exit_px=px, exit_t=utc(time.time()), exit_why=why)
                sb["closed"].append(p); shadow_moves.append(f"{sl} sell {s[:-4]} @ {px:g}" + (" (catastrophe stop)" if s in cat_s[sl] else ""))
        sh_x = sum(bidmark(b) for b in sh.values())
        for sl in SL:
            sb = sh[sl]
            if not gates_in:
                nv = bidmark(sb)
                for s, w, stop, _ in en_s[sl]:
                    px = real_px.get((sl, s, "buy"), tch[s][1])
                    other = sum(b["pos"][s]["qty"] * tch[s][0] for x, b in sh.items() if x != sl and s in b["pos"])
                    q = float(entry_qty(cfg, w, nv, sb["cash"], px, stop, inst[s], other, sh_x)[0])
                    if q * px < inst[s]["min_amt"]:
                        continue
                    sb["cash"] -= q * px
                    sb["pos"][s] = dict(qty=q * (1 - fee), entry_px=px, stop=stop, entry_t=utc(time.time()), bar=bar, mark=lv[s]["close"],
                                        cat_px=px - L["catastrophe_atr"] * lv[s]["atr14"])
                    shadow_moves.append(f"{sl} buy {s[:-4]} @ {px:g}")

    # 6. benchmark, marks, NAV, counters
    if not dry and data_ok and st["bh"] is None:
        st["bh"] = dict(qty=cfg["sleeve_usdt"] / tch["BTCUSDT"][1] * (1 - X["shadow_fee"]), px=tch["BTCUSDT"][1], t=utc(time.time()))
        st["started"] = utc(time.time())
    for B in (real, sh):
        for b in B.values():
            for s, p in b["pos"].items():
                if s in marks: p["mark"] = marks[s]
    nav_r, nav_s = books_nav(real, marks), books_nav(sh, marks)
    nav_b = st["bh"]["qty"] * marks.get("BTCUSDT", st["bh"]["px"]) if st["bh"] else None
    if now - close_t > LOG_DEADLINE:
        fail.append(f"decision log {(now - close_t) / 60:.0f} min after the close, later than 60 min after the scheduled wake")
    wake_failed = bool(fail) or order_fail

    # 7. decision log
    phase = "paper (Bybit Demo)"
    out.append(f"**Majors Breakout (3-speed) · wake for the 8h candle closing {utc(close_t)}** · run {utc(now)} · phase: {phase}" + (" · **DRY RUN, nothing placed or saved**" if dry else ""))
    out.append("")
    out.append("| Coin | Close | sma90 | ATR14 | " + " | ".join(f"{sl} {n}/{m}: hi / lo · state" for sl, (n, m) in engine.SLICES.items()) + " |")
    out.append("|---|---|---|---|" + "---|" * len(SL))
    acted = {(o["slice"], o["sym"]): o for o in orders}
    skipped = {(o[0], o[2]) for o in overlay if o[1] == "skip"}
    for s in U:
        l = lv.get(s)
        if not l:
            out.append(f"| {s[:-4]} | — | — | — | " + " | ".join("no data" for _ in SL) + " |"); continue
        cells = []
        for sl in SL:
            k = (sl, s); p = real[sl]["pos"].get(s)
            if k in acted:
                o = acted[k]
                act = f"**{o['side']}**: {o['result']}" if "result" in o and not o.get("filled") else f"**{o['side']}** {o['filled']:g} @ {fmt(o['avg'])}"
            elif k in skipped:
                act = "**entry SKIPPED (overlay)**"
            elif p:
                act = f"hold (entry {fmt(p['entry_px'])}, stop {fmt(p['stop'])})"
            else:
                act = "—"
            cells.append(f"{fmt(l['hi'][sl])} / {fmt(l['lo'][sl])} · {act}")
        out.append(f"| {s[:-4]} | {fmt(l['close'])} | {fmt(l['sma90'])} | {fmt(l['atr14'], 4)} | " + " | ".join(cells) + " |")
    out.append("")
    # one decision per slice (THE-320: a wake with a slice missing its decision is a failed wake)
    for sl in SL:
        mine = [o for o in orders if o["slice"] == sl]
        did = [f"{o['side']} {o['sym'][:-4]}" + ("" if o.get("filled") else " (not done)") for o in mine]
        held = [s[:-4] for s in real[sl]["pos"] if not any(o["sym"] == s for o in mine)]
        sk = [s[:-4] for x, k, s, _ in overlay if x == sl and k == "skip"]
        out.append(f"**Decision [{sl}]:** " + ("; ".join(did) if did else "no trade")
                   + (f" · skipped (overlay): {', '.join(sk)}" if sk else "") + (f" · holding {', '.join(held)}" if held else ""))
    missing_dec = [sl for sl in SL if not any(l.startswith(f"**Decision [{sl}]:**") for l in out)]
    if missing_dec:
        fail.append("no decision for slice " + ", ".join(missing_dec)); wake_failed = True
    out.append("")
    if orders:
        out.append("**Orders**")
        for o in orders:
            k = (o["slice"], o["sym"])
            rule = "rules exit" if k in rules_exit else "rules entry" if k in rules_entry else "overlay/retry"
            line = f"- [{o['slice']}] {o['side'].upper()} {o['sym']} ({rule}): {o['why']}."
            if "limit" in o:
                line += f" Touch {fmt(o['bid'])}/{fmt(o['ask'])}, IOC limit {fmt(o['limit'])}, qty {o['qty']:g}."
            if "status" in o:
                line += f" Filled {o['filled']:g} @ {fmt(o['avg'])}, fee ${o['fee_usdt']:.4f}, {o['status']}" + (f", {o['ms']} ms." if "ms" in o else ".")
            if "result" in o:
                line += f" {o['result']}."
            if o["side"] == "buy" and o.get("filled"):
                line += f" Invalidated by an 8h close < lo{engine.SLICES[o['slice']][1]} or < stop {fmt(o['stop'])}."
            out.append(line)
    else:
        out.append("**No trade:** " + ("no data." if not data_ok else "in no slice did a coin close above its channel high and 30-day average, and no held position hit its exit."))
    for sl, kind, s, why in overlay:
        out.append(f"- **Overlay [{sl}] {kind.replace('_', ' ')} {s}:** {why}")
    if gates_all or gates_in:
        out.append("**Gates:** " + "; ".join(gates_all + gates_in))
    if fail:
        out.append("**Failures:** " + "; ".join(fail))
    out.append("")
    out.append(f"**Books** (marked at closes) · Sleeve ${nav_r:,.2f}, shadow ${nav_s:,.2f}"
               + (f", BTC buy-and-hold ${nav_b:,.2f} (from {st['bh']['t']} @ {fmt(st['bh']['px'])})" if nav_b else "")
               + f" · Day {day}: {-day_loss * 100:+.2f}% · failed wakes in a row: {st['failed_wakes'] + 1 if wake_failed else 0}")
    for sl in SL:
        b = real[sl]
        pos_txt = ", ".join(f"{s[:-4]} {p['qty']:g}" for s, p in b["pos"].items()) or "no positions"
        out.append(f"- {sl}: ${book_nav(b, marks):,.2f} (cash ${b['cash']:,.2f}; {pos_txt}) · shadow ${book_nav(sh[sl], marks):,.2f}")
    if shadow_moves:
        out.append(f"- shadow moves: {'; '.join(shadow_moves)}")
    out.append("")
    out.append("Inputs: Bybit public spot 4h klines (mainnet, same feed as the backtest), Demo touch and fills; rules per `strategy.md`; limits per `" + cfg["limits_source"].split(".")[0] + "`.")

    if not dry:
        cb_flush(cfg, st, notes)
    if notes:
        out.append("")
        out.extend(f"- {n}" for n in notes)
    text = "\n".join(out)
    print(text)
    if dry:
        return 0

    st["failed_wakes"] = st["failed_wakes"] + 1 if wake_failed else 0
    st["day"] = {"date": day, "nav": day_nav}
    st["wakes"] += 1
    st["overlay"].extend({"bar": bar, "slice": sl, "kind": k, "sym": s, "why": w} for sl, k, s, w in overlay)
    if data_ok and not late:
        st["last_bar"] = bar
    save_state(st)
    os.makedirs(os.path.join(STATE_DIR, "logs"), exist_ok=True)
    open(os.path.join(STATE_DIR, "logs", f"{bar}.md"), "w").write(text)
    if st["log_issue"]:
        try:
            pc("POST", f"/api/issues/{st['log_issue']}/comments", {"body": text})
        except Exception as e:
            print(f"\n!! decision log NOT posted to {st['log_issue']}: {e}", file=sys.stderr)
        else:
            return 1 if wake_failed else 0
    else:
        print("\n!! no log issue set (runner.py set-log-issue THE-xxx)", file=sys.stderr)
    if not wake_failed:  # no posted decision log = failed wake
        st["failed_wakes"] += 1; save_state(st)
    return 2


# ---------- test order (strategy.md §8; THE-321 step 8) ----------

def test_order(cfg, st, a):
    """THE-321 step 8 plus THE-320's stop test: a small buy, two resting stop-sells on that coin with one cancelled
    alone, the sell-back, then a non-marketable probe. Every step is recorded, failures included; stops are always cleaned up."""
    if a.usdt > cfg["execution"]["max_test_order_usdt"]:
        sys.exit(f"test orders are capped at ${cfg['execution']['max_test_order_usdt']}")
    if any(b["pos"] or b["dust"] for b in st["real"].values()):
        sys.exit("slice-lots are open: test orders would disturb the reconciliation")
    k = creds(cfg)
    if not k:
        sys.exit("no Bybit Demo credentials yet")
    demo, s, inst = bybit.Demo(*k), a.symbol, bybit.instrument(a.symbol)
    c = inst["base"]
    bals = lambda: {x: v for x, v in demo.balances(detail=True).items() if x in ("USDT", c)}
    rep = {"t": utc(time.time()), "symbol": s, "usdt": a.usdt, "balances_before": bals()}
    bid, ask = bybit.touch(s)
    px = limit_px("Buy", bid, ask, inst, cfg["execution"]["touch_offset"])
    q = rnd(a.usdt / float(px), inst["step"], ROUND_DOWN)
    b = place(demo, s, "Buy", q, px, f"mb-test-{int(time.time())}-b")
    rep["buy"] = dict(bid=bid, ask=ask, limit=float(px), qty=float(q), **b, slip_vs_ask_bps=(b["avg"] / ask - 1) * 1e4 if b["filled"] else None)
    net = rnd(b["filled"] - b["fee_base"], inst["step"], ROUND_DOWN)

    # two resting stop-sells on the same coin (two slice-lots), far below the market; cancel A alone, B must survive
    T, live = {"steps": []}, []
    def step(name, fn):
        try:
            r = fn(); T["steps"].append({"step": name, "ok": True, "result": r}); return r
        except Exception as e:
            T["steps"].append({"step": name, "ok": False, "error": str(e)}); return None
    qa = rnd(net / 2, inst["step"], ROUND_DOWN); qb = net - qa
    if net > 0 and min(qa, qb) * Decimal(str(bid)) * Decimal("0.7") >= Decimal(str(inst["min_amt"])) and float(min(qa, qb)) >= inst["min_qty"]:
        tag = int(time.time())
        for name, qq, f in (("A", qa, "0.7"), ("B", qb, "0.75")):
            oid = step(f"place stop {name}", lambda qq=qq, f=f, name=name: demo.stop_sell(
                s, format(qq, "f"), format(rnd(bid * float(f), inst["tick"], ROUND_DOWN), "f"), f"mb-test-{tag}-stop{name}"))
            T[name] = oid
            if oid:
                live.append(oid)
        T["balances_with_two_stops"] = step("balances with two stops", bals)
        for name in ("A", "B"):
            if T.get(name):
                step(f"status {name}", lambda name=name: (demo.stop_status(s, T[name]) or {}).get("orderStatus"))
        if T.get("A"):
            if step("cancel A", lambda: demo.cancel(s, T["A"], stop=True) and "cancelled") is not None:
                live.remove(T["A"])
            step("status A after cancel", lambda: (demo.stop_status(s, T["A"]) or {}).get("orderStatus"))
        if T.get("B"):
            step("status B after cancel A", lambda: (demo.stop_status(s, T["B"]) or {}).get("orderStatus"))
        T["balances_after_cancel_A"] = step("balances after cancel A", bals)
        st_b = next((x["result"] for x in T["steps"] if x["step"] == "status B after cancel A" and x["ok"]), None)
        T["verdict"] = ("two stops accepted; cancelling A left B resting" if T.get("A") and T.get("B") and st_b in STOP_LIVE
                        else "FAILED: see steps (fallback: hourly price check in the runner)")
    else:
        T["verdict"] = f"not run: bought {net} {c}, too little for two stops above the venue minimum (use a larger --usdt)"
    for oid in list(live):  # never leave a test stop behind
        if step(f"cleanup cancel {oid}", lambda oid=oid: demo.cancel(s, oid, stop=True) and "cancelled") is not None:
            live.remove(oid)
    T["left_resting"] = live
    rep["two_stops"] = T

    if net > 0 and float(net) >= inst["min_qty"]:
        bid, ask = bybit.touch(s)
        px = limit_px("Sell", bid, ask, inst, cfg["execution"]["touch_offset"])
        x = place(demo, s, "Sell", net, px, f"mb-test-{int(time.time())}-s")
        rep["sell"] = dict(bid=bid, ask=ask, limit=float(px), qty=float(net), **x, slip_vs_bid_bps=(1 - x["avg"] / bid) * 1e4 if x["filled"] else None)
    # probe: an IOC buy priced at the bid can't cross a real book; a fill here means demo matching is synthetic
    bid, ask = bybit.touch(s)
    pq = rnd(max(inst["min_amt"] * 1.2 / bid, inst["min_qty"]), inst["step"], ROUND_UP)
    pr = place(demo, s, "Buy", pq, rnd(bid, inst["tick"], ROUND_DOWN), f"mb-test-{int(time.time())}-p")
    rep["probe_at_bid"] = dict(bid=bid, ask=ask, qty=float(pq), **pr)
    rep["balances_after"] = bals()
    st["test_orders"].append(rep)
    st["venue_base"] = None  # the next wake re-reads what the account holds outside the sleeve
    save_state(st)
    print(json.dumps(rep, indent=1, default=str))


def status(cfg, st, a):
    print(json.dumps({k: st.get(k) for k in ("started", "last_bar", "day", "failed_wakes", "halted", "log_issue", "wakes", "bh", "venue_base", "cb_pending")}, indent=1, default=str))
    for name in ("real", "shadow"):
        for sl, b in st[name].items():
            print(f"{name} {sl}: cash {b['cash']:.2f}, open {list(b['pos'])}, closed {len(b['closed'])}, dust {b['dust']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("wake"); w.add_argument("--dry-run", action="store_true")
    w.add_argument("--skip", action="append", default=[], metavar="[SLICE:]SYM=REASON")
    w.add_argument("--exit-early", action="append", default=[], metavar="[SLICE:]SYM=REASON")
    t = sub.add_parser("test-order"); t.add_argument("--symbol", default="DOGEUSDT"); t.add_argument("--usdt", type=float, default=18)
    sub.add_parser("status")
    for c in ("halt", "resume"):
        h = sub.add_parser(c); h.add_argument("--by", required=True); h.add_argument("--ref", required=True)
        if c == "resume":
            h.add_argument("--rebaseline", action="store_true", help="after a reconciled mismatch: venue baseline := balances − slice-lots")
    li = sub.add_parser("set-log-issue"); li.add_argument("issue")
    a = ap.parse_args()
    for kv in getattr(a, "skip", []) + getattr(a, "exit_early", []):
        if "=" not in kv or not kv.split("=", 1)[1].strip():
            sys.exit(f"overlay needs a written reason: {kv!r} (use [SLICE:]SYM=REASON)")
    cfg = load_cfg()
    _l = lock()
    st = load_state(cfg)
    if a.cmd == "wake":
        sys.exit(wake(cfg, st, a))
    if a.cmd == "test-order":
        return test_order(cfg, st, a)
    if a.cmd == "status":
        return status(cfg, st, a)
    if a.cmd == "halt":
        st["halted"] = {"by": a.by, "ref": a.ref, "t": utc(time.time())}
    elif a.cmd == "resume":
        if a.by.lower() != "nadia":
            sys.exit("only Nadia resumes (THE-319 §4)")
        if a.rebaseline:
            k = creds(cfg)
            if not k:
                sys.exit("no Bybit Demo credentials: can't rebaseline")
            bal = bybit.Demo(*k).balances()
            st["venue_base"] = {s[:-4]: bal.get(s[:-4], 0.0) - sum(b["pos"].get(s, {}).get("qty", 0) + b["dust"].get(s, 0) for b in st["real"].values())
                                for s in cfg["universe"]}
        st["halted"] = None
    elif a.cmd == "set-log-issue":
        st["log_issue"] = a.issue
    save_state(st); status(cfg, st, a)


if __name__ == "__main__":
    main()
