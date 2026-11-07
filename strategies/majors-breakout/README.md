# Majors Breakout

Desk strategy for Thierry's "active" paper sleeve (THE-319). An 8h Donchian breakout, long or cash, on BTC, ETH, SOL, XRP, DOGE and ADA against USDT on Bybit spot. About 1.2 round trips a week in the backtest; three decision points a day.

**Phase:** definition. Paper on Bybit Demo starts once `strategy.md` and `risk-policy.md` are merged and the runner is ready. No live capital.

## Files

| File | Owner | What it holds |
|---|---|---|
| `strategy.md` | Leo (Majors Trader) | Universe, candles, signals, sizing, cadence, overlay, execution |
| `backtest/` | Nadia (Head of Trading) | `fetch.py` (Bybit 4h klines), `bt.py` (simulation), `bt2.py` (variants), `results.txt` |
| `risk-policy.md` (to come) | Ingrid (Risk Manager), with Nadia's capital and promotion criteria | Limits, capital, halt rule, paper→live promotion criteria |
| `runner/` (to come, separate PR) | Leo (Majors Trader) | Order placement for this strategy only: signals, sleeve ledger, Bybit Demo orders, decision log, Crypto Book records, shadow book |

To reproduce the backtest: `cd backtest && python3 fetch.py BTCUSDT ETHUSDT SOLUSDT XRPUSDT DOGEUSDT ADAUSDT && python3 bt.py` (the CSVs are not committed). The proposal's numbers are the "No BTC regime filter" row.

## Change rules

Every change goes through a PR. Nadia merges `strategy.md` and the runner. `risk-policy.md` merges only with Ingrid's and David's approval, and once live, Thierry's confirmation as well.
