# Risk policy

Owner: Ingrid, with capital and promotion criteria from Nadia. Merges only with Ingrid and David approving (and, once live, Thierry's confirmation).

**Phase: definition.** No capital, no mandate, no trades.

## Limits and halt levels

*Ingrid drafts this section.* Open inputs from `strategy.md`: exit impact caps (2% normal / 5% forced proposed), the 20%-of-NAV trim to 15%, per-position cost cap, where idle cash sits.

## Capital and promotion criteria

*Drafted by Nadia.*

### Why the test looks like this

A lottery book's result comes almost entirely from one or two positions. A year of paper can look excellent because one token went 40×, or terrible because none did. Neither says much about the edge.

The backtest behind `strategy.md` (THE-273) also shows that **random in-band entries lose money today under every exit design tested** (0.63×–0.92× per position, 2022–25). The book only works if the watchlist gate plus the entry triggers lift the share of positions reaching T1 (3×) from about 15% to about 24%. History can't test that. Paper is that test, so the promotion test is built around it, not around the P&L line.

### 1. Paper capital

- **Notional paper book = the proposed live sleeve.** Micro-cap slippage depends on size, so paper at a different size gives the wrong cost picture. Until Thierry gives a figure (THE-270), the placeholder is **USD 100,000**: the smallest size in `strategy.md` §3 at which the depth floor and caps actually bind. The strategy's capacity ceiling is **USD 500,000**.
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
| P2 | Regime coverage | The period includes a drawdown of ≥ 30% from peak in an equal-weight basket of the watchlist. If not, paper is extended. | Tests the book in a bad tape, not only a good one. |
| P3 | Sample | ≥ **40 entries with a resolved T1 outcome**: T1 filled, or the position closed without it (time stop, revocation, other forced exit). | T1 can take up to 12 months to resolve, so open positions don't count. In practice P3, not P1, sets the paper length; expect 18–24 months. |
| P4 | Entries clear break-even | Share of resolved entries reaching T1 ≥ **24%**, or the break-even share recomputed from the paper book's own payoffs if that is higher. 90% CI reported. | Below break-even the book loses money by construction. 24% is the THE-273 break-even at today's payoffs; random entries got about 15%. |
| P5 | Entries beat the control | T1 rate ≥ **10 pp above** the shadow control's, on the same dates. 90% CI reported. | The edge being claimed is selection. This is the measurable part of it, and it doesn't depend on catching one 50×. |
| P6 | Net result vs. control, and luck | Net paper P&L after fees and slippage ≥ the control's. P&L is also reported with the best 1 and best 2 positions removed. **If one position accounts for more than 100% of net profit and P5 fails, the strategy isn't promoted**, whatever the headline. | Separates a lucky ticket from a working method. |
| P7 | Exit fillability | Every triggered stage sell was fillable at the logged size against the logged book within the normal exit impact cap. Unfillable sells are counted and reported. | Paper winners that couldn't be sold aren't winners. |
| P8 | Cost realism | Average cost ≤ **3% per side**, and modelled cost within 25% of measured cost on a sample of books checked after the fact. | THE-273 assumed 1.5% per side; above 3% the thin edge is gone. |
| P9 | Discipline | 100% of decisions logged with a rationale. **Zero** entries off the watchlist. **Zero** hard-limit breaches. Every revocation exit started immediately and every stage sell executed within 24 h of its trigger. | Live is autonomous, so paper must show the rules hold without supervision. |
| P10 | Drawdown | The paper book never breached a halt level above, or every breach was reviewed and is understood. | |

**Not a promotion criterion:** a positive headline P&L on its own. A positive P&L that fails P4 or P5 means "extend paper", not "go live".

### 4. Retirement during paper

Nadia recommends retiring the strategy, rather than extending paper, if at any quarterly review after **25 resolved entries**:

- the T1 rate is **at or below the shadow control's**, meaning the entry triggers add nothing; or
- the T1 rate is **below 15%** (the random-entry base rate), meaning selection is worse than random; or
- more than a third of triggered stage sells were unfillable, meaning the universe is too thin for this exit design at this size.

Each case is reported to David with the numbers. Paper risks no capital, but the desk's attention isn't free.

### 5. Live capital and scaling

- **Live sleeve:** Thierry's figure, set in the mandate, no higher than the USD 500,000 ceiling. It must be money he is fine losing entirely. Venue and custody are his call (THE-270). The strategy needs accounts on at least two of Binance, OKX, Bybit and Coinbase.
- **Stage L1:** live with **25%** of the mandated sleeve for ≥ **6 months**. P7–P10 continue live, and live slippage is compared with the paper fill model.
- **Stage L2:** full sleeve. Requires Ingrid's sign-off on L1, Nadia's recommendation to David, and a **new mandate confirmation** from Thierry. A mandate never expands itself.
- **No profit recycling above the cap.** Gains above the mandated sleeve are swept out each quarter. The cap is a ceiling on capital at risk, not a starting balance.

### Assumptions and review triggers

- **Assumes** T1 (3×, returns cost) as defined in `strategy.md` §4. If T1 moves, P4/P5 move with it and the clock resets for the exit tests.
- **Assumes** the watchlist holds about 15 or more eligible tokens on most days. With fewer, the control becomes "equal-weight the full eligible watchlist".
- **Known limit:** at 40 resolved entries, a 24% T1 rate has a 90% CI of roughly ±11 pp. The test can catch a clear edge or a clear failure, not a marginal one. If P4/P5 are inconclusive at 40, paper is extended; the thresholds aren't loosened.
- **Review:** when Thierry's sleeve and venue answer arrives (THE-270), and at every quarterly paper review.
