# Backtest — Majors Trend

**Result: it passes the kill test.** From 2018-01-01 to 2026-10-23, net of 0.1% per side, the strategy as written in `strategy.md` returned 17.2x (+38% CAGR) with a -34% max drawdown and a Sharpe of 1.12. Buy-and-hold 50/50 returned 4.5x with a -88% drawdown and a Sharpe of 0.60. The result holds for every SMA length from 100 to 200, for vol targets of 40–60%, at up to 0.5% per side, and in each of three sub-periods.

## Method

- **Data:** Coinbase Exchange daily candles for BTC-USD and ETH-USD, UTC days, 2017-01-01 → 2026-10-23 (3,583 days, no gaps). The 2017 data is only used to warm up the indicators. USD is a proxy for USDC. `backtest/fetch.py` downloads it to `backtest/prices.csv`.
- **Simulation** (`backtest/backtest.py`, Python standard library only): the signal and target weights are computed on day *t*'s close and traded at day *t+1*'s open, so no decision uses a price it couldn't have seen. Every traded dollar pays 0.1%. Flips trade at once; resizes happen only on Mondays and only when the slot is more than 5 pp off target (`strategy.md` §3–4). The sleeve starts in USDC on 2018-01-01.
- **Benchmarks:** buy on 2018-01-01's open (paying 0.1%) and hold, with no rebalancing.
- **Metrics:** daily returns, 365 days a year, risk-free rate 0. Sortino uses the downside deviation of all days. Calmar = CAGR ÷ |max DD|. *Avg exposure* = average share of NAV in BTC+ETH. *Fills* = every order; *round trips* = entry to full exit in one asset. *Longest whipsaw* = most consecutive losing round trips in one asset, net of fees.
- **Check:** an independent minimal version (binary SMA150, 50% slots, no fees, close-to-close) gives 18.7x against the full model's 18.2x at zero cost. The small gap comes from vol scaling and next-open execution.
- Reproduce: `cd backtest && python3 backtest.py` (about 35 s). The output is `backtest/results.txt`.

## 1. Headline — strategy vs buy-and-hold

| Run | End value | CAGR | Max DD | Sharpe | Sortino | Calmar | Avg exposure | Fills / round trips | Win rate | Longest whipsaw BTC / ETH |
|---|---|---|---|---|---|---|---|---|---|---|
| **Majors Trend (SMA150, 50% vol target)** | 17.16x | +38.0% | -34.4% | 1.12 | 1.71 | 1.11 | 41% | 223 / 74 | 26% | 6 / 6 |
| Buy & hold BTC | 5.84x | +22.2% | -81.4% | 0.64 | 0.92 | 0.27 | 100% | 1 / – | – | – |
| Buy & hold ETH | 3.21x | +14.2% | -94.0% | 0.58 | 0.85 | 0.15 | 100% | 1 / – | – | – |
| Buy & hold 50/50 | 4.53x | +18.7% | -88.2% | 0.60 | 0.85 | 0.21 | 100% | 2 / – | – | – |

Kill test (`strategy.md` §7): drawdown -34% vs -81% / -94% / -88%; Sharpe 1.12 vs 0.58–0.64; Sortino 1.71 vs 0.85–0.92. **Passes on both counts against all three benchmarks.**

The strategy loses on most trades (26% win rate) and makes its money on a few long trends. Expect runs of up to 6 losing round trips in a row in one asset; that is the normal cost of the method.

## 2. SMA length — either side of 150 (vol target 50%)

| Run | End value | CAGR | Max DD | Sharpe | Sortino | Calmar | Avg exposure | Fills / round trips | Win rate | Longest whipsaw BTC / ETH |
|---|---|---|---|---|---|---|---|---|---|---|
| SMA100 | 14.41x | +35.3% | -39.4% | 1.06 | 1.62 | 0.90 | 42% | 312 / 121 | 18% | 10 / 12 |
| SMA125 | 21.43x | +41.6% | -32.1% | 1.20 | 1.83 | 1.29 | 41% | 221 / 73 | 25% | 6 / 8 |
| **SMA150** | 17.16x | +38.0% | -34.4% | 1.12 | 1.71 | 1.11 | 41% | 223 / 74 | 26% | 6 / 6 |
| SMA175 | 13.32x | +34.1% | -40.1% | 1.04 | 1.56 | 0.85 | 41% | 200 / 61 | 25% | 5 / 8 |
| SMA200 | 11.13x | +31.4% | -43.2% | 0.97 | 1.44 | 0.73 | 41% | 199 / 62 | 23% | 9 / 6 |

The results form a smooth plateau, not a spike: Sharpe ranges from 0.97 to 1.20 and max DD from -32% to -43% across the whole band. 125 is the best cell, but the rule stays at 150 (`strategy.md` §2). Shorter lookbacks cost more in whipsaws (SMA100: 121 round trips, 12 losses in a row on ETH).

## 3. Vol target — and no vol scaling (SMA150)

| Run | End value | CAGR | Max DD | Sharpe | Sortino | Calmar | Avg exposure | Fills / round trips | Win rate | Longest whipsaw BTC / ETH |
|---|---|---|---|---|---|---|---|---|---|---|
| target 40% | 11.85x | +32.4% | -28.0% | 1.13 | 1.74 | 1.16 | 35% | 222 / 74 | 26% | 6 / 6 |
| **target 50%** | 17.16x | +38.0% | -34.4% | 1.12 | 1.71 | 1.11 | 41% | 223 / 74 | 26% | 6 / 6 |
| target 60% | 21.69x | +41.8% | -38.4% | 1.11 | 1.69 | 1.09 | 45% | 216 / 74 | 26% | 6 / 6 |
| no vol scaling (flat 50%) | 18.35x | +39.1% | -57.2% | 0.93 | 1.37 | 0.68 | 52% | 186 / 74 | 24% | 6 / 6 |

The vol target is a risk dial: Sharpe barely moves, while drawdown and return scale together. Vol scaling earns its place by cutting max DD from -57% to -34% for about the same return.

### Grid — Sharpe / Max DD

| SMA \ vol target | 40% | 50% | 60% | flat |
|---|---|---|---|---|
| 100 | 1.06 / -33% | 1.06 / -39% | 1.05 / -45% | 0.92 / -55% |
| 125 | 1.20 / -27% | 1.20 / -32% | 1.20 / -36% | 1.02 / -52% |
| **150** | 1.13 / -28% | **1.12 / -34%** | 1.11 / -38% | 0.93 / -57% |
| 175 | 1.04 / -33% | 1.04 / -40% | 1.02 / -45% | 0.87 / -60% |
| 200 | 0.97 / -36% | 0.97 / -43% | 0.96 / -48% | 0.78 / -65% |

All 20 cells beat buy-and-hold 50/50 (Sharpe 0.60, DD -88%) on both measures.

## 4. Costs (SMA150, 50% vol target)

| Run | End value | CAGR | Max DD | Sharpe | Sortino | Calmar | Avg exposure | Fills / round trips | Win rate | Longest whipsaw BTC / ETH |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.0%/side | 18.16x | +38.9% | -33.9% | 1.14 | 1.74 | 1.15 | 41% | 223 / 74 | 26% | 6 / 6 |
| **0.1%/side** | 17.16x | +38.0% | -34.4% | 1.12 | 1.71 | 1.11 | 41% | 223 / 74 | 26% | 6 / 6 |
| 0.2%/side | 16.21x | +37.2% | -34.8% | 1.10 | 1.68 | 1.07 | 41% | 223 / 74 | 26% | 6 / 6 |
| 0.5%/side | 13.65x | +34.5% | -36.1% | 1.04 | 1.59 | 0.96 | 41% | 223 / 74 | 26% | 6 / 6 |

About 25 fills a year. Costs are not what decides this strategy.

## 5. Sub-periods

| Run | End value | CAGR | Max DD | Sharpe | Sortino | Calmar | Avg exposure | Fills / round trips | Win rate | Longest whipsaw BTC / ETH |
|---|---|---|---|---|---|---|---|---|---|---|
| 2018–2020 Majors Trend | 3.61x | +53.4% | -34.4% | 1.39 | 2.10 | 1.55 | 33% | 82 / 23 | 13% | 5 / 6 |
| 2018–2020 B&H 50/50 | 1.54x | +15.5% | -88.2% | 0.60 | 0.83 | 0.18 | 100% | 2 / – | – | – |
| 2021–2023 Majors Trend | 2.53x | +36.3% | -30.9% | 1.07 | 1.63 | 1.17 | 42% | 76 / 27 | 33% | 4 / 4 |
| 2021–2023 B&H 50/50 | 2.27x | +31.5% | -77.4% | 0.74 | 1.07 | 0.41 | 100% | 2 / – | – | – |
| 2024–2026-10 Majors Trend | 1.79x | +23.0% | -24.9% | 0.82 | 1.26 | 0.92 | 48% | 66 / 24 | 29% | 6 / 3 |
| 2024–2026-10 B&H 50/50 | 1.48x | +14.9% | -58.6% | 0.53 | 0.78 | 0.26 | 100% | 2 / – | – | – |

The strategy wins in every window, but the edge is shrinking: Sharpe went from 1.39 to 1.07 to 0.82.

## Caveats

- **The start date helps.** 2018-01 is just after the 2017 peak, so buy-and-hold starts in an -80% drawdown that the trend filter mostly sat out. The sub-period table is the fairer read.
- **Small sample.** 74 round trips over two and a half cycles. With a 26% win rate, most of the return comes from a handful of long trends. Paper results will be noisy for months.
- **Backtest fills.** Next-open fills at a flat 0.1% assume a $450 order moves nothing, which is reasonable for BTC/ETH. The 0.5% row is the stress case.
- **Current state (2026-10-23 close):** both assets are on-trend (BTC 81,078 vs SMA150 71,447; ETH 2,384 vs 2,120), each at the full 50% slot. A paper start today would open both.
