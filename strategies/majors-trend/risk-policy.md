# Risk policy

Owner: Ingrid, with capital and promotion criteria from Nadia. Merges only with Ingrid and David approving (and, once live, Thierry's confirmation).

**Phase: definition.** No capital, no mandate, no trades. The desk-wide limits in [`../desk-risk-policy.md`](../desk-risk-policy.md) also apply; the tighter limit wins.

## Limits and halt levels

*Drafted by Ingrid.* Written against the THE-296 spec (BTC and ETH spot vs USDC, slow trend signal, volatility-scaled sizing, cash when off-trend, 0.1% per side fee assumption). `strategy.md` and the backtest don't exist yet. Where a limit depends on them, it says so.

### Definitions

- **Sleeve:** the strategy's capital in USD (paper: the notional in Capital below).
- **NAV:** USDC plus BTC and ETH marked at mid on the venue where held, at the 00:00 UTC daily close.
- **HWM:** highest daily NAV since the first trade of the phase.
- **Impact:** for one order, the gap between the pre-trade mid and the worst price filled (paper: on the logged book snapshot).
- **Hard limit:** a breach halts. **Review trigger:** I write a note within 24 h; nothing halts.

### Position and exposure limits (hard)

| # | Limit | Level | Why |
|---|---|---|---|
| L1 | Instruments | **BTC, ETH and USDC spot only.** No leverage, margin, borrowing, derivatives, shorting, lending, staking or yield. Cash never negative. | The strategy's edge is stepping aside in bear markets. None of these help with that, and each adds a loss path. |
| L2 | Per-asset weight | Market value of BTC, and of ETH, each ≤ **60%** of NAV after any rebalance; ≤ **70%** at any daily close. Above 70%, a trim back to 60% happens at the next scheduled check. | Vol-scaling should normally keep weights below this. The cap stops one coin carrying the whole book when the other is off-trend and realised vol is unusually low (low vol often comes just before a large move). Not trimming above 70% is the breach. |
| L3 | Gross exposure | BTC + ETH ≤ **100%** of NAV | Follows from L1. Stated so a rounding or fee error that would take cash negative is a breach. |
| L4 | Book volatility | Ex-ante annualised volatility of the book, using 60-day realised vol and correlation at current weights, ≤ **40%** after any rebalance | BTC and ETH each run about 50–80% a year. This caps the book at roughly two-thirds of holding one coin outright. The vol target itself is Leo's choice in `strategy.md` and must sit at or below this. |
| L5 | Trend filter | A coin is held only while **its own** trend signal (as defined in `strategy.md`) is on. A coin whose signal turns off is sold at the next scheduled check, in full. No discretionary holding through an off signal, and no buying ahead of an on signal. | This rule is the strategy. Breaking it in either direction is the failure the backtest can't see. |
| L6 | Trading cadence | Signal and size changes only at the scheduled check in `strategy.md` (at most once a day). Outside it, only trims under L2 and halt or kill exits. | Stops intraday reactions to noise, which is where whipsaw costs come from. |
| L7 | Order size and impact | No order below the venue minimum or below **$10** (drift below this is left alone). Impact ≤ **0.3%** per order for normal trades, ≤ **1%** for halt or kill exits. Limit or marketable-limit orders only; no unprotected market orders. | BTC and ETH books are deep enough that a $50–300 order should fill within the spread. A fill beyond 0.3% means the venue or the data is wrong. The $10 floor stops rebalancing churn on trivial drifts. |

### Whipsaw and cost (review triggers)

- **Turnover:** more than **25** trades in any trailing 12 months, or more than **4** round trips in one coin in any 90 days. Expected is 5–15 a year.
- **Cost:** realised fees plus impact over the trailing 12 months above **1.5%** of average NAV.
- **Signal flips:** a coin's signal flips on and back off within 10 days, three times in a row. I compare that against the backtest's longest whipsaw streak.

A long whipsaw streak is the main way this strategy loses money while working as designed. These triggers make sure it's noticed and compared with the backtest, without halting a strategy that's doing what it should.

### Halt levels

A halt stops all buys and size increases. Sells the strategy requires (signal off, L2 trims) still run. Recorded as an open `HALT — Majors Trend` issue in this project. Only Nadia resumes, after my written review. Nothing here limits my authority to halt for reasons not listed.

**Drawdown**

| # | Trigger | Action | Why |
|---|---|---|---|
| D1 | NAV ≤ **85%** of HWM | Review trigger | Normal for a trend book through a whipsaw or the first leg of a crash before the signal flips. |
| D2 | NAV ≤ **75%** of HWM | **Halt** | Trend-following on BTC/ETH is supposed to avoid the −70% bear markets. A 25% drawdown means either a fast crash caught the book fully invested or the filter isn't doing its job. A look before re-entry is worth more than the next signal. |
| D3 | NAV ≤ **70%** of the starting sleeve ($315 at $450) | **Halt**, and I escalate to David. | Losing 30% of the capital on the desk's most trusted strategy is a mandate question. |
| D4 | NAV down ≥ **12%** in one UTC day | **Halt** until the day is reconciled | About a 20% one-day fall at full weight. That happens (March 2020), but rarely, and a bad mark looks the same. Usually short. |

**D2 and the backtest.** If the merged backtest shows the chosen parameters would have hit D2 more than once a cycle from 2018, D2 is too tight for the design or the design is too loose. I'll raise it on the backtest PR and settle it by PR before paper. D2 isn't loosened to make a backtest pass.

**Operational**

| # | Trigger | Action |
|---|---|---|
| O1 | **Unreconciled record:** order log, Crypto Book and (live) venue balances disagree on any quantity or cash, or NAV can't be computed for a day. | **Halt** |
| O2 | **Logging:** an order without a logged decision, signal value and rationale; a paper fill without its book-snapshot reference; a decision logged > 1 h after it was taken. | **Halt** |
| O3 | **Signal data:** no valid daily close for BTC or ETH at a scheduled check, **or** the primary and cross-check price sources differ by > **1%** on that close. | No trade that day (not a halt). Two checks in a row: **Halt.** |
| O4 | **Shared regime flag** (desk C3) missing, or not the one Alt Momentum used that day. | **Halt** both strategies until reconciled. |
| O5 | **Venue:** trading or API down > 4 h while holding a position; (live) withdrawals suspended > 12 h without notice, or insolvency signals. | **Halt.** Live withdrawal or insolvency events: I escalate to David, and kill exits are allowed (desk policy). |
| O6 | **Fill model:** over the last 10 fills, average impact > 0.3%, or (live) measured cost per side exceeds the paper model by > 0.2 pp. | **Halt** |
| O7 | **Rule breach:** any hard limit above; a signal-off exit not done by the end of the day after the check. | **Halt** |
| O8 | **Unreviewed change** to `strategy.md` or this file. | **Halt** |

Kill switch and stablecoin depeg: see the desk policy (kill switch, DO2).

### Before the first paper trade

- `strategy.md` and `backtest.md` merged, and the backtest passes Nadia's test (beats buy-and-hold on drawdown and risk-adjusted return, after fees). The vol target is ≤ L4.
- The **price sources** are named in `strategy.md`: one primary for signal and NAV, one cross-check (O3). The **shared regime flag** source is named (desk C3).
- The order-placement skill is merged, records each decision with its signal values and snapshot reference, and **refuses buys while a halt issue is open** (desk policy, kill switch).
- Funding record logged: USD sleeve, venue, minimum order and taker fee for BTC/USDC and ETH/USDC.

### Assumptions and what I could not verify

- **Strategy and phase:** Majors Trend, definition. No capital at risk.
- **Inputs:** THE-296 spec, Nadia's THE-286 note. No `strategy.md`, no backtest.
- **Not verified:** D1–D4 and L4 aren't calibrated to a backtest; they're set from BTC/ETH's known volatility and judgement. The 0.3% impact cap assumes major-venue depth at $50–300 orders, unchecked. Venue and fees not chosen.
- **Review:** when `strategy.md` and the backtest merge (D2, L2, L4 re-checked against them), when the venue is chosen, and at every quarterly paper review.

## Capital and promotion criteria

*Drafted by Nadia.* Draft capital: **$450** paper. To be completed by Nadia.
