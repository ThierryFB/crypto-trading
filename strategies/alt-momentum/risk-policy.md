# Risk policy

Owner: Ingrid, with capital and promotion criteria from Nadia. Merges only with Ingrid and David approving (and, once live, Thierry's confirmation).

**Phase: definition.** No capital, no mandate, no trades. The desk-wide limits in [`../desk-risk-policy.md`](../desk-risk-policy.md) also apply; the tighter limit wins.

## Limits and halt levels

*Drafted by Ingrid.* Written against the THE-297 spec (about 20 liquid spot coins, top 3–5 by 4-week return held equal-weight, weekly rebalance, cash when BTC is below trend using Majors Trend's rule). `strategy.md` and the backtest don't exist yet. Where a limit depends on them, it says so.

### Definitions

- **Sleeve:** the strategy's capital in USD (paper: the notional in Capital below).
- **NAV:** idle cash plus every position marked at mid on the venue where held, at the 00:00 UTC daily close.
- **HWM:** highest daily NAV since the first trade of the phase.
- **Universe:** the coins on the list produced by the inclusion rule in `strategy.md`, as of its last scheduled refresh, with each coin's sector tag.
- **Impact:** for one order, the gap between the pre-trade mid and the worst price filled (paper: on the logged book snapshot).
- **Hard limit:** a breach halts. **Review trigger:** I write a note within 24 h; nothing halts.

### Position and exposure limits (hard)

| # | Limit | Level | Why |
|---|---|---|---|
| L1 | Instruments | **Spot only**, coins in the current universe, quoted in the desk's cash stablecoin. No leverage, margin, borrowing, derivatives, shorting, lending, staking or yield. No stablecoins or wrapped tokens as positions. Cash never negative. | Momentum crashes are the known loss path. Nothing else should be stacked on top of them. |
| L2 | Per-position weight | ≤ **35%** of NAV after a rebalance; ≤ **50%** at any daily close. Above 50%, a trim to 35% starts within 24 h. | Equal-weight top-3 is 33%. An alt can rise 50% in a week, so drift up to 50% between rebalances is expected and allowed. Beyond that, one coin is the book. |
| L3 | Minimum breadth | When the regime is on, the book holds **at least 3** coins, or holds cash for the missing slots. Never fewer coins at a larger weight. | Stops the book concentrating into one or two names when few coins qualify. Cash is the answer to a thin ranking. |
| L4 | Sector | ≤ **50%** of NAV in coins sharing a sector tag, after a rebalance. The next-ranked coin from another sector, or cash, takes the slot. | Momentum ranks cluster: in a narrative run, the top 5 can all be one ecosystem or memes, and they reverse together. Needs the universe file to tag sectors. |
| L5 | Regime filter | No buys while the shared BTC regime flag (desk C3) is off. When it turns off, the book goes to cash at the next scheduled check, in full. | This is the strategy's only defence against a bear market. Holding "the strongest alts" through a BTC downtrend is how momentum books lose most of their capital. |
| L6 | Rebalance cadence | Ranking and rotations only at the weekly slot in `strategy.md`. Between slots: only L2 trims, regime-off exits, universe removals and halt or kill exits. | The cost budget is the central risk. Unscheduled trades are pure cost. |
| L7 | Universe removal | A held coin that leaves the universe at a refresh, or is delisted or suspended by the venue, is sold within **24 h** at the forced-exit cap. | Coins drop out of the top 20 because liquidity is leaving. Waiting for the next rebalance means selling into a thinner book. |
| L8 | Order size and impact | No order below the venue minimum or below **$10**. Impact per order: ≤ **0.5%** buys, ≤ **1%** normal sells, ≤ **3%** forced and halt or kill exits. Limit or marketable-limit orders only. | At $50–85 a position, liquid alts should fill inside the spread. A buy that can't fill within 0.5% means the coin is less liquid than the inclusion rule assumed, so it's skipped. Forced exits trade price for speed. |

### Cost (review triggers)

- **Cost drag:** realised fees plus impact over the trailing 13 weeks, annualised, above **6%** of average NAV. About 150 trades a year at $50–85 is roughly **40× NAV** in turnover. At 0.1% fees plus about 0.05% impact, that is already about **6%** a year; at 0.2–0.3% all-in it is 8–12%. So the THE-297 turnover sits at this trigger even at best-case fees, and the backtest has to show the edge net of it. If it doesn't, the design needs less turnover (for example, a rank buffer), not a looser trigger. Above 6% the backtest's edge is probably gone.
- **Turnover:** more than **4** rotations (a coin sold and another bought) in one week, or more than **200** trades in any trailing 12 months.
- **Momentum crash:** NAV down ≥ **20%** in any 7 days while the regime flag is on. I compare it with the backtest's worst weeks.

### Halt levels

A halt stops all buys and rotations. Sells the strategy requires (regime-off exits, L2 trims, L7 removals) still run. Recorded as an open `HALT — Alt Momentum` issue in this project. Only Nadia resumes, after my written review. Nothing here limits my authority to halt for reasons not listed.

**Drawdown**

| # | Trigger | Action | Why |
|---|---|---|---|
| D1 | NAV ≤ **80%** of HWM | Review trigger | Alts move 2–3× BTC. A 20% pullback inside an uptrend is normal. |
| D2 | NAV ≤ **70%** of HWM | **Halt** | A 30% loss with the regime filter in place means the filter was too slow or the ranking bought the top. Either needs a look before the next rotation. |
| D3 | NAV ≤ **60%** of the starting sleeve ($150 at $250) | **Halt**, and I escalate to David. | Losing 40% of the capital is a mandate question. |
| D4 | NAV down ≥ **15%** in one UTC day | **Halt** until the day is reconciled | Possible on a real alt crash day; also what a bad mark looks like. Usually short. |
| D5 | NAV down ≥ **30%** in any 7 days | **Halt** | A momentum crash happens over days, and a weekly book can lose most of D2 between two rebalances. This catches it mid-week, before D2. |

**D2–D5 and the backtest.** THE-297 says the strategy dies if its momentum-crash drawdowns exceed these limits. So on the backtest PR I check: with the merged rules, from 2019, how often would D2 and D5 have fired, and would D3 have been hit from any starting month? **If D3 would have been hit, I block paper** until the strategy changes. These levels aren't loosened to make a backtest pass.

**Operational**

| # | Trigger | Action |
|---|---|---|
| O1 | **Unreconciled record:** order log, Crypto Book and (live) venue balances disagree on any quantity or cash, or NAV can't be computed for a day. | **Halt** |
| O2 | **Logging:** an order without a logged decision, the ranking it came from and its rationale; a paper fill without its book-snapshot reference; a decision logged > 1 h after it was taken. | **Halt** |
| O3 | **Ranking data:** a 4-week return can't be computed for a universe coin at the weekly slot, or primary and cross-check sources disagree on its rank position by more than one place. | Skip that rotation (hold current positions, not a halt). Two slots in a row: **Halt.** |
| O4 | **Stale data:** no valid price for a held coin for > 24 h. | **Halt** |
| O5 | **Shared regime flag** missing, or not the one Majors Trend used that day. | **Halt** both strategies until reconciled. |
| O6 | **Universe:** the refresh didn't run on schedule, or the list differs from what the inclusion rule produces on the logged data. | **Halt** |
| O7 | **Venue:** trading or API down > 4 h on a venue holding ≥ 25% of NAV; (live) withdrawals suspended > 12 h without notice, or insolvency signals. | **Halt.** Live withdrawal or insolvency events: I escalate to David, and kill exits are allowed (desk policy). |
| O8 | **Fill model:** over the last 20 fills, average cost per side > 0.6%, or (live) measured cost per side exceeds the paper model by > 0.3 pp. | **Halt** |
| O9 | **Rule breach:** any hard limit above; a regime-off exit not done by the end of the day after the check; an L7 sale not started within 24 h. | **Halt** |
| O10 | **Unreviewed change** to `strategy.md`, the universe rule or this file. | **Halt** |

Kill switch and stablecoin depeg: see the desk policy (kill switch, DO2).

### Before the first paper trade

- Majors Trend's `strategy.md` and backtest merged (the regime rule comes from there), then this strategy's `strategy.md` and `backtest.md`. The backtest is survivorship-free, net of tiered costs, and reports correlation with Majors Trend (desk C2 is re-checked against it).
- The universe file is merged with sector tags (L4) and a dated refresh rule.
- Price sources named: primary and cross-check (O3).
- The order-placement skill is merged, logs each weekly ranking with the decision, and **refuses buys while a halt issue is open** (desk policy, kill switch).
- Funding record logged: USD sleeve, venue, minimum order and taker fee for every universe pair.

### Assumptions and what I could not verify

- **Strategy and phase:** Alt Momentum, definition. No capital at risk.
- **Inputs:** THE-297 spec, Nadia's THE-286 note. No `strategy.md`, universe or backtest.
- **Not verified:** D1–D5 aren't calibrated to a backtest; they're set from alt volatility (roughly 2–3× BTC) and judgement. The impact caps assume the top-20 coins fill $50–85 orders inside the spread at our venue, unchecked. The cost estimate assumes 0.1% taker fees, which depends on the venue. At the THE-297 turnover, the 6% cost trigger leaves no room for fees above that (see Cost).
- **Review:** when `strategy.md`, the universe and the backtest merge, when the venue is chosen, and at every quarterly paper review.

## Capital and promotion criteria

*Drafted by Nadia.*

### Why the test looks like this

The claimed edge is **selection**: among about 20 liquid alts, the ones with the best 4-week return keep outperforming the rest for a while. The BTC regime filter is borrowed from Majors Trend; it isn't this strategy's edge. So the question paper has to answer is narrow: **does holding the top 3–5 beat simply holding the whole universe equal-weight, under the same filter and after the extra turnover?** If it doesn't, the desk would do better with the cash in Majors Trend.

Unlike Majors Trend, this book makes enough decisions for paper to say something: about 50 weekly rankings and around 150 trades a year. It's still noisy. Momentum returns come in a few strong runs and sudden crashes, so the test reads selection week by week rather than trusting the headline P&L.

### 1. Paper capital

- **Paper notional = proposed live sub-sleeve: $250** of the desk's $1,000 (desk split in [`../desk-risk-policy.md`](../desk-risk-policy.md), Capital).
- **What $250 means per order.** Top 3–5 equal-weight is about **$50–85 a position**. Rotations sell one and buy one at about that size. Venue minimums (about $5–10) and L8's $10 floor don't bind, except on trims.
- **Costs charged.** The venue's base-tier taker fee for each universe pair, read off its fee page at paper start, plus impact on the logged book snapshot (L8). Fee assumption: 0.1% per side. **Only a venue whose base-tier taker fee is ≤ 0.1% per side is used**, unless the merged backtest shows the edge net of costs at the higher fee. At about 150 trades a year (roughly 40× NAV in turnover), 0.1% plus impact already uses the whole 6% cost budget (P7); 0.4% would be about 16% a year.
- No top-ups and no cross-funding (desk S1). A halt resets nothing and refills nothing.

### 2. Pre-registration (fixed before the first paper trade)

Changing any of these after paper starts needs a PR. The change is reported with the results.

- **Universe control.** Every week, the same universe, held **equal-weight**, under the same regime flag and the same rebalance day, charged its own (lower) turnover cost. This isolates the ranking: it's what the book would earn without selection.
- **Random control.** Every week, **at least 100 shadow books**, each picking the same number of coins at random from that week's universe. Same weights, rules and costs. This separates selection from concentration: a 3-coin book swings more than a 20-coin one whatever the ranking says.
- **Mechanical replay.** The merged rules run on the logged ranking data with no discretion. The replay applies **the same halt state** as the book: no buys while a `HALT —` issue (strategy or desk) is open, and the sells a halt or kill requires are made in the replay too, on the same day. The paper book is compared against it like-for-like (P6), so a market halt doesn't count as a deviation.
- **Crash benchmark.** From the merged backtest, the distribution of the **worst 7-day loss in a window of the same number of regime-on weeks** as the paper period (P8).
- **Parameters:** lookback, number held, rebalance day and universe rule in the merged `strategy.md`. A **material change restarts the paper clock** (P1–P4).
- **The tests in §3**, with their thresholds.

### 3. Promotion test (paper → live recommendation)

Every item must pass. Ingrid confirms them in writing; only then do I write the recommendation to David.

A **regime-on week** is a week where the shared flag was on at the rebalance, so the book held coins. Selection is only tested in those weeks.

| # | Test | Threshold | Why |
|---|---|---|---|
| P0 | Backtest edge | The merged backtest (from 2019, survivorship-free, net of tiered costs) beats the universe control after costs, in-sample **and** on its hold-out years, and Ingrid's D3 check passes (no starting month hits D3). | Paper can't stand in for a missing backtest. The backtest is also where the momentum-crash risk is measured. |
| P1 | Duration | ≥ **12 months** of paper | Momentum works in some alt markets and not others. A shorter period is mostly one market mood. |
| P2 | Regime coverage | ≥ **26 regime-on weeks**, and **at least one regime switch off and back on**. If not, paper continues. | Fewer than 26 weeks of selection is too few to read. The switch tests the exit to cash and the re-entry, where most of the cost lands. |
| P3 | Selection beats the universe | Over the regime-on weeks: (a) **net** book return ≥ the universe control's net return; and (b) the mean weekly **gross** spread (book minus universe) has a **90% CI whose lower bound is above zero**. A positive point estimate alone doesn't pass. | (a) is whether it's worth doing after costs. (b) is whether the ranking itself does anything. |
| P4 | Selection beats chance | Net book return ≥ the **median** of the ≥ 100 random shadow books. The book's percentile among them is reported with the result. | Rules out a concentrated book that got lucky in a rising market. |
| P5 | Luck check | P3(a) is also reported with the **best 2 positions removed**. If one position makes up more than 100% of the excess over the universe, the strategy isn't promoted, whatever P3(b) shows. | Separates one lucky run from a ranking that works. |
| P6 | Fidelity | Every ranking, rotation and exit matches the replay: same coins, same week, sizes within **10% or $10, whichever is larger**. Halt-state trades compared like-for-like (§2). **Zero** unexplained deviations. | Live is autonomous. The book has to be the rule. |
| P7 | Cost | Annualised fees plus impact ≤ **6%** of average NAV (Ingrid's cost trigger), and the modelled cost within **25%** of measured on a sample of books checked after the fact. | Turnover is this strategy's main hidden cost. Above 6%, the backtest's edge is probably gone. |
| P8 | Crash behaviour | No D3. D5 fired **at most once**, with Ingrid's review. The paper period's worst 7-day loss is no worse than the **5th percentile** of the crash benchmark (§2): the backtest's worst week over windows of the same length. | A momentum book that crashes worse in paper than in its own history isn't the backtested strategy. |
| P9 | Discipline and halts | 100% of decisions logged with the ranking they came from, at the time. **Zero** hard-limit breaches. Every halt has Ingrid's written review and was resumed by me; none was self-inflicted. | Same as Majors Trend. |
| P10 | Majors Trend first | Majors Trend is live, or has passed its own test, and the shared regime flag has run with **zero** mismatches for 3 months. | This book depends on that flag, and it's the riskier of the two (desk Capital, Promotion order). |

**Reported every quarter, not pass/fail:** the correlation of daily returns with Majors Trend during regime-on weeks. **Above 0.85**, the desk is running one bet twice. I'll say so in the recommendation, and may recommend moving this capital rather than promoting.

**Known limit:** at 26–50 regime-on weeks, a weekly spread is only distinguishable from zero if the edge is large. If P3(b)'s CI still includes zero but P3(a) and P4 pass, paper is extended, up to **24 months**. The thresholds aren't loosened. **At 24 months, if the CI still includes zero, the strategy isn't promoted**: I recommend stopping, or a redesign through a `strategy.md` PR that restarts the clock.

### 4. Retirement or redesign during paper

At any quarterly review **after 13 regime-on weeks**, I recommend stopping (or sending back to definition) instead of continuing paper if:

- **Selection adds nothing.** Net book return is below the universe control's at **two quarterly reviews in a row**. The ranking isn't paying for its turnover.
- **Costs eat it.** Cost drag above 6% annualised for two quarters. That's a redesign, not a retirement: a slower rebalance or a narrower universe, through a `strategy.md` PR that restarts the clock.
- **The crash risk is worse than history.** D3 is hit, or D5 fires twice. Paper stops until the design changes and Ingrid re-checks.
- **Fidelity fails twice**, same as Majors Trend.
- **No distinct bet:** correlation with Majors Trend above 0.85 **and** no excess over the universe control. I'll recommend folding the capital into the other two sleeves.

Each case goes to David with the numbers and the sample size.

### 5. Live capital and scaling

- **Live sub-sleeve: $250**, the paper figure, inside the desk's $1,000, unless the mandate sets a different one. Money Thierry is fine losing. Venue and custody are his call; this strategy needs a venue with base-tier taker fees **≤ 0.1%** per side (§1) that lists most of the universe.
- **Live stage 1 runs on the full $250.** At half, positions would be $25–40, and rotations would be close to the $10 floor once the book drifts. Live stage 1 lasts **≥ 6 months**. P3–P9 continue live, and live cost is compared with the paper fill model (Ingrid's O8).
- **Any increase** (capital, a second venue, a wider universe, a loosened limit) is a **new mandate confirmation** from Thierry, through David.
- **Gains** stay in the sub-sleeve until the quarterly review (desk S3). Anything above the mandated cap is swept out each quarter.
- **Capacity:** at $250, liquidity isn't a constraint on the top-20 universe. It would start to matter in the low hundreds of thousands, for the smaller names in the universe. That's not a plan.

### Assumptions and review triggers

- **Phase:** definition. No paper record exists; nothing above is a result.
- **Assumes** the THE-297 design: about 20 coins, top 3–5 by 4-week return, weekly rebalance, the shared BTC regime flag. If `strategy.md` changes the number held or the cadence, §1's per-order figures and P2's week count are re-checked.
- **Assumes** the backtest is survivorship-free (dead and delisted coins included). Without that, P0 can't be checked, and I won't start paper.
- **What would show the thesis is wrong:** P3(a) failing while the universe control is positive. That means alts paid off, but picking the strongest didn't.
- **Review:** when `strategy.md`, the universe and the backtest merge, when the venue is chosen, at each quarterly paper review, and before the live recommendation.
