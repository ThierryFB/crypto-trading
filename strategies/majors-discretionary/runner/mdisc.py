#!/usr/bin/env python3
"""Majors Discretionary runner (strategy.md §2-§8, risk-policy.md L1-L11, D1-D3, O1-O7). Ticket-driven: no
ticket, no order. Each wake is two steps, so every ticket is in the decision log before its order (L10, O3):

  mdisc.py inputs                      print the §3 data block (step 1)
  mdisc.py post WAKE.json              steps 2-5: check WAKE.json, record the six forecasts, post the decision log
                                       (read, forecasts, position review, tickets with ids and their pre-check)
  mdisc.py execute                     step 6: re-read the posted log, verify each ticket (O3), re-check it at the
                                       current touch, place what passes; sweep fired stops, keep every stop resting,
                                       reconcile with Demo, run the shadow book, Crypto Book rows; post the fills
  mdisc.py wake WAKE.json              post, then execute
  mdisc.py key-check                   read-only /v5/user/query-api: permissions and read-only flag, never the key
  mdisc.py test-order [--usdt 18]      the Demo stop-market test (order gate item 4); outside the sleeve
  mdisc.py score | status | backfill THE-334 | halt --by X --ref Y | resume --by Nadia --ref Y [--rebaseline]

WAKE.json: {"read": "...", "news": "...", "forecasts": {"BTC": 0.55, ...all six}, "review": {"L-0001": "..."},
            "tickets": [ticket, ...], "no_trade": "reason (when there are no tickets)"}; tickets per strategy.md §4.
State lives in $MD_STATE_DIR (default: Leo's persistent workspace), never in the repo.
"""
import argparse, datetime as dt, fcntl, json, os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import inputs, tickets, forecasts, execute as ex, shadow  # noqa: E402
from inputs import bybit, engine  # noqa: E402
import runner as mb  # noqa: E402

STATE_DIR = os.environ.get("MD_STATE_DIR",
                           "/paperclip/instances/default/workspaces/a3ae5ff4-6eb6-4daa-9169-f2568b7087ba/majors-discretionary-state")
LOG_DEADLINE = 60 * 60  # O1: the decision log within 60 min of the scheduled wake


def load_cfg():
    return json.load(open(os.path.join(HERE, "config.json")))


def load_state(cfg):
    p = os.path.join(STATE_DIR, "state.json")
    st = json.load(open(p)) if os.path.exists(p) else {}
    for k, v in dict(version=2, cash=float(cfg["sleeve_usdt"]), lots={}, closed=[], dust={}, next_lot=1, forecasts=[], week=None,
                     day=None, halted=None, wakes=[], tickets={}, cb_pending=[], venue_base=None, stop_test=None, test_orders=[],
                     started=None, shadow=None, bh=None, log_issue=cfg["log_issue"]).items():
        st.setdefault(k, v)
    return st


def save_state(st):
    os.makedirs(STATE_DIR, exist_ok=True)
    p = os.path.join(STATE_DIR, "state.json")
    with open(p + ".tmp", "w") as f:
        json.dump(st, f, indent=1)
    os.replace(p + ".tmp", p)


def lock():
    os.makedirs(STATE_DIR, exist_ok=True)
    f = open(os.path.join(STATE_DIR, "lock"), "w")
    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    return f


# ---------- time ----------

def slots(cfg, day0, day1):
    out = []
    for d in range(day0, day1 + 1):
        for s in cfg["wakes_utc"]:
            h, m = map(int, s.split(":"))
            out.append(d * 86400 + h * 3600 + m * 60)
    return out


def sched_for(cfg, now):
    """The scheduled wake this run belongs to: the latest slot at or before now."""
    return max(s for s in slots(cfg, int(now // 86400) - 1, int(now // 86400)) if s <= now)


def week_start(t):
    return int(t // 86400 - (dt.datetime.fromtimestamp(t, dt.timezone.utc).weekday())) * 86400


def roll(st, now, nav):
    """Day NAV = the first NAV seen in the UTC day (the 00:05 wake); week NAV and cost reset on Monday 00:00 UTC."""
    day = dt.datetime.fromtimestamp(now, dt.timezone.utc).strftime("%Y-%m-%d")
    if not st["day"] or st["day"]["date"] != day:
        st["day"] = {"date": day, "nav": nav}
    if not st["week"] or st["week"]["start"] != week_start(now):
        st["week"] = {"start": week_start(now), "nav": nav, "cost": 0.0}


def streak(st):
    n = 0
    for w in reversed(st["wakes"]):
        if not w.get("failed") or w["sched"] <= (st.get("streak_reset") or 0):
            break
        n += 1
    return n


# ---------- book ----------

def nav(st, mids):
    lots = ex.open_lots(st).values()
    return st["cash"] + sum(l["qty"] * mids.get(l["coin"], l["entry_px"]) for l in lots) + \
        sum(q * mids.get(c, 0) for c, q in st["dust"].items())


def halt_reasons(cfg, st, n, check_issues=True):
    L, out = cfg["limits"], []
    if st["halted"]:
        out.append(f"halted by {st['halted']['by']} ({st['halted']['ref']})")
    if n <= L["D3_halt_nav_usdt"]:
        out.append(f"D3: NAV ${n:.2f} ≤ ${L['D3_halt_nav_usdt']}")
    if st["day"] and st["day"]["nav"] and 1 - n / st["day"]["nav"] >= L["D2_day_halt_nav"]:
        out.append(f"D2: day loss ≥ {L['D2_day_halt_nav']:.0%}")
    if streak(st) >= L["O1_halt_failed_wakes"]:
        out.append(f"O1: {streak(st)} failed wakes in a row")
    if check_issues:
        try:
            out += [f"open halt issue {h}" for h in mb.halt_issues(cfg)]
        except Exception as e:
            out.append(f"could not check for HALT issues ({e})")
    return out


def ctx_for(cfg, st, touch, inst, now, halted, forecasts_, prev_wake):
    mids = {c: (b + a) / 2 for c, (b, a) in touch.items()}
    n = nav(st, mids)
    return dict(nav=n, cash=st["cash"], week_start_nav=st["week"]["nav"], week_cost=st["week"]["cost"],
                day_loss=1 - n / st["day"]["nav"] if st["day"]["nav"] else 0, halted=halted, touch=touch,
                inst={c: dict(min_qty=i["min_qty"], min_amt=i["min_amt"]) for c, i in inst.items()}, now=now,
                prev_wake=prev_wake,
                lots={k: dict(coin=l["coin"], qty=l["qty"], entry_px=l["entry_px"], stop=l["stop"]) for k, l in ex.open_lots(st).items()},
                forecasts=forecasts_, entries_this_wake=0, new_coins_this_wake=0, coins_this_wake=set())


def market(cfg):
    """Demo touch and instrument data for every coin; a coin that fails is left out (and its tickets refused)."""
    touch, inst, errs = {}, {}, []
    for s in cfg["universe"]:
        try:
            touch[s[:-4]] = bybit.touch(s); inst[s[:-4]] = bybit.instrument(s)
        except Exception as e:
            errs.append(f"{s[:-4]} touch: {e}")
    return touch, inst, errs


def closes_8h(cfg, now):
    out = {}
    for s in cfg["universe"]:
        B = engine.bars8h(bybit.klines4h(s), now)
        out[s[:-4]] = {k + engine.BAR: v[3] for k, v in B.items()}
    return out


def score(cfg, st, now):
    if any(r["y"] is None and r["resolve_t"] <= now for r in st["forecasts"]):
        try:
            forecasts.resolve(st["forecasts"], closes_8h(cfg, now))
        except Exception as e:
            return f"Forecasts: resolution skipped ({e})."
    return forecasts.score_block(st["forecasts"])


def books_block(cfg, st, mids):
    n = nav(st, mids)
    budget = cfg["limits"]["L8_week_cost_nav"] * st["week"]["nav"]
    s = (f"**Book:** NAV ${n:,.2f} (cash ${st['cash']:,.2f}) · day {st['day']['date']} {n / st['day']['nav'] - 1:+.2%} · "
         f"week cost ${st['week']['cost']:.2f} of ${budget:.2f} (L8) · failed wakes in a row: {streak(st)}")
    marks = {c + "USDT": p for c, p in mids.items()}
    return s + "\n" + shadow.render(st["shadow"], marks, st["bh"], cfg["sleeve_usdt"])


def post_comment(st, body):
    if not st["log_issue"]:
        raise RuntimeError("no log issue in config.json")
    return mb.pc("POST", f"/api/issues/{st['log_issue']}/comments", {"body": body})


# ---------- post (steps 2-5) ----------

def fmt(x):
    return f"{x:,.6g}" if abs(x) < 1000 else f"{x:,.1f}"


def cmd_post(cfg, st, a):
    w = json.load(open(a.wake))
    now = time.time()
    sched = sched_for(cfg, now)
    if st["wakes"] and st["wakes"][-1]["sched"] >= sched:
        sys.exit(f"the {ex.utc(sched)} wake is already posted (comment `{st['wakes'][-1]['comment_id']}`); post a correction by hand")
    coins = [s[:-4] for s in cfg["universe"]]
    sweep_notes, sweep_orders = [], []
    if ex.open_lots(st):  # stops and targets that filled since the last run, so the review is against the real book
        k = mb.creds(cfg)
        if k:
            touch0, inst0, _ = market(cfg)
            roll(st, now, nav(st, {c: (b_ + a_) / 2 for c, (b_, a_) in touch0.items()}))
            sweep_notes += ex.sweep(cfg, st, bybit.Demo(*k), inst0, now, sweep_orders, sweep_notes)
        else:
            sweep_notes.append("no Bybit Demo credentials: fired stops not checked")
    problems = []
    if not str(w.get("read", "")).strip():
        problems.append("no market read")
    fp, _ = tickets.check_wake({"forecasts": w.get("forecasts")}, dict(lots={}, touch={}, nav=1, cash=1, week_start_nav=1, week_cost=0,
                               day_loss=0, halted=[], inst={}, now=now, prev_wake=None), cfg)
    problems += fp
    lots = ex.open_lots(st)
    review = w.get("review") or {}
    problems += [f"no review for {lid} ({l['coin']})" for lid, l in lots.items() if not str(review.get(lid, "")).strip()]
    T = w.get("tickets") or []
    if not T and not str(w.get("no_trade", "")).strip():
        problems.append("no tickets and no no-trade reason")
    if problems:
        sys.exit("not posted, fix WAKE.json: " + "; ".join(problems))

    D = inputs.collect(cfg["universe"], now)
    touch, inst, merr = market(cfg)
    missing = [c for c in coins if c not in D["coins"] or c not in touch]
    if missing:
        sys.exit("not posted: no price for " + ", ".join(missing) + " (" + "; ".join(D["errors"] + merr) + "); retry")
    mids = {c: (b + a_) / 2 for c, (b, a_) in touch.items()}
    roll(st, now, nav(st, mids))
    halted = halt_reasons(cfg, st, nav(st, mids))
    gate = ex.merged_gate() + ([] if (st.get("stop_test") or {}).get("ok") else ["Demo stop-market test not passed"])
    F = {c: float(w["forecasts"][c]) for c in coins}
    ctx = ctx_for(cfg, st, touch, inst, now, halted, F, st["wakes"][-1]["sched"] if st["wakes"] else None)
    _, res = tickets.check_wake({"forecasts": F, "tickets": T}, ctx, cfg)

    # missed wakes since the last posted one count as failed (O1)
    prev = st["wakes"][-1]["sched"] if st["wakes"] else None
    missed = [s for s in slots(cfg, int(prev // 86400), int(sched // 86400)) if prev < s < sched] if prev else []
    late = now - sched > LOG_DEADLINE
    stamp = dt.datetime.fromtimestamp(sched, dt.timezone.utc)
    tid0 = stamp.strftime("T-%Y%m%d-%H%M")
    recs = []
    for i, t in enumerate(T, 1):
        t = {"id": f"{tid0}-{i}", **{k: v for k, v in t.items() if k != "id"}}
        recs.append(t)

    phase = "paper" if not gate else "definition (forecast-only)"
    L = [f"## Wake {stamp:%a %d %b %H:%M}Z: Majors Discretionary · phase: {phase}", ""]
    L.append((f"**LATE:** posted {(now - sched) / 60:.0f} min after the scheduled time, so this wake fails O1." if late else
              f"**On time** (posted {ex.utc(now)[11:]}).")
              + (f" **Missed wakes:** {', '.join(ex.utc(s) for s in missed)} (each counts as failed)." if missed else ""))
    L.append("**Halts:** " + ("; ".join(halted) + ". Entries refused; exits only as risk-policy.md allows." if halted else
                              "none (no open `HALT — majors-discretionary` / `HALT — desk` issue, no runner halt)."))
    L.append("**Order gate:** " + ("met." if not gate else "not met: " + "; ".join(gate) + ". No ticket is placed."))
    L += ["", f"### Inputs (runner, {ex.utc(D['t'])[11:]})", inputs.render(D)]
    if str(w.get("news", "")).strip():
        L += ["", w["news"].strip()]
    L += ["", "### Market read", w["read"].strip()]
    rt = forecasts.resolve_close_t(now)
    L += ["", f"### Forecasts: P(higher at the {ex.utc(rt)} 8h close than the mid at this wake)",
          "| " + " | ".join(coins) + " |", "|" + "---|" * len(coins),
          "| " + " | ".join(f"{F[c]:.2f}" for c in coins) + " |",
          "| " + " | ".join(fmt(mids[c]) for c in coins) + " |"]
    if str(w.get("forecast_note", "")).strip():
        L.append(w["forecast_note"].strip())
    L += ["", "### Position review"]
    L += [f"- {o['lot']} {o['coin']}: {o['why']}: sold {o['filled']:g} @ {o['avg']:g}" for o in sweep_orders]
    L += [f"- {n}" for n in sweep_notes]
    if lots:
        L += ["| Lot | Coin | Qty | Entry | Mid | P&L | Stop (resting) | Target | Time limit |", "|---|---|---|---|---|---|---|---|---|"]
        for lid, l in lots.items():
            so = l.get("stop_order")
            L.append(f"| {lid} | {l['coin']} | {l['qty']:g} | {fmt(l['entry_px'])} | {fmt(mids[l['coin']])} | "
                     f"{(mids[l['coin']] - l['entry_px']) * l['qty']:+.2f} | {fmt(l['stop'])} ({'yes' if so else '**NO**'}) | "
                     f"{fmt(l['target']) if l['target'] else '—'} | {l['time_limit_utc'] or '—'} |")
        for lid, l in lots.items():
            flags = []
            if l["time_limit_utc"] and tickets.ts(l["time_limit_utc"]) <= now and not any(
                    t.get("lot") == lid and (t["type"] == "exit" or t.get("time_limit_utc")) for t in T):
                flags.append("**past its time limit with no exit and no new time limit** (drift check 6)")
            if l["target"] and mids[l["coin"]] >= l["target"] and not l.get("target_order"):
                flags.append("at or above its target")
            L.append(f"- **{lid} {l['coin']}** ({l['ticket']}): {review[lid].strip()}" + (" · " + "; ".join(flags) if flags else ""))
    else:
        L.append("No open positions.")
    L += ["", "### Decision"]
    if recs:
        for t, (_, plan, bad) in zip(recs, res):
            L.append(ex.render_ticket(t))
            if bad:
                L.append(f"Pre-check: **REFUSED**: {'; '.join(bad)}.")
            elif plan["type"] == "entry":
                L.append(f"Pre-check: OK at the touch now: {plan['qty']:.6g} {plan['coin']} ≈ ${plan['value']:.2f}, "
                         f"${plan['risk']:.2f} at risk to {plan['stop']:g}" + (f"; {plan['note']}" if plan["note"] else "") + ".")
            else:
                L.append("Pre-check: OK.")
        L.append("The runner re-checks each ticket at the touch when it places it; the fills follow in the next comment.")
    else:
        L.append(f"**No trade:** {w['no_trade'].strip()}")
    L += ["", "### Books and score", books_block(cfg, st, mids), score(cfg, st, now)]
    body = "\n".join(L)
    if a.dry_run:
        print(body); return 0
    if sweep_orders:
        save_state(st)  # the fills are booked even if the post fails
    c = post_comment(st, body)
    posted = tickets.ts(c["createdAt"]) if c.get("createdAt") else now
    st["forecasts"].extend(forecasts.record(now, F, mids, {c_: D["coins"][c_]["up24_90d"] for c_ in coins}))
    for s in missed:
        st["wakes"].append(dict(sched=s, failed=True, missed=True))
    W = dict(sched=sched, posted_t=posted, comment_id=c["id"], failed=late, tickets=[t["id"] for t in recs], forecasts=F, entries=0)
    st["wakes"].append(W)
    for t, (_, plan, bad) in zip(recs, res):
        st["tickets"][t["id"]] = dict(id=t["id"], ticket=t, sha=ex.digest(t), comment_id=c["id"], posted_t=posted, sched=sched,
                                      status="refused" if bad else "pending", result="pre-check: " + "; ".join(bad) if bad else None)
    if streak(st) >= cfg["limits"]["O1_halt_failed_wakes"] and not st["halted"]:
        st["halted"] = dict(by="runner", ref=f"O1: {streak(st)} failed wakes in a row; Ingrid reviews, Nadia resumes", t=ex.iso(now))
    save_state(st)
    print(f"posted {st['log_issue']} comment {c['id']}: {len(recs)} ticket(s), "
          f"{sum(1 for _, _, b in res if not b)} passed the pre-check")
    return 0


# ---------- execute (step 6) ----------

def cmd_execute(cfg, st, a):
    now = time.time()
    W = st["wakes"][-1] if st["wakes"] and not st["wakes"][-1].get("missed") else None
    pend = [st["tickets"][i] for i in (W["tickets"] if W else []) if st["tickets"][i]["status"] == "pending"]
    coins = [s[:-4] for s in cfg["universe"]]
    notes, orders, errs, out = [], [], [], []
    venue = bool(pend or ex.open_lots(st) or st["shadow"])  # nothing to trade or hold: forecast-only, no venue reads
    k = mb.creds(cfg) if venue else None
    demo = bybit.Demo(*k) if k else None
    touch, inst, merr = market(cfg)
    if venue:
        errs += merr
    bal = None
    if demo:
        try:
            bal = demo.balances()
        except Exception as e:
            errs.append(f"Demo balances: {e}")
    elif ex.open_lots(st):
        errs.append("no Bybit Demo credentials while lots are open")
    if bal is not None:
        errs += ex.sweep(cfg, st, demo, inst, now, orders, notes)
        recon = ex.reconcile(st, demo.balances(), inst, coins, notes)
        notes.append("Lots vs Demo balances: " + ("; ".join(recon) if recon else "every coin adds up"))
        if recon and not st["halted"]:
            st["halted"] = dict(by="runner", ref="O2: lots don't reconcile with the Demo balances; reconcile, then Nadia resumes", t=ex.iso(now))
    mids = {c: (b + a_) / 2 for c, (b, a_) in touch.items()}
    roll(st, now, nav(st, mids))
    halted = halt_reasons(cfg, st, nav(st, mids))
    gate = (ex.merged_gate() + ex.venue_gate(st, demo)) if pend else []
    if pend and bal is None and "no Bybit Demo credentials" not in gate:
        gate.append("Demo balances unreadable")
    ctx = ctx_for(cfg, st, touch, inst, now, halted, W["forecasts"] if W else {},
                  st["wakes"][-2]["sched"] if len(st["wakes"]) > 1 else None)
    ctx["entries_this_wake"] = W["entries"] if W else 0
    unresolved = False
    for rec in pend:
        t = rec["ticket"]
        tag = f"{rec['id']} {t.get('type')} {t.get('coin', '')}"
        if now - rec["posted_t"] > ex.TICKET_TTL:
            rec.update(status="expired", result=f"not placed within {ex.TICKET_TTL // 60} min of its log comment"); out.append((tag, rec["result"])); continue
        try:
            cm = mb.pc("GET", f"/api/issues/{st['log_issue']}/comments/{rec['comment_id']}")
        except Exception:
            cm = None
        probs, breach = ex.verify(rec, cm)
        if breach and not st["halted"]:
            st["halted"] = dict(by="runner", ref=probs[0], t=ex.iso(now))
            ctx["halted"] = ctx["halted"] + [probs[0]]
        if probs:
            rec.update(status="refused", result="; ".join(probs)); out.append((tag, "REFUSED: " + rec["result"])); continue
        if gate:
            rec.update(status="refused", result="order gate not met: " + "; ".join(gate)); out.append((tag, "not placed: " + rec["result"])); continue
        ctx["lots"] = {k_: dict(coin=l["coin"], qty=l["qty"], entry_px=l["entry_px"], stop=l["stop"]) for k_, l in ex.open_lots(st).items()}
        ctx["cash"], ctx["week_cost"], ctx["nav"] = st["cash"], st["week"]["cost"], nav(st, mids)
        plan, bad = tickets.check(t, ctx, cfg)
        if not bad and t["type"] == "exit" and ctx["halted"] and not (t.get("requested_by") and t.get("request_ref")):
            bad = ["under a halt, a discretionary exit needs requested_by (Nadia or Ingrid) and request_ref"]
        if not bad and t["type"] == "adjust" and ctx["halted"] and "stop" not in plan:
            bad = ["under a halt, only stop tightening is allowed"]
        if bad:
            rec.update(status="refused", result="; ".join(bad)); out.append((tag, "REFUSED: " + rec["result"])); continue
        try:
            o, fail = {"entry": ex.do_entry, "exit": ex.do_exit, "adjust": ex.do_adjust}[t["type"]](cfg, st, demo, plan, rec, inst, now)
        except Exception as e:
            rec.update(status="error", result=f"order error: {e}"); out.append((tag, rec["result"])); unresolved = True; continue
        orders.append(o)
        unresolved |= bool(fail)
        rec.update(status="placed", result=o.get("result") or "done", order=o)
        if t["type"] == "entry" and o.get("lot"):
            W["entries"] += 1; ctx["entries_this_wake"] += 1; ctx["coins_this_wake"].add(plan["coin"])
            if not st["started"]:  # paper starts at the first strategy order; the benchmarks start with it
                st["started"] = ex.iso(now)
                st["shadow"] = shadow.new(cfg["sleeve_usdt"], int(now // engine.BAR) * engine.BAR - engine.BAR, ex.iso(now))
                b, a_ = touch["BTC"]
                st["bh"] = dict(qty=cfg["sleeve_usdt"] / a_ * (1 - cfg["execution"]["shadow_fee"]), px=a_, t=ex.iso(now))
        out.append((tag, _order_line(o)))
    unprotected = ex.ensure_stops(st, demo, inst, notes) if demo and ex.open_lots(st) else (list(ex.open_lots(st)) if ex.open_lots(st) else [])
    moves = []
    if st["shadow"]:
        try:
            bars = {s: engine.bars8h(bybit.klines4h(s), now) for s in cfg["universe"]}
            moves = shadow.step(st["shadow"], bars, cfg["execution"]["shadow_fee"])
        except Exception as e:
            errs.append(f"shadow book: {e}")
    ex.cb_flush(cfg, st, notes)
    failed = bool(errs) or unresolved or bool(unprotected)
    if W:
        W["failed"] = W.get("failed") or failed
    if streak(st) >= cfg["limits"]["O1_halt_failed_wakes"] and not st["halted"]:
        st["halted"] = dict(by="runner", ref=f"O1: {streak(st)} failed wakes in a row; Ingrid reviews, Nadia resumes", t=ex.iso(now))

    L = [f"**Runner fills for the {ex.utc(W['sched']) if W else '—'} wake** (log `{W['comment_id'] if W else '—'}`) · run {ex.utc(now)}"]
    L += [f"- {tag}: {r}" for tag, r in out] or ["- No tickets to place."]
    L += [f"- {o['lot']} {o['coin']}: {o['why']}: sold {o['filled']:g} @ {o['avg']:g}" for o in orders if o["kind"] == "exit" and not o.get("ticket")]
    if moves:
        L.append("- Shadow moves since the last run: " + "; ".join(moves))
    L += [f"- {n}" for n in notes]
    if errs:
        L.append("- **Errors:** " + "; ".join(errs))
    if halted or st["halted"]:
        L.append("- **Halts:** " + "; ".join(halt_reasons(cfg, st, nav(st, mids), check_issues=False) or halted))
    L += ["", books_block(cfg, st, mids)]
    body = "\n".join(L)
    print(body)
    save_state(st)
    if a.no_post or (not pend and not orders and not notes_worth(notes)):
        return 1 if failed else 0
    try:
        post_comment(st, body)
    except Exception as e:
        print(f"!! fills comment NOT posted: {e}", file=sys.stderr)
        if W:
            W["failed"] = True; save_state(st)
        return 2
    return 1 if failed else 0


def notes_worth(notes):
    return any(not n.startswith("Lots vs Demo balances: every coin") for n in notes)


def _order_line(o):
    if o["kind"] == "entry":
        if not o.get("filled"):
            return f"{o.get('result')} (touch {o['bid']:g}/{o['ask']:g}, IOC {o['limit']:g})"
        return (f"**bought {o['filled']:g} @ {o['avg']:g}** → {o['lot']} (touch {o['bid']:g}/{o['ask']:g}, IOC {o['limit']:g}, "
                f"fee ${o['fee_usdt']:.4f}, {o['ms']} ms) · {o['stop']}" + (f" · {o['target']}" if o.get("target") else ""))
    if o["kind"] == "exit":
        return f"sold {o['filled']:g} @ {o['avg']:g} in {o['attempts']} IOC(s), fee ${o['fee_usdt']:.4f} · {o['result']}"
    return o["result"]


# ---------- the Demo checks (order gate items 3-4) ----------

def cmd_key_check(cfg, st, a):
    k = mb.creds(cfg)
    if not k:
        sys.exit("no Bybit Demo credentials readable")
    try:
        r = bybit.Demo(*k).query_api()
    except Exception as e:
        print(f"key check FAILED: {e}"); return 1
    print(json.dumps({"readOnly": r.get("readOnly"), "permissions": r.get("permissions")}, indent=1))
    return 0


def cmd_test_order(cfg, st, a):
    """Order gate item 4 (Ingrid's precondition): a resting stop-market sell placed, read back, cancelled and read back
    again on a ≤ $20 lot, plus whether a resting target can sit next to it. Outside the sleeve: no lot, no Crypto Book
    row, nothing left resting, the coin flattened back to its pre-test balance."""
    from decimal import Decimal, ROUND_DOWN
    X = cfg["execution"]
    if a.usdt > X["max_test_order_usdt"]:
        sys.exit(f"test orders are capped at ${X['max_test_order_usdt']}")
    if ex.open_lots(st):
        sys.exit("lots are open: a test order would disturb the reconciliation")
    k = mb.creds(cfg)
    if not k:
        sys.exit("no Bybit Demo credentials")
    demo, s = bybit.Demo(*k), a.symbol
    I, c = bybit.instrument(s), a.symbol[:-4]
    bals = lambda: {x: v for x, v in demo.balances(detail=True).items() if x in ("USDT", c)}
    R, live = dict(t=ex.iso(time.time()), symbol=s, usdt=a.usdt, steps=[], balances_before=bals()), []

    def step(name, fn):
        try:
            r = fn(); R["steps"].append(dict(step=name, ok=True, result=r)); return r
        except Exception as e:
            R["steps"].append(dict(step=name, ok=False, error=str(e))); return None

    bid, ask = bybit.touch(s)
    px = mb.limit_px("Buy", bid, ask, I, X["touch_offset"])
    q = mb.rnd(a.usdt / float(px), I["step"], ROUND_DOWN)
    b = mb.place(demo, s, "Buy", q, px, f"md-test-{int(time.time())}-b")
    R["buy"] = dict(bid=bid, ask=ask, limit=float(px), qty=float(q), **b)
    net = mb.rnd(b["filled"] - b["fee_base"], I["step"], ROUND_DOWN)
    stop_ok = False
    if net > 0:
        tag = int(time.time())
        trig = mb.rnd(bid * 0.7, I["tick"], ROUND_DOWN)
        sid = step("place stop-market sell", lambda: demo.stop_sell(s, format(net, "f"), format(trig, "f"), f"md-test-{tag}-s"))
        if sid:
            live.append((sid, True))
            st1 = step("read back stop", lambda: (demo.stop_status(s, sid) or {}).get("orderStatus"))
            R["balances_with_stop"] = step("balances with the stop", bals)
            tid = step("place resting target next to it", lambda: demo.limit_sell(
                s, format(net, "f"), format(mb.rnd(ask * 1.5, I["tick"], ROUND_DOWN), "f"), f"md-test-{tag}-t"))
            if tid:
                live.append((tid, False))
                step("read back target", lambda: (demo.stop_status(s, tid) or {}).get("orderStatus"))
                step("read back stop with target", lambda: (demo.stop_status(s, sid) or {}).get("orderStatus"))
                R["balances_with_stop_and_target"] = step("balances with stop and target", bals)
                if step("cancel target", lambda: demo.cancel(s, tid) and "cancelled") is not None:
                    live.remove((tid, False))
            R["target_coexists"] = bool(tid)
            amended = step("amend stop up (tighten)", lambda: demo.amend_stop(s, sid, format(mb.rnd(bid * 0.75, I["tick"], ROUND_DOWN), "f")) and "amended")
            R["amend_ok"] = amended is not None
            if step("cancel stop", lambda: demo.cancel(s, sid, stop=True) and "cancelled") is not None:
                live.remove((sid, True))
            st2 = step("read back stop after cancel", lambda: (demo.stop_status(s, sid) or {}).get("orderStatus"))
            stop_ok = st1 in mb.STOP_LIVE and st2 not in mb.STOP_LIVE + (None,)
    for oid, is_stop in list(live):  # never leave a test order resting
        if step(f"cleanup cancel {oid}", lambda oid=oid, is_stop=is_stop: demo.cancel(s, oid, stop=is_stop) and "cancelled") is not None:
            live.remove((oid, is_stop))
    R["left_resting"] = [o for o, _ in live]
    R["flatten"] = []
    before = Decimal(str((R["balances_before"].get(c) or {}).get("wallet", 0)))
    for i in range(3):
        bid, ask = bybit.touch(s)
        extra = mb.rnd(Decimal(str((bals().get(c) or {}).get("wallet", 0))) - before, I["step"], ROUND_DOWN)
        if extra <= 0 or float(extra) < I["min_qty"] or float(extra) * bid < I["min_amt"]:
            break
        x = mb.place(demo, s, "Sell", extra, mb.limit_px("Sell", bid, ask, I, X["touch_offset"]), f"md-test-{int(time.time())}-f{i}")
        R["flatten"].append(dict(bid=bid, ask=ask, qty=float(extra), **x))
    R["balances_after"] = bals()
    R["ok"] = stop_ok and not R["left_resting"]
    st["test_orders"].append(R)
    if R["ok"]:
        st["stop_test"] = dict(t=R["t"], ok=True, target_coexists=R.get("target_coexists"), amend_ok=R.get("amend_ok"))
    st["venue_base"] = None  # the next run re-reads what the account holds outside the sleeve
    save_state(st)
    print(json.dumps(R, indent=1, default=str))
    return 0 if R["ok"] else 1


# ---------- backfill (forecast-only wakes posted by hand since 12 Nov) ----------

WAKE_RE = re.compile(r"^## Wake \w{3} (\d{1,2}) (\w{3}) (\d{2}):(\d{2})Z: Majors Discretionary")


def parse_wake(body, year):
    """(sched, {coin: p}, {coin: mid}, {coin: base or None}) from a hand-posted wake log, or None."""
    m = WAKE_RE.match(body or "")
    if not m:
        return None
    t = dt.datetime.strptime(f"{year} {m[1]} {m[2]} {m[3]}:{m[4]}", "%Y %d %b %H:%M").replace(tzinfo=dt.timezone.utc).timestamp()
    lines = body.split("\n")
    num = lambda x: float(re.sub(r"[^\d.\-]", "", x.replace("−", "-").split("(")[0]) or "nan")
    head = next((i for i, l in enumerate(lines) if l.startswith("| Coin |")), None)
    mids, base = {}, {}
    if head is not None:
        cols = [x.strip() for x in lines[head].strip("|").split("|")]
        bi = next((j for j, x in enumerate(cols) if x.startswith("Up-24h")), None)
        for l in lines[head + 2:]:
            if not l.startswith("|"):
                break
            v = [x.strip() for x in l.strip("|").split("|")]
            mids[v[0]] = num(v[1])
            base[v[0]] = num(v[bi]) / 100 if bi is not None else None
    fh = next((i for i, l in enumerate(lines) if l.replace(" ", "") == "|BTC|ETH|SOL|XRP|DOGE|ADA|"), None)
    if fh is None:
        return None
    F = dict(zip(["BTC", "ETH", "SOL", "XRP", "DOGE", "ADA"], (num(x) for x in lines[fh + 2].strip("|").split("|"))))
    return t, F, mids, base


def base_at(sym, t):
    """A coin's share of up-24h windows over the 90 days before t, from closed 8h candles (as inputs.py computes it)."""
    B = engine.bars8h(bybit.klines4h(sym), t)
    c = [B[k][3] for k in sorted(B)]
    return sum(c[i + 3] > c[i] for i in range(len(c) - 273, len(c) - 3)) / 270


def cmd_backfill(cfg, st, a):
    """Load the forecasts of the hand-posted forecast-only wakes into the store, so Brier counts them from the first
    scored wake (Thu 12 Nov 00:05Z; the 11 Nov 14:35Z rehearsal is left out)."""
    if st["forecasts"]:
        sys.exit("the forecast store isn't empty: backfill runs once")
    d = mb.pc("GET", f"/api/issues/{a.issue}/comments?limit=500")
    C = sorted(d if isinstance(d, list) else d["comments"], key=lambda c: c["createdAt"])
    first = tickets.ts(a.first)
    n = 0
    for c in C:
        if c.get("authorAgentId") != os.environ.get("PAPERCLIP_AGENT_ID"):
            continue
        p = parse_wake(c["body"], c["createdAt"][:4])
        if not p or p[0] < first:
            continue
        t, F, mids, base = p
        if set(F) != {"BTC", "ETH", "SOL", "XRP", "DOGE", "ADA"} or any(c_ not in mids for c_ in F):
            print(f"skipped {c['id']}: could not parse"); continue
        for c_ in F:
            if base.get(c_) is None:
                base[c_] = base_at(c_ + "USDT", t)
        posted = tickets.ts(c["createdAt"][:19] + "+00:00")
        st["forecasts"].extend(forecasts.record(t, F, mids, base))
        st["wakes"].append(dict(sched=t, posted_t=posted, comment_id=c["id"], failed=posted - t > LOG_DEADLINE, tickets=[],
                                forecasts=F, entries=0, backfilled=True))
        n += 1
        print(f"{ex.utc(t)}: {F} (posted {ex.utc(posted)}{', LATE' if posted - t > LOG_DEADLINE else ''})")
    save_state(st)
    print(f"{n} wakes, {6 * n} forecasts loaded")
    print(score(cfg, st, time.time()))
    save_state(st)


# ---------- the rest ----------

def cmd_inputs(cfg, st, a):
    print(inputs.render(inputs.collect(cfg["universe"])))


def cmd_score(cfg, st, a):
    print(score(cfg, st, time.time()))
    save_state(st)


def cmd_status(cfg, st, a):
    print(json.dumps({k: st.get(k) for k in ("cash", "started", "halted", "day", "week", "venue_base", "stop_test", "bh", "dust")}, indent=1))
    print("open lots:", json.dumps({k: {x: l[x] for x in ("coin", "qty", "entry_px", "stop", "target", "time_limit_utc", "ticket")}
                                    for k, l in ex.open_lots(st).items()}, indent=1))
    print(f"wakes {len(st['wakes'])}, failed streak {streak(st)}, forecasts {len(st['forecasts'])}, closed lots {len(st['closed'])}, "
          f"Crypto Book queue {len(st['cb_pending'])}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("inputs")
    for c in ("post", "wake"):
        p = sub.add_parser(c); p.add_argument("wake"); p.add_argument("--dry-run", action="store_true")
    sub.add_parser("execute")
    for c in ("execute", "wake"):
        sub.choices[c].add_argument("--no-post", action="store_true")
    t = sub.add_parser("test-order"); t.add_argument("--symbol", default="DOGEUSDT"); t.add_argument("--usdt", type=float, default=18)
    b = sub.add_parser("backfill"); b.add_argument("issue"); b.add_argument("--first", default="2026-11-12T00:05Z")
    for c in ("key-check", "score", "status"):
        sub.add_parser(c)
    for c in ("halt", "resume"):
        h = sub.add_parser(c); h.add_argument("--by", required=True); h.add_argument("--ref", required=True)
        if c == "resume":
            h.add_argument("--rebaseline", action="store_true", help="after a reconciled mismatch: baseline := Demo balances − lots")
    a = ap.parse_args()
    cfg = load_cfg()
    _l = lock()
    st = load_state(cfg)
    if a.cmd == "wake":
        rc = cmd_post(cfg, st, a)
        sys.exit(rc if rc or a.dry_run else cmd_execute(cfg, load_state(cfg), a))
    if a.cmd in ("halt", "resume"):
        if a.cmd == "halt":
            st["halted"] = dict(by=a.by, ref=a.ref, t=ex.iso(time.time()))
        else:
            if a.by.lower() != "nadia":
                sys.exit("only Nadia resumes (risk-policy.md, Halt levels)")
            if a.rebaseline:
                k = mb.creds(cfg)
                if not k:
                    sys.exit("no Bybit Demo credentials: can't rebaseline")
                bal = bybit.Demo(*k).balances()
                st["venue_base"] = {c: bal.get(c, 0.0) - sum(l["qty"] for l in ex.open_lots(st).values() if l["coin"] == c) - st["dust"].get(c, 0)
                                    for c in (s[:-4] for s in cfg["universe"])}
            st["halted"] = None
            st["streak_reset"] = time.time()  # a resume clears the O1 streak
        save_state(st); return cmd_status(cfg, st, a)
    fn = {"inputs": cmd_inputs, "post": cmd_post, "execute": cmd_execute, "key-check": cmd_key_check, "test-order": cmd_test_order,
          "score": cmd_score, "status": cmd_status, "backfill": cmd_backfill}[a.cmd]
    sys.exit(fn(cfg, st, a))


if __name__ == "__main__":
    main()
