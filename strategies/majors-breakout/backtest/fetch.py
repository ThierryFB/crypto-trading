import json, urllib.request, csv, sys, time
SYMS = sys.argv[1:]
START = 1609459200000  # 2021-01-01
def get(sym, end):
    u = f"https://api.bybit.com/v5/market/kline?category=spot&symbol={sym}&interval=240&limit=1000&end={end}"
    return json.load(urllib.request.urlopen(u, timeout=30)).get("result",{}).get("list",[])
for s in SYMS:
    rows = {}; end = int(time.time()*1000)
    while True:
        L = get(s, end)
        if not L: break
        for r in L: rows[int(r[0])] = r
        oldest = min(int(r[0]) for r in L)
        if oldest <= START or len(L) < 1000: break
        end = oldest - 1
    with open(f"{s}.csv","w") as f:
        w = csv.writer(f); w.writerow(["ts","o","h","l","c","v","turnover"])
        for k in sorted(rows):
            if k >= START: w.writerow(rows[k])
    print(s, len(rows), time.strftime('%Y-%m-%d', time.gmtime(min(rows)/1000)))
