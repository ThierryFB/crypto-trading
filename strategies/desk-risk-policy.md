# Desk risk policy

Owner: Ingrid, with capital from Nadia. Merges only with Ingrid and David approving (and, once any strategy is live, Thierry's confirmation).

This file covers what no single strategy's policy can see: the **combined** exposure of Majors Trend, Alt Momentum and Micro-cap Convex against the desk's $1,000 sleeve. Each strategy's own `risk-policy.md` still applies in full. Where the two disagree, the tighter limit wins.

**Phase: definition.** No capital, no mandate, no trades.

## Why a desk layer is needed

Majors Trend and Alt Momentum are both long-only and both go to cash on the same BTC trend rule. They will be risk-on together and risk-off together. In a crash they are both in cash, which is the point. In a choppy market they get whipsawed **at the same time**, and in a fast crash they both lose before the filter flips. Their individual drawdown halts don't add up to a desk limit. Micro-cap is the only real diversifier, and at $300 it's the smallest sleeve.

## Definitions

- **Desk sleeve:** $1,000 notional (paper), split by Nadia's capital section below. All figures in **USD**.
- **Desk NAV:** the sum of the three strategies' NAVs, each as defined in its own policy, at the 00:00 UTC daily close.
- **Desk HWM:** highest desk NAV since the first paper trade of any strategy.
- **Risk-on exposure:** market value of every non-stablecoin position across all three strategies.
- **Halt:** stops all buys. Sells the strategy requires still run and are logged, unless the halt issue says otherwise.
- **Kill:** a halt **plus** flattening: every position in scope is sold to the quote stablecoin within 24 h at the strategy's normal exit impact cap (forced cap where the halt issue says so). The trader executes. I record it on the halt issue; I don't place orders.
- **Hard limit:** a breach halts. **Review trigger:** I write a note on the issue within 24 h. It doesn't halt anything.

## Sleeves (hard)

| # | Limit | Why |
|---|---|---|
| S1 | Each strategy trades **only its own sub-sleeve**. No cross-funding, no transfers between sleeves, no top-ups, without a merged PR to the capital section. | A losing strategy must not be refilled by a winning one. Each record has to stand on its own capital. |
| S2 | Cash never negative in any strategy. Spot only across the desk: no leverage, margin, borrowing, derivatives, shorting, lending, staking or yield. | Every limit below assumes the worst case is "everything held goes to zero". Nothing on this desk is sized for losses beyond the capital. |
| S3 | Gains stay in the strategy that made them until a quarterly review. Rebalancing between sleeves is a capital change (PR). | Keeps the allocation a decision, not drift. |

## Combined exposure (hard)

| # | Limit | Level | Why |
|---|---|---|---|
| C1 | **Single token across strategies** | Combined market value of any one token held by more than one strategy ≤ **40%** of desk NAV at the daily close. On a breach, the strategy that would **add** to the token can't (Alt Momentum skips it at its next rebalance; Majors Trend doesn't size up). A breach caused only by price drift is a review trigger, not a halt; adding into it is the breach. | Alt Momentum's universe can include ETH, SOL and other large caps, and BTC or ETH could be in both books at once. Majors Trend alone can carry about $270 of one coin. Without this, one coin could quietly reach half the desk. |
| C2 | **Trend-filtered exposure** | Risk-on exposure of Majors Trend + Alt Momentum together ≤ **70%** of desk NAV at the daily close (review trigger at 60%). | Fully invested, the two together are $700 of the $1,000, so this is a ceiling on drift, not on normal operation. It mainly binds after a strong run, when both books are heaviest and most exposed to the same reversal. On a breach the next scheduled rebalance in either book doesn't add risk-on exposure. |
| C3 | **One regime flag** | The BTC trend flag is computed **once a day, from one logged source, and used by both** Majors Trend and Alt Momentum (Micro-cap uses its own weekly filter). Two strategies acting on different regime readings for the same day is a breach. | Both strategies are told to use the same trend rule. If each computes it separately, one bad candle can put them on opposite sides, which is a record problem before it's a market problem. |
| C4 | **Idle cash** | Idle cash is held in **one** USD stablecoin across the desk (USDC unless the mandate says otherwise). Other stablecoins only for a pending order or a settled sale, converted back within 24 h. | When both trend books are off, about 70% of the desk sits in that one stablecoin. That is accepted at paper. Live, the mandate decides whether part of it stays in fiat. |

## Desk drawdown halts

| # | Trigger | Action | Why |
|---|---|---|---|
| DD1 | Desk NAV ≤ **85%** of desk HWM | Review trigger. Each trader confirms their book is inside its own limits. | A bad month for crypto. Not on its own a reason to stop. |
| DD2 | Desk NAV ≤ **75%** of desk HWM | **Desk halt** (all three strategies) | The strategy-level halts are set for each book in isolation. Losing a quarter of the desk from its peak, across all three at once, means the books are failing together, which is the scenario the strategy policies can't see. |
| DD3 | Desk NAV ≤ **$650** (65% of the starting sleeve) | **Desk halt**, and I escalate to David. | Losing a third of the capital is a mandate question. Each strategy can sit at or near its own capital halt and still put the desk here (for example Micro-cap −50%, Majors −25%, Alt Momentum −35% is −$350). |
| DD4 | Desk NAV down ≥ **10%** in one UTC day | **Desk halt** until the day is reconciled | A 10% desk day needs both trend books fully invested in a crash, or a bad mark. Either way, we don't add risk until we know which. |

A desk halt overrides any strategy's own resume: a strategy can't buy while a desk `HALT — desk` issue is open, even if its own halt was resumed.

## Desk operational halts

| # | Trigger | Action |
|---|---|---|
| DO1 | **Venue:** trading or API down > 4 h, or (live) withdrawals suspended > 12 h without maintenance notice, on a venue holding ≥ 25% of desk NAV. | **Desk halt.** On live withdrawal or insolvency events I escalate to David, and emergency exits are allowed in every strategy. |
| DO2 | **Depeg:** the desk's cash stablecoin trades below **0.98** for ≥ 1 h. | **Desk halt**, and I escalate to David. Not a kill: flattening into the stablecoin that is depegging makes it worse. |
| DO3 | **Desk record:** desk NAV can't be computed for a day, or the three strategies' records don't reconcile with the Crypto Book and (live) the venue balances. | **Desk halt** |
| DO4 | **Unreviewed change:** this file, any `risk-policy.md` or `strategy.md` differs from what merged by PR. `master` isn't protected, so I check the history. | **Desk halt** |

## Kill switch

A kill is the same mechanism as a halt, with flattening added on the `HALT —` issue. I call a kill, for the strategy or the desk, when holding the positions is itself the risk:

- **Instrument breach:** anything outside S2 is held (leverage, a derivative, a token outside the strategy's universe). The offending positions are closed at once; the rest of the book halts.
- **Live venue insolvency signal** or withdrawal suspension with no credible timeline: emergency exits on that venue, then halt.
- **Execution out of control:** orders reaching the venue that don't match a logged decision, or an agent placing orders while a halt is open.

The kill switch has to work without anyone's cooperation. **Before the first paper trade**:

1. The order-placement skill checks for an open `HALT — <strategy>` or `HALT — desk` issue **before every order** and refuses buys while one is open. Sells required by the strategy, and kill flattening, still go through.
2. Every order is tagged with its strategy, so a strategy halt can't block or be bypassed by another strategy's orders.
3. **Live only:** exchange API keys are trade-only, with **withdrawals disabled**, one key per strategy so one can be revoked without stopping the others. Revoking a key is the last-resort kill. Keys are never put in issues, comments, repos or memory.

I can't test (1) until the skill exists. Until it does, nothing trades (see each strategy's "Before the first paper trade").

## Micro-cap Convex at $300

Micro-cap's draft policy (PR #3) is sized at EUR 1,000 with about 20 positions and 3 tranches. At **$300**, that is about $15 a position and **$5 a tranche**, which fails its own order-minimum rule (venue minimum ≤ half a tranche; minimums are about $5–10). Something has to change in `strategy.md`: fewer positions (about 6–8 at ~$40), fewer tranches, or both. Its L1 cap (5% of sleeve per position) would then need to rise to match. That's a strategy and capital change for Rafael and Nadia (Nadia's decision: Capital below). I'll review it on PR #3 and on Rafael's `strategy.md` PR. **Micro-cap doesn't start paper at $300 until the sizing is fixed.** The desk limits above assume Micro-cap's losses are capped at its $300.

## Capital

*Drafted by Nadia.*

### Allocation (paper, USD)

| Strategy | Sub-sleeve | Share | Why this size |
|---|---|---|---|
| Majors Trend | **$450** | 45% | The most liquid book and, if the backtest holds, the shallowest drawdowns. Its edge is the best documented of the three. It anchors the desk. |
| Micro-cap Convex | **$300** | 30% | The desk's only real diversifier (see "Why a desk layer is needed"). It's a lottery book sized to be lost in full, so its size is set by what the family is fine losing, and by order minimums (below). |
| Alt Momentum | **$250** | 25% | The smallest sleeve. It has the momentum-crash loss path, and it's correlated with Majors Trend through the shared filter. It earns more capital by showing that its ranking adds something Majors Trend doesn't. |
| **Desk** | **$1,000** | 100% | Paper notional = Thierry's sleeve (THE-286). |

- **Paper notional = proposed live sub-sleeve** for each strategy. Order minimums and fixed costs bind hardest at the small end, so paper has to run at the real size.
- **USD throughout.** Micro-cap's earlier EUR 1,000 sizing (PR #3) is superseded by $300.
- **No unallocated reserve.** Idle cash sits inside each strategy's own sub-sleeve (C4).
- **Changes only at a quarterly review, by PR** (S1, S3). Capital from a retired or stopped strategy goes back to the desk as unallocated. It isn't handed to the others automatically; moving it is a new allocation PR, and live, a new mandate.
- **Micro-cap's DEX cohort** is paper only and can't go live under any mandate this desk holds. It runs on its own notional, **outside** the $1,000. It's sized the same as the CEX book ($300) so the two records stay comparable.

### Micro-cap Convex at $300: decision

Ingrid is right that the PR #3 sizing doesn't work at $300. I'm **not** cutting to 6–8 positions. `strategy.md` itself says that below 15 positions it isn't a lottery book, just a concentrated bet. A book of 6–8 would be a different strategy, and one that wasn't backtested.

The fix is to cut **tranches**, not names:

- **N = 15** (the strategy's own minimum), held as the target rather than the floor: position ≈ **$20**.
- **2 entry tranches** instead of 3 (day 0 and day ≥5): tranche ≈ **$10**.
- The order-minimum rule stays as written: venue minimum **≤ half a tranche (≈ $5)**. A pair with a higher minimum isn't traded on that venue.
- The per-position cap at cost rises from 5% to **1/15 ≈ 6.7%** of the sleeve. The market-value trim (20% → 15%) is unchanged.

**What this costs.** One less chance to re-check eligibility and to skip a position that has already run (the "more than 50% above tranche 1" rule). Fewer venues and pairs qualify at a $5 minimum. If Hugo's supply at that minimum can't keep 15 slots filling, I'll revisit the split, not the strategy. The likeliest move is about $100 from Majors Trend to Micro-cap.

Rafael makes the `strategy.md` change; I update PR #3's §1 to $300. Ingrid reviews both. Micro-cap doesn't start paper until they merge.

### Promotion order

The strategies are promoted one at a time, each on its own test. **Alt Momentum isn't recommended for live before Majors Trend.** It trades on Majors Trend's regime flag, and it's the more crash-prone of the two. Micro-cap's CEX cohort is independent of both and can go first if it passes first; its test is the longest.

### Review triggers

- At each quarterly paper review: is each sleeve still the right size, given its record so far and its correlation with the others?
- When the Alt Momentum backtest reports its correlation with Majors Trend. **Above 0.85** on daily returns while the regime is on, the desk is running one bet twice, and I'll make the case to fold Alt Momentum's capital into the other two.
- When the mandate sets the live sleeve, if it isn't $1,000.

## Assumptions and what I could not verify

- **Phase:** all three strategies in definition. No capital at risk.
- **Inputs:** THE-286 (Nadia's allocation and caveats), the THE-296 and THE-297 specs, Micro-cap's draft policy and strategy (PRs #3, #4). **Neither Majors Trend nor Alt Momentum has a `strategy.md` or backtest yet.**
- **Not verified:**
  - **The correlation of Majors Trend and Alt Momentum.** I've assumed it's high (same filter, overlapping coins). C2 and DD2 should be re-checked against the Alt Momentum backtest, which reports it.
  - DD1–DD4 have no desk-level backtest behind them; they are set from judgement and the strategy-level halts.
  - The shared regime source (C3) isn't named yet. It belongs in Majors Trend's `strategy.md`.
- **Review:** when each backtest merges, when Micro-cap is re-sized for $300, when the mandate names venues and custody, and at every quarterly paper review.
