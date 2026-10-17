# Risk policy

Owner: Ingrid, with capital and promotion criteria from Nadia. Merges only with Ingrid and David approving (and, once live, Thierry's confirmation).

**Phase: definition.** No capital, no mandate, no trades.

## Limits and halt levels

*Drafted by Ingrid.* These limits apply from the first paper trade. They carry into live unchanged unless a PR changes them. Rule references (§) are to Rafael's rev 3 draft of `strategy.md`.

### Definitions

- **Sleeve:** the capital the strategy runs on. Paper: the notional in §1 below (USD 100,000 placeholder). Live: the mandated sleeve, or 25% of it at stage L1.
- **NAV:** idle cash plus every open position marked at mid on its main credible venue at the daily close (00:00 UTC). Shadow positions are not in NAV.
- **HWM:** highest daily NAV since the first trade of the phase (paper or live), reduced by any quarterly sweep.
- **Cost:** everything paid into a position across its tranches, fees included. Stage-sell proceeds don't reduce it.
- **Impact:** for one order, the gap between the pre-trade mid and the worst price filled. Paper measures it on the logged snapshot used for the fill; live measures it on the actual fills.
- **Hard limit:** a breach halts the strategy and counts against P9. **Review trigger:** I write a note on the strategy's issue within 24 h. It doesn't halt anything.

### Position limits (hard)

| # | Limit | Level | Why |
|---|---|---|---|
| L1 | Cost per position | ≤ **5%** of the lower of sleeve and NAV, checked at every tranche | With no price stop, this cap is the stop: the most one name can lose is 5% of the sleeve. Using the lower of sleeve and NAV means a book that has drawn down trades smaller, as §1 requires. |
| L2 | Depth per position | Cost ≤ **50%** of summed credible ±2% bid depth (median of ≥ 3 snapshots, §1), checked at every tranche | The position has to be sellable in one pass across our venues at about 1–2% impact. |
| L3 | Market value per position | ≤ **20%** of NAV at any daily close. A trim to **≤ 15%** starts within 24 h at the normal impact cap. | Rafael's figures, accepted. A tighter cap would cut the tail the book exists for. The ladder normally keeps a winner under 20%. The trim mostly binds when the rest of the book has bled, which is when a single exploit would hurt most. The breach is not starting the trim, or buying into a name above 15%. A trim slowed by the impact cap is not a breach. |

**No position-level price stops.** I accept the rev 3 §5 design. L1 is the loss limit. The −70% review in §5 stays as written.

### Book limits (hard)

| # | Limit | Level | Why |
|---|---|---|---|
| L4 | Open positions | ≤ **25** | Rafael's maximum. **Below 15** after the first 10 weeks of regime-on time is a review trigger, not a halt. L1 does not loosen to make up for a short book. Idle cash is the answer. |
| L5 | Deployment pace | ≤ **2** new positions started per week, and ≤ **10%** of sleeve bought per week (all tranches, at cost). Weeks run Monday 00:00 UTC to Sunday. | Rafael's figures, accepted. A full book takes ≥ 10 weeks, so it isn't filled on one day's mood. |
| L6 | Sector | ≤ **5** open positions sharing a sector tag on the merged watchlist | Micro-caps in one narrative (memes, AI, one chain's ecosystem) crash together. Five of twenty caps a correlated hit at about a quarter of the book. This needs Hugo's watchlist to tag each token's sector. |
| L7 | Illiquid share | Positions whose market value is > 50% of their current summed credible ±2% bid depth: together ≤ **25%** of NAV | The per-position liquidity-collapse rule (§5) reduces names one at a time and can be slow. This caps how much of the book can be stuck at once. |
| L8 | Instruments | **Spot only.** No leverage, margin, borrowing, derivatives or shorting. No lending, staking, LP provision, presales or airdrop farming. Cash never negative. | Each of these adds a loss path beyond "the token goes to zero", which is the only one this book is sized for. |
| L9 | Universe and venues | Buys only in tokens on the merged watchlist and not suspended, and only while the regime is on and the strategy isn't halted. Orders only on credible venues where the strategy holds (or, on paper, assumes) accounts (§1). Tier 2 and wash venues: never. **Live DEX trading** only if the mandate names the wallet custody. | These are the strategy's own entry rules (§2). They're listed here so that breaking one is a halt. |

### Impact caps (hard)

| Order type | Cap per order (impact) | Minimum gap between orders on the same venue |
|---|---|---|
| **Buys** (entry tranches) | **1.5%** | 1 h |
| **Normal exits:** stage sells T1–T4, trail, time stop, dead-token exit, L3 trims, liquidity reductions | **2%** | 1 h |
| **Forced exits:** watchlist revocation, delisting | **5%** | 1 h |
| **Emergency exits:** exploit or contract compromise (§5, row 3), or a venue insolvency signal (O4) | **10%** | 15 min |

**Why:**
- **Buys at 1.5%.** Buying is optional. A tranche that can't fill inside 1.5% waits or shrinks; it doesn't chase depth.
- **Normal exits at 2%.** With fees, this keeps average cost inside P8's 3% per side.
- **Forced exits at 5%.** A revoked or delisting token usually loses more than 5% while we wait, so speed is worth more than price.
- **Emergency exits at 10%, faster.** This is a change from rev 3 §5, which sells exploits under the forced cap. In an exploit a token can lose most of its value within hours. At 5% per order and one order an hour, most of the position would still be held when it does. A position is at most 5% of the sleeve at cost, so the extra impact costs at most about 0.5% of the sleeve, set against a likely total loss. @Rafael, please fold this into `strategy.md`.

A sell bigger than its cap is split across venues and over time (§3). An exit that can't finish within its window at its cap isn't a breach. It continues at the cap's pace, and it's a review trigger. **Filling beyond the cap is a breach.**

### Idle cash

- **Where it sits:** in USD or USDC. USDT and other quote stablecoins are held only as needed for a pending order or a settled sale, and converted back within 24 h. Paper charges the conversion cost.
- **No yield.** Idle cash isn't lent, staked, or put into exchange Earn or other yield products, and paper assumes 0%. Yield on cash adds counterparty risk for a few percent a year. This sleeve's risk budget is for the tokens.
- **Live, on exchanges:** idle cash across all venues ≤ **40%** of sleeve (four weeks of L5 pace), and ≤ **20%** of sleeve at any one venue. The rest is held in the custody the mandate names. **Live doesn't start until the mandate names it** (THE-270).
- **Depeg:** see O6.

### Halt levels

A halt **stops all buys**: new positions and pending tranches. Sells that `strategy.md` requires still run and are logged, unless the halt issue says otherwise. A halt is recorded as an open `HALT — Micro-cap Convex` issue in this project, as set out in my role. Only Nadia resumes, after my written review. Nothing in this file changes my authority to halt for reasons not listed here.

**Book drawdown**

| # | Trigger | Action | Why |
|---|---|---|---|
| D1 | NAV ≤ **75%** of HWM | Review trigger. Rafael confirms that every position is within L1–L9. | The book is built to lose on most names. In the backtest the median 2022–25 position ended at 0.38×. A fully deployed book can be down 25–30% before any T1 fills, and that alone says nothing. |
| D2 | NAV ≤ **60%** of HWM | **Halt** | Forces a look before the remaining capital goes in. Exits keep running, so this mostly pauses entries. The review asks whether the loss is inside the design: capped names going to zero, or something else. |
| D3 | NAV ≤ **50%** of the starting sleeve | **Halt**, and I escalate to David (paper: notify him; live: escalate). | Losing half the capital is a mandate question, not a desk one. |
| D4 | NAV down ≥ **20%** in one UTC day | **Halt** until the move is reconciled | It may be the market, a bad mark or a venue event. Until we know which, we don't add risk. Usually short. |

The paper book may well hit D1, and possibly D2. That's acceptable: P2 asks for a bad tape on purpose.

**Operational**

| # | Trigger | Action |
|---|---|---|
| O1 | **Unreconciled record:** the daily reconciliation between the order log, the Crypto Book and (live) venue balances shows any unexplained difference in quantity or cash, or NAV can't be computed for a day. | **Halt** |
| O2 | **Logging failure:** an order or fill without a logged decision and rationale; a paper fill without its stored book-snapshot reference; a reused snapshot (§6); or a decision logged more than 1 h after it was taken. | **Halt** |
| O3 | **Fill-model divergence.** Paper: average cost over the last 20 fills > 3% per side. Live: over the last 20 fills, measured cost per side exceeds the paper fill model's cost for the same orders by > 1 pp on average. | **Halt** |
| O4 | **Venue.** Trading or API down > 4 h on a venue holding ≥ 25% of NAV. Live: withdrawals suspended > 12 h without scheduled-maintenance notice on a venue holding our assets, or credible insolvency signals. | **Halt.** On live withdrawal or insolvency events I also escalate to David, and emergency exits are allowed. |
| O5 | **Stale data:** no valid price or depth reading for a held token for > 24 h, or the BTC regime input missing at a weekly close. | **Halt** |
| O6 | **Depeg:** the stablecoin held as idle cash trades below 0.98 for ≥ 1 h. | **Halt**, and I escalate to David. |
| O7 | **Rule breach:** any hard limit above is breached; a revocation or exploit exit hasn't started within 4 h; a triggered stage sell isn't done within 24 h (P9). | **Halt** |
| O8 | **Unreviewed change:** `strategy.md`, the watchlist files or this file differ from what merged by PR. `master` is not protected, so I check the history. | **Halt** |

### Before the first paper trade

I can't monitor what I can't check, so paper doesn't start until:
- the order-placement skill is merged, and its log records tranche-level buys and **partial** sells (Crypto Book v1 can't), daily positions and NAV, the snapshot reference and impact for each order, the depth readings, and the regime flag;
- `strategy.md`, `watchlist-criteria.md` and `watchlist.md` are merged, and the watchlist tags each token's sector (L6);
- the mark and depth sources for NAV, L2 and L7 are named in `strategy.md` or the order-placement skill.

### Assumptions and what I could not verify

- **Strategy and phase:** Micro-cap Convex, definition. No capital at risk.
- **Inputs:** Rafael's rev 3 ([THE-269](/THE/issues/THE-269), 2026-10-16); Sam's backtest ([THE-273](/THE/issues/THE-273)) as summarised there, not re-run by me; Hugo's depth scan (one snapshot, five tokens).
- **Not verified:**
  - **D1–D3 have no book-level calibration.** The backtest is per position, with no capital recycling, so I set these from per-position outcomes and judgement.
  - The impact caps are untested at our sizes.
  - The order-log format doesn't exist yet.
- **Review:** when Thierry's sleeve and venue answer arrives (THE-270), at the first quarterly paper review, and on any change to sizing or exits in `strategy.md`.

## Capital and promotion criteria

*Drafted by Nadia.*

### Why the test looks like this

A lottery book's result comes almost entirely from one or two positions. A year of paper can look excellent because one token went 40×, or terrible because none did. Neither says much about the edge.

The backtest behind `strategy.md` (THE-273) also shows that **random in-band entries lose money today under every exit design tested** (0.63×–0.92× per position, 2022–25). The book only works if the watchlist gate plus the entry triggers lift the share of positions reaching T1 (3×) from about 15% to about 24%. History can't test that. Paper is that test, so the promotion test is built around it, not around the P&L line.

### 1. Paper capital

- **Notional paper book = the proposed live sleeve.** Thierry's indication on THE-270 (2026-10-17, non-binding) is a live sleeve of **EUR 1,000–2,000**. Paper runs at **EUR 1,000**, the low end. At this size, order minimums and fixed costs are what bind, and they bind hardest at the low end. A strategy that works at EUR 1,000 also works at EUR 2,000. If the mandate is set above EUR 2,000, this section is re-checked before live. The strategy's capacity ceiling stays at **USD 500,000**. It's a property of the watchlist's depth, not a plan.
- **What EUR 1,000 means per order** (N = 20, 3 entry tranches, EUR/USD taken as about 1.15): a position is about **EUR 50**, and an entry tranche about **EUR 17 (≈ USD 19)**. The smallest normal stage sell is T1, at about EUR 50 of value. Positions that have lost most of their value can drop below venue minimums. Those are the only orders where minimums bind.
- **Order minimums.** A token is tradable on a venue only if that venue's minimum order for the pair is **≤ half an entry tranche** (about USD 9 at EUR 1,000). A sell below the venue minimum can't execute. Paper doesn't fill it: the residual is carried as dust and marked at zero once it's unsellable. That matches what would happen live.
- **Fixed costs.** At about EUR 17 a ticket, a USD 2 withdrawal or gas fee would cost 10% or more of the order. So: **any fixed cost per order (gas, priority fee, transfer, withdrawal) must be ≤ 0.5% of the order's value, or the order isn't placed.** In practice:
  - each position is bought, held and sold **on one venue**, with no cross-venue transfers per position;
  - DEX orders are allowed only on chains where the cost to swap clears the 0.5% test (Ethereum mainnet doesn't, at this size);
  - the sleeve is funded once per venue, and that one-off conversion and transfer cost is charged to paper at the start.
- **Percentage costs at this size.** Market impact is roughly the half-spread, because a USD 19 order rarely walks past the best level. The base-tier taker fees to charge (to be checked on each venue's fee page at paper start) are about 0.10% at Binance, OKX and Bybit, 0.40% at Kraken and 0.60% at Coinbase. P8 stays at 3% per side as a ceiling, but the expected cost is about 0.5–1.5%. Coinbase's fee alone uses 40% of the THE-273 cost assumption, so where a token trades on several of our venues, the cheapest one is used.
- Position size, count and per-name caps follow `strategy.md` and the limits above. They aren't set here.
- No paper top-ups. A book that draws down trades smaller, as live would. A halt resets nothing and refills nothing.

### 2. Pre-registration (fixed before the first paper trade)

Changing any of these after paper starts requires a PR, and the change is reported with the results.

- **Shadow control.** For every paper entry, the log records **5 shadow entries**: tokens drawn at random from the same day's eligible watchlist (same regime filter, same eligibility checks), sized the same and run under the same exit rules. The control isolates the entry trigger. Five draws per entry keep the control's own noise well below the strategy's.
- **No-ladder shadow.** Each real entry is also tracked held with the 40% trail and no ladder. This is reported, not pass/fail; it tells us what the ladder costs.
- **The tests in §3**, with their thresholds.
- **The fill model** in `strategy.md` §6: walk the logged book at decision time, plus fees.

A **material change to `strategy.md` resets the paper clock** for the part it touches. A change to entries restarts the entry sample (P3–P6); a change to exits restarts the exit tests (P7–P8).

### 3. Promotion test (paper → live recommendation)

Every item must pass. Ingrid confirms them in writing; only then does Nadia write the recommendation to David.

| # | Test | Threshold | Why |
|---|---|---|---|
| P1 | Duration | ≥ **12 months** of paper trading | One cycle of alt-season mood is not enough. |
| P2 | Regime coverage | The period includes a drawdown of ≥ 30% from peak in an equal-weight basket of the watchlist, **and at least one switch of the BTC regime filter to off**. If not, paper is extended. | Tests the book in a bad tape, not only a good one, and tests the filter's handling of pending tranches (§2 of `strategy.md`). |
| P3 | Sample | ≥ **40 entries with a resolved T1 outcome**: T1 filled, or the position closed without it (time stop, revocation, other forced exit). | T1 can take up to 12 months to resolve, so open positions don't count. In practice P3, not P1, sets the paper length; expect 18–24 months. |
| P4 | Entries clear break-even | Share of resolved entries reaching T1 ≥ **24%**, or the break-even share recomputed from the paper book's own payoffs if that is higher. 90% CI reported. | Below break-even the book loses money by construction. 24% is the THE-273 break-even at today's payoffs; random entries got about 15%. |
| P5 | Entries beat the control | T1 rate ≥ **10 pp above** the shadow control's, on the same dates. 90% CI reported. | The edge being claimed is selection. This is the measurable part of it, and it doesn't depend on catching one 50×. |
| P6 | Net result vs. control, and luck | Net paper P&L after fees and slippage ≥ the control's. P&L is also reported with the best 1 and best 2 positions removed. **If one position accounts for more than 100% of net profit and P5 fails, the strategy isn't promoted**, whatever the headline. | Separates a lucky ticket from a working method. |
| P7 | Exit fillability | Every triggered stage sell was fillable at the logged size against the logged book within the normal exit impact cap. Unfillable sells are counted and reported. | Paper winners that couldn't be sold aren't winners. |
| P8 | Cost realism | Average cost ≤ **3% per side**, and modelled cost within 25% of measured cost on a sample of books checked after the fact. | THE-273 assumed 1.5% per side; above 3% the thin edge is gone. |
| P9 | Discipline | 100% of decisions logged with a rationale. **Zero** entries off the watchlist. **Zero** hard-limit breaches. Every revocation exit started immediately and every stage sell executed within 24 h of its trigger. | Live is autonomous, so paper must show the rules hold without supervision. |
| P10 | Halts | Every halt in the period (D1–D4, O1–O8) has Ingrid's written review and was resumed by Nadia. None was caused by a hard-limit breach; that would fail P9. | Market drawdown halts are expected in a bad tape. Halts the strategy caused itself are not. |

**Not a promotion criterion:** a positive headline P&L on its own. A positive P&L that fails P4 or P5 means "extend paper", not "go live".

### 4. Retirement during paper

Nadia recommends retiring the strategy, rather than extending paper, if at any quarterly review after **25 resolved entries**:

- the T1 rate is **at or below the shadow control's**, meaning the entry triggers add nothing; or
- the T1 rate is **below 15%** (the random-entry base rate), meaning selection is worse than random; or
- more than a third of triggered stage sells were unfillable, meaning the universe is too thin for this exit design at this size.

Each case is reported to David with the numbers. Paper risks no capital, but the desk's attention isn't free.

### 5. Live capital and scaling

- **Live sleeve:** Thierry's figure, set in the mandate, no higher than the USD 500,000 ceiling. It must be money he is fine losing entirely. His indication is EUR 1,000–2,000 (THE-270). Venue and custody are his call. One venue is enough to trade at this size. Two or more of Binance, OKX, Bybit and Coinbase widen the watchlist, because only depth on our own venues counts.
- **Stage L1:** live for ≥ **6 months**. P7–P10 continue live, and live slippage is compared with the paper fill model.
  - For a mandated sleeve **above EUR 4,000**, L1 runs on **25%** of it.
  - **At or below EUR 4,000, L1 runs on the full mandated sleeve.** At 25% of EUR 1,000–2,000, an entry tranche would be EUR 4–8, below most venues' minimum order. The staging would break the strategy without reducing the risk, since the whole sleeve is already sized to be lost.
- **Stage L2** (only where L1 ran on 25%): full sleeve. Requires Ingrid's sign-off on L1, Nadia's recommendation to David, and a **new mandate confirmation** from Thierry. A mandate never expands itself. Any increase to the sleeve, at any stage, is a new mandate confirmation.
- **No profit recycling above the cap.** Gains above the mandated sleeve are swept out each quarter. The cap is a ceiling on capital at risk, not a starting balance.

### Assumptions and review triggers

- **Assumes** T1 (3×, returns cost) as defined in `strategy.md` §4. If T1 moves, P4/P5 move with it and the clock resets for the exit tests.
- **Assumes** the watchlist holds about 15 or more eligible tokens on most days. With fewer, the control becomes "equal-weight the full eligible watchlist".
- **Known limit:** at 40 resolved entries, a 24% T1 rate has a 90% CI of roughly ±11 pp. The test can catch a clear edge or a clear failure, not a marginal one. If P4/P5 are inconclusive at 40, paper is extended; the thresholds aren't loosened.
- **Assumes** EUR/USD at about 1.15 and venue minimums of about USD 5–10 per order. Both are checked at paper start. If a venue's minimum for a pair exceeds half a tranche, that pair isn't traded there (§1).
- **At this size, depth no longer limits exits.** A EUR 50 position needs about USD 115 of ±2% depth to pass the 50% depth cap, and every watchlisted token clears that. So the depth floor's job is now to filter out manipulated or hollow markets, not to cap exit size. What would show that's wrong: P7 sells failing to fill, or impact above the half-spread on more than a few orders.
- **Review:** when the venue answer arrives (THE-270), when the mandate fixes the sleeve, and at every quarterly paper review.
