# Desk inputs

One fixed pull of the market data the desk reads on every wake and brief (THE-425). It covers every strategy, so it lives here and not in a strategy folder. **Data inputs only:** no trading logic, no limits, nothing a runner gate reads. The Majors Discretionary runner's own `inputs.py` block (prices, 8h levels, Bybit perps, Fear & Greed, stablecoins) is unchanged; this pull is the context around it.

```
python3 strategies/desk-inputs/desk_inputs.py                  # markdown block, paste into the wake log or brief
python3 strategies/desk-inputs/desk_inputs.py --json OUT.json  # also the raw data
python3 strategies/desk-inputs/desk_inputs.py --only etf,options
```

Stdlib only, keyless, about 25 s. Each source fails on its own. A failure prints as a line under **Missing this pull**, with the reason, and nothing is filled in. Every figure shows the day or time it covers.

| Section | Source | Notes |
|---|---|---|
| Spot ETF flows | Farside BTC / ETH / SOL tables | Last 5 trading days, US$m, plus the biggest 3 funds of the last day. Farside only 403s the default curl/Python UA; a browser UA reads it. Funds not yet reported for a day are listed ("not yet in: IBIT"), so a partial total is visible. |
| Options | Deribit public API | DVOL and its 24h change; ATM IV, 25-delta risk reversal (Black-76 deltas at mark IV) and the expiry nearest 30 days; put/call OI over all expiries. BTC and ETH. |
| Perps across venues | Bybit, Binance and OKX public APIs | OI summed over the 3 venues (USD) and its 24h change, per-venue OI change and funding, for the 6 majors. Liquidations: OKX only, over whatever window its last 100 orders cover (often about 1h). |
| Cross-asset and rates | Treasury.gov yield curve CSV, FRED CSV (no key), Yahoo chart API | 2y, 10y, 2s10s; S&P 500, Nasdaq, VIX, broad dollar (weekly lag), 10y. ES, NQ, DXY and gold come from Yahoo, which rate-limits this IP (429), so they're usually missing. |
| Macro calendar | Forex Factory weekly JSON; federalreserve.gov month pages | USD high/medium data releases with consensus and prior; Fed speeches, minutes, Beige Book, FOMC over the next 7 days, in UTC. The FF feed is Sun–Sat only, so on Saturday next week's data releases are missing. |
| Token unlocks | CoinGecko unlocks page | Cliff unlocks in the next 7 days, ≥ $5m or ≥ 5% of market cap, plus any major. A secondary source; no primary (Tokenomist) check. |
| On-chain | Coin Metrics community API; mempool.space | BTC and ETH MVRV, net exchange flow (flash estimate), active addresses (1-day lag); BTC fees. |
| Headlines | CoinDesk, The Block, Cointelegraph RSS | Last 12h, 8 per feed. |

**Not covered (needs a key; asked on THE-425):** aggregate cross-exchange liquidations and long/short (Coinalyze, free key), intraday index futures and the dollar (Twelve Data, free key, through ETF and FX proxies), primary-source unlocks (Tokenomist, paid).
