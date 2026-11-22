"""Desk inputs pull (THE-425): one fixed script, so every wake and brief gets the same data, or an explicit MISSING line.

Data inputs only: no trading logic, no limits. Stdlib only, keyless sources only. Each source fails on its own and is
reported as MISSING with the reason; nothing is filled in or guessed. Every figure carries the date it covers.

    python3 desk_inputs.py                 # markdown block on stdout
    python3 desk_inputs.py --json OUT.json # also write the raw data
    python3 desk_inputs.py --only etf,options
"""
import argparse, csv, datetime as dt, html, io, json, math, re, sys, time, urllib.request
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
COINS = ["BTC", "ETH", "SOL", "XRP", "DOGE", "ADA"]  # majors-discretionary universe
NOW = time.time()


def fetch(url, timeout=30, tries=2, ua=UA):
    """Browser UA by default: Farside, The Block and others 403 the default Python/curl UA. FRED is the reverse: it
    stalls for a browser or custom UA, so it passes ua=None (urllib's own UA)."""
    err = None
    for i in range(tries):
        try:
            r = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "*/*"} if ua else {})
            with urllib.request.urlopen(r, timeout=timeout) as f:
                return f.read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            err = e
            if getattr(e, "code", None) in (401, 402, 403, 404):
                break
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"{url.split('?')[0]}: {err}")


def jget(url, **kw):
    return json.loads(fetch(url, **kw))


def utc(t):
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d %H:%MZ")


def pct(x, d=1):
    return "—" if x is None else f"{x * 100:+.{d}f}%"


def cells(row):
    return [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", c))).strip()
            for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)]


# ---------------------------------------------------------------- ETF flows (Farside, US$m)

def farside(asset, days=5):
    rows = [cells(r) for r in re.findall(r"<tr[^>]*>(.*?)</tr>", fetch(f"https://farside.co.uk/{asset}/"), re.S)]
    head = next(r for r in rows if len(r) > 3 and r[0] == "" and r[1])
    dated = [r for r in rows if re.match(r"\d{1,2} \w{3} \d{4}$", r[0] or "")]
    if not dated:
        raise RuntimeError(f"farside {asset}: no dated rows (layout changed?)")

    def num(s):
        s = s.replace(",", "")
        return None if s in ("", "-") else -float(s[1:-1]) if s.startswith("(") else float(s)
    out = []
    for r in dated[-days:]:
        fund = {h: num(v) for h, v in zip(head[1:-1], r[1:-1])}
        out.append(dict(day=r[0], total=num(r[-1]), pending=[h for h, v in fund.items() if v is None],
                        top=sorted(((h, v) for h, v in fund.items() if v), key=lambda x: -abs(x[1]))[:3]))
    return out


def etf():
    return {a: farside(a) for a in ("btc", "eth", "sol")}


def render_etf(D):
    L = []
    for a, rows in D.items():
        L.append(f"- **{a.upper()}** (Farside, US$m, by trading day): " + "; ".join(
            f"{r['day'][:-5]} {r['total']:+,.1f}" + (f" (not yet in: {', '.join(r['pending'])})" if r["pending"] else "")
            for r in rows))
        last = rows[-1]
        if last["top"]:
            L.append(f"  - {last['day']}: " + ", ".join(f"{h} {v:+,.1f}" for h, v in last["top"]))
    return L


# ---------------------------------------------------------------- Options (Deribit public)

def ncdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def options_coin(c):
    end = int(NOW * 1000)
    dv = jget(f"https://www.deribit.com/api/v2/public/get_volatility_index_data?currency={c}"
              f"&start_timestamp={end - 26 * 3600 * 1000}&end_timestamp={end}&resolution=3600")["result"]["data"]
    book = jget(f"https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency={c}&kind=option")["result"]
    calls = sum(o["open_interest"] for o in book if o["instrument_name"].endswith("-C"))
    puts = sum(o["open_interest"] for o in book if o["instrument_name"].endswith("-P"))
    # expiry closest to 30 days out; 25-delta skew from Black-76 deltas at each option's mark IV
    exp = {}
    for o in book:
        e = o["instrument_name"].split("-")[1]
        exp.setdefault(e, []).append(o)
    T = {e: (dt.datetime.strptime(e, "%d%b%y").replace(hour=8, tzinfo=dt.timezone.utc).timestamp() - NOW) / 31557600
         for e in exp}
    e = min((x for x in exp if T[x] > 7 / 365), key=lambda x: abs(T[x] - 30 / 365))
    t, pts = T[e], {"C": [], "P": []}
    for o in exp[e]:
        iv, F, K = o.get("mark_iv"), o.get("underlying_price"), float(o["instrument_name"].split("-")[2])
        if not iv or not F:
            continue
        d1 = (math.log(F / K) + (iv / 100) ** 2 * t / 2) / (iv / 100 * math.sqrt(t))
        k = o["instrument_name"][-1]
        pts[k].append((ncdf(d1) if k == "C" else ncdf(d1) - 1, iv, K, F))

    def at(k, target):
        p = sorted(pts[k])
        for (d0, v0, *_), (d1_, v1, *_) in zip(p, p[1:]):
            if d0 <= target <= d1_:
                return v0 + (v1 - v0) * (target - d0) / (d1_ - d0) if d1_ != d0 else v0
        return None
    c25, p25, atm = at("C", 0.25), at("P", -0.25), at("C", 0.5)
    return dict(dvol=dv[-1][4], dvol_24h=dv[-1][4] - dv[0][4] if len(dv) > 24 else None, dvol_t=dv[-1][0] / 1000,
                pc_oi=puts / calls if calls else None, expiry=e, days=t * 365, atm_iv=atm,
                rr25=(c25 - p25) if c25 and p25 else None)


def options():
    return {c: options_coin(c) for c in ("BTC", "ETH")}


def render_options(D):
    L = ["| | DVOL | DVOL 24h | ATM IV | 25d RR (call − put) | Expiry | Put/call OI |", "|---|---|---|---|---|---|---|"]
    for c, d in D.items():
        f = lambda x, s="": "—" if x is None else f"{x:{s}.1f}"  # noqa: E731
        L.append(f"| {c} | {d['dvol']:.1f} | {f(d['dvol_24h'], '+')} | {f(d['atm_iv'])} | {f(d['rr25'], '+')} | "
                 f"{d['expiry']} ({d['days']:.0f}d) | {d['pc_oi']:.2f} |")
    L.append(f"\nDeribit, at {utc(next(iter(D.values()))['dvol_t'])}. RR < 0 = puts bid over calls.")
    return L


# ---------------------------------------------------------------- Cross-exchange perps (Bybit + Binance + OKX)

def perps_coin(c):
    s, row = c + "USDT", {}
    t = jget(f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={s}")["result"]["list"][0]
    oi = jget(f"https://api.bybit.com/v5/market/open-interest?category=linear&symbol={s}&intervalTime=4h&limit=7")
    px, ois = float(t["markPrice"]), [float(x["openInterest"]) for x in oi["result"]["list"]]
    # OI level in USD; OI 24h change in coins on every venue, so a price move doesn't read as (de)leveraging
    row["bybit"] = dict(oi=ois[0] * px, oi_24h=ois[0] / ois[-1] - 1, funding=float(t["fundingRate"]))
    try:
        h = jget(f"https://fapi.binance.com/futures/data/openInterestHist?symbol={s}&period=4h&limit=7")
        f = jget(f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={s}")
        row["binance"] = dict(oi=float(h[-1]["sumOpenInterestValue"]),
                              oi_24h=float(h[-1]["sumOpenInterest"]) / float(h[0]["sumOpenInterest"]) - 1,
                              funding=float(f["lastFundingRate"]))
    except Exception as e:  # noqa: BLE001
        row["binance"] = dict(error=str(e))
    try:
        i = f"{c}-USDT-SWAP"
        h = jget(f"https://www.okx.com/api/v5/rubik/stat/contracts/open-interest-history?instId={i}&period=4H&limit=7")["data"]
        f = jget(f"https://www.okx.com/api/v5/public/funding-rate?instId={i}")["data"][0]
        row["okx"] = dict(oi=float(h[0][3]), oi_24h=float(h[0][2]) / float(h[-1][2]) - 1, funding=float(f["fundingRate"]))
    except Exception as e:  # noqa: BLE001
        row["okx"] = dict(error=str(e))
    return row


def okx_liqs(c):
    """OKX only (Bybit and Binance have no REST liquidation feed). Sums what the last page covers, and says how long."""
    d = jget(f"https://www.okx.com/api/v5/public/liquidation-orders?instType=SWAP&uly={c}-USDT&state=filled&limit=100")
    det = [x for blk in d["data"] for x in blk["details"]]
    ct = float(jget(f"https://www.okx.com/api/v5/public/instruments?instType=SWAP&instId={c}-USDT-SWAP")["data"][0]["ctVal"])
    lng = sum(float(x["sz"]) * ct * float(x["bkPx"]) for x in det if x["posSide"] == "long")
    sht = sum(float(x["sz"]) * ct * float(x["bkPx"]) for x in det if x["posSide"] == "short")
    ts = [int(x["ts"]) / 1000 for x in det]
    return dict(long=lng, short=sht, n=len(det), hours=(NOW - min(ts)) / 3600 if ts else 0)


def positioning(c):
    """Per-venue, keyless: Binance account long/short ratio, Bybit buy/sell account ratio (4h)."""
    b = jget(f"https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol={c}USDT&period=4h&limit=1")[-1]
    y = jget(f"https://api.bybit.com/v5/market/account-ratio?category=linear&symbol={c}USDT&period=4h&limit=1")["result"]["list"][0]
    return dict(binance_long=float(b["longAccount"]), bybit_long=float(y["buyRatio"]), t=int(b["timestamp"]) / 1000)


def coinbase_premium():
    cb = float(jget("https://api.exchange.coinbase.com/products/BTC-USD/ticker")["price"])
    bn = float(jget("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT")["price"])
    return dict(coinbase=cb, binance=bn, premium=cb / bn - 1)


def deribit_basis(c):
    """Annualized basis of the dated future nearest 90 days, mark vs index."""
    fut = [o for o in jget(f"https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency={c}&kind=future")["result"]
           if "PERPETUAL" not in o["instrument_name"]]
    T = lambda o: (dt.datetime.strptime(o["instrument_name"].split("-")[1], "%d%b%y").replace(hour=8, tzinfo=dt.timezone.utc)  # noqa: E731
                   .timestamp() - NOW) / 31557600
    o = min((o for o in fut if T(o) > 14 / 365), key=lambda o: abs(T(o) - 90 / 365))
    return dict(instrument=o["instrument_name"], days=T(o) * 365,
                basis_ann=(o["mark_price"] / o["estimated_delivery_price"] - 1) / T(o))


def perps():
    D = dict(coins={}, liq={}, pos={}, basis={}, errors=[])
    for c in COINS:
        try:
            D["coins"][c] = perps_coin(c)
        except Exception as e:  # noqa: BLE001
            D["errors"].append(f"{c}: {e}")
    for c in ("BTC", "ETH"):
        try:
            D["liq"][c] = okx_liqs(c)
        except Exception as e:  # noqa: BLE001
            D["errors"].append(f"{c} OKX liquidations: {e}")
        try:
            D["pos"][c] = positioning(c)
        except Exception as e:  # noqa: BLE001
            D["errors"].append(f"{c} long/short: {e}")
        try:
            D["basis"][c] = deribit_basis(c)
        except Exception as e:  # noqa: BLE001
            D["errors"].append(f"{c} Deribit basis: {e}")
    try:
        D["premium"] = coinbase_premium()
    except Exception as e:  # noqa: BLE001
        D["premium"] = None; D["errors"].append(f"Coinbase premium: {e}")
    return D


def render_perps(D):
    L = ["| Coin | OI, 3 venues | OI 24h (coins) | Bybit / Binance / OKX OI 24h (coins) | Funding Bybit / Binance / OKX (per 8h) |",
         "|---|---|---|---|---|"]
    for c, r in D["coins"].items():
        ok = {v: x for v, x in r.items() if "oi" in x}
        tot = sum(x["oi"] for x in ok.values())
        prev = sum(x["oi"] / (1 + x["oi_24h"]) for x in ok.values())  # same coin on every venue, so a USD weight is fine
        g = lambda v, k, f: f(r[v][k]) if v in ok else "MISSING"  # noqa: E731
        L.append(f"| {c} | ${tot / 1e9:,.2f}bn ({len(ok)}/3) | {pct(tot / prev - 1)} | "
                 + " / ".join(g(v, "oi_24h", pct) for v in ("bybit", "binance", "okx")) + " | "
                 + " / ".join(g(v, "funding", lambda x: f"{x * 100:+.4f}%") for v in ("bybit", "binance", "okx")) + " |")
        for v, x in r.items():
            if "error" in x:
                D["errors"].append(f"{c} {v}: {x['error']}")
    for c, x in D["liq"].items():
        L.append(f"- {c} liquidations, **OKX only**, last {x['hours']:.1f}h ({x['n']} orders): longs ${x['long'] / 1e6:,.2f}m, "
                 f"shorts ${x['short'] / 1e6:,.2f}m.")
    L.append("- Aggregate cross-exchange liquidations: **MISSING** (needs a Coinalyze or CoinGlass key, THE-425).")
    for c, x in D["pos"].items():
        L.append(f"- {c} accounts long, 4h to {utc(x['t'])}: Binance {x['binance_long'] * 100:.0f}%, Bybit {x['bybit_long'] * 100:.0f}% "
                 "(per venue, share of accounts, not size).")
    for c, x in D["basis"].items():
        L.append(f"- {c} Deribit basis, {x['instrument']} ({x['days']:.0f}d): {pct(x['basis_ann'])} annualized.")
    p = D.get("premium")
    if p:
        L.append(f"- Coinbase premium (BTC-USD vs Binance BTCUSDT): {pct(p['premium'], 3)}.")
    return L


# ---------------------------------------------------------------- Cross-asset and rates

def fred(series):
    start = (dt.date.today() - dt.timedelta(days=21)).isoformat()
    rows = [r for r in csv.reader(io.StringIO(fetch(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}&cosd={start}",
                                                   tries=3, ua=None)))][1:]
    rows = [(d, float(v)) for d, v in rows if v not in (".", "")]
    return dict(date=rows[-1][0], value=rows[-1][1], prev_date=rows[-2][0], prev=rows[-2][1])


def treasury():
    y = dt.date.today().year
    t = fetch(f"https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/{y}/all"
              f"?type=daily_treasury_yield_curve&field_tdr_date_value={y}&page&_format=csv")
    r = list(csv.DictReader(io.StringIO(t)))
    return dict(date=r[0]["Date"], y2=float(r[0]["2 Yr"]), y10=float(r[0]["10 Yr"]),
                prev_date=r[1]["Date"], y2_prev=float(r[1]["2 Yr"]), y10_prev=float(r[1]["10 Yr"]))


def yahoo(sym):
    """Intraday futures and DXY. Yahoo rate-limits the runner's IP (429), so this is often MISSING."""
    r = jget(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=5d&interval=1d", tries=1)["chart"]["result"][0]
    m = r["meta"]
    return dict(price=m["regularMarketPrice"], t=m["regularMarketTime"], prev=m.get("chartPreviousClose"))


FRED = [("SP500", "S&P 500"), ("NASDAQCOM", "Nasdaq Composite"), ("VIXCLS", "VIX"), ("DTWEXBGS", "Broad dollar (Fed, weekly lag)")]  # 10y comes from Treasury.gov only: FRED DGS10 is the same series a day later
YAHOO = [("ES=F", "ES (S&P fut)"), ("NQ=F", "NQ (Nasdaq fut)"), ("DX-Y.NYB", "DXY (ICE)"), ("GC=F", "Gold fut")]


def cross():
    D = dict(fred={}, yahoo={}, errors=[])
    try:
        D["treasury"] = treasury()
    except Exception as e:  # noqa: BLE001
        D["treasury"] = None; D["errors"].append(f"Treasury yields: {e}")
    for s, name in FRED:
        try:
            D["fred"][s] = fred(s)
        except Exception as e:  # noqa: BLE001
            D["errors"].append(f"FRED {s}: {e}")
    for s, name in YAHOO:
        try:
            D["yahoo"][s] = yahoo(s)
        except Exception as e:  # noqa: BLE001
            D["errors"].append(f"Yahoo {s}: {e}")
    return D


def render_cross(D):
    L = []
    t = D.get("treasury")
    if t:
        L.append(f"- UST (Treasury.gov), close {t['date']}: 2y {t['y2']:.2f}% ({(t['y2'] - t['y2_prev']) * 100:+.0f}bp), "
                 f"10y {t['y10']:.2f}% ({(t['y10'] - t['y10_prev']) * 100:+.0f}bp), 2s10s {(t['y10'] - t['y2']) * 100:+.0f}bp.")
    for s, name in FRED:
        x = D["fred"].get(s)
        if x:
            ch = pct(x["value"] / x["prev"] - 1, 2)
            L.append(f"- {name}, close {x['date']}: {x['value']:,.2f} ({ch} vs {x['prev_date']}).")
    for s, name in YAHOO:
        x = D["yahoo"].get(s)
        if x:
            ch = pct(x["price"] / x["prev"] - 1, 2) if x.get("prev") else "—"
            L.append(f"- {name}, at {utc(x['t'])}: {x['price']:,.2f} ({ch} vs prior close).")
    return L


# ---------------------------------------------------------------- Macro calendar (Forex Factory weekly feed)

def fed_calendar(days=7):
    """federalreserve.gov month pages. Each panel is time | event | day (the day comes after the event); times are ET."""
    ny, out = ZoneInfo("America/New_York"), []
    today = dt.datetime.now(ZoneInfo("America/New_York")).date()
    months = {(today.year, today.month), ((today + dt.timedelta(days=days)).year, (today + dt.timedelta(days=days)).month)}
    for y, m in sorted(months):
        name = dt.date(y, m, 1).strftime("%B").lower()
        t = fetch(f"https://www.federalreserve.gov/newsevents/{y}-{name}.htm")
        for p in t.split("panel-body")[1:]:
            col = {}
            for k, v in re.findall(r'<div class="col-xs-(\d+)">(.*?)</div>', p, re.S):
                col.setdefault(k, re.findall(r"<p[^>]*>(.*?)</p>", v, re.S))  # first row only: a panel can trail an empty one
            if not (col.get("2") and col.get("7") and col.get("3")):
                continue
            tm, ev, day = (re.sub(r"<[^>]+>", "", col[k][0]).strip() for k in ("2", "7", "3"))
            mt = re.match(r"(\d{1,2}):(\d{2}) ([ap])\.m\.", tm)
            if not mt or not day.isdigit():
                continue
            h = int(mt.group(1)) % 12 + (12 if mt.group(3) == "p" else 0)
            ts = dt.datetime(y, m, int(day), h, int(mt.group(2)), tzinfo=ny).timestamp()
            if NOW - 12 * 3600 <= ts <= NOW + days * 86400:
                out.append(dict(t=ts, title=html.unescape(ev)))
    return sorted(out, key=lambda x: x["t"])


def ff_events():
    """Forex Factory weekly feed. The JSON often 429s; the XML copy of the same feed is served from cache (times in GMT)."""
    try:
        return [dict(e, t=dt.datetime.fromisoformat(e["date"]).timestamp())
                for e in jget("https://nfs.faireconomy.media/ff_calendar_thisweek.json", tries=1)], "json"
    except Exception as e:  # noqa: BLE001
        json_err = e
    out = []
    for ev in ElementTree.fromstring(fetch("https://nfs.faireconomy.media/ff_calendar_thisweek.xml").encode("utf-8")).iter("event"):
        g = lambda k: (ev.findtext(k) or "").strip()  # noqa: E731
        tm = g("time")
        if not re.match(r"\d{1,2}:\d{2}[ap]m$", tm):  # "All Day" / "Tentative": keep at 00:00
            tm = "12:00am"
        t = dt.datetime.strptime(f"{g('date')} {tm}", "%m-%d-%Y %I:%M%p").replace(tzinfo=dt.timezone.utc).timestamp()
        out.append(dict(t=t, title=g("title"), country=g("country"), impact=g("impact"), forecast=g("forecast"),
                        previous=g("previous")))
    return out, f"xml (json failed: {json_err})"


def calendar():
    D = dict(ff=[], fed=[], errors=[])
    try:
        evs, D["ff_src"] = ff_events()
        D["ff"] = sorted((dict(t=e["t"], title=e["title"], impact=e["impact"], forecast=e.get("forecast"), previous=e.get("previous"))
                          for e in evs if e["country"] == "USD" and e["impact"] in ("High", "Medium") and e["t"] >= NOW - 12 * 3600),
                         key=lambda x: x["t"])
    except Exception as e:  # noqa: BLE001
        D["ff"] = None; D["errors"].append(f"Forex Factory feed: {e}")
    try:
        D["fed"] = fed_calendar()
    except Exception as e:  # noqa: BLE001
        D["fed"] = None; D["errors"].append(f"Fed calendar: {e}")
    return D


def render_calendar(D):
    L = ["**Data releases** (Forex Factory weekly feed, USD high/medium impact, from 12h ago; no actuals in the feed):"]
    if D["ff"] is not None:
        L += [f"- {utc(e['t'])} **{e['title']}** ({e['impact']})" + (f", cons. {e['forecast']}" if e["forecast"] else "")
              + (f", prev. {e['previous']}" if e["previous"] else "") for e in D["ff"]] or [
            "- None left this week. The feed covers Sun–Sat only, so on a Saturday next week's releases are **MISSING**."]
    else:
        L.append("- **MISSING**: Forex Factory JSON and XML both failed (see Missing below). This is not \"no releases\".")
    L.append("\n**Fed** (federalreserve.gov, next 7 days):")
    if D["fed"] is not None:
        L += [f"- {utc(e['t'])} {e['title']}" for e in D["fed"]] or ["- None listed."]
    else:
        L.append("- **MISSING**: federalreserve.gov failed (see Missing below).")
    return L


# ---------------------------------------------------------------- Token unlocks (CoinGecko unlocks page, secondary)

def unlocks(days=7):
    t = fetch("https://www.coingecko.com/en/highlights/incoming-token-unlocks")
    out = []
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>", t, re.S):
        ts = re.search(r'data-sort="(\d{10})"', r)
        c = cells(r)
        if not ts or len(c) < 12:
            continue
        m = re.search(r"([\d.,]+[KMB]?) (\S+) \$([\d,.]+[KMB]?) \(([\d.-]+|-)%\)", c[-2])
        if not m:
            continue
        usd = m.group(3).replace(",", "")
        usd = float(usd[:-1]) * {"K": 1e3, "M": 1e6, "B": 1e9}[usd[-1]] if usd[-1] in "KMB" else float(usd)
        if int(ts.group(1)) - NOW <= days * 86400:
            out.append(dict(t=int(ts.group(1)), coin=c[2], usd=usd, pct_mcap=None if m.group(4) == "-" else float(m.group(4)),
                            mcap=c[8]))
    return out


def render_unlocks(D):
    big = [u for u in D if u["usd"] >= 5e6 or (u["pct_mcap"] or 0) >= 5 or u["coin"].split()[-1] in COINS]
    L = [f"- {utc(u['t'])} **{u['coin']}**: ${u['usd'] / 1e6:,.1f}m" + (f" ({u['pct_mcap']:.1f}% of mcap)" if u["pct_mcap"] is not None else "")
         for u in sorted(big, key=lambda x: x["t"])]
    return (L or ["- None ≥ $5m or ≥ 5% of mcap in the next 7 days."]) + [
        "", f"CoinGecko unlocks page (secondary source, cliff unlocks only, {len(D)} rows in the next 7 days). "
            "Primary-source check (Tokenomist) is MISSING: it needs a paid key (THE-425)."] + (
        ["**The page shows 50 rows at most and hit that cap, so later unlocks this week may be cut off.**"] if len(D) >= 50 else [])


# ---------------------------------------------------------------- On-chain (Coin Metrics community, mempool.space)

def onchain():
    res = dict(errors=[])
    for a in ("btc", "eth"):  # one asset per call: a multi-asset page fills up with the first asset's rows
        try:
            r = jget(f"https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets={a}"
                     "&metrics=CapMVRVCur,FlowInExNtv,FlowOutExNtv,AdrActCnt&frequency=1d&page_size=1&paging_from=end")["data"][-1]
            res[a.upper()] = dict(day=r["time"][:10], mvrv=float(r["CapMVRVCur"]), active=int(float(r["AdrActCnt"])),
                                  net_ex=float(r["FlowInExNtv"]) - float(r["FlowOutExNtv"]), flash=r.get("FlowInExNtv-status") == "flash")
        except Exception as e:  # noqa: BLE001
            res["errors"].append(f"Coin Metrics {a}: {e}")
    try:
        res["fees"] = jget("https://mempool.space/api/v1/fees/recommended")
    except Exception as e:  # noqa: BLE001
        res["fees"] = dict(error=str(e))
    return res


def render_onchain(D):
    L = []
    for a in ("BTC", "ETH"):
        x = D.get(a)
        if x:
            L.append(f"- {a}, day {x['day']}: MVRV {x['mvrv']:.2f}, net exchange flow {x['net_ex']:+,.0f} {a} "
                     f"({'in' if x['net_ex'] > 0 else 'out'}{', flash estimate' if x['flash'] else ''}), active addresses {x['active']:,}.")
    f = D.get("fees", {})
    if "fastestFee" in f:
        L.append(f"- BTC mempool fees: fastest {f['fastestFee']} / hour {f['hourFee']} sat/vB.")
    L.append("\nCoin Metrics community API (1-day lag).")
    return L


# ---------------------------------------------------------------- Headlines (RSS)

RSS = [("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"), ("The Block", "https://www.theblock.co/rss.xml"),
       ("Cointelegraph", "https://cointelegraph.com/rss")]


def news(hours=18, n=8):  # 18h: the 06:00Z brief reads back to 14:00Z the day before
    out, errs = {}, []
    for name, url in RSS:
        try:
            root = ElementTree.fromstring(fetch(url).encode())
            items = []
            for it in root.iter("item"):
                ts = dt.datetime.strptime(it.findtext("pubDate").strip()[:25].strip(), "%a, %d %b %Y %H:%M:%S").replace(
                    tzinfo=dt.timezone.utc).timestamp()
                if ts >= NOW - hours * 3600:
                    items.append(dict(t=ts, title=(it.findtext("title") or "").strip(), link=(it.findtext("link") or "").strip()))
            out[name] = sorted(items, key=lambda x: -x["t"])[:n]
        except Exception as e:  # noqa: BLE001
            errs.append(f"{name}: {e}")
    if errs:
        out["_errors"] = errs
    return out


def render_news(D):
    L = []
    for name, items in D.items():
        if name == "_errors":
            continue
        L.append(f"- **{name}** ({len(items)} in 18h): " + (" · ".join(f"{utc(i['t'])[11:]} {i['title']}" for i in items) or "none"))
    return L


# ---------------------------------------------------------------- main

SECTIONS = [("etf", "Spot ETF flows", etf, render_etf), ("options", "Options", options, render_options),
            ("perps", "Perps across venues", perps, render_perps), ("cross", "Cross-asset and rates", cross, render_cross),
            ("calendar", "Macro calendar", calendar, render_calendar), ("unlocks", "Token unlocks, next 7 days", unlocks, render_unlocks),
            ("onchain", "On-chain", onchain, render_onchain), ("news", "Headlines", news, render_news)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    ap.add_argument("--only", help="comma list of: " + ",".join(s[0] for s in SECTIONS))
    a = ap.parse_args()
    only = set(a.only.split(",")) if a.only else None
    data, missing, L = dict(t=NOW), [], [f"## Desk inputs, pulled {utc(NOW)}"]
    for key, title, fn, render in SECTIONS:
        if only and key not in only:
            continue
        L += ["", f"### {title}"]
        try:
            data[key] = fn()
            L += render(data[key])
            for e in (data[key].get("errors", []) + data[key].get("_errors", [])) if isinstance(data[key], dict) else []:
                missing.append(f"{title}: {e}")
        except Exception as e:  # noqa: BLE001
            data[key] = None
            L.append(f"- **MISSING**: {e}")
            missing.append(f"{title}: {e}")
    L += ["", "### Missing this pull"] + ([f"- {m}" for m in missing] or ["- Nothing."])
    print("\n".join(L))
    if a.json:
        json.dump(dict(data, missing=missing), open(a.json, "w"), indent=1, default=str)


if __name__ == "__main__":
    sys.exit(main())
