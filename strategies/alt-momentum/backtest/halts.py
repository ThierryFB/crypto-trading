#!/usr/bin/env python3
"""How often Ingrid's draft halt levels (PR #8, risk-policy.md D1-D5) would have fired on the base backtest.
   python3 halts.py > halts.txt

The weekly backtest only marks NAV at Sunday closes. This rebuilds a daily NAV from the same book: each week's
weights (after that week's costs) are marked at every CMC daily close until the next rebalance. The daily path is
then scaled so each week ends on the weekly backtest's value; the week-end gap is reported as a check.
Daily closes come from CMC's keyless daily endpoint (see data.py), one JSON per coin per 2-year window."""
import os, json, glob, datetime as dt
from bt import *   # noqa

DAILY_DIRS = os.environ.get('CMC_DAILY_DIRS', ':'.join([
    '/paperclip/instances/default/workspaces/a3ae5ff4-6eb6-4daa-9169-f2568b7087ba/the-297/daily',
    '/paperclip/instances/default/workspaces/7a92fdbc-8b54-460f-b557-c3bbcc38c515/the-273/daily'])).split(':')

def load_daily(ids):
    px = {i: {} for i in ids}
    for d in DAILY_DIRS:
        for i in ids:
            for f in glob.glob(os.path.join(d, f'{i}.*.json')):
                try:
                    q = json.load(open(f))['data']['quotes']
                except Exception:
                    continue
                for r in q:
                    c = r['quote']['close']
                    if c and c > 0:
                        px[i].setdefault(r['timeClose'][:10], c)
    return px

def day(s): return dt.date.fromisoformat(s)

def daily_nav(r, px):
    """[(date, nav)] at every daily close, plus regime flag per day and the week-end gaps."""
    out = [(r['curve'][0][0], 1.0, False)]; gaps = []; missing = 0
    ends = dict(r['curve'])
    for w, eq_c, hold in r['book']:
        d0, d1 = day(dates[w]), day(dates[w + 1])
        base = {i: px.get(i, {}).get(dates[w]) for i in hold}
        missing += sum(7 for i in hold if not base[i])
        last = dict(base)
        path = []
        for n in range(1, (d1 - d0).days + 1):
            ds = (d0 + dt.timedelta(n)).isoformat()
            g = 1 - sum(hold.values())
            for i, wt in hold.items():
                p = px.get(i, {}).get(ds)
                if p: last[i] = p
                elif base[i]: missing += 1
                g += wt * (last[i] / base[i] if base[i] and last[i] else 1.0)
            path.append((ds, eq_c * g))
        end = ends[dates[w + 1]]
        if path and path[-1][1] > 0:
            k = end / path[-1][1]; gaps.append(abs(k - 1))
            path = [(ds, v * k ** ((n + 1) / len(path))) for n, (ds, v) in enumerate(path)]
        out += [(ds, v, bool(hold)) for ds, v in path]
    return out, gaps, missing

def episodes(flags, rearm=None, gap=7):
    """Count separate firings; return (count, index of each first firing).
    rearm[k] True means the level is armed again (a new HWM). Without rearm, firings within `gap` days are one cluster."""
    starts = []; armed = True; lastf = -10 ** 9
    for k, f in enumerate(flags):
        if rearm is not None and rearm[k]:
            armed = True
        if f:
            if (rearm is not None and armed) or (rearm is None and k - lastf > gap):
                starts.append(k); armed = False
            lastf = k
    return len(starts), starts

def levels(nav):
    v = [x for _, x, _ in nav]; ds = [d for d, _, _ in nav]; on = [o for _, _, o in nav]
    hwm = []; pk = 0
    for x in v:
        pk = max(pk, x); hwm.append(pk)
    dd = [x / h for x, h in zip(v, hwm)]
    newhi = [k == 0 or x >= hwm[k - 1] for k, x in enumerate(v)]
    d1d = [1.0] + [v[k] / v[k - 1] for k in range(1, len(v))]
    d7 = [1.0] * 7 + [v[k] / v[k - 7] for k in range(7, len(v))]
    return ds, v, on, dd, d1d, d7, newhi

def main():
    r = run()
    ids = set(i for _, _, h in r['book'] for i in h)
    px = load_daily(ids)
    held_days = sum(len(h) * 7 for _, _, h in r['book'])
    nav, gaps, missing = daily_nav(r, px)
    ds, v, on, dd, d1d, d7, newhi = levels(nav)
    print(f"Base run, daily NAV rebuilt from the weekly book, {ds[0]} .. {ds[-1]} ({len(ds)} days). "
          f"Coin-days without a daily close (last close carried): {missing} of {held_days}. "
          f"Week-end gap between the daily rebuild and the weekly backtest: median {st.median(gaps):.2%}, max {max(gaps):.1%}.\n")

    print("## Halt and review levels, base run from 2019-01-06\n")
    print("Episodes: D1/D2 count drawdowns (a level fires once, and re-arms only at a new HWM). D3 fires once. "
          "D4, D5 and the review trigger count clusters (firings within 7 days are one episode). "
          "In practice the first halt stops the strategy until Nadia resumes it, so later episodes assume a resume.\n")
    print("| Level | Rule | Episodes | Days at or past the level | First fires (date: value) |\n|---|---|---|---|---|")
    def line(tag, rule, flags, val, fmt, rearm=None):
        n, st_ = episodes(flags, rearm)
        firsts = '; '.join(f"{ds[k]}: {fmt(val[k])}" for k in st_[:6]) + (' …' if n > 6 else '')
        print(f"| {tag} | {rule} | {n} | {sum(flags)} | {firsts or '–'} |")
    line('D1 (review)', 'NAV ≤ 80% of HWM', [x <= 0.8 for x in dd], dd, lambda x: f"{x - 1:.0%}", newhi)
    line('D2 (halt)', 'NAV ≤ 70% of HWM', [x <= 0.7 for x in dd], dd, lambda x: f"{x - 1:.0%}", newhi)
    line('D3 (halt)', 'NAV ≤ 60% of start', [x <= 0.6 for x in v], v, lambda x: f"{x:.2f}x", [False] * len(v))
    line('D4 (halt)', 'NAV down ≥ 15% in one UTC day', [x <= 0.85 for x in d1d], d1d, lambda x: f"{x - 1:.0%}")
    line('D5 (halt)', 'NAV down ≥ 30% in 7 days', [x <= 0.7 for x in d7], d7, lambda x: f"{x - 1:.0%}")
    line('Momentum crash (review)', 'NAV down ≥ 20% in 7 days, regime on', [x <= 0.8 and o for x, o in zip(d7, on)], d7, lambda x: f"{x - 1:.0%}")
    k = min(range(len(dd)), key=lambda k: dd[k])
    print(f"\nWorst daily drawdown from HWM: {dd[k] - 1:.0%} on {ds[k]} (weekly closes: {stats(r['curve'], r['rets'])['mdd']:.0%}). "
          f"Worst day: {min(d1d) - 1:.0%}. Worst 7 days: {min(d7) - 1:.0%}. Lowest NAV vs start: {min(v):.2f}x.")
    first = {}
    for tag, flags in (('D2', [x <= 0.7 for x in dd]), ('D3', [x <= 0.6 for x in v]), ('D4', [x <= 0.85 for x in d1d]), ('D5', [x <= 0.7 for x in d7])):
        if any(flags): first[tag] = ds[flags.index(True)]
    if first:
        t = min(first, key=first.get)
        print(f"First halt of any kind: {t} on {first[t]}, after a NAV high of {max(v[:ds.index(first[t]) + 1]):.2f}x.")

    print("\n## D3 from every starting month (fresh $1 on the first Sunday of the month)\n")
    print("| Start | Lowest daily NAV vs start | Date | D3 hit | D2 episodes | D5 episodes |\n|---|---|---|---|---|---|")
    hits = []; rows = []
    months = [d for k, d in enumerate(dates) if d >= START and d < dates[-5] and (k == 0 or d[:7] != dates[k - 1][:7])]
    for s in months:
        rs = run(start=s)
        nv, _, _ = daily_nav(rs, px)
        ds_, v_, on_, dd_, d1_, d7_, nh_ = levels(nv)
        k = min(range(len(v_)), key=lambda k: v_[k])
        hit = v_[k] <= 0.6; hits.append(hit)
        rows.append((s, v_[k], ds_[k], hit, episodes([x <= 0.7 for x in dd_], nh_)[0], episodes([x <= 0.7 for x in d7_])[0]))
    for s, lo, d, hit, n2, n5 in rows:
        print(f"| {s[:7]} | {lo:.2f}x | {d} | {'yes' if hit else 'no'} | {n2} | {n5} |")
    print(f"\nD3 would have been hit from {sum(hits)} of {len(hits)} starting months.")

if __name__ == '__main__':
    main()
