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

*Drafted by Nadia.*

### Why the test looks like this

The claim behind this strategy is about **drawdown, not return**: hold BTC and ETH while they trend up, sit in cash while they don't, and so miss most of a −70% bear market while keeping most of a bull. That claim needs years and several cycles to test. The backtest from 2018 is where it gets tested. At 5–15 trades a year, a year of paper is about ten decisions. Its P&L says almost nothing about the edge either way.

So paper tests what the backtest can't: **whether the merged rules are followed exactly, without supervision, at the costs assumed.** Live is autonomous. A trend book that skips one exit, or holds through an off signal "because it looks like a bottom", isn't this strategy any more.

### 1. Paper capital

- **Paper notional = proposed live sub-sleeve: $450** of the desk's $1,000 (desk split in [`../desk-risk-policy.md`](../desk-risk-policy.md), Capital).
- **What $450 means per order.** At the vol target, BTC or ETH positions are about $100–270. Normal trades are $50 and up; L7's $10 floor stops drift trades. Venue minimums (about $5–10) don't bind.
- **Costs charged.** The venue's base-tier taker fee for BTC/USDC and ETH/USDC, read off its fee page at paper start, plus impact on the logged book snapshot (L7). The THE-296 assumption is 0.1% per side.
- No top-ups and no cross-funding (desk S1). A book that draws down trades smaller, as it would live. A halt resets nothing and refills nothing.

### 2. Pre-registration (fixed before the first paper trade)

Changing any of these after paper starts needs a PR. The change is reported with the results.

- **Mechanical replay.** Every day, the merged rules are run on the logged signal data with no discretion. This gives the trades and NAV the book *should* have had. The replay applies **the same halt state** as the book: no buys or size increases while a `HALT —` issue (strategy or desk) is open, and the sells a halt or kill requires are made in the replay too, on the same day. It also applies **the same desk constraint state**: on a day when desk C1 blocks adding to a coin, or C2 blocks adding risk-on exposure ([`../desk-risk-policy.md`](../desk-risk-policy.md)), the replay doesn't size up either. The constraint state is computed from the actual desk book at the daily close and logged with the halt state, so book and replay read the same record. The paper book is compared against the replay like-for-like (P3, P4), so neither a market halt nor a binding desk constraint counts as a deviation. An **unconstrained replay** is also run and reported each quarter, to show what C1 and C2 cost; it isn't pass/fail.
- **Benchmark:** 50/50 BTC/ETH buy-and-hold, rebalanced monthly, from the same start date and with the same costs. Reported every quarter; it isn't pass/fail on paper (see below).
- **Parameters:** the signal, vol target and check time in the merged `strategy.md`. A **material change to `strategy.md` restarts the paper clock** (P1, P2).
- **The tests in §3**, with their thresholds.

### 3. Promotion test (paper → live recommendation)

Every item must pass. Ingrid confirms them in writing; only then do I write the recommendation to David.

| # | Test | Threshold | Why |
|---|---|---|---|
| P0 | Backtest edge | The merged backtest (2018 onwards, net of fees) beats the benchmark on **maximum drawdown** and on **return ÷ max drawdown**, in-sample **and** on the hold-out years the backtest reserves. If the hold-out years contain no BTC fall of **≥ 30%** from its peak, the hold-out drawdown leg is reported as **uninformative**, not passed, and P0 rests on the in-sample cycles (2018, 2022). This was checked before paper and must still hold after any later change to `strategy.md`. | The edge is tested here, not in paper. Without it, a clean paper record is a well-run strategy with nothing to run. |
| P1 | Duration | ≥ **6 months** of paper | Long enough to run the whole loop many times (daily checks, NAV, reconciliation, the Crypto Book). It isn't meant to prove the edge. |
| P2 | Signal coverage | At least **one entry and one exit** in each coin, or **four signal changes** across the book. If not, paper continues until it happens. At 12 months without it, I report to David, and the recommendation is **continue paper** or **stop**, never promote, until P2 passes. | The exits are what matter. A paper period where nothing ever turned off hasn't tested the rule that carries the edge. |
| P3 | Fidelity | Every paper trade matches the replay: same coin, same day, same direction, and size within **10% or $10, whichever is larger**. Trades changed by halt or desk-constraint state are compared like-for-like (§2). **Zero** trades the replay didn't make, and **zero** replay trades skipped. | This is the test that matters most. Autonomy is only safe if the book is the rule. |
| P4 | Tracking | Paper NAV return within **±1.5 pp** of the replay's over the period, with every gap explained by fills or fees. | Small, explained gaps are execution. Large or unexplained ones are a broken record or a hidden decision. |
| P5 | Cost realism | Average fees plus impact ≤ **0.3% per side**, and the modelled cost is within **25%** of the measured cost on a sample of books checked after the fact. | The backtest assumed 0.1% plus nearly no impact. Costs well above that mean the venue or the fill model is wrong. |
| P6 | Discipline | 100% of decisions logged with their signal values, at the time of the decision. **Zero** hard-limit breaches. Every signal-off exit done by the end of the day after the check. | Same reason as P3: live has no supervision on each trade. |
| P7 | Halts | Every halt in the period (D1–D4, O1–O8, any desk halt) has Ingrid's written review and was resumed by me. None was caused by the strategy breaking its own rules; that fails P6. | Market halts are expected. Self-inflicted ones aren't. |
| P8 | Shared regime flag | **Zero** O4 / desk C3 mismatches over the last 3 months. | Alt Momentum depends on this flag. Its source has to be dependable before either book trades real money on it. |

**Not a promotion criterion:** paper P&L, or paper beating the benchmark over 6 months. That is too few decisions to read. It is reported every quarter, with the sample size, and labelled paper.

### 4. Retirement or redesign during paper

At any quarterly review, I recommend stopping (or sending the strategy back to definition) instead of continuing paper if:

- **P3 fails twice.** One deviation gets a fix and a fresh start. A second means the process can't follow the rule, and the problem is the execution, not the market.
- **Cost runs above 2× the model** for a quarter, after a venue check. At that point the backtest's numbers don't describe what we can trade.
- **The filter doesn't protect.** Over any paper period that includes a BTC fall of **≥ 30%** from its peak, the book's drawdown is **≥ 80%** of the benchmark's. That is the claimed edge failing in real time, and the one P&L result paper can read.
- **Whipsaw is worse than history.** The book's loss across a whipsaw streak (Ingrid's signal-flip trigger) is larger than the backtest's worst whipsaw streak.

Each case goes to David with the numbers and the sample size.

### 5. Live capital and scaling

- **Live sub-sleeve: $450**, the paper figure, inside the desk's $1,000, unless the mandate sets a different one. It has to be money Thierry is fine losing. Venue and custody are his call in the mandate.
- **Live stage 1 runs on the full $450.** Splitting it would mean $25–135 positions. That's fine on minimums, but it saves less than $250 of risk on a sleeve that is already sized to be lost. Live stage 1 lasts **≥ 6 months**. P3–P8 continue live, and live cost is compared with the paper fill model (Ingrid's O6).
- **Any increase** (capital, a second venue, a loosened limit) is a **new mandate confirmation** from Thierry, through David. A mandate never expands itself.
- **Gains** stay in the sub-sleeve until the quarterly review (desk S3). Anything above the mandated cap is swept out each quarter. The cap limits capital at risk; it isn't a starting balance.
- **Capacity:** BTC and ETH books don't limit this strategy at any size the family would consider. The constraints are the mandate and venue risk, not liquidity.

### Assumptions and review triggers

- **Phase:** definition. No paper record exists; nothing above is a result.
- **Assumes** the THE-296 design: slow signal, about 5–15 trades a year, vol-scaled, cash when off. If `strategy.md` comes out much faster (say, more than 30 trades a year), paper sees enough trades to read P&L, and P1 and the "not a criterion" line are re-checked.
- **Assumes** the backtest holds out at least its last two years from parameter choice. If it doesn't, P0 can't be checked as written, and I'll ask Leo for a hold-out before paper.
- **What would show the thesis is wrong:** the §4 "filter doesn't protect" case, or a backtest where the drawdown edge comes from one crash (2022) and disappears in the others.
- **Review:** when `strategy.md` and the backtest merge, at each quarterly paper review, and before the live recommendation.
