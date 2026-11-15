"""Majors Discretionary execution on Bybit Demo (strategy.md §4, risk-policy.md L3, L9, L10, O2, O3, O5, O7).

Every function takes the venue as an argument (bybit.Demo, or the fake in test_execute.py). Gate code: a change
here is a risk-policy change (risk-policy.md, Runner independence).
"""
import datetime as dt, hashlib, json, os, re, subprocess, time
from decimal import ROUND_DOWN, ROUND_UP

from inputs import bybit  # noqa: F401  (same module object the caller patches)
import runner as mb  # breakout runner helpers: rnd, limit_px, place, STOP_LIVE, cb_post

HERE = os.path.dirname(os.path.abspath(__file__))
RUNNER_PATHS = ("strategies/majors-discretionary/runner/", "strategies/majors-breakout/runner/")
TICKET_TTL = 60 * 60  # a ticket is valid for its own wake only: placed within 60 min of its log comment


def utc(t):
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d %H:%MZ")


def iso(t):
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).isoformat(timespec="seconds")


# ---------- tickets in the log (L10, O3) ----------

def canon(t):
    return json.dumps({k: v for k, v in t.items() if k != "id"}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(t):
    return hashlib.sha256(canon(t).encode()).hexdigest()


def render_ticket(t):
    return "```json\n" + json.dumps(t, indent=1, ensure_ascii=False) + "\n```"


def tickets_in(body):
    """Every ```json block in a comment that parses to a ticket with an id: {id: ticket}."""
    out = {}
    for m in re.finditer(r"```json\s*\n(.*?)\n```", body or "", re.S):
        try:
            t = json.loads(m.group(1))
        except ValueError:
            continue
        if isinstance(t, dict) and t.get("id"):
            out[t["id"]] = t
    return out


def verify(rec, comment):
    """O3 before the order: the ticket is in its log comment, unedited, and identical to what the runner will trade.
    Returns (problems, is_breach). A breach halts; an unreachable comment only refuses."""
    if comment is None:
        return [f"log comment `{rec['comment_id']}` could not be read: not placed"], False
    if comment.get("deletedAt"):
        return [f"O3: log comment `{rec['comment_id']}` was deleted"], True
    if comment.get("updatedAt") != comment.get("createdAt"):
        return [f"O3: log comment `{rec['comment_id']}` was edited after posting"], True
    t = tickets_in(comment.get("body")).get(rec["id"])
    if t is None:
        return [f"O3: ticket {rec['id']} is not in log comment `{rec['comment_id']}`"], True
    if digest(t) != rec["sha"]:
        return [f"O3: ticket {rec['id']} in the log differs from the one submitted"], True
    return [], False


# ---------- order gate (THE-321, Nadia 11 Nov: items 1-4) ----------

def repo_top():
    return subprocess.run(["git", "-C", HERE, "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True).stdout.strip()


def merged_gate():
    """Items 1-2 and O7: strategy.md, risk-policy.md and this runner are on origin/master, and the runner that is about
    to trade is byte-identical to the merged one. Returns the list of what's missing (empty = met)."""
    try:
        top = repo_top()
        subprocess.run(["git", "-C", top, "fetch", "-q", "origin", "master"], capture_output=True, timeout=60)
        tree = subprocess.run(["git", "-C", top, "ls-tree", "-r", "--name-only", "origin/master", "strategies/"],
                              capture_output=True, text=True, check=True).stdout.split()
    except Exception as e:
        return [f"git check failed: {e}"]
    need = ["strategies/majors-discretionary/strategy.md", "strategies/majors-discretionary/risk-policy.md",
            "strategies/majors-discretionary/runner/mdisc.py", "strategies/majors-discretionary/runner/execute.py",
            "strategies/majors-discretionary/runner/tickets.py"]
    miss = [f"{p} not on master" for p in need if p not in tree]
    if not miss:
        d = subprocess.run(["git", "-C", top, "diff", "--name-only", "origin/master", "--", *RUNNER_PATHS],
                           capture_output=True, text=True).stdout.split()
        d += subprocess.run(["git", "-C", top, "ls-files", "--others", "--exclude-standard", "--", *RUNNER_PATHS],
                            capture_output=True, text=True).stdout.split()
        d = [x for x in d if "__pycache__" not in x]
        if d:
            miss.append("O7: runner differs from origin/master (" + ", ".join(sorted(set(d))) + ")")
    return miss


def venue_gate(st, demo):
    """Items 3-4: the key passes the read-only check and the resting stop-market test has passed."""
    miss = []
    if demo is None:
        miss.append("no Bybit Demo credentials")
    else:
        try:
            demo.query_api()
        except Exception as e:
            miss.append(f"Demo key check failed ({e})")
    if not (st.get("stop_test") or {}).get("ok"):
        miss.append("resting stop-market test on Demo not passed (mdisc.py test-order)")
    return miss


# ---------- lots ----------

def open_lots(st):
    return {k: l for k, l in st["lots"].items() if l["qty"] > 0}


def inst_of(inst, coin):
    return inst.get(coin) or bybit.instrument(coin + "USDT")


def _live(demo, sym, oid):
    o = demo.stop_status(sym, oid)
    return (o or {}).get("orderStatus") in mb.STOP_LIVE + ("PartiallyFilled",), o


def place_stop(demo, lot, inst, link):
    """L3: the lot's resting stop-market sell for its whole quantity. Returns (order dict or None, error)."""
    q = mb.rnd(lot["qty"], inst["step"], ROUND_DOWN)
    trig = mb.rnd(lot["stop"], inst["tick"], ROUND_UP)
    if float(q) < inst["min_qty"] or float(q) * float(trig) < inst["min_amt"]:
        return None, f"{q} is below the venue minimum at the stop"
    err = None
    for _ in range(2):  # O5: retry once before reporting the lot unprotected
        try:
            oid = demo.stop_sell(lot["coin"] + "USDT", format(q, "f"), format(trig, "f"), link)
            return dict(id=oid, px=float(trig), qty=float(q)), None
        except Exception as e:
            err = str(e)
    return None, err


def place_target(demo, lot, inst, link):
    q = mb.rnd(lot["qty"], inst["step"], ROUND_DOWN)
    px = mb.rnd(lot["target"], inst["tick"], ROUND_UP)
    try:
        return dict(id=demo.limit_sell(lot["coin"] + "USDT", format(q, "f"), format(px, "f"), link), px=float(px), qty=float(q)), None
    except Exception as e:
        return None, str(e)


def cancel_resting(demo, lot):
    """Cancel the lot's own stop and target (never another lot's). Returns problems; non-empty = don't sell."""
    sym, bad = lot["coin"] + "USDT", []
    for k, stop in (("stop_order", True), ("target_order", False)):
        o = lot.get(k)
        if not o:
            continue
        try:
            demo.cancel(sym, o["id"], stop=stop); lot[k] = None
        except Exception as e:
            live, _ = _live(demo, sym, o["id"])
            if live:
                bad.append(f"{k.split('_')[0]} `{o['id']}` not cancelled ({e})")
            else:
                lot[k] = None
    return bad


def book_sell(st, lot, q, cost, fee_q, ref_px):
    """Cash and cost for a sell on a lot. ref_px: the mid when sent (or the stop trigger for a stop fill)."""
    st["cash"] += cost - fee_q
    lot["qty"] -= q
    lot.setdefault("exit_fills", []).append([q, cost / q, fee_q])
    return fee_q + max(ref_px * q - cost, 0.0)


def settle(cfg, st, lid, lot, why, bid, inst, now):
    """A lot whose remainder can't be sold is closed: dust stays marked in NAV, the Crypto Book exit is queued."""
    if lot["qty"] > 0 and (lot["qty"] * bid >= inst["min_amt"] and lot["qty"] >= inst["min_qty"]):
        return False
    if lot["qty"] > 0:
        st["dust"][lot["coin"]] = st["dust"].get(lot["coin"], 0) + lot["qty"]; lot["qty"] = 0
    xf = lot.pop("exit_fills", [])
    q = sum(x[0] for x in xf) or 1
    lot.update(exit_px=sum(x[0] * x[1] for x in xf) / q, exit_t=iso(now), exit_why=why, exit_fee_usdt=sum(x[2] for x in xf),
               pnl=sum(x[0] * x[1] - x[2] for x in xf) - lot["entry_cost_usdt"])
    st["closed"].append(dict(lot, lot=lid)); del st["lots"][lid]
    st["cb_pending"].append({"entry_link": lot["link"], "body": {
        "side": "exit", "book": cfg["strategy"], "token_symbol": lot["coin"], "trader": cfg["trader"], "trade_date": iso(now),
        "exit_price": f"{lot['exit_px']:.10g}", "reason": f"{lid} ({lot['ticket']}): {why}"}})
    return True


def sweep(cfg, st, demo, inst, now, orders, notes):
    """Resting stops and targets that filled between wakes close (part of) their lot; a vanished stop is re-placed
    later by ensure_stops. Returns errors (a failed check = an unresolved error for O1)."""
    errs = []
    for lid, lot in list(open_lots(st).items()):
        sym = lot["coin"] + "USDT"
        for k in ("stop_order", "target_order"):
            o = lot.get(k)
            if not o or lid not in st["lots"]:
                continue
            try:
                live, rec = _live(demo, sym, o["id"])
                if live:
                    continue
                F = demo.fills(sym, o["id"]) if rec else []
            except Exception as e:
                errs.append(f"{lid} {k.split('_')[0]} check: {e}"); continue
            lot[k] = None
            q = sum(f[0] for f in F)
            if not q:
                notes.append(f"{lid} {lot['coin']} {k.split('_')[0]} `{o['id']}` is {(rec or {}).get('orderStatus', 'unknown to Bybit')} with no fill")
                continue
            cost, fee_q = sum(f[0] * f[1] for f in F), sum(f[2] for f in F if f[3] == "USDT")
            why = f"{'stop' if k == 'stop_order' else 'target'} {o['px']:g} filled on the venue between wakes"
            st["week"]["cost"] += book_sell(st, lot, q, cost, fee_q, o["px"])
            orders.append(dict(kind="exit", lot=lid, coin=lot["coin"], why=why, filled=q, avg=cost / q, fee_usdt=fee_q,
                               status=(rec or {}).get("orderStatus")))
            other = "target_order" if k == "stop_order" else "stop_order"
            if lot.get(other):  # the other resting order would now oversell: cancel it; ensure_stops re-places a stop
                try:
                    demo.cancel(sym, lot[other]["id"], stop=other == "stop_order"); lot[other] = None
                except Exception as e:
                    if _live(demo, sym, lot[other]["id"])[0]:
                        errs.append(f"{lid} {other.split('_')[0]} `{lot[other]['id']}` not cancelled after the {k.split('_')[0]} filled ({e})")
                    else:
                        lot[other] = None
            settle(cfg, st, lid, lot, why, o["px"], inst_of(inst, lot["coin"]), now)
    return errs


def ensure_stops(st, demo, inst, notes):
    """O5: every open lot has its resting stop. Returns the lots left unprotected."""
    bad = []
    for lid, lot in open_lots(st).items():
        if lot.get("stop_order"):
            continue
        o, err = place_stop(demo, lot, inst_of(inst, lot["coin"]), f"md-{lid}-s{int(time.time())}")
        if o:
            lot["stop_order"] = o; notes.append(f"{lid} {lot['coin']} stop re-placed: sell {o['qty']:g} if ≤ {o['px']:g} (`{o['id']}`)")
        else:
            bad.append(lid); notes.append(f"**{lid} {lot['coin']} has NO resting stop** ({err}): unprotected (O5)")
    return bad


def reconcile(st, bal, inst, coins, notes):
    """O2: lots + dust + the baseline captured at the first venue read equal each coin's Demo balance."""
    held = {c: sum(l["qty"] for l in st["lots"].values() if l["coin"] == c) + st["dust"].get(c, 0) for c in coins}
    bad = []
    if st.get("venue_base") is None:
        if any(held.values()):
            return ["no venue baseline while lots are open"]
        st["venue_base"] = {c: bal.get(c, 0.0) for c in coins}
        notes.append("Venue baseline captured (Demo balances outside the sleeve): " + ", ".join(f"{c} {q:g}" for c, q in st["venue_base"].items()))
    for c in coins:
        want, got = st["venue_base"].get(c, 0.0) + held[c], bal.get(c, 0.0)
        step = float(inst[c]["step"]) if c in inst else 1e-8
        if abs(got - want) > max(1e-6 * max(abs(want), abs(got)), step):
            bad.append(f"{c} Demo {got:g} ≠ baseline + lots {want:g}")
    return bad


# ---------- the three ticket kinds ----------

def do_entry(cfg, st, demo, plan, rec, inst, now):
    X, c = cfg["execution"], plan["coin"]
    sym, I = c + "USDT", inst_of(inst, c)
    bid, ask = bybit.touch(sym)
    mid = (bid + ask) / 2
    px = min(mb.rnd(plan["limit"], I["tick"], ROUND_DOWN), mb.limit_px("Buy", bid, ask, I, X["touch_offset"]))
    q = mb.rnd(plan["qty"], I["step"], ROUND_DOWN)
    out = dict(kind="entry", ticket=rec["id"], coin=c, bid=bid, ask=ask, limit=float(px), qty=float(q))
    if float(px) * float(q) - plan["value"] > 1e-6 or float(q) * (float(px) - plan["stop"]) > plan["risk"] + 1e-6:
        out["result"] = "REFUSED: rounding would exceed the checked size"; return out, None
    link = f"md-{rec['id']}"
    f = mb.place(demo, sym, "Buy", q, px, link)
    out.update(f)
    if f["filled"] <= 0:
        out["result"] = "IOC not filled: ticket expired (no resting buys, L9)"; return out, None
    net = f["filled"] - f["fee_base"]
    cost = f["fee_usdt"] + max(f["avg"] - mid, 0) * f["filled"]
    st["cash"] -= f["cost"] + f["fee_quote"]
    st["week"]["cost"] += cost
    lid = f"L-{st['next_lot']:04d}"; st["next_lot"] += 1
    t = rec["ticket"]
    lot = dict(coin=c, qty=net, entry_px=f["avg"], stop=plan["stop"], target=plan["target"], time_limit_utc=plan["time_limit_utc"],
               ticket=rec["id"], link=link, order_id=f["order_id"], entry_t=iso(now), entry_cost_usdt=f["cost"] + f["fee_quote"],
               entry_fee_usdt=f["fee_usdt"], slip_usdt=cost - f["fee_usdt"], mid_at_send=mid, risk_usdt=net * (f["avg"] - plan["stop"]),
               thesis=t["thesis"], forecast_24h=t["forecast_24h"], stop_order=None, target_order=None, cb_id=None, history=[])
    st["lots"][lid] = lot
    out["lot"] = lid
    so, err = place_stop(demo, lot, I, f"md-{lid}-s")
    lot["stop_order"] = so
    out["stop"] = f"resting stop-market sell {so['qty']:g} if ≤ {so['px']:g} (`{so['id']}`)" if so else f"**stop NOT placed** ({err})"
    if lot["target"] is not None and X.get("resting_target"):
        to, err = place_target(demo, lot, I, f"md-{lid}-t")
        lot["target_order"] = to
        out["target"] = f"resting limit sell at {to['px']:g} (`{to['id']}`)" if to else f"target not resting ({err}): taken at a wake"
    th = t["thesis"]
    st["cb_pending"].append({"link": link, "body": {
        "side": "entry", "book": cfg["strategy"], "token_symbol": c, "trader": cfg["trader"], "trade_date": iso(now),
        "entry_price": f"{f['avg']:.10g}", "position_size": f"{net:.10g}",
        "reason": f"{lid} ({rec['id']}, paper, Bybit Demo, p24h {t['forecast_24h']}): {th['why_now']} Invalidated if: {th['invalidated_if']}",
        "planned_exit": f"stop {plan['stop']:g} (resting)" + (f"; target {plan['target']:g}" if plan["target"] else "")
                        + (f"; time limit {plan['time_limit_utc']}" if plan["time_limit_utc"] else "")}})
    return out, (None if so else lid)


def do_exit(cfg, st, demo, plan, rec, inst, now):
    X, lid = cfg["execution"], plan["lot"]
    lot = st["lots"][lid]
    sym, I = lot["coin"] + "USDT", inst_of(inst, lot["coin"])
    out = dict(kind="exit", ticket=rec["id"], lot=lid, coin=lot["coin"], why=plan["reason"], filled=0.0, cost=0.0, fee_usdt=0.0, attempts=0)
    bad = cancel_resting(demo, lot)
    if bad:
        out["result"] = "not placed: " + "; ".join(bad); return out, True
    want = min(plan["qty"], lot["qty"])
    left = want
    for i in range(X["exit_attempts"]):
        bid, ask = bybit.touch(sym)
        q = mb.rnd(left, I["step"], ROUND_DOWN)
        if float(q) < I["min_qty"] or float(q) * bid < I["min_amt"]:
            break
        f = mb.place(demo, sym, "Sell", q, mb.limit_px("Sell", bid, ask, I, X["touch_offset"]), f"md-{rec['id']}-x{i}")
        out["attempts"] += 1; out.update(bid=bid, ask=ask, status=f["status"])
        if f["filled"]:
            st["week"]["cost"] += book_sell(st, lot, f["filled"], f["cost"], f["fee_usdt"], (bid + ask) / 2)
            out["filled"] += f["filled"]; out["cost"] += f["cost"]; out["fee_usdt"] += f["fee_usdt"]
            left -= f["filled"]
    out["avg"] = out["cost"] / out["filled"] if out["filled"] else 0.0
    bid = bybit.touch(sym)[0]
    if settle(cfg, st, lid, lot, plan["reason"], bid, I, now):
        out["result"] = f"lot closed, VWAP {st['closed'][-1]['exit_px']:g}"; return out, False
    unfilled = left > 0 and left * bid >= I["min_amt"]
    out["result"] = (f"partial: {lot['qty']:g} left in the lot" if not unfilled else
                     f"IOC {'partly ' if out['filled'] else 'not '}filled: {lot['qty']:g} left, stop re-placed; a new exit ticket is needed")
    return out, unfilled


def do_adjust(cfg, st, demo, plan, rec, inst, now):
    lid = plan["lot"]
    lot = st["lots"][lid]
    sym, I = lot["coin"] + "USDT", inst_of(inst, lot["coin"])
    out, err = dict(kind="adjust", ticket=rec["id"], lot=lid, coin=lot["coin"], why=plan["reason"], done=[]), False
    if "stop" in plan:
        new, old = mb.rnd(plan["stop"], I["tick"], ROUND_UP), lot["stop"]
        o = lot.get("stop_order")
        try:
            if o:
                demo.amend_stop(sym, o["id"], format(new, "f")); o["px"] = float(new)
            lot["stop"] = plan["stop"]; out["done"].append(f"stop {old:g} → {plan['stop']:g}")
        except Exception as e:  # amend refused: place the new stop first, then cancel the old one, so the lot is never bare
            n, perr = place_stop(demo, dict(lot, stop=plan["stop"]), I, f"md-{rec['id']}-s")
            if n:
                try:
                    demo.cancel(sym, o["id"], stop=True)
                except Exception as ce:
                    out["done"].append(f"old stop `{o['id']}` not cancelled ({ce})"); err = True
                lot["stop_order"], lot["stop"] = n, plan["stop"]; out["done"].append(f"stop → {plan['stop']:g} (replaced, `{n['id']}`)")
            else:
                out["done"].append(f"stop not moved (amend: {e}; replace: {perr}); the old stop {lot['stop']:g} stays"); err = True
    if "time_limit_utc" in plan:
        lot["time_limit_utc"] = plan["time_limit_utc"]; out["done"].append(f"time limit → {plan['time_limit_utc']}")
    if "target" in plan:
        lot["target"] = float(plan["target"])
        if cfg["execution"].get("resting_target"):
            if lot.get("target_order"):
                try:
                    demo.cancel(sym, lot["target_order"]["id"]); lot["target_order"] = None
                except Exception as e:
                    out["done"].append(f"old target not cancelled ({e})"); err = True
            if not lot.get("target_order"):
                to, terr = place_target(demo, lot, I, f"md-{rec['id']}-t")
                lot["target_order"] = to
                out["done"].append(f"target → {lot['target']:g}" + ("" if to else f" (not resting: {terr})"))
        else:
            out["done"].append(f"target → {lot['target']:g}")
    lot["history"].append(dict(t=iso(now), ticket=rec["id"], stop=lot["stop"], target=lot["target"], time_limit_utc=lot["time_limit_utc"]))
    out["result"] = "; ".join(out["done"])
    return out, err


# ---------- Crypto Book ----------

def cb_flush(cfg, st, notes):
    """POST queued rows. Exits wait for their entry's id. Failures stay queued (O2 checks the Crypto Book too)."""
    keep, rows = [], list(st["lots"].values()) + st["closed"]
    for item in st["cb_pending"]:
        body = dict(item["body"])
        if body["side"] == "exit":
            eid = next((r["cb_id"] for r in rows if r.get("link") == item["entry_link"] and r.get("cb_id")), None)
            if not eid:
                keep.append(item); continue
            body["entry_trade_id"] = eid
        try:
            tid = mb.cb_post(cfg, body)
            if body["side"] == "entry":
                for r in rows:
                    if r.get("link") == item["link"]:
                        r["cb_id"] = tid
            notes.append(f"Crypto Book {body['side']} {body['token_symbol']} recorded (`{tid}`)")
        except Exception as e:
            keep.append(item); notes.append(f"Crypto Book {body['side']} {body['token_symbol']} **not recorded** ({e}); retried next run")
    st["cb_pending"] = keep
