"""THE-297 Alt Momentum: loader + point-in-time universe on CMC weekly historical snapshots (THE-271 cache).
The snapshots list every coin CMC tracked on that date, including coins that later died, so the universe is survivorship-free."""
import os, sys, io, contextlib, math

# THE-271 snapshot cache (dates.txt, snap/*.tsv, analyze.py). Not in the repo: about 560 files from CMC's keyless
# historical-listings endpoint (data-api/v3/cryptocurrency/listings/historical?date=...).
SRC = os.environ.get('CMC_SNAP_DIR', '/paperclip/instances/default/workspaces/7a92fdbc-8b54-460f-b557-c3bbcc38c515/the-271')
_cwd = os.getcwd(); os.chdir(SRC)
sys_argv = sys.argv; sys.argv = ['x']
with contextlib.redirect_stdout(io.StringIO()):
    exec(open('analyze.py').read().split('start_w = ')[0])   # dates, N, P, M, V, SYM, ok, NAN
sys.argv = sys_argv; os.chdir(_cwd)

BTC, ETH = 1, 1027
# Pegged / non-crypto-beta tokens the 12-week peg test can miss (yield-bearing or depegged stables, gold).
SYM_EXCL = {'USTC', 'UST', 'SUSDE', 'USDE', 'PAXG', 'XAUT', 'XAUT0', 'USYC', 'BUIDL', 'USDTB', 'SUSDS', 'SDAI', 'USD0'}
# Major-asset derivatives (wrapped, bridged, liquid-staking) are caught by the ratio test below; these prefixes catch the rest.
SYM_PREFIX_EXCL = ('WBTC', 'WETH', 'STETH', 'WSTETH', 'CBBTC', 'CBETH', 'RETH', 'WEETH', 'EETH', 'BTCB', 'WBNB', 'WBETH')
MIN_WEEKS = 12          # listed at least 12 weekly snapshots
VOL_FLOOR = 20e6        # 4-week median CMC 24h volume, USD
UNIV_N = 20

def med(xs):
    xs = sorted(xs); n = len(xs)
    return (xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2) if n else 0.0

def pegged(i, w):
    xs = [P[i][k] for k in range(max(0, w - 11), w + 1) if ok(P[i][k])]
    return bool(xs) and sum(0.9 <= x <= 1.1 for x in xs) / len(xs) >= 0.8

def derivative(i, w, majors):
    """Price tracks a larger coin within 5% on >= 80% of the last 12 weeks (wrapped / bridged / LST)."""
    for j in majors:
        if j == i:
            continue
        r = [P[i][k] / P[j][k] for k in range(max(0, w - 11), w + 1) if ok(P[i][k]) and ok(P[j][k])]
        if len(r) >= 4 and sum(abs(x - 1) < 0.05 for x in r) / len(r) >= 0.8:
            return True
    return False

def excluded_sym(i):
    s = SYM[i].upper()
    return s in SYM_EXCL or s.startswith(SYM_PREFIX_EXCL)

def universe(w, n=UNIV_N, include_majors=False, vol_floor=VOL_FLOOR):
    """Top-n by market cap at snapshot w among coins that pass the inclusion rule, using data up to w only."""
    live = [i for i in P if ok(P[i][w]) and M[i][w] > 0]
    big = sorted(live, key=lambda i: -M[i][w])[:100]
    out = []
    for i in big:
        if not include_majors and i in (BTC, ETH):
            continue
        if excluded_sym(i) or pegged(i, w):
            continue
        if sum(ok(P[i][k]) for k in range(0, w + 1)) < MIN_WEEKS:
            continue
        if med([V[i][k] for k in range(max(0, w - 3), w + 1)]) < vol_floor:
            continue
        if derivative(i, w, big[:15]):
            continue
        out.append(i)
        if len(out) == n:
            break
    return out

if __name__ == '__main__':
    for d in ('2019-01-06', '2020-03-01', '2021-05-02', '2022-06-05', '2023-01-01', '2024-03-03', '2025-06-01', dates[-1]):
        w = dates.index(d)
        print(d, ' '.join(SYM[i] for i in universe(w)))
