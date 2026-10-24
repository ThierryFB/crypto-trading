"""Fetch daily BTC-USD and ETH-USD candles from Coinbase Exchange's public API.

Writes prices.csv (date, btc_open, btc_close, eth_open, eth_close), UTC days.
Coinbase USD is used as a proxy for USDC: the books share liquidity and the
USD/USDC basis is negligible next to the fee assumption.

    python3 fetch.py [end-date YYYY-MM-DD]   # default: yesterday (last closed day)
"""
import csv, datetime as dt, json, os, sys, time, urllib.request

START = dt.date(2017, 1, 1)  # warm-up for the longest lookback before 2018-01-01
API = "https://api.exchange.coinbase.com/products/{}/candles?granularity=86400&start={}&end={}"


def candles(product, start, end):
    out, day = {}, start
    while day <= end:
        chunk_end = min(day + dt.timedelta(days=299), end)
        url = API.format(product, f"{day}T00:00:00Z", f"{chunk_end}T00:00:00Z")
        req = urllib.request.Request(url, headers={"User-Agent": "majors-trend-backtest"})
        for row in json.load(urllib.request.urlopen(req, timeout=30)):
            t, low, high, opn, close, vol = row
            out[dt.datetime.fromtimestamp(t, dt.timezone.utc).date()] = (opn, close)
        day = chunk_end + dt.timedelta(days=1)
        time.sleep(0.4)
    return out


def main():
    end = (dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1
           else dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1))
    btc, eth = candles("BTC-USD", START, end), candles("ETH-USD", START, end)
    days = sorted(set(btc) & set(eth))
    missing = (days[-1] - days[0]).days + 1 - len(days)
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prices.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "btc_open", "btc_close", "eth_open", "eth_close"])
        for d in days:
            w.writerow([d, *btc[d], *eth[d]])
    print(f"{len(days)} days {days[0]}..{days[-1]}, {missing} missing -> {path}")


if __name__ == "__main__":
    main()
