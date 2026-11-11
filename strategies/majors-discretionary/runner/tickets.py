"""Majors Discretionary ticket checks (strategy.md §4-§5, risk-policy.md L1-L10, D1-D3). Pure functions, no I/O.

check(ticket, ctx, cfg) returns (plan, reasons). reasons empty = allowed; plan says what the runner would place.
ctx describes the book at this wake:
  nav, cash, week_start_nav, week_cost, day_loss, halted (list of reasons, empty = none),
  entries_this_wake (already accepted), forecasts {COIN: p}, touch {COIN: (bid, ask)},
  inst {COIN: {min_qty, min_amt}}, now (epoch s), prev_wake (epoch s),
  lots {lot_id: {coin, qty, entry_px, stop}}.
Coins are bare symbols (BTC); the venue pair is COIN + USDT.
"""
import datetime as dt

ENTRY_KEYS = ("coin", "risk_usd", "entry", "stop", "forecast_24h", "thesis")


def ts(s):
    """'2026-11-13T07:40Z' (or with seconds / +00:00) -> epoch s."""
    s = s.strip().replace("Z", "+00:00")
    t = dt.datetime.fromisoformat(s)
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)
    return t.timestamp()


def coin_lots(ctx, coin):
    return [l for l in ctx["lots"].values() if l["coin"] == coin and l["qty"] > 0]


def check(t, ctx, cfg):
    kind = t.get("type")
    if kind == "entry":
        return check_entry(t, ctx, cfg)
    if kind == "exit":
        return check_exit(t, ctx)
    if kind == "adjust":
        return check_adjust(t, ctx)
    return None, [f"unknown ticket type {kind!r}"]


def check_entry(t, ctx, cfg):
    L, X = cfg["limits"], cfg["execution"]
    bad = [f"missing {k}" for k in ENTRY_KEYS if t.get(k) in (None, "")]
    if bad:
        return None, bad
    coin = str(t["coin"]).upper()
    if coin + "USDT" not in cfg["universe"]:
        return None, [f"L1: {coin} is not in the universe"]
    if coin not in ctx["touch"]:
        return None, [f"no price for {coin} this wake"]
    bid, ask = ctx["touch"][coin]
    nav = ctx["nav"]

    # gates that stop every entry (exits stay allowed)
    if ctx["halted"]:
        bad.append("halted: " + "; ".join(ctx["halted"]))
    if ctx["day_loss"] >= L["D1_day_pause_nav"]:
        bad.append(f"D1: day loss {ctx['day_loss']:.1%} ≥ {L['D1_day_pause_nav']:.0%}, no entries until 00:00 UTC")
    if ctx["entries_this_wake"] >= L["L7_max_entries_per_wake"]:
        bad.append(f"L7: already {ctx['entries_this_wake']} entries this wake")
    if coin in ctx.get("coins_this_wake", ()):
        bad.append(f"L5: a {coin} entry is already accepted this wake")

    # thesis (strategy.md §3-§4)
    th = t["thesis"] if isinstance(t["thesis"], dict) else {}
    for k in ("why_now", "invalidated_if"):
        if not str(th.get(k, "")).strip():
            bad.append(f"thesis.{k} missing")
    src = th.get("sources") or []
    if not src:
        bad.append("thesis.sources missing")
    for i, s in enumerate(src):
        try:
            at = ts(s["at"])
        except Exception:
            bad.append(f"source {i + 1} has no valid timestamp"); continue
        if at > ctx["now"] + 300:
            bad.append(f"source {i + 1} is timestamped in the future")
    if src and ctx.get("prev_wake") and all(_at(s) is not None and _at(s) < ctx["prev_wake"] for s in src):
        bad.append("every source is older than the previous wake: no 'why now'")

    # forecast (strategy.md §4: equal to this wake's step-3 forecast, and > 0.5)
    p, fc = t["forecast_24h"], ctx["forecasts"].get(coin)
    if fc is None:
        bad.append(f"no step-3 forecast for {coin} this wake")
    elif abs(float(p) - fc) > 1e-9:
        bad.append(f"forecast_24h {p} ≠ this wake's forecast {fc}")
    if float(p) <= 0.5:
        bad.append(f"forecast_24h {p} ≤ 0.5")

    # price, stop, target, time limit
    off = X["touch_offset"]
    px = ask * (1 + off) if t["entry"] == "touch" else float(t["entry"])
    stop = float(t["stop"])
    if t["entry"] != "touch" and px > ask * (1 + off):
        bad.append(f"limit {px:g} above the touch + {off:.1%} (L9)")
    if stop >= px or stop >= bid:
        bad.append(f"stop {stop:g} not below the entry {px:g} and the bid {bid:g}")
    tgt, tl = t.get("target"), t.get("time_limit_utc")
    if tgt in (None, "") and tl in (None, ""):
        bad.append("needs a target or a time_limit_utc")
    if tgt not in (None, "") and float(tgt) <= px:
        bad.append(f"target {tgt} not above the entry {px:g}")
    if tl not in (None, ""):
        try:
            if ts(tl) <= ctx["now"]:
                bad.append("time_limit_utc is in the past")
        except Exception:
            bad.append("time_limit_utc is not a valid UTC time")
    if bad:
        return None, bad

    # L5: one position per coin, add only above the average entry with the existing stop at or above its entry
    held = coin_lots(ctx, coin)
    if held:
        q0 = sum(l["qty"] for l in held)
        avg = sum(l["qty"] * l["entry_px"] for l in held) / q0
        if any(l["stop"] < l["entry_px"] for l in held):
            bad.append(f"L5: {coin} is held and its stop is still below its entry")
        if px < avg:
            bad.append(f"L5: add at {px:g} is below the average entry {avg:g}")
    open_coins = {l["coin"] for l in ctx["lots"].values() if l["qty"] > 0}
    if coin not in open_coins and len(open_coins) + ctx.get("new_coins_this_wake", 0) >= L["L6_max_positions"]:
        bad.append(f"L6: already {len(open_coins)} positions")

    # L2 sizing from the stop, then L4 shrink-to-fit
    risk = float(t["risk_usd"])
    cap_risk = L["L2_risk_per_trade_nav"] * nav
    if risk <= 0:
        bad.append("risk_usd must be positive")
    if risk > cap_risk + 1e-9:
        bad.append(f"L2: risk_usd {risk:.2f} > {L['L2_risk_per_trade_nav']:.2%} of NAV ({cap_risk:.2f})")
    if bad:
        return None, bad
    qty = risk / (px - stop)
    note = None
    held_val = sum(l["qty"] for l in held) * bid
    room = L["L4_max_coin_nav"] * nav - held_val
    if qty * px > room:
        if room < L["L4_min_entry_nav"] * nav:
            return None, [f"L4: {coin} room ${max(room, 0):.2f} < {L['L4_min_entry_nav']:.0%} of NAV, skipped"]
        note = f"L4: shrunk ${qty * px:.2f} → ${room:.2f} (≤ {L['L4_max_coin_nav']:.0%} of NAV in {coin})"
        qty = room / px
    val = qty * px
    held_risk = sum(max(l["entry_px"] - l["stop"], 0) * l["qty"] for l in held)
    if held_risk + qty * (px - stop) > cap_risk + 1e-9:
        bad.append(f"L5/L2: {coin} combined risk {held_risk + qty * (px - stop):.2f} > {cap_risk:.2f}")

    # L8 cost budget: what's spent plus this entry's expected cost must fit the week
    budget = L["L8_week_cost_nav"] * ctx["week_start_nav"]
    est = val * X["est_cost_per_side"]
    if ctx["week_cost"] + est > budget + 1e-9:
        bad.append(f"L8: week cost ${ctx['week_cost']:.2f} + this entry ~${est:.2f} > budget ${budget:.2f}")
    if val + est > ctx["cash"] + 1e-9:
        bad.append(f"needs ${val:.2f}, cash ${ctx['cash']:.2f}")
    m = ctx["inst"].get(coin, {})
    if qty < m.get("min_qty", 0) or val < m.get("min_amt", 0):
        bad.append(f"below the venue minimum (${val:.2f})")
    if bad:
        return None, bad
    plan = dict(type="entry", coin=coin, limit=px, qty=qty, value=val, risk=qty * (px - stop), stop=stop,
                target=float(tgt) if tgt not in (None, "") else None, time_limit_utc=tl or None, est_cost=est, note=note)
    return plan, []


def _at(s):
    try:
        return ts(s["at"])
    except Exception:
        return None


def check_exit(t, ctx):
    lot = ctx["lots"].get(t.get("lot"))
    bad = []
    if not lot or lot["qty"] <= 0:
        bad.append(f"no open lot {t.get('lot')!r}")
    elif str(t.get("coin", "")).upper() != lot["coin"]:
        bad.append(f"lot {t['lot']} is {lot['coin']}, not {t.get('coin')}")
    f = t.get("fraction", 1.0)
    if not isinstance(f, (int, float)) or not 0 < f <= 1:
        bad.append(f"fraction {f!r} not in (0, 1]")
    if not str(t.get("reason", "")).strip():
        bad.append("reason missing")
    if bad:
        return None, bad
    return dict(type="exit", coin=lot["coin"], lot=t["lot"], qty=lot["qty"] * f, reason=t["reason"]), []


def check_adjust(t, ctx):
    lot = ctx["lots"].get(t.get("lot"))
    bad = []
    if not lot or lot["qty"] <= 0:
        return None, [f"no open lot {t.get('lot')!r}"]
    if not str(t.get("reason", "")).strip():
        bad.append("reason missing")
    plan = dict(type="adjust", coin=lot["coin"], lot=t["lot"], reason=t.get("reason"))
    if t.get("stop") not in (None, ""):
        s = float(t["stop"])
        if s < lot["stop"]:
            bad.append(f"L3: stop {s:g} below the current {lot['stop']:g}; a stop is never loosened")
        bid = ctx["touch"].get(lot["coin"], (None,))[0]
        if bid is not None and s >= bid:
            bad.append(f"stop {s:g} at or above the bid {bid:g}: use an exit ticket")
        plan["stop"] = s
    for k in ("target", "time_limit_utc"):
        if t.get(k) not in (None, ""):
            plan[k] = t[k]
    if len(plan) == 4:
        bad.append("nothing to adjust")
    return (None, bad) if bad else (plan, [])


def check_wake(w, ctx, cfg):
    """A whole wake: the six forecasts, then every ticket in order (accepted entries count toward L6/L7).
    Returns (forecast_problems, [(ticket, plan, reasons)])."""
    L = cfg["limits"]
    coins = [s[:-4] for s in cfg["universe"]]
    fp = []
    F = w.get("forecasts") or {}
    for c in coins:
        p = F.get(c)
        if p is None:
            fp.append(f"no forecast for {c}")
        elif not L["forecast_min"] <= float(p) <= L["forecast_max"]:
            fp.append(f"{c} forecast {p} outside {L['forecast_min']}–{L['forecast_max']}")
    ctx = dict(ctx, forecasts={c: float(p) for c, p in F.items() if p is not None}, entries_this_wake=0, new_coins_this_wake=0,
               coins_this_wake=set())
    out = []
    for t in w.get("tickets") or []:
        plan, bad = check(t, ctx, cfg)
        if plan and plan["type"] == "entry":
            if not coin_lots(ctx, plan["coin"]):
                ctx["new_coins_this_wake"] += 1
            ctx["coins_this_wake"].add(plan["coin"])
            ctx["entries_this_wake"] += 1
            ctx["cash"] -= plan["value"] + plan["est_cost"]
            ctx["week_cost"] += plan["est_cost"]
        out.append((t, plan, bad))
    return fp, out
