"""THE-320, discretionary version: a zero-skill trader run under Nadia's §3 limits.
Random entries at 8h wakes (00/08/16 UTC) on Bybit 8h bars built from 4h candles; fills at next bar open.
Stop = entry - k*ATR14 (k random 1.5-3), checked intrabar (filled at stop, or at the open if it gapped).
Exit also at a random time limit (1-7 days). Costs 0.15%/side (fees+slippage).
Limits: risk R of NAV to stop, <=25% NAV per coin, <=4 positions, <=2 entries/wake,
fee budget 0.2% NAV/week (Mon 00:00 UTC), -4% day -> no entries, -10% day / NAV<=80% -> flagged (halt).
Output: per-config distribution over 13-week windows (the 3-month review horizon), from every weekly start.
"""
import csv, random, statistics as st, sys
import os
D = os.environ.get("DATA_DIR", "data") + "/"  # 4h CSVs from ../../majors-breakout/backtest/fetch.py
SY = ["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","DOGEUSDT","ADAUSDT"]
H8 = 28800

def load(s):
    b = {}
    for r in csv.DictReader(open(D + s + ".csv")):
        t = int(r["ts"])//1000; k = t - t % H8
        o,h,l,c = map(float,(r["o"],r["h"],r["l"],r["c"]))
        if k not in b: b[k] = [o,h,l,c]
        else: x=b[k]; x[1]=max(x[1],h); x[2]=min(x[2],l); x[3]=c
    return b
data = {s: load(s) for s in SY}
T = sorted(set.intersection(*[set(d) for d in data.values()]))
atr = {s: {} for s in SY}
for s in SY:
    tr = []; prev = None
    for t in T:
        o,h,l,c = data[s][t]
        tr.append(max(h-l, abs(h-prev) if prev else 0, abs(l-prev) if prev else 0)); prev = c
        if len(tr) >= 14: atr[s][t] = sum(tr[-14:])/14

def run(t0, R, p_entry, size_mode, seed, weeks=13, COST=0.0015, FEEB=0.002):
    rng = random.Random(seed)
    TT = [t for t in T if t0 <= t < t0 + weeks*7*86400]
    cash = 2000.0; pos = {}; pend = []
    fee_wk = {}; day_open = {}; navs = []
    out = dict(rt=0, halt_floor=False, halt_day=False, pause_days=set(), budget_bind_wakes=0, worst_day=0, risk=[])
    for i, t in enumerate(TT):
        bar = {s: data[s][t] for s in SY}
        wk = (t - 345600) // 604800  # weeks start Mon 00:00 UTC
        # fills at open
        for side, s, q, stop, tl in pend:
            px = bar[s][0]
            if side == "buy":
                cost = q*px; fee = cost*COST
                if cost + fee > cash: q = (cash/(1+COST))/px; cost = q*px; fee = cost*COST
                if q <= 0: continue
                cash -= cost + fee; pos[s] = [q, stop, tl]; fee_wk[wk] = fee_wk.get(wk,0) + fee
            elif s in pos:
                q = pos.pop(s)[0]; v = q*px; fee = v*COST
                cash += v - fee; fee_wk[wk] = fee_wk.get(wk,0) + fee; out["rt"] += 1
        pend = []
        # intrabar stops (resting on the venue)
        for s in list(pos):
            q, stop, tl = pos[s]; o,h,l,c = bar[s]
            if l <= stop:
                px = min(o, stop); v = q*px; fee = v*COST
                cash += v - fee; fee_wk[wk] = fee_wk.get(wk,0) + fee; out["rt"] += 1; pos.pop(s)
        nav = cash + sum(q*bar[s][3] for s,(q,_,_) in pos.items())
        navs.append(nav)
        dkey = t // 86400  # the 3 bars opening 00/08/16 close inside this UTC day
        if dkey not in day_open: day_open[dkey] = navs[-2] if len(navs) > 1 else 2000.0
        dop = day_open.get(dkey, 2000.0)
        dd = nav/dop - 1; out["worst_day"] = min(out["worst_day"], dd)
        if nav <= 1600: out["halt_floor"] = True
        if dd <= -0.10: out["halt_day"] = True
        if dd <= -0.04: out["pause_days"].add(dkey)
        if out["halt_floor"] or out["halt_day"] or i == len(TT)-1: break_after = True
        else: break_after = False
        # decisions at close t+8h, fill next open
        tc = t + H8
        for s,(q,stop,tl) in list(pos.items()):
            if tc >= tl: pend.append(("sell", s, q, 0, 0))
        if break_after: break
        if dd <= -0.04: continue
        if fee_wk.get(wk,0) >= FEEB*nav:
            out["budget_bind_wakes"] += 1; continue
        n_new = 0
        free = [s for s in SY if s not in pos]
        rng.shuffle(free)
        for s in free:
            if len(pos) + n_new >= 4 or n_new >= 2: break
            if rng.random() > p_entry or t not in atr[s]: continue
            px = bar[s][3]; k = rng.uniform(1.5, 3.0); sd = k*atr[s][t]
            q = R*nav/sd
            capq = 0.25*nav/px
            if size_mode == "half": q = min(q, capq*rng.uniform(0.4, 1.0))
            q = min(q, capq)
            out["risk"].append(q*sd/nav)
            pend.append(("buy", s, q, px - sd, tc + rng.randint(3, 21)*H8)); n_new += 1
    out["end"] = navs[-1]/2000; peak = 2000; mdd = 0
    for n in navs: peak = max(peak, n); mdd = min(mdd, n/peak - 1)
    out["mdd"] = mdd; out["weeks"] = len(navs)/21
    return out

if __name__ == "__main__":
    starts = [t for t in T if t % 604800 == 345600 and t + 13*7*86400 < T[-1]][::2]
    for R in (0.0075, 0.005, 0.0035):
        for p, mode in ((0.15, "half"), (0.35, "full")):
            rs = [run(t0, R, p, mode, seed) for t0 in starts for seed in range(3)]
            rt = st.mean(r["rt"]/r["weeks"] for r in rs)
            fl = sum(r["halt_floor"] for r in rs)/len(rs); dh = sum(r["halt_day"] for r in rs)/len(rs)
            wd = sorted(r["worst_day"] for r in rs); md = sorted(r["mdd"] for r in rs)
            en = sorted(r["end"] for r in rs)
            pd = st.mean(len(r["pause_days"]) for r in rs)
            rk = [x for r in rs for x in r["risk"]]
            print(f"R={R:.4f} p={p} {mode:4s} n={len(rs)} rt/wk={rt:4.1f} avg_risk={st.mean(rk)*100:.2f}% "
                  f"P(NAV<=1600)={fl*100:4.1f}% P(-10%day)={dh*100:4.1f}% "
                  f"mDD p50={md[len(md)//2]*100:5.1f}% p5={md[len(md)//20]*100:5.1f}% "
                  f"worstday p5={wd[len(wd)//20]*100:5.1f}% min={wd[0]*100:5.1f}% "
                  f"end p5={en[len(en)//20]:.3f} p50={en[len(en)//2]:.3f} pause_days/13wk={pd:.1f}")
