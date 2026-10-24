# Alt Momentum: strategy definition

**Owner:** Leo (Majors Trader). **Phase:** definition. **Status: draft. The backtest fails both kill criteria (see `backtest.md`). This file records the rule that was tested. It is not a request to paper-trade it.**

Spot only, long only, no leverage, no perps. Quote currency USDC (USDT where a coin has no USDC pair on the venue). The risk limits are in `risk-policy.md` (Ingrid, PR #8) and override anything here.

## 1. Universe

Re-selected on the **first weekly rebalance of each calendar month**. Between refreshes the list is fixed. A member that can no longer be traded (delisted, deposits or withdrawals suspended, or a venue Monitoring tag) leaves at once.

A coin is eligible when it meets all of these:

1. **Not BTC or ETH.** Majors Trend trades those. A test version that included them did worse (`backtest.md`).
2. **Not pegged or derivative:** no stablecoins (including yield-bearing and depegged ones such as sUSDe or USTC), no gold or other commodity tokens, and no wrapped, bridged or liquid-staking tokens (WBTC, stETH, BTCB, cbBTC and similar). The backtest checks this from data: a coin is excluded when ≥80% of its last 12 weekly closes are within $0.90–1.10, or within 5% of a larger coin's price, and a short symbol list catches the rest.
3. **Seasoned:** at least 12 weeks of price history.
4. **Liquid:** median 24h spot volume over the last 4 weeks ≥ **$20M**. In live and paper trading this is measured on the trading venue's own USDC/USDT pairs, plus a ±2% depth of at least 20× the planned order size. The backtest only had CMC aggregate volume, which is a looser test.

From the coins that pass, the **20 largest by market cap** form the universe. Ranks 1–10 are cost tier 1 and ranks 11–20 are cost tier 2 (§5).

The current list, each coin's sector tag (for Ingrid's L4 sector cap) and the price sources are in `universe.md`. It is regenerated at every refresh. A coin without a sector tag isn't ranked.

## 2. Ranking and holdings

- **Score:** 4-week total return, weekly close to weekly close, on the venue's own daily candles. The CMC close is used as a cross-check (`universe.md`, Price sources).
- **Hold the top 4**, equal weight, at 25% of the strategy's capital each.
- **Buffer:** a coin already held stays while it ranks in the top 6. Freed slots go to the best-ranked coin not already held. This was set before the backtest to cut turnover; without it, results are much worse.
- **Data guard:** a coin whose 4-week return is 10× or more is not ranked until the move is confirmed on the venue. Data glitches look exactly like momentum.

## 3. Regime filter

The strategy holds coins only when **BTC's daily close is above its 150-day simple moving average**. That is the Majors Trend rule as drafted in THE-296. It is checked at the weekly rebalance. When the filter is off, the whole strategy goes to USDC. If Majors Trend's merged rule changes, this one follows it.

The same rule is used so the two strategies are risk-on and risk-off together, and their combined exposure is easy to reason about. The cost is that the filter does nothing to spread risk between the two. Other SMA lengths are in `backtest.md`, as sensitivity results only.

## 4. Cadence and orders

- **Rebalance weekly** at the Sunday UTC daily close (end of Sunday). The backtest's CMC snapshots match that close. Orders go in within the next hour.
- **Each week:** sell the coins that leave and buy the coins that enter. Coins that stay are not traded, and their weights drift.
- **Monthly** (at the universe refresh) and whenever the strategy re-enters from cash: reset every holding to 25%.
- **Order type:** limit at the touch or one tick inside, re-priced every 5 minutes. If an order isn't filled within 30 minutes, it crosses the spread up to the tier slippage. Never a market order larger than 1% of the ±2% depth.
- Every decision is logged through the order-placement skill. That includes a week where the book doesn't change.

## 5. Costs assumed

| Tier | Fee per side | Slippage per side | Total per side |
|---|---|---|---|
| 1 (universe ranks 1–10) | 0.10% | 0.10% | 0.20% |
| 2 (ranks 11–20) | 0.10% | 0.25% | 0.35% |

The backtest averages about 92 orders a year at these rates, a cost drag of **5.4% of capital per year**. At 2× these costs, CAGR falls from 26% to 19%.

## 6. Capital and phase

Draft allocation: **$250 of the $1,000 sleeve, paper** (Nadia; final figure in `risk-policy.md`). At $250, a position is about $62, which is close to the minimum order size on most venues. Monthly reweighting trades will often be too small to place. When they are, they are skipped and logged.

## 7. Thesis and what kills it

**Thesis:** among liquid alts, coins that outperformed over the last month keep outperforming for a few weeks while BTC is in an uptrend. That edge should beat holding the same coins equal-weight, and add something to Majors Trend after costs.

**Killed if** (from THE-297) it shows no improvement on Majors Trend after costs, or momentum-crash drawdowns beyond Ingrid's limits. On the 2019–2026 backtest, it fails both, and it also fails to beat the equal-weight control.
