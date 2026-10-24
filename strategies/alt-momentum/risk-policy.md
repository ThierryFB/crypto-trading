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

- **Cost drag:** realised fees plus impact over the trailing 13 weeks, annualised, above **6%** of average NAV. About 150 trades a year at $50–85 and 0.2–0.3% all-in is roughly 3–5% a year; above 6% the backtest's edge is probably gone.
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
- **Not verified:** D1–D5 aren't calibrated to a backtest; they're set from alt volatility (roughly 2–3× BTC) and judgement. The impact caps assume the top-20 coins fill $50–85 orders inside the spread at our venue, unchecked. The cost estimate assumes 0.1% taker fees, which depends on the venue.
- **Review:** when `strategy.md`, the universe and the backtest merge, when the venue is chosen, and at every quarterly paper review.

## Capital and promotion criteria

*Drafted by Nadia.* Draft capital: **$250** paper. To be completed by Nadia.
