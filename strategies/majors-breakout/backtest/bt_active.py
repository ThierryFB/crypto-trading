"""THE-319 follow-up: higher-frequency variants (target 3-10 round trips/week), long-only spot, Bybit.
Decision at each bar close (8h bar = the 3 wakes; 4h bar = 6 wakes); fill at next bar open; COST per side.
Reports gross (cost 0) vs net, and fees paid per year as % of average NAV (the fee drag).
"""
import csv, math, statistics as st

def load(sym, bar=28800):
    b = {}
    for r in csv.DictReader(open(f"{sym}.csv")):
        t = int(r["ts"])//1000; k = t - t % bar
        o,h,l,c = map(float,(r["o"],r["h"],r["l"],r["c"]))
        if k not in b: b[k] = [o,h,l,c]
        else: x=b[k]; x[1]=max(x[1],h); x[2]=min(x[2],l); x[3]=c
    return b

def atr(H, n=14):
    return sum(max(H[i][1]-H[i][2], abs(H[i][1]-H[i-1][3]), abs(H[i][2]-H[i-1][3])) for i in range(-n,0))/n

def rsi(H, n):
    g=l=0.0
    for i in range(-n,0):
        d = H[i][3]-H[i-1][3]; g += max(d,0); l += max(-d,0)
    return 100.0 if l == 0 else 100 - 100/(1+g/l)

# ---- signal families: entry(H) -> score or None ; exit(H, p) -> bool (p = dict with entry info) ----
def breakout(n_in, n_out, trend):
    def entry(H):
        if len(H) < max(n_in, trend, 15)+1: return None
        c = H[-1][3]; hi = max(x[1] for x in H[-n_in-1:-1])
        if c > hi and c > sum(x[3] for x in H[-trend:])/trend: return (c-hi)/atr(H)
    def exit_(H, p):
        return H[-1][3] < min(x[2] for x in H[-n_out-1:-1])
    return entry, exit_

def dip(trend, rsi_n, rsi_lo, exit_ma, max_bars):
    """Buy a short-term oversold close while the asset is above its trend; exit on bounce or time."""
    def entry(H):
        if len(H) < max(trend, 15)+1: return None
        c = H[-1][3]
        if c > sum(x[3] for x in H[-trend:])/trend:
            r = rsi(H, rsi_n)
            if r < rsi_lo: return rsi_lo - r
    def exit_(H, p):
        return H[-1][3] > sum(x[3] for x in H[-exit_ma:])/exit_ma or p["bars"] >= max_bars
    return entry, exit_

def run(syms, sig, RISK=0.01, CAP=0.25, MAXPOS=4, STOP_ATR=2.0, COST=0.0015, bar=28800,
        DAYLOSS=None, start=None, end=None):
    entry, exit_ = sig
    data = {s: load(s, bar) for s in syms}; btc = load("BTCUSDT", bar)
    T = sorted(set().union(*[set(d) for d in data.values()]))
    if start: T = [t for t in T if t >= start]
    if end: T = [t for t in T if t < end]
    cash = 1.0; pos = {}; pending = []; eq = []; trades = []; fills = 0; fees = 0.0
    hist = {s: [] for s in syms}; last = {}
    for t in T:
        for side, s, frac, stop in pending:
            if t not in data[s]: continue
            px = data[s][t][0]
            if side == "buy":
                nav = cash + sum(p["qty"]*last[q] for q,p in pos.items())
                val = min(frac*nav, cash)
                if val < 1e-6: continue
                cash -= val; fees += val*COST
                pos[s] = dict(qty=val*(1-COST)/px, stop=stop, cost_in=val, t=t, bars=0); fills += 1
            elif s in pos:
                p = pos.pop(s); gross = p["qty"]*px; fees += gross*COST
                cash += gross*(1-COST); fills += 1
                trades.append((s, p["t"], t, gross*(1-COST)/p["cost_in"] - 1))
        pending = []
        for s in syms:
            if t in data[s]: hist[s].append(data[s][t]); last[s] = data[s][t][3]
        nav = cash + sum(p["qty"]*last[q] for q,p in pos.items()); eq.append((t, nav))
        for s, p in pos.items():
            if t in data[s]: p["bars"] += 1
        for s, p in list(pos.items()):
            H = hist[s]
            if t in data[s] and (H[-1][3] < p["stop"] or exit_(H, p)): pending.append(("sell", s, None, None))
        if DAYLOSS:  # no new entries if NAV fell DAYLOSS from start of UTC day
            d0 = [n for (tt,n) in eq if tt >= t - (t % 86400)]
            if d0 and nav/d0[0]-1 <= -DAYLOSS: continue
        held = set(pos) - {x[1] for x in pending}
        cands = []
        for s in syms:
            H = hist[s]
            if s in pos or t not in data[s]: continue
            sc = entry(H)
            if sc is not None:
                a = atr(H); c = H[-1][3]
                cands.append((sc, s, min(CAP, RISK/(STOP_ATR*a/c)), c - STOP_ATR*a))
        for _, s, frac, stop in sorted(cands, reverse=True):
            if len(held) >= MAXPOS: break
            pending.append(("buy", s, frac, stop)); held.add(s)
    navs = [n for _,n in eq]; rets = [navs[i]/navs[i-1]-1 for i in range(1,len(navs))]
    yrs = (eq[-1][0]-eq[0][0])/31536000; weeks = yrs*52.18
    peak = mdd = 0
    for n in navs: peak = max(peak,n); mdd = min(mdd, n/peak-1)
    wk = [0]*(int(weeks)+1)
    for x in trades:
        i = int((x[2]-eq[0][0])//604800)
        if i < len(wk): wk[i] += 1
    wk = wk[:int(weeks)]
    bt = [btc[t][3] for t in T if t in btc]
    return dict(end=navs[-1], cagr=navs[-1]**(1/yrs)-1, mdd=mdd,
                sharpe=st.mean(rets)/st.pstdev(rets)*math.sqrt(31536000/bar) if rets else 0,
                rt=len(trades), rt_wk=len(trades)/weeks, med_wk=st.median(wk), ge3=sum(1 for w in wk if w>=3)/len(wk),
                zero=sum(1 for w in wk if w==0)/len(wk), win=sum(1 for x in trades if x[3]>0)/max(1,len(trades)),
                avg=st.mean([x[3] for x in trades]) if trades else 0,
                drag=fees/st.mean(navs)/yrs, btc=bt[-1]/bt[0], yrs=yrs, eq=eq, trades=trades, fees=fees)

def combine(results, w=None):
    """Independent sub-books sharing one account: NAV = weighted sum of sub-book NAVs (each starts at 1)."""
    w = w or [1/len(results)]*len(results)
    T = sorted(set.intersection(*[set(t for t,_ in r["eq"]) for r in results]))
    m = [dict(r["eq"]) for r in results]
    navs = [sum(wi*mi[t] for wi,mi in zip(w,m)) for t in T]
    bar = T[1]-T[0]; rets = [navs[i]/navs[i-1]-1 for i in range(1,len(navs))]
    yrs = (T[-1]-T[0])/31536000; weeks = yrs*52.18
    peak = mdd = 0
    for n in navs: peak = max(peak,n); mdd = min(mdd, n/peak-1)
    trades = [x for r in results for x in r["trades"]]
    wk = [0]*(int(weeks)+1)
    for x in trades:
        i = int((x[2]-T[0])//604800)
        if 0 <= i < len(wk): wk[i] += 1
    wk = wk[:int(weeks)]
    return dict(end=navs[-1], cagr=navs[-1]**(1/yrs)-1, mdd=mdd,
                sharpe=st.mean(rets)/st.pstdev(rets)*math.sqrt(31536000/bar), rt=len(trades), rt_wk=len(trades)/weeks,
                med_wk=st.median(wk), ge3=sum(1 for v in wk if v>=3)/len(wk), zero=sum(1 for v in wk if v==0)/len(wk),
                win=sum(1 for x in trades if x[3]>0)/max(1,len(trades)), avg=st.mean([x[3] for x in trades]),
                drag=sum(wi*r["fees"] for wi,r in zip(w,results))/st.mean(navs)/yrs, btc=results[0]["btc"], yrs=yrs)

HDR = ("| Variant | Cost/side | End | CAGR | MaxDD | Sharpe | RT/wk | Median RT/wk | Weeks ≥3 RT | Weeks 0 RT | Win | Avg RT net | Fee drag/yr |\n"
       "|---|---|---|---|---|---|---|---|---|---|---|---|---|")
def fmt(name, cost, r):
    return (f"| {name} | {cost*100:.2f}% | {r['end']:.2f}x | {r['cagr']*100:+.1f}% | {r['mdd']*100:.0f}% | {r['sharpe']:.2f} | "
            f"{r['rt_wk']:.1f} | {r['med_wk']:.0f} | {r['ge3']*100:.0f}% | {r['zero']*100:.0f}% | {r['win']*100:.0f}% | "
            f"{r['avg']*100:+.2f}% | {r['drag']*100:.1f}% |")

U6  = ["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","DOGEUSDT","ADAUSDT"]
U15 = U6 + ["LINKUSDT","AVAXUSDT","DOTUSDT","LTCUSDT","BCHUSDT","NEARUSDT","ATOMUSDT","UNIUSDT","TRXUSDT"]
YEARS = [(1640995200,1672531200,"2022"),(1672531200,1704067200,"2023"),(1704067200,1735689600,"2024"),
         (1735689600,1767225600,"2025"),(1767225600,1800000000,"2026 YTD")]
