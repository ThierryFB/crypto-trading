#!/usr/bin/env python3
"""Majors Breakout runner: order placement for this strategy only (strategy.md §5-§8).

  runner.py wake --dry-run                     compute the wake's decision, place nothing, save nothing
  runner.py wake [--skip SYM=why] [--exit-early SYM=why]
                                               act on the candle that just closed: orders on Bybit Demo,
                                               ledger, shadow book, BTC benchmark, decision log, Crypto Book
  runner.py test-order [--symbol DOGEUSDT --usdt 10]
                                               one small buy + sell-back + non-marketable probe, outside the sleeve
  runner.py status | halt --by NAME --ref ISSUE | resume --by NAME --ref ISSUE | set-log-issue ISSUE

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
MAX_WAKE_DELAY = 2 * 3600  # a wake later than this after its close places no orders (strategy.md §5)


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


def book_nav(b, marks):
    return b["cash"] + sum(p["qty"] * marks[s] for s, p in b["pos"].items()) + \
        sum(q * marks.get(s, 0) for s, q in b["dust"].items())


def load_state(cfg):
    p = os.path.join(STATE_DIR, "state.json")
    if os.path.exists(p):
        return json.load(open(p))
    return {"version": 1, "started": None, "real": new_book(cfg["sleeve_usdt"]), "shadow": new_book(cfg["sleeve_usdt"]),
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
    for item in st["cb_pending"]:
        body = dict(item["body"])
        if body["side"] == "exit":
            eid = item.get("entry_id") or next((c["cb_id"] for c in st["real"]["closed"] + list(st["real"]["pos"].values())
                                                if c.get("link_id") == item["entry_link"] and c.get("cb_id")), None)
            if not eid:
                keep.append(item); continue
            body["entry_trade_id"] = eid
        try:
            tid = cb_post(cfg, body)
            if body["side"] == "entry":
                for p in list(st["real"]["pos"].values()) + st["real"]["closed"]:
                    if p.get("link_id") == item["link"]:
                        p["cb_id"] = tid
            notes.append(f"Crypto Book {body['side']} {body['token_symbol']} recorded (`{tid}`)")
        except Exception as e:
            keep.append(item); notes.append(f"Crypto Book {body['side']} {body['token_symbol']} **not recorded** ({e}); retried next wake")
    st["cb_pending"] = keep


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


def check_entry(cfg, b, sym, qty, px, stop, nav, n_after, usdt_avail, inst, gates):
    """Every reason this buy would break a limit. Empty list = allowed."""
    L, v = cfg["limits"], float(qty) * float(px)
    bad = list(gates)
    if sym not in cfg["universe"]: bad.append("not in universe")
    if sym in b["pos"]: bad.append("already held")
    if n_after > L["max_positions"]: bad.append(f"{n_after} positions > {L['max_positions']}")
    if float(px) <= stop: bad.append("limit price at or below stop")
    if float(qty) * (float(px) - stop) > L["risk_per_trade_nav"] * nav * (1 + 1e-9): bad.append("risk at stop > 1% NAV")
    if v > L["max_position_nav"] * nav * (1 + 1e-9): bad.append("position > 25% NAV")
    if v > b["cash"] + 1e-9: bad.append(f"needs ${v:.2f}, sleeve cash ${b['cash']:.2f}")
    if usdt_avail is not None and v > usdt_avail: bad.append(f"demo USDT {usdt_avail:.2f} < ${v:.2f}")
    if float(qty) < inst["min_qty"] or v < inst["min_amt"]: bad.append(f"below venue minimum (${v:.2f})")
    return bad


def entry_qty(cfg, w, nav, cash, px, stop, inst):
    """bt.py sizing (weight × NAV, capped at cash), then trimmed so the risk and position limits hold at the limit price."""
    L, px = cfg["limits"], float(px)
    val = min(w * nav, cash)
    q = val / px
    if px > stop:
        q = min(q, L["risk_per_trade_nav"] * nav / (px - stop))
    q = min(q, L["max_position_nav"] * nav / px)
    return rnd(max(q, 0), inst["step"], ROUND_DOWN)


# ---------- the wake ----------

def wake(cfg, st, a):
    U, L, X = cfg["universe"], cfg["limits"], cfg["execution"]
    now = time.time()
    bar = int(now // engine.BAR * engine.BAR) - engine.BAR
    close_t = bar + engine.BAR
    dry = a.dry_run
    if st["last_bar"] == bar and not dry:
        print(f"Candle closing {utc(close_t)} already acted on; nothing placed."); return 0
    out, notes, fail, orders = [], [], [], []
    late = now - close_t > MAX_WAKE_DELAY

    # 1. data: closed 8h candles from the same feed as bt.py, the touch from Demo
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

    real, sh = st["real"], st["shadow"]
    marks = {s: lv[s]["close"] for s in lv if lv[s]}
    for b in (real, sh):  # a coin we hold but couldn't price this wake keeps its last mark
        for s, p in b["pos"].items():
            marks.setdefault(s, p.get("mark", p["entry_px"]))
    nav_r, nav_s = book_nav(real, marks), book_nav(sh, marks)
    day = dt.datetime.fromtimestamp(close_t, dt.timezone.utc).strftime("%Y-%m-%d")
    day_nav = st["day"]["nav"] if st["day"] and st["day"]["date"] == day else nav_r
    day_loss = 1 - nav_r / day_nav if day_nav else 0

    # 2. gates (risk policy; the runner refuses, Ingrid halts)
    gates_all, gates_in = [], []
    if st["halted"]:
        (gates_in if L["halt_allows_exits"] else gates_all).append(f"halted by {st['halted']['by']} ({st['halted']['ref']})")
    if not data_ok: gates_all.append("data check failed")
    if late: gates_all.append(f"late wake ({(now - close_t) / 60:.0f} min after the close)")
    if st["failed_wakes"] >= L["halt_failed_wakes"]: gates_in.append(f"{st['failed_wakes']} failed wakes in a row: halt condition, Ingrid to review")
    if nav_r <= L["halt_nav_usdt"]: gates_in.append(f"NAV ${nav_r:.2f} ≤ ${L['halt_nav_usdt']}: halt condition, Ingrid to review")
    if day_loss >= L["daily_loss_nav"]: gates_in.append(f"day loss {day_loss * 100:.1f}% ≥ {L['daily_loss_nav'] * 100:.0f}%: no entries until next UTC day")

    # 3. decisions: rules for both books, overlay on the real book only
    ex_r, en_r = engine.decide(lv, {s: p["stop"] for s, p in real["pos"].items()}) if data_ok else ({}, [])
    ex_s, en_s = engine.decide(lv, {s: p["stop"] for s, p in sh["pos"].items()}) if data_ok else ({}, [])
    rules_exit, rules_entry, held_before = set(ex_r), {e[0] for e in en_r}, set(real["pos"])
    for s, p in real["pos"].items():
        if p.get("exit_pending") and s not in ex_r and data_ok:
            ex_r[s] = f"retry of unfilled exit ({p['exit_pending']})"
    skip = dict(kv.split("=", 1) for kv in a.skip)
    early = dict(kv.split("=", 1) for kv in a.exit_early)
    overlay = []
    for s, why in early.items():
        if s in real["pos"] and s not in ex_r:
            ex_r[s] = f"OVERLAY early exit: {why}"; overlay.append(("exit_early", s, why))
        else:
            notes.append(f"Overlay early exit {s} ignored: {'not held' if s not in real['pos'] else 'rules already exit'}")
    kept = []
    for e in en_r:
        if e[0] in skip:
            overlay.append(("skip", e[0], skip[e[0]]))
        else:
            kept.append(e)
    for s in set(skip) - {e[0] for e in en_r}:
        notes.append(f"Overlay skip {s} ignored: no rules entry to skip")
    en_r = kept

    # 4. execution
    can_trade = not dry and not gates_all
    demo = bal = None
    if can_trade and (ex_r or en_r):
        missing = merged_on_master()
        k = creds(cfg)
        if missing:
            gates_all.append("not tradable: missing on master: " + ", ".join(missing)); can_trade = False
        elif not k:
            gates_all.append("no Bybit Demo credentials"); can_trade = False
        else:
            demo = bybit.Demo(*k)
            try:
                bal = demo.balances()
            except Exception as e:
                fail.append(f"balances: {e}"); gates_all.append("could not read demo balances"); can_trade = False
    order_fail = False
    real_px = {}  # (sym, side) -> avg fill, for the shadow book
    for s, why in ex_r.items():
        p = real["pos"][s]
        rec = dict(sym=s, side="sell", why=why, filled=0.0, cost=0.0, fee_usdt=0.0, attempts=0)
        if not can_trade:
            rec["result"] = "not placed: " + "; ".join(gates_all or ["dry run"]); orders.append(rec); continue
        base = inst[s]["base"]
        for i in range(X["exit_attempts"]):
            try:
                bid, ask = bybit.touch(s)
                q = rnd(min(p["qty"], bal.get(base, 0)), inst[s]["step"], ROUND_DOWN)
                if q <= 0 or float(q) < inst[s]["min_qty"]:
                    if i == 0:
                        rec["result"] = f"nothing sellable (ledger {p['qty']:g}, demo {bal.get(base, 0):g}): reconcile"; order_fail = True
                    break
                px = limit_px("Sell", bid, ask, inst[s], X["touch_offset"])
                f = place(demo, s, "Sell", q, px, f"mb-{bar}-{s}-x{i}")
            except Exception as e:
                rec["result"] = f"order error: {e}"; order_fail = True; break
            rec["attempts"] += 1; rec.update(bid=bid, ask=ask, limit=float(px), qty=float(q), status=f["status"], ms=f["ms"])
            p["qty"] -= f["filled"]; bal[base] = bal.get(base, 0) - f["filled"]
            real["cash"] += f["cost"] - f["fee_quote"] - f["fee_base"] * f["avg"]
            rec["filled"] += f["filled"]; rec["cost"] += f["cost"]; rec["fee_usdt"] += f["fee_usdt"]
            if f["filled"]:
                p.setdefault("exit_fills", []).append([f["filled"], f["avg"], f["fee_usdt"]])
            if p["qty"] * bid < inst[s]["min_amt"] or p["qty"] < inst[s]["min_qty"]:
                break
        rec["avg"] = rec["cost"] / rec["filled"] if rec["filled"] else 0.0
        orders.append(rec)
        if p.get("exit_fills") and 0 < p["qty"] and (p["qty"] * rec["bid"] < inst[s]["min_amt"] or p["qty"] < inst[s]["min_qty"]):
            real["dust"][s] = real["dust"].get(s, 0) + p["qty"]; p["qty"] = 0  # unsellable remainder, still marked in NAV
        if p["qty"] <= 0:
            xf = p.pop("exit_fills"); q = sum(x[0] for x in xf)
            p.pop("exit_pending", None)
            p.update(sym=s, exit_px=sum(x[0] * x[1] for x in xf) / q, exit_t=utc(time.time()), exit_why=why,
                     exit_fee_usdt=sum(x[2] for x in xf))
            real["closed"].append(p); del real["pos"][s]; real_px[(s, "sell")] = p["exit_px"]
            st["cb_pending"].append({"entry_link": p["link_id"], "body": {
                "side": "exit", "book": cfg["strategy"], "token_symbol": s.replace("USDT", ""), "trader": cfg["trader"],
                "trade_date": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                "exit_price": f"{p['exit_px']:.10g}", "reason": why}})
        else:
            p["exit_pending"] = why
            rec.setdefault("result", f"{'partial; ' if rec['filled'] else 'IOC not filled; '}{p['qty']:g} left, retried next wake")

    navx = real["cash"] + sum(p["qty"] * tch[s][0] for s, p in real["pos"].items() if s in tch)  # NAV at the bid, for sizing
    n_held = len(real["pos"])
    for s, w, stop, strength in en_r:
        rec = dict(sym=s, side="buy", why=f"close {lv[s]['close']:g} > hi20 {lv[s]['hi20']:g} and > sma90 {lv[s]['sma90']:.6g}; strength {strength:.2f} ATR",
                   stop=stop, weight=w)
        if not can_trade or gates_in:
            rec["result"] = "not placed: " + "; ".join(gates_all + gates_in or ["dry run"]); orders.append(rec); continue
        try:
            bid, ask = bybit.touch(s)
            px = limit_px("Buy", bid, ask, inst[s], X["touch_offset"])
            q = entry_qty(cfg, w, navx, real["cash"], px, stop, inst[s])
            bad = check_entry(cfg, real, s, q, px, stop, navx, n_held + 1, bal.get("USDT"), inst[s], [])
            rec.update(bid=bid, ask=ask, limit=float(px), qty=float(q))
            if bad:
                rec["result"] = "REFUSED: " + "; ".join(bad); orders.append(rec); continue
            link = f"mb-{bar}-{s}-e"
            f = place(demo, s, "Buy", q, px, link)
        except Exception as e:
            rec["result"] = f"order error: {e}"; order_fail = True; orders.append(rec); continue
        rec.update(**f); orders.append(rec)
        if f["filled"] <= 0:
            rec["result"] = "IOC not filled; dropped (strategy.md §7)"; continue
        net = f["filled"] - f["fee_base"]
        real["cash"] -= f["cost"] + f["fee_quote"]; bal["USDT"] = bal.get("USDT", 0) - f["cost"]
        real["pos"][s] = dict(qty=net, entry_px=f["avg"], stop=stop, entry_t=utc(time.time()), bar=bar, link_id=link,
                              order_id=f["order_id"], entry_fee_usdt=f["fee_usdt"], cb_id=None, mark=lv[s]["close"])
        n_held += 1; real_px[(s, "buy")] = f["avg"]
        st["cb_pending"].append({"link": link, "body": {
            "side": "entry", "book": cfg["strategy"], "token_symbol": s.replace("USDT", ""), "trader": cfg["trader"],
            "trade_date": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "entry_price": f"{f['avg']:.10g}", "position_size": f"{net:.10g}",
            "reason": f"Majors Breakout (paper, Bybit Demo): {rec['why']}",
            "planned_exit": f"8h close < lo10 (now {lv[s]['lo10']:g}) or < stop {stop:.6g}"}})

    # 5. shadow book (rules only, same gates and data as the real book; strategy.md §6)
    shadow_moves = []
    if data_ok and not gates_all and not dry:
        fee = X["shadow_fee"]
        for s in ex_s:
            p = sh["pos"].pop(s); px = real_px.get((s, "sell"), tch[s][0])
            sh["cash"] += p["qty"] * px * (1 - fee); p.update(exit_px=px, exit_t=utc(time.time()), exit_why=ex_s[s])
            sh["closed"].append(p); shadow_moves.append(f"sell {s} @ {px:g}")
        if not gates_in:
            nv = sh["cash"] + sum(p["qty"] * tch[s][0] for s, p in sh["pos"].items() if s in tch)
            for s, w, stop, _ in en_s:
                px = real_px.get((s, "buy"), tch[s][1])
                q = float(entry_qty(cfg, w, nv, sh["cash"], px, stop, inst[s]))
                if q * px < inst[s]["min_amt"]:
                    continue
                sh["cash"] -= q * px
                sh["pos"][s] = dict(qty=q * (1 - fee), entry_px=px, stop=stop, entry_t=utc(time.time()), bar=bar, mark=lv[s]["close"])
                shadow_moves.append(f"buy {s} @ {px:g}")

    # 6. benchmark, marks, NAV, counters
    if not dry and data_ok and st["bh"] is None:
        st["bh"] = dict(qty=cfg["sleeve_usdt"] / tch["BTCUSDT"][1] * (1 - X["shadow_fee"]), px=tch["BTCUSDT"][1], t=utc(time.time()))
        st["started"] = utc(time.time())
    for b in (real, sh):
        for s, p in b["pos"].items():
            if s in marks: p["mark"] = marks[s]
    nav_r, nav_s = book_nav(real, marks), book_nav(sh, marks)
    nav_b = st["bh"]["qty"] * marks.get("BTCUSDT", st["bh"]["px"]) if st["bh"] else None
    wake_failed = bool(fail) or order_fail

    # 7. decision log
    phase = "paper (Bybit Demo)"
    out.append(f"**Majors Breakout · wake for the 8h candle closing {utc(close_t)}** · run {utc(now)} · phase: {phase}" + (" · **DRY RUN, nothing placed or saved**" if dry else ""))
    out.append("")
    out.append("| Coin | Close | hi20 | lo10 | sma90 | ATR14 | Held: entry / stop | Rules say | Action |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    acted = {o["sym"]: o for o in orders}
    skipped = {o[1] for o in overlay if o[0] == "skip"}
    for s in U:
        l = lv.get(s)
        held = f"{fmt(real['pos'][s]['entry_px'])} / {fmt(real['pos'][s]['stop'])}" if s in real["pos"] else "—"
        if not l:
            out.append(f"| {s[:-4]} | — | — | — | — | — | {held} | no data | none |"); continue
        rule = "exit" if s in rules_exit else "entry" if s in rules_entry else "hold" if s in held_before else "no signal"
        if s in acted:
            o = acted[s]
            act = f"{o['side']}: {o['result']}" if "result" in o and not o.get("filled") else f"{o['side']} {o['filled']:g} @ {fmt(o['avg'])}"
        else:
            act = "SKIPPED (overlay)" if s in skipped else "none"
        out.append(f"| {s[:-4]} | {fmt(l['close'])} | {fmt(l['hi20'])} | {fmt(l['lo10'])} | {fmt(l['sma90'])} | {fmt(l['atr14'], 4)} | {held} | {rule} | {act} |")
    out.append("")
    if orders:
        out.append("**Orders**")
        for o in orders:
            line = f"- {o['side'].upper()} {o['sym']}: {o['why']}."
            if "limit" in o:
                line += f" Touch {fmt(o['bid'])}/{fmt(o['ask'])}, IOC limit {fmt(o['limit'])}, qty {o['qty']:g}."
            if "status" in o:
                line += f" Filled {o['filled']:g} @ {fmt(o['avg'])}, fee ${o['fee_usdt']:.4f}, {o['status']}, {o['ms']} ms."
            if "result" in o:
                line += f" {o['result']}."
            if o["side"] == "buy" and o.get("filled"):
                line += f" Invalidated by an 8h close < lo10 or < stop {fmt(o['stop'])}."
            out.append(line)
    else:
        out.append("**No trade:** " + ("no data." if not data_ok else "no coin closed above its 20-candle high and 30-day average, and no held coin hit its exit."))
    for kind, s, why in overlay:
        out.append(f"- **Overlay {kind.replace('_', ' ')} {s}:** {why}")
    if gates_all or gates_in:
        out.append("**Gates:** " + "; ".join(gates_all + gates_in))
    if fail:
        out.append("**Failures:** " + "; ".join(fail))
    pos_txt = ", ".join(f"{s[:-4]} {p['qty']:g}" for s, p in real["pos"].items()) or "none"
    out.append("")
    out.append(f"**Books** (marked at closes) · Real ${nav_r:,.2f} (cash ${real['cash']:,.2f}; {pos_txt}) · Rules-only shadow ${nav_s:,.2f}"
               + (f" ({'; '.join(shadow_moves)})" if shadow_moves else "")
               + (f" · BTC buy-and-hold ${nav_b:,.2f} (from {st['bh']['t']} @ {fmt(st['bh']['px'])})" if nav_b else "")
               + f" · Day {day}: {-day_loss * 100:+.2f}% · failed wakes in a row: {st['failed_wakes'] + 1 if wake_failed else 0}")
    out.append("")
    out.append("Inputs: Bybit public spot 4h klines (mainnet, same feed as `bt.py`), Demo touch and fills; rules per `strategy.md`; limits per `" + cfg["limits_source"].split(".")[0] + "`.")

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
    st["overlay"].extend({"bar": bar, "kind": k, "sym": s, "why": w} for k, s, w in overlay)
    if data_ok and not late:
        st["last_bar"] = bar
    save_state(st)
    os.makedirs(os.path.join(STATE_DIR, "logs"), exist_ok=True)
    open(os.path.join(STATE_DIR, "logs", f"{bar}.md"), "w").write(text)
    if st["log_issue"]:
        try:
            pc("POST", f"/api/issues/{st['log_issue']}/comments", {"body": text})
        except Exception as e:
            print(f"\n!! decision log NOT posted to {st['log_issue']}: {e}", file=sys.stderr); return 2
    else:
        print("\n!! no log issue set (runner.py set-log-issue THE-xxx)", file=sys.stderr); return 2
    return 1 if wake_failed else 0


# ---------- test order (strategy.md §7; THE-321 step 8) ----------

def test_order(cfg, st, a):
    if a.usdt > cfg["execution"]["max_test_order_usdt"]:
        sys.exit(f"test orders are capped at ${cfg['execution']['max_test_order_usdt']}")
    k = creds(cfg)
    if not k:
        sys.exit("no Bybit Demo credentials yet")
    demo, s, inst = bybit.Demo(*k), a.symbol, bybit.instrument(a.symbol)
    rep = {"t": utc(time.time()), "symbol": s, "usdt": a.usdt, "balances_before": {c: v for c, v in demo.balances().items() if c in ("USDT", inst["base"])}}
    bid, ask = bybit.touch(s)
    px = limit_px("Buy", bid, ask, inst, cfg["execution"]["touch_offset"])
    q = rnd(a.usdt / float(px), inst["step"], ROUND_DOWN)
    b = place(demo, s, "Buy", q, px, f"mb-test-{int(time.time())}-b")
    rep["buy"] = dict(bid=bid, ask=ask, limit=float(px), qty=float(q), **b, slip_vs_ask_bps=(b["avg"] / ask - 1) * 1e4 if b["filled"] else None)
    net = rnd(b["filled"] - b["fee_base"], inst["step"], ROUND_DOWN)
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
    rep["balances_after"] = {c: v for c, v in demo.balances().items() if c in ("USDT", inst["base"])}
    st["test_orders"].append(rep); save_state(st)
    print(json.dumps(rep, indent=1))


def status(cfg, st, a):
    print(json.dumps({k: st[k] for k in ("started", "last_bar", "day", "failed_wakes", "halted", "log_issue", "wakes", "bh", "cb_pending")}, indent=1, default=str))
    for name in ("real", "shadow"):
        b = st[name]
        print(f"{name}: cash {b['cash']:.2f}, open {list(b['pos'])}, closed {len(b['closed'])}, dust {b['dust']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("wake"); w.add_argument("--dry-run", action="store_true")
    w.add_argument("--skip", action="append", default=[], metavar="SYM=REASON")
    w.add_argument("--exit-early", action="append", default=[], metavar="SYM=REASON")
    t = sub.add_parser("test-order"); t.add_argument("--symbol", default="DOGEUSDT"); t.add_argument("--usdt", type=float, default=10)
    sub.add_parser("status")
    for c in ("halt", "resume"):
        h = sub.add_parser(c); h.add_argument("--by", required=True); h.add_argument("--ref", required=True)
    li = sub.add_parser("set-log-issue"); li.add_argument("issue")
    a = ap.parse_args()
    for kv in getattr(a, "skip", []) + getattr(a, "exit_early", []):
        if "=" not in kv or not kv.split("=", 1)[1].strip():
            sys.exit(f"overlay needs a written reason: {kv!r} (use SYM=REASON)")
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
        st["halted"] = None
    elif a.cmd == "set-log-issue":
        st["log_issue"] = a.issue
    save_state(st); status(cfg, st, a)


if __name__ == "__main__":
    main()
