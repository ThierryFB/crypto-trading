#!/usr/bin/env python3
"""Majors Discretionary runner (strategy.md §2-§7, risk-policy.md L1-L11). WORK IN PROGRESS (THE-321):
inputs, forecasts, scoring and the ticket checks are built; order placement is not yet wired, so nothing here
can place an order.

  mdisc.py inputs                      print the §3 data block
  mdisc.py forecast WAKE.json          record the wake's six forecasts at the current mids (validated)
  mdisc.py check WAKE.json             check every ticket in WAKE.json against the limits; places nothing
  mdisc.py score                       resolve due forecasts, print the Brier / calibration block

WAKE.json: {"forecasts": {"BTC": 0.55, ...all six}, "tickets": [ticket, ...]} (tickets per strategy.md §4).
State lives in $MD_STATE_DIR (default: Leo's persistent workspace), never in the repo.
"""
import argparse, datetime as dt, fcntl, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import inputs, tickets, forecasts  # noqa: E402
from inputs import bybit, engine  # noqa: E402

STATE_DIR = os.environ.get("MD_STATE_DIR",
                           "/paperclip/instances/default/workspaces/a3ae5ff4-6eb6-4daa-9169-f2568b7087ba/majors-discretionary-state")


def load_cfg():
    return json.load(open(os.path.join(HERE, "config.json")))


def load_state(cfg):
    p = os.path.join(STATE_DIR, "state.json")
    if os.path.exists(p):
        return json.load(open(p))
    return {"version": 1, "cash": cfg["sleeve_usdt"], "lots": {}, "next_lot": 1, "forecasts": [], "week": None,
            "day": None, "failed_wakes": 0, "halted": None, "last_wake": None}


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


def nav(st, mids):
    return st["cash"] + sum(l["qty"] * mids.get(l["coin"], l["entry_px"]) for l in st["lots"].values())


def week_start(t):
    d = dt.datetime.fromtimestamp(t, dt.timezone.utc)
    return int((d - dt.timedelta(days=d.weekday())).replace(hour=0, minute=0, second=0, microsecond=0).timestamp())


def ctx_from(st, D, cfg, now):
    mids = {c: d["mid"] for c, d in D["coins"].items()}
    n = nav(st, mids)
    wk = st["week"] if st["week"] and st["week"]["start"] == week_start(now) else {"start": week_start(now), "nav": n, "cost": 0.0}
    today = dt.datetime.fromtimestamp(now, dt.timezone.utc).strftime("%Y-%m-%d")
    day_nav = st["day"]["nav"] if st["day"] and st["day"]["date"] == today else n
    halted = [f"halted by {st['halted']['by']} ({st['halted']['ref']})"] if st["halted"] else []
    L = cfg["limits"]
    if n <= L["D3_halt_nav_usdt"]: halted.append(f"D3: NAV ${n:.2f} ≤ ${L['D3_halt_nav_usdt']}")
    if day_nav and 1 - n / day_nav >= L["D2_day_halt_nav"]: halted.append("D2: day loss ≥ 10%")
    if st["failed_wakes"] >= L["O1_halt_failed_wakes"]: halted.append(f"O1: {st['failed_wakes']} failed wakes in a row")
    inst = {}
    for c in D["coins"]:
        try:
            i = bybit.instrument(c + "USDT"); inst[c] = dict(min_qty=i["min_qty"], min_amt=i["min_amt"])
        except Exception:
            pass
    return dict(nav=n, cash=st["cash"], week_start_nav=wk["nav"], week_cost=wk["cost"], day_loss=1 - n / day_nav if day_nav else 0,
                halted=halted, touch={c: (d["bid"], d["ask"]) for c, d in D["coins"].items()}, inst=inst, now=now,
                prev_wake=st["last_wake"], lots=st["lots"], forecasts={})


def closes_8h(universe, now):
    out = {}
    for s in universe:
        B = engine.bars8h(bybit.klines4h(s), now)
        out[s[:-4]] = {k + engine.BAR: v[3] for k, v in B.items()}
    return out


def cmd_inputs(cfg, st, a):
    print(inputs.render(inputs.collect(cfg["universe"])))


def cmd_forecast(cfg, st, a):
    w = json.load(open(a.wake))
    fp, _ = tickets.check_wake({"forecasts": w.get("forecasts")}, dict(lots={}, touch={}, nav=1, cash=1, week_start_nav=1,
                               week_cost=0, day_loss=0, halted=[], inst={}, now=time.time(), prev_wake=None), cfg)
    if fp:
        sys.exit("forecasts refused: " + "; ".join(fp))
    now = time.time()
    D = inputs.collect(cfg["universe"], now)
    missing = [c for c in w["forecasts"] if c not in D["coins"]]
    if missing:
        sys.exit("no mid for " + ", ".join(missing) + ": " + "; ".join(D["errors"]))
    R = forecasts.record(now, w["forecasts"], {c: d["mid"] for c, d in D["coins"].items()},
                         {c: d["up24_90d"] for c, d in D["coins"].items()})
    st["forecasts"].extend(R)
    save_state(st)
    for r in R:
        print(f"{r['coin']}: p={r['p']:.2f} at mid {r['px0']:.6g}, resolves on the 8h close at "
              f"{dt.datetime.fromtimestamp(r['resolve_t'], dt.timezone.utc):%Y-%m-%d %H:%MZ} (base rate {r['base']:.0%})")


def cmd_check(cfg, st, a):
    w = json.load(open(a.wake))
    now = time.time()
    D = inputs.collect(cfg["universe"], now)
    ctx = ctx_from(st, D, cfg, now)
    fp, res = tickets.check_wake(w, ctx, cfg)
    print(f"NAV ${ctx['nav']:.2f}, cash ${ctx['cash']:.2f}, week cost ${ctx['week_cost']:.2f} of "
          f"${cfg['limits']['L8_week_cost_nav'] * ctx['week_start_nav']:.2f}")
    for p in fp:
        print("FORECAST:", p)
    for t, plan, bad in res:
        tag = f"{t.get('type')} {t.get('coin', '')} {t.get('lot', '')}".strip()
        if bad:
            print(f"REFUSED {tag}: " + "; ".join(bad))
        else:
            print(f"OK {tag}: " + json.dumps({k: v for k, v in plan.items() if v is not None}, default=str))
    return 1 if fp or any(bad for _, _, bad in res) else 0


def cmd_score(cfg, st, a):
    now = time.time()
    due = [r for r in st["forecasts"] if r["y"] is None and r["resolve_t"] <= now]
    if due:
        forecasts.resolve(st["forecasts"], closes_8h(cfg["universe"], now))
        save_state(st)
    print(forecasts.score_block(st["forecasts"]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("inputs")
    for c in ("forecast", "check"):
        sub.add_parser(c).add_argument("wake")
    sub.add_parser("score")
    a = ap.parse_args()
    cfg = load_cfg()
    _l = lock()
    st = load_state(cfg)
    sys.exit({"inputs": cmd_inputs, "forecast": cmd_forecast, "check": cmd_check, "score": cmd_score}[a.cmd](cfg, st, a))


if __name__ == "__main__":
    main()
