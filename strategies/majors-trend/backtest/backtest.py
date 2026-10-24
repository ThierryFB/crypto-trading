"""Majors Trend backtest: BTC/ETH vs USDC, close-vs-SMA trend filter, vol-scaled slots.

Rules (see ../strategy.md):
  - Two slots, BTC and ETH, each with a 50% budget. Rest is USDC. No leverage.
  - On-trend: day's close > SMA(close, N). Off-trend slot is 100% USDC.
  - On-trend slot weight = 0.5 * min(1, target_vol / realised_vol), realised vol =
    stdev of the last 60 daily log returns * sqrt(365).
  - Signal read at the UTC daily close; trade at the next day's open.
  - Flip -> trade at once. Otherwise resize only on Mondays and only if the target
    differs from the held weight by more than 5 percentage points.
  - Every traded dollar pays `fee` (fee + slippage, per side).

    python3 backtest.py              # prints the tables used in ../backtest.md
"""
import csv, datetime as dt, math, os, statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
START = "2018-01-01"
VOL_WIN, BAND = 60, 0.05
BASE = dict(sma=150, tvol=0.50, fee=0.001)


def load():
    with open(os.path.join(HERE, "prices.csv")) as f:
        rows = list(csv.DictReader(f))
    dates = [r["date"] for r in rows]
    px = {a: {k: [float(r[f"{a}_{k}"]) for r in rows] for k in ("open", "close")} for a in ("btc", "eth")}
    return dates, px


def targets(close, sma, tvol):
    """Target slot weight per day (decided at that day's close), None during warm-up."""
    out = [None] * len(close)
    rets = [0.0] + [math.log(close[i] / close[i - 1]) for i in range(1, len(close))]
    run = 0.0
    for i, c in enumerate(close):
        run += c
        if i >= sma:
            run -= close[i - sma]
        if i < max(sma, VOL_WIN) - 1:
            continue
        on = c > run / sma
        if not on:
            out[i] = 0.0
        elif tvol is None:
            out[i] = 0.5
        else:
            vol = st.stdev(rets[i - VOL_WIN + 1:i + 1]) * math.sqrt(365)
            out[i] = 0.5 * min(1.0, tvol / vol)
    return out


def run(dates, px, sma, tvol, fee, start=START, end=None):
    i0 = dates.index(start)
    i1 = len(dates) if end is None else dates.index(end) + 1
    tgt = {a: targets(px[a]["close"], sma, tvol) for a in px}
    units = {a: 0.0 for a in px}
    cash, equity, invested, fills = 1.0, [], [], 0
    trips = []          # (exit index, asset, net return of the round trip)
    open_cost = {a: 0.0 for a in px}
    realised = {a: 0.0 for a in px}   # cash from partial trims inside a round trip
    for i in range(i0, i1):
        # execute yesterday's close decision at today's open
        if i > i0:
            nav_open = cash + sum(units[a] * px[a]["open"][i] for a in px)
            weekday_check = _weekday(dates[i - 1]) == 0
            for a in px:
                t, p = tgt[a][i - 1], px[a]["open"][i]
                held_w = units[a] * p / nav_open
                flip = (t > 0) != (units[a] > 0)
                resize = weekday_check and t > 0 and units[a] > 0 and abs(t - held_w) > BAND
                if not (flip or resize):
                    continue
                trade_val = t * nav_open - units[a] * p
                cost = abs(trade_val) * fee
                if trade_val > 0:                       # buy
                    open_cost[a] += trade_val + cost
                    cash -= trade_val + cost
                    units[a] += trade_val / p
                else:                                   # sell
                    sold = -trade_val / p
                    proceeds = -trade_val - cost
                    if t == 0:                          # full exit closes the round trip
                        trips.append((i, a, (proceeds + realised[a]) / open_cost[a] - 1))
                        open_cost[a], realised[a] = 0.0, 0.0
                        units[a] = 0.0
                    else:                               # partial trim: book the cash
                        realised[a] += proceeds
                        units[a] -= sold
                    cash += proceeds
                fills += 1
        equity.append(cash + sum(units[a] * px[a]["close"][i] for a in px))
        invested.append(1 - cash / equity[-1])
    return dict(equity=equity, dates=dates[i0:i1], fills=fills, trips=trips, exposure=st.mean(invested))


def _weekday(iso):
    return dt.date.fromisoformat(iso).weekday()


def hold(dates, px, weights, fee, start=START, end=None):
    i0 = dates.index(start)
    i1 = len(dates) if end is None else dates.index(end) + 1
    units = {a: w * (1 - fee) / px[a]["open"][i0] for a, w in weights.items()}
    eq = [sum(units[a] * px[a]["close"][i] for a in units) for i in range(i0, i1)]
    return dict(equity=eq, dates=dates[i0:i1], fills=len(weights), trips=[], exposure=1.0)


def stats(res):
    eq = [1.0] + res["equity"]
    r = [eq[i] / eq[i - 1] - 1 for i in range(1, len(eq))]
    years = len(r) / 365
    cagr = eq[-1] ** (1 / years) - 1
    peak, mdd = eq[0], 0.0
    for v in eq:
        peak = max(peak, v)
        mdd = min(mdd, v / peak - 1)
    mu, sd = st.mean(r), st.stdev(r)
    down = math.sqrt(sum(min(x, 0) ** 2 for x in r) / len(r))
    trips = res["trips"]
    per_asset = {}  # longest run of consecutive losing round trips, per asset
    for a in ("btc", "eth"):
        s = b = 0
        for _, aa, ret in sorted(trips):
            if aa != a:
                continue
            s = s + 1 if ret < 0 else 0
            b = max(b, s)
        per_asset[a] = b
    return dict(
        final=eq[-1], cagr=cagr, mdd=mdd,
        sharpe=mu / sd * math.sqrt(365), sortino=mu / down * math.sqrt(365),
        calmar=cagr / -mdd if mdd else float("nan"),
        fills=res["fills"], trips=len(trips),
        win=(sum(1 for t in trips if t[2] > 0) / len(trips)) if trips else float("nan"),
        exposure=res["exposure"], whip_btc=per_asset["btc"], whip_eth=per_asset["eth"],
    )


def row(name, s):
    whip = f"{s['whip_btc']} / {s['whip_eth']}" if s["trips"] else "–"
    trips = f"{s['fills']} / {s['trips']}" if s["trips"] else f"{s['fills']} / –"
    win = f"{s['win']:.0%}" if s["trips"] else "–"
    return (f"| {name} | {s['final']:.2f}x | {s['cagr']:+.1%} | {s['mdd']:.1%} | {s['sharpe']:.2f} | "
            f"{s['sortino']:.2f} | {s['calmar']:.2f} | {s['exposure']:.0%} | {trips} | {win} | {whip} |")


HEAD = ("| Run | End value | CAGR | Max DD | Sharpe | Sortino | Calmar | Avg exposure | Fills / round trips | Win rate | Longest whipsaw BTC / ETH |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|")


def strat(dates, px, **kw):
    p = {**BASE, **kw}
    return stats(run(dates, px, p["sma"], p["tvol"], p["fee"], kw.get("start", START), kw.get("end")))


def main():
    dates, px = load()
    fee = BASE["fee"]
    print(f"Period {START} .. {dates[-1]}, fee+slippage {fee:.1%}/side\n")

    print("## Headline\n" + HEAD)
    print(row("**Majors Trend (SMA150, 50% vol target)**", strat(dates, px)))
    for name, w in (("Buy & hold BTC", {"btc": 1}), ("Buy & hold ETH", {"eth": 1}),
                    ("Buy & hold 50/50", {"btc": .5, "eth": .5})):
        print(row(name, stats(hold(dates, px, w, fee))))

    print("\n## SMA length (vol target 50%)\n" + HEAD)
    for n in (100, 125, 150, 175, 200):
        print(row(f"SMA{n}", strat(dates, px, sma=n)))

    print("\n## Vol target (SMA150)\n" + HEAD)
    for tv in (0.40, 0.50, 0.60, None):
        print(row("no vol scaling (flat 50%)" if tv is None else f"target {tv:.0%}", strat(dates, px, tvol=tv)))

    print("\n## Grid: Sharpe / Max DD\n")
    tvs = (0.40, 0.50, 0.60, None)
    print("| SMA \\ vol target | " + " | ".join("flat" if t is None else f"{t:.0%}" for t in tvs) + " |")
    print("|---|" + "---|" * len(tvs))
    for n in (100, 125, 150, 175, 200):
        cells = []
        for tv in tvs:
            s = strat(dates, px, sma=n, tvol=tv)
            cells.append(f"{s['sharpe']:.2f} / {s['mdd']:.0%}")
        print(f"| {n} | " + " | ".join(cells) + " |")

    print("\n## Costs (SMA150, 50% vol target)\n" + HEAD)
    for f in (0.0, 0.001, 0.002, 0.005):
        print(row(f"{f:.1%}/side", strat(dates, px, fee=f)))

    print("\n## Sub-periods\n" + HEAD)
    for a, b, label in (("2018-01-01", "2020-12-31", "2018–2020"), ("2021-01-01", "2023-12-31", "2021–2023"),
                        ("2024-01-01", None, f"2024–{dates[-1][:7]}")):
        print(row(f"{label} Majors Trend", strat(dates, px, start=a, end=b)))
        print(row(f"{label} B&H 50/50", stats(hold(dates, px, {"btc": .5, "eth": .5}, fee, a, b))))


if __name__ == "__main__":
    main()
