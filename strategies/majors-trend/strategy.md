# Strategy — Majors Trend

Owner: Leo (Majors Trader). Merged by Nadia. Capital, limits and the kill switch live in `risk-policy.md`; where the two disagree, the risk policy wins.

**One line:** each of BTC and ETH is held only while its daily close is above its 150-day simple moving average, at a weight scaled down when its volatility is above 50%; everything else is in USDC.

## 1. Universe

- **BTC/USDC and ETH/USDC spot.** Nothing else.
- No leverage, no margin, no perps, no lending or staking of the sleeve.
- The sleeve's quote currency is USDC. Uninvested capital stays in USDC on the venue.

## 2. Trend signal

**Rule:** an asset is *on-trend* when its UTC daily close is strictly above the simple average of its last 150 daily closes (today's included). Otherwise it is *off-trend*.

Why this rule:
- **One parameter.** A close-vs-SMA filter has a single lookback; a breakout system needs separate entry and exit windows. Fewer knobs, less room to fit noise.
- **150 days**, chosen before running any backtest: the middle of the 100–200-day band set in THE-296, so neighbours on both sides can be tested without leaving it. It is the same length for both assets.
- **The backtest does not change the choice.** SMA125 scored slightly better (`backtest.md` §3). The chosen value stays; switching to the best neighbour would be the parameter shopping we said we wouldn't do. The result that matters is that every length from 100 to 200 beats buy-and-hold on drawdown and risk-adjusted return.

## 3. Sizing

The sleeve is split into two **slots**, BTC and ETH, each with a budget of 50% of sleeve NAV.

- **Off-trend slot:** 0% in the asset; its budget is in USDC.
- **On-trend slot:** target weight = `50% × min(1, 50% ÷ σ)`, where σ is the asset's realised volatility, i.e. the standard deviation of its last 60 daily log returns × √365. A slot never exceeds 50% of NAV, so the sleeve never exceeds 100%.
- **One or both off-trend:** the off-trend slot's budget stays in USDC. It is **not** moved to the other asset. One on-trend asset means at most 50% invested; both off means 100% USDC.
- Weights are measured on sleeve NAV (both positions plus USDC) at the time of the trade, so gains in one slot are shared with the other at its next entry or resize.

## 4. Cadence

- **Check daily** just after 00:00 UTC, using the daily candle that has just closed (the previous UTC day's). A check is named by that candle: "Monday's check" reads Monday's candle and runs just after 00:00 UTC Tuesday.
- **Flips act at once:** off→on buys the slot to target; on→off sells the slot to zero. The orders go out in the same check.
- **Resizes weekly:** at Monday's check, an on-trend slot whose held weight differs from target by more than **5 percentage points** of NAV is traded back to target. There are no resizes at other checks, and none inside the band. (`backtest.py` does the same: it decides on Monday's close and trades at Tuesday's open.)
- No intraday decisions. A move during the day does nothing until the next daily close.

## 5. Data sources

| Use | Source | Detail |
|---|---|---|
| **Primary** (signal, σ, NAV marks) | Coinbase Exchange public daily candles, `BTC-USD` and `ETH-USD` | The same feed as `backtest/fetch.py`, so paper trades the rule that was tested. UTC days. |
| **Cross-check** | Kraken public daily OHLC, `XBTUSDC` and `ETHUSDC` | UTC days. On 2026-10-20 → 23 its closes were within 0.05% of the primary. |

- **The primary decides.** The SMA150, σ and on/off verdict are computed only from the primary. The cross-check is used only to validate that close.
- **If they disagree** by more than **1%** on an asset's close, or the primary has no closed candle for either asset at the check, then no trade is placed that day for either asset. I log a no-trade with both prices and retry at the next check. Two such checks in a row is Ingrid's halt (risk policy O3).
- Within 1%, the primary's verdict stands, even if the cross-check's close would land on the other side of the SMA.

**Shared BTC regime flag** (desk C3, also used by Alt Momentum)

- **Definition:** `on` when BTC's primary daily close is strictly above its SMA150, otherwise `off`. This is exactly the BTC trend signal in §2, with no vol scaling. It is `unknown` when the data check above fails for BTC.
- **Computed once a day** at the daily check, from the primary source and validated against the cross-check as above. Alt Momentum reads this flag; it does not compute its own.
- **Published by 00:30 UTC** for the candle that just closed. It goes out as a comment on a standing `BTC regime flag` issue in this project, with the date, the primary and cross-check BTC closes, SMA150 and the flag. A flag not posted by 01:00 UTC counts as missing (risk policy O4).
- An `unknown` flag means neither strategy acts on regime that day.

## 6. Execution

- **Order type:** marketable limit, immediate-or-cancel, priced at the touch ± 0.1% (buy above the ask, sell below the bid). If the fill is partial, the remainder is re-tried at the next check; nothing chases price in between.
- **Cost assumption:** 0.1% per side, fee plus slippage combined, until a venue is chosen. The backtest also shows 0.2% and 0.5%.
- Orders are placed and logged only through the `order-placement` skill, and each entry and exit is recorded in the Crypto Book (`book` = this project's name).

## 7. Every decision is logged with

Strategy and phase, the primary and cross-check closes, the SMA150 for the asset, σ and the target weight, the trade (or the deliberate no-trade), and what would invalidate it (for a trend entry: a daily close back below the SMA150).

## 8. What would kill it

- **Before paper:** failing to beat buy-and-hold BTC, ETH and 50/50 on max drawdown *and* on Sharpe/Sortino in `backtest.md`. (It passes: §1 of `backtest.md`.)
- **In paper and live:** the promotion and kill criteria in `risk-policy.md`. As evidence for changing this file, I will watch for a drawdown deeper than the backtest's -34% or a losing streak longer than 6 round trips in one asset. Either one means the backtest no longer describes the market, and I'll take it to Nadia as a PR with the numbers.
