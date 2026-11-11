"""The runner's input block (strategy.md §3): prices and 8h levels, perp funding / open interest / long-short
(Bybit public linear), Fear & Greed (alternative.me), USDT + USDC supply (DefiLlama). All keyless.
Each source fails on its own: a missing input is reported, never invented."""
import json, os, sys, time, urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "majors-breakout", "runner"))
import bybit, engine  # noqa: E402


def get(url, timeout=20):
    r = urllib.request.Request(url, headers={"User-Agent": "majors-discretionary-runner"})
    with urllib.request.urlopen(r, timeout=timeout) as f:
        return json.load(f)


def coin_block(sym, now):
    B = engine.bars8h(bybit.klines4h(sym), now)
    H = [B[k] for k in sorted(B)]
    lv = engine.levels(H)
    bid, ask = bybit.touch(sym)
    closes = [x[3] for x in H]
    d = dict(bid=bid, ask=ask, mid=(bid + ask) / 2, last_close_t=max(B) + engine.BAR, close=lv["close"],
             chg_24h=closes[-1] / closes[-4] - 1, chg_7d=closes[-1] / closes[-22] - 1,
             atr14=lv["atr14"], atr_pct=lv["atr14"] / lv["close"], sma90=lv["sma90"], hi=lv["hi"], lo=lv["lo"],
             up24_90d=sum(closes[i + 3] > closes[i] for i in range(len(closes) - 273, len(closes) - 3)) / 270)
    return d, H


def perp_block(sym):
    q = dict(category="linear", symbol=sym)
    f = bybit.public("/v5/market/funding/history", **q, limit=3)["list"]
    oi = bybit.public("/v5/market/open-interest", **q, intervalTime="4h", limit=7)["list"]
    ls = bybit.public("/v5/market/account-ratio", **q, period="4h", limit=1)["list"]
    return dict(funding=float(f[0]["fundingRate"]), funding_avg3=sum(float(x["fundingRate"]) for x in f) / len(f),
                oi=float(oi[0]["openInterest"]), oi_chg_24h=float(oi[0]["openInterest"]) / float(oi[-1]["openInterest"]) - 1,
                long_ratio=float(ls[0]["buyRatio"]))


def fear_greed():
    d = get("https://api.alternative.me/fng/?limit=2")["data"]
    return dict(value=int(d[0]["value"]), label=d[0]["value_classification"], prev=int(d[1]["value"]),
                at=int(d[0]["timestamp"]))


def stables():
    A = get("https://stablecoins.llama.fi/stablecoins?includePrices=false")["peggedAssets"]
    out = {}
    for a in A:
        if a["symbol"] in ("USDT", "USDC"):
            now, wk = a["circulating"].get("peggedUSD", 0), a.get("circulatingPrevWeek", {}).get("peggedUSD", 0)
            out[a["symbol"]] = dict(supply=now, chg_7d=now / wk - 1 if wk else None)
    tot = sum(v["supply"] for v in out.values())
    return dict(out, total=tot)


def collect(universe, now=None):
    """{'coins': {COIN: {...}}, 'perp': {COIN: {...}}, 'fng': {...}, 'stables': {...}, 'errors': [...], 'hist': {COIN: H}}"""
    now = now or time.time()
    D = dict(t=now, coins={}, perp={}, hist={}, errors=[])
    for s in universe:
        c = s[:-4]
        try:
            D["coins"][c], D["hist"][c] = coin_block(s, now)
        except Exception as e:
            D["errors"].append(f"{c} spot: {e}")
        try:
            D["perp"][c] = perp_block(s)
        except Exception as e:
            D["errors"].append(f"{c} perp: {e}")
    for k, fn in (("fng", fear_greed), ("stables", stables)):
        try:
            D[k] = fn()
        except Exception as e:
            D[k] = None; D["errors"].append(f"{k}: {e}")
    return D


def pct(x, d=1):
    return "—" if x is None else f"{x * 100:+.{d}f}%"


def render(D):
    L = ["| Coin | Mid | 24h | 7d | ATR14 (8h) | vs sma90 | Funding (last / avg 3) | OI 24h | Long share | Up-24h, 90d |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for c, d in D["coins"].items():
        p = D["perp"].get(c)
        pp = (f"{p['funding'] * 100:+.4f}% / {p['funding_avg3'] * 100:+.4f}% | {pct(p['oi_chg_24h'])} | {p['long_ratio']:.0%}"
              if p else "— | — | —")
        L.append(f"| {c} | {d['mid']:.6g} | {pct(d['chg_24h'])} | {pct(d['chg_7d'])} | {pct(d['atr_pct'], 2)[1:]} | "
                 f"{pct(d['close'] / d['sma90'] - 1)} | {pp} | {d['up24_90d']:.0%} |")
    f, s = D.get("fng"), D.get("stables")
    if f:
        L.append(f"\nFear & Greed: **{f['value']}** ({f['label']}), previous {f['prev']}.")
    if s:
        L.append("Stablecoins: " + ", ".join(f"{k} ${v['supply'] / 1e9:,.1f}bn ({pct(v['chg_7d'], 2)} 7d)"
                                         for k, v in s.items() if k != "total") + f"; total ${s['total'] / 1e9:,.1f}bn.")
    if D["errors"]:
        L.append("\n**Input errors:** " + "; ".join(D["errors"]))
    return "\n".join(L)


if __name__ == "__main__":
    cfg = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")))
    print(render(collect(cfg["universe"])))
