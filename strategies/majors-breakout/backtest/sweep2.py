from bt_active import *
from concurrent.futures import ProcessPoolExecutor
U10 = U6 + ["LINKUSDT","AVAXUSDT","LTCUSDT","BCHUSDT"]
V = [
 ("Breakout 20/10 4h bars, U6", U6, breakout(20,10,180), dict(bar=14400)),
 ("Breakout 40/20 4h bars, U6", U6, breakout(40,20,180), dict(bar=14400)),
 ("Breakout 10/5, U10, 5 pos", U10, breakout(10,5,90), dict(MAXPOS=5, CAP=0.2)),
 ("Breakout 20/10 4h bars, U10, 5 pos", U10, breakout(20,10,180), dict(MAXPOS=5, CAP=0.2, bar=14400)),
]
def job(a):
    i, c = a; name, U, sig, kw = V[i]
    return fmt(name, c, run(U, sig, COST=c, **kw))
def yjob(a):
    i, y = a; name, U, sig, kw = V[i]; s,e,n = YEARS[y]
    r = run(U, sig, COST=0.0015, start=s, end=e, **kw)
    return f"{name} {n}: {r['end']:.2f}x DD {r['mdd']*100:.0f}% RT/wk {r['rt_wk']:.1f} | BTC {r['btc']:.2f}x"
if __name__ == "__main__":
    print(HDR)
    with ProcessPoolExecutor(8) as ex:
        for l in ex.map(job, [(i,c) for i in range(len(V)) for c in (0.0, 0.001, 0.0015, 0.003)]): print(l, flush=True)
        for l in ex.map(yjob, [(i,y) for i in (0,2) for y in range(5)]): print(l, flush=True)
