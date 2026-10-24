#!/usr/bin/env python3
"""THE-297 Alt Momentum backtest on CMC weekly snapshots (survivorship-free), 2019-01 -> last snapshot.

Rules (see strategy.md):
  - Universe: data.universe(): top 20 by market cap among non-stable, non-wrapped coins (BTC/ETH excluded),
    listed >= 12 weeks, 4-week median 24h volume >= $20M. Refreshed on the first rebalance of each month.
  - Rank universe members by 4-week return. Hold the top K (=4) equal-weight.
    A holding stays while it ranks inside the top K+2 (buffer); empty slots go to the best-ranked non-holding.
  - Regime: invested only when BTC daily close > SMA150 of BTC daily closes (the Majors Trend rule), read at the
    weekly snapshot close. Off-regime -> 100% USDC (0% yield).
  - Weekly rebalance at the snapshot close: exits and entries every week; weights reset to 1/K on the monthly refresh
    and whenever the book re-enters from cash; otherwise held weights drift.
  - Cost per traded dollar = fee + tier slippage: fee 0.10%; slippage 0.10% for universe ranks 1-10, 0.25% for 11-20.
  - A held coin with no price at the next snapshot is valued at its next price within 4 weeks; if none, -100%.
"""
import os, sys, math, statistics as st, csv, collections, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from data import *   # noqa

START = '2019-01-06'
BASE = dict(look=4, k=4, buf=2, regime='sma150', fee=0.001, slip1=0.001, slip2=0.0025, cost_mult=1.0,
            majors=False, univ_n=20, reweight='monthly', abs_mom=False, start=START)

# --- BTC daily (same file as Majors Trend) ---
# Majors Trend's backtest folder (prices.csv + backtest.py). Default: the sibling strategy in this repo.
MT_DIR = os.environ.get('MT_DIR', os.path.join(HERE, '..', '..', 'majors-trend', 'backtest'))
_rows = list(csv.DictReader(open(os.path.join(MT_DIR, 'prices.csv'))))
DD = [r['date'] for r in _rows]; BC = [float(r['btc_close']) for r in _rows]; EC = [float(r['eth_close']) for r in _rows]
DIX = {d: i for i, d in enumerate(DD)}

def btc_on(d, n):
    i = DIX[d]
    return BC[i] > sum(BC[i - n + 1:i + 1]) / n

w0 = dates.index(START)
WEEKS = list(range(w0, N))
_ucache = {}
def univ(w, n, majors):
    key = (w, n, majors)
    if key not in _ucache:
        _ucache[key] = universe(w, n=n, include_majors=majors)
    return _ucache[key]

def price_fwd(i, w):
    """Price at w+1, else first price within the next 4 weeks, else 0 (coin gone)."""
    for k in range(w + 1, min(N, w + 5)):
        if ok(P[i][k]):
            return P[i][k], k
    return (0.0, None) if w + 1 < N else (NAN, None)

def ret4(i, w, look):
    a, b = P[i][w], P[i][w - look] if w - look >= 0 else NAN
    return a / b - 1 if ok(a) and ok(b) and b > 0 else NAN

def run(**kw):
    c = {**BASE, **kw}
    eq = 1.0; hold = {}            # coin -> weight (fraction of equity)
    s0 = dates.index(c['start'])
    curve = [(dates[s0], 1.0)]; rets = []; trades = 0; cost_paid = 0.0; invested = []
    U = None; tier = {}
    glitch_skips = 0
    book = []                      # (week index, equity after costs, weights held over the coming week)
    for w in range(s0, N - 1):
        d = dates[w]
        new_month = U is None or d[:7] != dates[w - 1][:7]
        if new_month:
            U = univ(w, c['univ_n'], c['majors'])
            tier = {i: (c['slip1'] if r < 10 else c['slip2']) for r, i in enumerate(U)}
        on = True if c['regime'] == 'none' else btc_on(d, int(c['regime'][3:]))
        target = {}
        if on:
            members = [i for i in U if ok(P[i][w])]
            sc = {i: ret4(i, w, c['look']) for i in members}
            # data-glitch guard: a >=10x lookback move is not ranked (see THE-273 glitch notes)
            for i in list(sc):
                if ok(sc[i]) and sc[i] >= 9:
                    del sc[i]; glitch_skips += 1
            ranked = sorted((i for i in sc if ok(sc[i]) and (not c['abs_mom'] or sc[i] > 0)), key=lambda i: -sc[i])
            keep = [i for i in hold if i in ranked[:c['k'] + c['buf']]]
            pick = keep + [i for i in ranked if i not in keep][:c['k'] - len(keep)]
            if c['reweight'] == 'weekly' or new_month or not hold:
                target = {i: 1 / c['k'] for i in pick}
            else:
                freed = sum(wt for i, wt in hold.items() if i not in pick)
                entrants = [i for i in pick if i not in hold]
                target = {i: hold[i] for i in pick if i in hold}
                # held weights are fractions of total equity; cash left by exits funds entrants
                cash_w = 1 - sum(hold.values()) + freed
                for i in entrants:
                    target[i] = min(1 / c['k'], cash_w / max(1, len(entrants)))
        # trade at the snapshot close
        cost = 0.0
        for i in set(hold) | set(target):
            dw = target.get(i, 0) - hold.get(i, 0)
            if abs(dw) > 1e-12:
                s = tier.get(i, c['slip2'])
                cost += abs(dw) * (c['fee'] + s) * c['cost_mult']
                if (i in target) != (i in hold) or abs(dw) > 0.02:
                    trades += 1
        hold = target
        eq_before = eq
        eq *= (1 - cost); cost_paid += cost
        book.append((w, eq, dict(hold)))
        # mark to next snapshot
        g = 1 - sum(hold.values())
        nh = {}
        for i, wt in hold.items():
            p1, k = price_fwd(i, w)
            r = p1 / P[i][w] if ok(p1) else 1.0
            g += wt * r
            if p1 > 0 and k == w + 1:
                nh[i] = wt * r
        eq_after = eq * g
        hold = {i: v / g for i, v in nh.items()} if g > 0 else {}
        rets.append(eq_after / eq_before - 1)
        invested.append(1 if target else 0)
        eq = eq_after
        curve.append((dates[w + 1], eq))
    return dict(curve=curve, rets=rets, trades=trades, cost=cost_paid, costfrac_yr=cost_paid / (len(rets) / 52.18), invested=invested, glitch=glitch_skips, book=book, cfg=c)

def stats(curve, rets, trades=None, cost=None, invested=None):
    yrs = len(rets) / 52.18
    e = [v for _, v in curve]
    cagr = e[-1] ** (1 / yrs) - 1
    pk, mdd = e[0], 0.0
    for v in e:
        pk = max(pk, v); mdd = min(mdd, v / pk - 1)
    mu, sd = st.mean(rets), st.stdev(rets)
    dn = math.sqrt(sum(min(x, 0) ** 2 for x in rets) / len(rets))
    return dict(final=e[-1], cagr=cagr, mdd=mdd, sharpe=mu / sd * math.sqrt(52), sortino=mu / dn * math.sqrt(52),
                vol=sd * math.sqrt(52), worst=min(rets), trades_yr=(trades / yrs if trades is not None else None),
                cost_yr=None, expo=(st.mean(invested) if invested else None))

# --- benchmarks on the same weekly grid ---
def bh_btc():
    c = [(dates[w], P[BTC][w] / P[BTC][w0] * (1 - 0.002)) for w in WEEKS]
    r = [c[k][1] / c[k - 1][1] - 1 for k in range(1, len(c))]
    return [(dates[w0], 1.0)] + c[1:], [c[1][1] - 1] + r[1:]

def majors_trend():
    """Majors Trend draft (SMA150, 50% vol target) daily equity from its own backtest.py, sampled at the snapshot dates."""
    spec = importlib.util.spec_from_file_location('mt', os.path.join(MT_DIR, 'backtest.py'))
    mt = importlib.util.module_from_spec(spec)
    cwd = os.getcwd(); spec.loader.exec_module(mt)
    dd, px = mt.load()
    res = mt.run(dd, px, mt.BASE['sma'], mt.BASE['tvol'], mt.BASE['fee'], start='2018-01-01')
    m = dict(zip(res['dates'], res['equity']))
    c = [(dates[w], m[dates[w]] / m[dates[w0]]) for w in WEEKS]
    r = [c[k][1] / c[k - 1][1] - 1 for k in range(1, len(c))]
    return c, r

def corr(a, b):
    ma, mb = st.mean(a), st.mean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    return num / math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
