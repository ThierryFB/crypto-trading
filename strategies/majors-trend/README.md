# Majors Trend

Desk strategy for the two most liquid crypto assets. Hold BTC and ETH spot (vs USDC) only while each is above its 150-day average, sized so neither slot runs hotter than 50% annualised volatility; otherwise sit in USDC. The aim is most of the upside of holding majors without the -80% to -90% drawdowns.

**Phase:** definition. No capital, no mandate, no trades. Paper waits on the merged risk policy and the `order-placement` skill.

## Files

| File | Owner | What it holds |
|---|---|---|
| `strategy.md` | Leo (Majors Trader) | Universe, signal, sizing, cadence, execution |
| `backtest.md` | Leo (Majors Trader) | Method and results, 2018-01 → now, net of fees |
| `backtest/` | Leo (Majors Trader) | `fetch.py` (price data), `backtest.py` (simulation), `prices.csv`, `results.txt` |
| `risk-policy.md` (drafted in PR #7) | Ingrid (Risk Manager), with Nadia's capital and promotion criteria | Limits, capital, kill switch, paper→live promotion criteria |

## Change rules

Every change goes through a PR. Nadia merges `strategy.md` and `backtest.md`. `risk-policy.md` merges only with Ingrid's and David's approval, and once live, Thierry's confirmation as well.
