"""Quick backtest for THE-319: 8h Donchian breakout, long-only spot, Bybit majors.
Decisions only at 00/08/16 UTC (the 3 wakes), on the 8h bar that just closed; fill at next bar open.
"""
import csv, math, sys, statistics as st
from collections import defaultdict

def load(sym):
    rows = list(csv.DictReader(open(f"{sym}.csv")))
    b = {}
    for r in rows:
        t = int(r["ts"])//1000; k = t - t % 28800
        o,h,l,c = map(float,(r["o"],r["h"],r["l"],r["c"]))
        if k not in b: b[k] = [o,h,l,c]
        else: x=b[k]; x[1]=max(x[1],h); x[2]=min(x[2],l); x[3]=c
    return b

def run(syms, N_IN=20, N_OUT=10, ATR_N=14, STOP_ATR=2.0, RISK=0.01, CAP=0.25, MAXPOS=4,
        COST=0.0015, REGIME=True, TREND_N=90, start=None, end=None, verbose=False):
    data = {s: load(s) for s in syms}
    btc = load("BTCUSDT")
    # BTC daily closes for regime (SMA150 of daily close, desk C3)
    daily = {}
    for k in sorted(btc): daily[k - k % 86400] = btc[k][3]
    dk = sorted(daily); dsma = {}
    for i in range(149, len(dk)):
        dsma[dk[i]] = (daily[dk[i]], sum(daily[dk[j]] for j in range(i-149, i+1))/150)
    T = sorted(set().union(*[set(d) for d in data.values()]))
    if start: T = [t for t in T if t >= start]
    if end: T = [t for t in T if t < end]
    cash = 1.0; pos = {}  # sym -> [qty, stop, entry_px, entry_t]
    eq = []; trades = []; fills = 0
    hist = {s: [] for s in syms}
    pending = []  # orders to fill at next bar open
    for t in T:
        # fill pending at this bar's open
        for (side, s, frac_or_qty, stop) in pending:
            if s not in data or t not in data[s]: continue
            px = data[s][t][0]
            if side == "buy":
                nav = cash + sum(p[0]*data[q][t][0] for q,p in pos.items() if t in data[q])
                val = min(frac_or_qty*nav, cash)
                if val < 1e-6: continue
                cash -= val; qty = val*(1-COST)/px
                pos[s] = [qty, stop, px, t]; fills += 1
            else:
                if s not in pos: continue
                qty, _, epx, et = pos.pop(s)
                cash += qty*px*(1-COST); fills += 1
                trades.append((s, et, t, px*(1-COST)/(epx/(1-COST)) - 1))
        pending = []
        # update history with this bar (it closes at t+8h; decision at close)
        for s in syms:
            if t in data[s]: hist[s].append(data[s][t])
        nav = cash + sum(p[0]*hist[q][-1][3] for q,p in pos.items())
        eq.append((t, nav))
        day = (t + 28800) - (t + 28800) % 86400 - 86400  # last fully closed day at decision time
        reg = dsma.get(day); regime_on = (reg is None and not REGIME) or (reg is not None and reg[0] > reg[1])
        if not REGIME: regime_on = True
        # exits
        for s, p in list(pos.items()):
            H = hist[s]
            if len(H) < N_OUT+1: continue
            c = H[-1][3]; lo = min(x[2] for x in H[-N_OUT-1:-1])
            if c < lo or c < p[1] or not regime_on:
                pending.append(("sell", s, None, None))
        # entries
        held = set(pos) - {x[1] for x in pending if x[0]=="sell"}
        cands = []
        for s in syms:
            H = hist[s]
            if s in pos or len(H) < max(N_IN, ATR_N, TREND_N)+1 or not regime_on: continue
            c = H[-1][3]; hi = max(x[1] for x in H[-N_IN-1:-1])
            sma = sum(x[3] for x in H[-TREND_N:])/TREND_N
            if c > hi and c > sma:
                trs = [max(H[i][1]-H[i][2], abs(H[i][1]-H[i-1][3]), abs(H[i][2]-H[i-1][3])) for i in range(-ATR_N,0)]
                atr = sum(trs)/ATR_N
                stopd = STOP_ATR*atr/c
                frac = min(CAP, RISK/stopd)
                cands.append(((c-hi)/atr, s, frac, c - STOP_ATR*atr))
        for _, s, frac, stop in sorted(cands, reverse=True):
            if len(held) >= MAXPOS: break
            pending.append(("buy", s, frac, stop)); held.add(s)
    # stats
    navs = [n for _,n in eq]
    rets = [navs[i]/navs[i-1]-1 for i in range(1,len(navs))]
    yrs = (eq[-1][0]-eq[0][0])/31536000
    peak = 0; mdd = 0
    for n in navs: peak = max(peak,n); mdd = min(mdd, n/peak-1)
    sh = st.mean(rets)/st.pstdev(rets)*math.sqrt(3*365) if rets else 0
    wins = [x for x in trades if x[3] > 0]
    weeks = yrs*52.18
    bt = [btc[t][3] for t in T if t in btc]
    bpk=0; bdd=0
    for n in bt: bpk=max(bpk,n); bdd=min(bdd,n/bpk-1)
    return dict(end=navs[-1], cagr=navs[-1]**(1/yrs)-1, mdd=mdd, sharpe=sh, rt=len(trades), rt_wk=len(trades)/weeks,
                fills_wk=fills/weeks, win=len(wins)/max(1,len(trades)),
                avg=st.mean([x[3] for x in trades]) if trades else 0,
                btc=bt[-1]/bt[0], btc_cagr=(bt[-1]/bt[0])**(1/yrs)-1, btc_mdd=bdd, yrs=yrs,
                weeks_no_trade=sum(1 for w in range(int(weeks)) if not any(eq[0][0]+w*604800 <= x[1] < eq[0][0]+(w+1)*604800 or eq[0][0]+w*604800 <= x[2] < eq[0][0]+(w+1)*604800 for x in trades))/max(1,int(weeks)))

def fmt(name, r):
    return (f"| {name} | {r['end']:.2f}x | {r['cagr']*100:+.1f}% | {r['mdd']*100:.0f}% | {r['sharpe']:.2f} | "
            f"{r['rt']} | {r['rt_wk']:.2f} | {r['fills_wk']:.2f} | {r['weeks_no_trade']*100:.0f}% | {r['win']*100:.0f}% | {r['avg']*100:+.2f}% | "
            f"{r['btc']:.2f}x / {r['btc_mdd']*100:.0f}% |")

if __name__ == "__main__":
    U6 = ["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","DOGEUSDT","ADAUSDT"]
    U8 = U6 + ["LINKUSDT","AVAXUSDT"]
    print("| Run | End | CAGR | MaxDD | Sharpe | Round trips | RT/wk | Fills/wk | Weeks w/o fill | Win | Avg trade | BTC B&H end / DD |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    print(fmt("**Base: U6, 20/10, regime on, 0.15%/side**", run(U6)))
    print(fmt("No BTC regime filter", run(U6, REGIME=False)))
    print(fmt("U8", run(U8)))
    print(fmt("Entry 15 / exit 7", run(U6, N_IN=15, N_OUT=7)))
    print(fmt("Entry 30 / exit 15", run(U6, N_IN=30, N_OUT=15)))
    print(fmt("Cost 0.25%/side", run(U6, COST=0.0025)))
    print(fmt("Cost 0.5%/side", run(U6, COST=0.005)))
    for a,b,n in [(1640995200,1672531200,"2022"),(1672531200,1704067200,"2023"),(1704067200,1735689600,"2024"),(1735689600,1767225600,"2025"),(1767225600,1800000000,"2026 YTD")]:
        print(fmt(f"Base {n}", run(U6, start=a, end=b)))
