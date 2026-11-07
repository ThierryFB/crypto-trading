"""Parity check: engine.py must reproduce backtest/bt.py run(U6, REGIME=False) trade for trade.
Run from backtest/ after fetch.py:  cd ../backtest && python3 ../runner/test_parity.py
"""
import csv, inspect, os, sys
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)), os.getcwd()]
import engine
import bt

U6 = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT"]
COST = 0.0015


def bt_trades():
    src = inspect.getsource(bt.run).replace("    # stats", "    global _TR, _NAV; _TR = trades; _NAV = eq\n    # stats")
    exec(src, bt.__dict__)
    bt.run(U6, REGIME=False)
    return bt._TR, bt._NAV


def engine_trades():
    data = {s: bt.load(s) for s in U6}
    T = sorted(set().union(*[set(d) for d in data.values()]))
    cash = 1.0; pos = {}; trades = []; eq = []; pending = []
    hist = {s: [] for s in U6}
    for t in T:
        for side, s, w, stop in pending:
            if t not in data[s]:
                continue
            px = data[s][t][0]
            if side == "buy":
                nav = cash + sum(p[0] * data[q][t][0] for q, p in pos.items() if t in data[q])
                val = min(w * nav, cash)
                if val < 1e-6:
                    continue
                cash -= val; pos[s] = [val * (1 - COST) / px, stop, px, t]
            elif s in pos:
                qty, _, epx, et = pos.pop(s)
                cash += qty * px * (1 - COST)
                trades.append((s, et, t, px * (1 - COST) / (epx / (1 - COST)) - 1))
        pending = []
        for s in U6:
            if t in data[s]:
                hist[s].append(data[s][t])
        eq.append((t, cash + sum(p[0] * hist[q][-1][3] for q, p in pos.items())))
        lv = {s: engine.levels(hist[s]) for s in U6}
        exits, entries = engine.decide(lv, {s: p[1] for s, p in pos.items()})
        pending = [("sell", s, None, None) for s in exits] + [("buy", s, w, stop) for s, w, stop, _ in entries]
    return trades, eq


def bars_match():
    bad = 0
    for s in U6:
        rows = [(int(r["ts"]) // 1000, *map(float, (r["o"], r["h"], r["l"], r["c"]))) for r in csv.DictReader(open(f"{s}.csv"))]
        mine, ref = engine.bars8h(rows), bt.load(s)
        bad += sum(1 for k in mine if mine[k] != ref[k]) + len(set(ref) - set(mine))
        print(f"{s}: {len(mine)} complete 8h bars, bt.py has {len(ref)} (incomplete/missing-half bars dropped: {len(set(ref) - set(mine))})")
    return bad


if __name__ == "__main__":
    a, na = bt_trades()
    b, nb = engine_trades()
    same = [(x[0], x[1], x[2]) for x in a] == [(x[0], x[1], x[2]) for x in b]
    maxdiff = max(abs(x[3] - y[3]) for x, y in zip(a, b)) if same else None
    print(f"bt.py round trips {len(a)}, engine {len(b)}, identical: {same}, max return diff {maxdiff}")
    print(f"end NAV bt {na[-1][1]:.4f} engine {nb[-1][1]:.4f}")
    bars_match()
    sys.exit(0 if same and abs(na[-1][1] - nb[-1][1]) < 1e-9 else 1)
