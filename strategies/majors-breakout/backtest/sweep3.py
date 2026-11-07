"""Multi-speed breakout: same rules at 2-3 channel lengths, each on its own slice of the book (U6, 8h wakes)."""
from bt_active import *
from concurrent.futures import ProcessPoolExecutor
SPEEDS = {"10/5": (10,5), "20/10": (20,10), "40/20": (40,20)}
COMBOS = [("2-speed 10/5 + 20/10", ["10/5","20/10"]), ("3-speed 10/5 + 20/10 + 40/20", ["10/5","20/10","40/20"])]
def sub(a):
    k, c, s, e = a; n_in, n_out = SPEEDS[k]
    return run(U6, breakout(n_in, n_out, 90), COST=c, start=s, end=e)
if __name__ == "__main__":
    with ProcessPoolExecutor(8) as ex:
        print(HDR)
        for c in (0.0, 0.001, 0.0015, 0.003):
            R = dict(zip(SPEEDS, ex.map(sub, [(k,c,None,None) for k in SPEEDS])))
            for name, ks in COMBOS: print(fmt(name, c, combine([R[k] for k in ks])), flush=True)
        for s,e,n in YEARS:
            R = dict(zip(SPEEDS, ex.map(sub, [(k,0.0015,s,e) for k in SPEEDS])))
            for name, ks in COMBOS:
                r = combine([R[k] for k in ks])
                print(f"{name} {n}: {r['end']:.2f}x DD {r['mdd']*100:.0f}% RT/wk {r['rt_wk']:.1f} weeks>=3 {r['ge3']*100:.0f}% | BTC {r['btc']:.2f}x")
