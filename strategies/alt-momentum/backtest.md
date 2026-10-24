# Alt Momentum: backtest, 2019-01 → 2026-10

**Verdict: kill.** After costs, Alt Momentum returns far less than Majors Trend (CAGR +26% vs +47%) with a much deeper drawdown (−72% vs −29%). It doesn't beat the same alts held equal-weight, so the momentum ranking adds nothing. Adding it to Majors Trend at the draft 450:250 split lowers Sharpe from 1.25 to 1.07 and deepens the drawdown from −29% to −48%. No tested setting fixes the drawdown: every one is −66% or worse. Its correlation with Majors Trend is 0.50, so it isn't a noisy copy. It is a worse, different bet: alt beta.

All numbers come from `backtest/results.txt`, produced by `python3 backtest/report.py`.

## Method

- **Data:** CoinMarketCap weekly historical listings (the THE-271 cache). Each snapshot lists every coin CMC tracked on that date, including coins that later collapsed or were delisted. Of the 86 coins that were ever in the universe, 52 are now more than 90% below their post-2019 high or no longer listed (FTT, LUNC, HEX, OMG, WAVES, EOS, …). So the backtest has no survivorship bias.
- **Period:** 2019-01-06 → 2026-10-11, 405 weekly steps. Signals and fills both use the Sunday close. The regime filter uses BTC daily closes from Majors Trend's `prices.csv`.
- **Rules:** exactly as in `strategy.md`: universe refreshed monthly (15 coins at the thinnest point in early 2019, 20 most of the time), 4-week return, top 4 with a ±2 buffer, BTC > SMA150, weekly exits and entries, monthly reweighting.
- **Costs:** fee 0.10% plus slippage of 0.10% (tier 1) or 0.25% (tier 2), per side, on every traded dollar. Cash earns 0%.
- **Dead coins:** a holding without a price at the next snapshot is valued at its next price within 4 weeks. If there is none, it is a −100% loss.
- **Benchmarks:** BTC buy-and-hold, and Majors Trend's own `backtest.py` at its draft settings (SMA150, 50% vol target). The Majors Trend daily equity is sampled at the same Sunday closes, so the two are compared week for week. **Control:** hold all universe coins equal-weight, with the same regime filter. If momentum has an edge, it should beat this.
- **Parameters:** the base rule was fixed before the first run. The grids below show the settings either side of it. I didn't pick the best one.

## Headline

| Run | End value | CAGR | Max DD (weekly) | Sharpe | Sortino | Vol | Worst week | Orders / yr | Cost drag / yr | Time invested |
|---|---|---|---|---|---|---|---|---|---|---|
| **Alt Momentum (base)** | 5.92x | +25.7% | −72% | 0.64 | 1.22 | 71% | −27% | 92 | 5.4% | 58% |
| Control: equal-weight whole universe, same regime filter | 7.59x | +29.8% | −64% | 0.73 | 1.25 | 59% | −26% | 114 | 1.7% | 58% |
| Majors Trend draft (SMA150, 50% vol target) | 20.25x | +47.3% | −29% | 1.25 | 2.43 | 36% | −14% | – | – | – |
| Buy & hold BTC | 20.49x | +47.6% | −75% | 0.96 | 1.53 | 59% | −33% | – | – | – |

## Against Majors Trend

| Pair (weekly returns) | Correlation | Beta of Alt Momentum to it |
|---|---|---|
| Alt Momentum vs Majors Trend, all weeks | 0.50 | 0.99 |
| Alt Momentum vs Majors Trend, weeks Alt Momentum is invested | 0.52 | 1.06 |
| Alt Momentum vs BTC | 0.40 | 0.49 |
| Majors Trend vs BTC | 0.76 | – |

Combined at 450:250, rebalanced weekly at no extra cost: 17.25x, +44.3% CAGR, −48% max DD, Sharpe 1.07. Majors Trend alone: 20.25x, +47.3%, −29%, 1.25. The diversification doesn't pay for the drawdown it adds.

## Calendar years

| Year | Alt Momentum | EW-universe control | Majors Trend | BTC |
|---|---|---|---|---|
| 2019 | −48% | −28% | +56% | +82% |
| 2020 | +87% | +54% | +145% | +254% |
| 2021 | +761% | +598% | +76% | +93% |
| 2022 | −13% | −13% | −12% | −67% |
| 2023 | +42% | +24% | +78% | +151% |
| 2024 | −46% | +11% | +70% | +121% |
| 2025 | −12% | −34% | +1% | −6% |
| 2026 (to 10-11) | +19% | +24% | +12% | −5% |

Nearly all of the return comes from 2021. In 2019 and 2024, BTC was in an uptrend, so the filter kept the strategy invested, but alts bled against BTC, and momentum kept buying the coins that were about to reverse.

## Drawdowns (the momentum-crash test)

| Drawdown | Peak | Trough | Recovered |
|---|---|---|---|
| −72% | 2023-12-24 | 2024-11-03 | not yet |
| −72% | 2019-06-23 | 2020-05-10 | 2021-01-31 |
| −52% | 2021-11-21 | 2023-06-18 | 2023-12-10 |

The strategy spent 179 of 406 weeks at or below 60% of its high-water mark. Ingrid's limits for this strategy aren't drafted yet (THE-298). For reference, the Micro-cap Convex draft halts at NAV ≤ 60% of HWM (D2). Under that rule this strategy would have halted in 2019, and again in 2024. Weekly closes understate drawdowns, so the intraweek troughs were deeper.

## Sensitivity: lookback × holdings (CAGR / max DD / Sharpe)

| Lookback \ top K | 3 | 4 | 5 |
|---|---|---|---|
| 2 weeks | +37% / −68% / 0.79 | +45% / −67% / 0.90 | +41% / −66% / 0.86 |
| 4 weeks (base) | +20% / −73% / 0.56 | **+26% / −72% / 0.64** | +31% / −72% / 0.71 |
| 8 weeks | −3% / −80% / 0.31 | +27% / −75% / 0.67 | +25% / −76% / 0.65 |
| 12 weeks | +31% / −75% / 0.66 | +37% / −70% / 0.75 | +42% / −68% / 0.80 |

The results jump around from cell to cell, with no smooth pattern: they look like noise, not an edge. The best cell (2 weeks, top 4) is still below Majors Trend on Sharpe (0.90 vs 1.25), and its drawdown is more than twice as deep (−67%).

## Regime filter

| Filter | End value | CAGR | Max DD | Sharpe | Orders / yr | Cost drag / yr |
|---|---|---|---|---|---|---|
| BTC > SMA150 (base, Majors Trend rule) | 5.92x | +25.7% | −72% | 0.64 | 92 | 5.4% |
| BTC > SMA100 | 13.41x | +39.7% | −74% | 0.79 | 92 | 5.5% |
| BTC > SMA200 | 2.63x | +13.3% | −78% | 0.51 | 91 | 5.4% |
| No filter | 2.10x | +10.0% | −91% | 0.53 | 143 | 8.3% |

The filter is necessary: without it, the drawdown is −91%. But it isn't enough, because a BTC filter doesn't protect against alts falling while BTC rises. Moving the SMA by ±50 days changes the final value by 5×. That's another sign the result is fragile.

## Costs

| Costs | End value | CAGR | Max DD | Sharpe | Cost drag / yr |
|---|---|---|---|---|---|
| None | 9.00x | +32.7% | −71% | 0.72 | 0.0% |
| Base | 5.92x | +25.7% | −72% | 0.64 | 5.4% |
| 2× base | 3.89x | +19.1% | −75% | 0.57 | 10.8% |
| 3× base | 2.55x | +12.8% | −78% | 0.49 | 16.2% |

Cost drag is the central risk, as the brief expected. Even with no costs, the strategy is still well behind Majors Trend.

## Other construction choices

| Variant | End value | CAGR | Max DD | Sharpe | Orders / yr |
|---|---|---|---|---|---|
| No buffer (strict top 4 every week) | 2.91x | +14.8% | −72% | 0.52 | 115 |
| Reset to equal weight every week | 6.60x | +27.5% | −72% | 0.66 | 109 |
| Only hold coins with a positive 4-week return | 7.11x | +28.8% | −76% | 0.67 | 91 |
| Universe includes BTC and ETH | 4.83x | +22.5% | −73% | 0.59 | 92 |

## Limitations

- **Weekly data only.** Drawdowns are measured on weekly closes, and fills are at the same close that produced the signal. Both make the strategy look better than it would trade.
- **CMC volume overstates liquidity**, especially for 2019 (wash trading), and the backtest assumes every universe coin was tradable on one venue. Live costs for tier-2 coins are likely higher than 0.35% per side, which makes the results worse.
- **The Majors Trend comparison uses its draft rule** (THE-296, not merged). If that rule changes, rerun `report.py`. At any SMA from 100 to 200 days, Majors Trend has a Sharpe of 0.97–1.20 and a drawdown no worse than −43%, so the verdict holds across its own range.
- **Glitch guard:** one ranking was skipped because of a ≥10× four-week move.

## Reproduce

```
cd strategies/alt-momentum/backtest
CMC_SNAP_DIR=<THE-271 snapshot cache> MT_DIR=../../majors-trend/backtest python3 report.py > results.txt
```

`MT_DIR` needs Majors Trend's `prices.csv` and `backtest.py` (its PR). The CMC cache isn't in the repo. The source is listed in `data.py`.
