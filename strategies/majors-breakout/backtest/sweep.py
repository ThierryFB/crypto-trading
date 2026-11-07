from bt_active import *
import sys
from concurrent.futures import ProcessPoolExecutor
V = [
 ("Old base: breakout 20/10, U6", U6, breakout(20,10,90), {}),
 ("Breakout 10/5, U6", U6, breakout(10,5,90), {}),
 ("Breakout 10/5, U15, 6 pos", U15, breakout(10,5,90), dict(MAXPOS=6, CAP=0.2)),
 ("Breakout 20/10, U15, 6 pos", U15, breakout(20,10,90), dict(MAXPOS=6, CAP=0.2)),
 ("Breakout 6/3, U15, 6 pos", U15, breakout(6,3,90), dict(MAXPOS=6, CAP=0.2)),
 ("Breakout 20/10 4h bars, U15, 6 pos", U15, breakout(20,10,180), dict(MAXPOS=6, CAP=0.2, bar=14400)),
 ("Dip RSI2<10, exit>SMA5|6 bars, U15", U15, dip(90,2,10,5,6), dict(MAXPOS=6, CAP=0.2)),
 ("Dip RSI3<15, exit>SMA5|6 bars, U15", U15, dip(90,3,15,5,6), dict(MAXPOS=6, CAP=0.2)),
 ("Dip RSI2<10, exit>SMA5|6 bars, U6", U6, dip(90,2,10,5,6), dict(MAXPOS=4)),
 ("Dip RSI2<10 4h, exit>SMA5|12 bars, U15", U15, dip(180,2,10,5,12), dict(MAXPOS=6, CAP=0.2, bar=14400)),
]
def job(a):
    i, c = a; name, U, sig, kw = V[i]
    return fmt(name, c, run(U, sig, COST=c, **kw))
if __name__ == "__main__":
    args = [(i,c) for i in range(len(V)) for c in (0.0, 0.0015, 0.003)]
    print(HDR)
    with ProcessPoolExecutor(8) as ex:
        for line in ex.map(job, args): print(line, flush=True)
