"""Parity check: engine.py must reproduce backtest/bt_active.py trade for trade, for every slice, and the
3-speed combination (sweep3.py) to the same end NAV.
Run from backtest/ after fetch.py:  cd ../backtest && python3 ../runner/test_parity.py
"""
import csv, os, sys
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)), os.getcwd()]
import engine
import bt_active as bta

U6 = bta.U6
COST = 0.0015


def engine_trades(sl):
    """bt_active.run's fill mechanics (fill at next open, NAV for sizing at the last close), engine.py's decisions."""
    data = {s: bta.load(s) for s in U6}
    T = sorted(set().union(*[set(d) for d in data.values()]))
    cash = 1.0; pos = {}; trades = []; eq = []; pending = []
    hist = {s: [] for s in U6}; last = {}
    for t in T:
        for side, s, w, stop in pending:
            if t not in data[s]:
                continue
            px = data[s][t][0]
            if side == "buy":
                nav = cash + sum(p["qty"] * last[q] for q, p in pos.items())
                val = min(w * nav, cash)
                if val < 1e-6:
                    continue
                cash -= val; pos[s] = dict(qty=val * (1 - COST) / px, stop=stop, cost_in=val, t=t)
            elif s in pos:
                p = pos.pop(s); gross = p["qty"] * px
                cash += gross * (1 - COST)
                trades.append((s, p["t"], t, gross * (1 - COST) / p["cost_in"] - 1))
        for s in U6:
            if t in data[s]:
                hist[s].append(data[s][t]); last[s] = data[s][t][3]
        eq.append((t, cash + sum(p["qty"] * last[q] for q, p in pos.items())))
        lv = {s: engine.levels(hist[s]) if t in data[s] else None for s in U6}
        exits, entries = engine.decide(lv, {s: p["stop"] for s, p in pos.items()}, sl)
        pending = [("sell", s, None, None) for s in exits] + [("buy", s, w, stop) for s, w, stop, _ in entries]
    return dict(trades=trades, eq=eq)


def bars_match():
    bad = 0
    for s in U6:
        rows = [(int(r["ts"]) // 1000, *map(float, (r["o"], r["h"], r["l"], r["c"]))) for r in csv.DictReader(open(f"{s}.csv"))]
        mine, ref = engine.bars8h(rows), bta.load(s)
        bad += sum(1 for k in mine if mine[k] != ref[k]) + len(set(ref) - set(mine))
        print(f"{s}: {len(mine)} complete 8h bars, bt_active.py has {len(ref)} (incomplete/missing-half bars dropped: {len(set(ref) - set(mine))})")
    return bad


if __name__ == "__main__":
    ok = True; mine, ref = [], []
    for sl, (n_in, n_out) in engine.SLICES.items():
        a = bta.run(U6, bta.breakout(n_in, n_out, engine.TREND_N), RISK=engine.RISK, CAP=engine.CAP, MAXPOS=engine.MAXPOS,
                    STOP_ATR=engine.STOP_ATR, COST=COST)
        b = engine_trades(sl)
        same = [x[:3] for x in a["trades"]] == [x[:3] for x in b["trades"]]
        maxdiff = max(abs(x[3] - y[3]) for x, y in zip(a["trades"], b["trades"])) if same else None
        nav_ok = abs(a["eq"][-1][1] - b["eq"][-1][1]) < 1e-9
        print(f"{sl} {n_in}/{n_out}: bt_active round trips {len(a['trades'])}, engine {len(b['trades'])}, identical: {same}, "
              f"max return diff {maxdiff}, end NAV {a['eq'][-1][1]:.4f} vs {b['eq'][-1][1]:.4f}")
        ok &= same and nav_ok
        ref.append(a); mine.append(b)
    T = sorted(set.intersection(*[set(t for t, _ in r["eq"]) for r in ref]))
    end = lambda R: sum(dict(r["eq"])[T[-1]] for r in R) / len(R)
    print(f"3-speed end NAV: sweep3/combine {bta.combine(ref)['end']:.4f}, engine {end(mine):.4f}")
    ok &= abs(bta.combine(ref)["end"] - end(mine)) < 1e-9
    bars_match()
    sys.exit(0 if ok else 1)
