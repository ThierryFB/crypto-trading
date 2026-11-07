from bt import *
U6 = ["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","DOGEUSDT","ADAUSDT"]
for a,b,n in [(1640995200,1672531200,"2022"),(1672531200,1704067200,"2023"),(1704067200,1735689600,"2024"),(1735689600,1767225600,"2025"),(1767225600,1800000000,"2026 YTD")]:
    print(fmt(f"NoRegime {n}", run(U6, REGIME=False, start=a, end=b)))
print(fmt("NoRegime 15/7", run(U6, REGIME=False, N_IN=15, N_OUT=7)))
print(fmt("NoRegime 30/15", run(U6, REGIME=False, N_IN=30, N_OUT=15)))
print(fmt("NoRegime cost 0.5%", run(U6, REGIME=False, COST=0.005)))
print(fmt("NoRegime U8", run(U6+["LINKUSDT","AVAXUSDT"], REGIME=False)))
# current state
b = load("BTCUSDT"); d={}
for k in sorted(b): d[k-k%86400]=b[k][3]
ks=sorted(d)[:-1]; print("BTC last daily close", d[ks[-1]], "SMA150", sum(d[k] for k in ks[-150:])/150)
