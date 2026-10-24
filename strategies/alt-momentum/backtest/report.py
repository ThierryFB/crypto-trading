#!/usr/bin/env python3
"""Prints the tables used in backtest.md.   python3 report.py > results.txt"""
from bt import *

def S(**kw):
    r = run(**kw)
    return r, stats(r['curve'], r['rets'], r['trades'], None, r['invested'])

H = ("| Run | End value | CAGR | Max DD (weekly) | Sharpe | Sortino | Vol | Worst week | Orders / yr | Cost drag / yr | Time invested |\n"
     "|---|---|---|---|---|---|---|---|---|---|---|")
def row(n, s, r=None):
    tr = f"{s['trades_yr']:.0f}" if s['trades_yr'] is not None else '–'
    cd = f"{r['costfrac_yr']:.1%}" if r else '–'
    return (f"| {n} | {s['final']:.2f}x | {s['cagr']:+.1%} | {s['mdd']:.0%} | {s['sharpe']:.2f} | {s['sortino']:.2f} | "
            f"{s['vol']:.0%} | {s['worst']:.0%} | {tr} | {cd} | {'–' if s['expo'] is None else format(s['expo'], '.0%')} |")

def years(curve):
    by = collections.OrderedDict(); prev = 1.0; out = {}
    for d, v in curve:
        by.setdefault(d[:4], []).append(v)
    for y, vs in by.items():
        out[y] = vs[-1] / prev - 1; prev = vs[-1]
    return out

def episodes(curve, n=3):
    """Largest peak-to-trough drawdowns, non-overlapping."""
    eps = []; pk, pd = curve[0][1], curve[0][0]; tr, td = pk, pd
    for d, v in curve + [(None, float('inf'))]:
        if v >= pk:
            if tr < pk:
                eps.append((tr / pk - 1, pd, td, d))
            pk, pd, tr, td = v, d, v, d
        elif v < tr:
            tr, td = v, d
    return sorted(eps)[:n]

def main():
    rb, sb = S()
    rc, sc = S(k=20, buf=0)
    cb, rbb = bh_btc(); s_btc = stats(cb, rbb)
    cm, rm = majors_trend(); s_mt = stats(cm, rm)
    print(f"Weekly CMC snapshots {START} .. {dates[-1]} ({len(rb['rets'])} weeks). Base: 4-week return, top 4 (+2 buffer), "
          f"BTC > SMA150 regime, fee 0.10% + slippage 0.10%/0.25% per side. Glitch-guard skips: {rb['glitch']}\n")
    print("## Headline\n" + H)
    print(row('**Alt Momentum (base)**', sb, rb))
    print(row('Control: equal-weight whole universe, same regime filter', sc, rc))
    print(row('Majors Trend draft (SMA150, 50% vol target), sampled weekly', s_mt))
    print(row('Buy & hold BTC', s_btc))

    print("\n## Correlation of weekly returns\n")
    am = rb['rets']
    both = [(a, b) for a, b, x in zip(am, rm, rb['invested']) if x]
    beta = lambda a, b: sum((x - st.mean(a)) * (y - st.mean(b)) for x, y in zip(a, b)) / sum((y - st.mean(b)) ** 2 for y in b)
    print("| Pair | Correlation | Beta of Alt Momentum to it |\n|---|---|---|")
    print(f"| Alt Momentum vs Majors Trend, all weeks | {corr(am, rm):.2f} | {beta(am, rm):.2f} |")
    print(f"| Alt Momentum vs Majors Trend, weeks Alt Momentum is invested | {corr(*zip(*both)):.2f} | {beta(*map(list, zip(*both))):.2f} |")
    print(f"| Alt Momentum vs BTC | {corr(am, rbb):.2f} | {beta(am, rbb):.2f} |")
    print(f"| Majors Trend vs BTC | {corr(rm, rbb):.2f} | – |")
    mix = [(1 + 0.64 * b + 0.36 * a) for a, b in zip(am, rm)]   # $450 MT + $250 AM, weekly rebalanced
    e = 1.0; cv = [(dates[w0], 1.0)]
    for k, g in enumerate(mix):
        e *= g; cv.append((dates[w0 + k + 1], e))
    s_mix = stats(cv, [g - 1 for g in mix])
    print(f"\nMajors Trend + Alt Momentum at the draft 450:250 split (weekly rebalanced, no extra cost): "
          f"{s_mix['final']:.2f}x, CAGR {s_mix['cagr']:+.1%}, max DD {s_mix['mdd']:.0%}, Sharpe {s_mix['sharpe']:.2f} "
          f"(Majors Trend alone: {s_mt['final']:.2f}x, {s_mt['cagr']:+.1%}, {s_mt['mdd']:.0%}, {s_mt['sharpe']:.2f}).")

    print("\n## Calendar years\n")
    ya, yc, ym, yb = years(rb['curve']), years(rc['curve']), years(cm), years(cb)
    print("| Year | Alt Momentum | EW-universe control | Majors Trend | BTC |\n|---|---|---|---|---|")
    for y in ya:
        print(f"| {y}{' (to ' + dates[-1][5:] + ')' if y == dates[-1][:4] else ''} | {ya[y]:+.0%} | {yc[y]:+.0%} | {ym[y]:+.0%} | {yb[y]:+.0%} |")

    print("\n## Worst drawdowns, Alt Momentum base (weekly closes)\n")
    print("| Drawdown | Peak | Trough | Recovered |\n|---|---|---|---|")
    for dd, p, t, rcv in episodes(rb['curve']):
        print(f"| {dd:.0%} | {p} | {t} | {rcv or 'not yet'} |")
    pk = 0; wk40 = 0
    for _, v in rb['curve']:
        pk = max(pk, v); wk40 += v / pk <= 0.6
    print(f"\nWeeks spent at or below 60% of the high-water mark: {wk40} of {len(rb['curve'])}.")

    print("\n## Sensitivity: lookback x holdings (CAGR / max DD / Sharpe)\n")
    ks = (3, 4, 5)
    print("| Lookback \\ top K | " + " | ".join(map(str, ks)) + " |\n|---|" + "---|" * len(ks))
    for lb in (2, 4, 8, 12):
        cells = []
        for k in ks:
            s = S(look=lb, k=k)[1]
            cells.append(f"{s['cagr']:+.0%} / {s['mdd']:.0%} / {s['sharpe']:.2f}")
        print(f"| {lb} weeks | " + " | ".join(cells) + " |")

    print("\n## Regime filter\n" + H)
    for reg, n in (('sma150', 'BTC > SMA150 (base, Majors Trend rule)'), ('sma100', 'BTC > SMA100'),
                   ('sma200', 'BTC > SMA200'), ('none', 'No filter (always invested)')):
        r, s = S(regime=reg); print(row(n, s, r))

    print("\n## Costs\n" + H)
    for m, n in ((0, 'No costs'), (1, 'Base (0.20% / 0.35% per side)'), (2, '2x base'), (3, '3x base')):
        r, s = S(cost_mult=m); print(row(n, s, r))

    print("\n## Other construction choices\n" + H)
    for kw, n in ((dict(buf=0), 'No buffer (strict top 4 every week)'), (dict(reweight='weekly'), 'Reset to equal weight every week'),
                  (dict(abs_mom=True), 'Only hold coins with a positive 4-week return'),
                  (dict(majors=True), 'Universe includes BTC and ETH')):
        r, s = S(**kw); print(row(n, s, r))

    print("\n## Universe\n")
    ever = set(); sizes = []
    for w in WEEKS[:-1]:
        if w == w0 or dates[w][:7] != dates[w - 1][:7]:
            u = univ(w, 20, False); ever |= set(u); sizes.append(len(u))
    last = N - 1
    dead = [i for i in ever if not ok(P[i][last]) or P[i][last] < 0.1 * max(P[i][k] for k in range(w0, N) if ok(P[i][k]))]
    gone = [i for i in ever if not ok(P[i][last])]
    print(f"Monthly refreshes: {len(sizes)}; size min {min(sizes)}, median {st.median(sizes)}; {len(ever)} distinct coins were members.")
    print(f"{len(dead)} of them are now >90% below their post-2019 high or no longer listed ({len(gone)} no longer listed): "
          + ', '.join(sorted(SYM[i] for i in dead)) + '.')

if __name__ == '__main__':
    main()
