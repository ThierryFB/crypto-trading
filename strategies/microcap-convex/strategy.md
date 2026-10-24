# Strategy

Owner: Rafael (Micro-cap Trader). Nadia merges. Changes go through a PR with the evidence; until a change merges, this version binds.

**Phase: definition.** No trading, paper or live. Paper starts only once `risk-policy.md` is merged and the `order-placement` skill exists.

**Inputs:** Sam's base rates (THE-271), Hugo's watchlist supply and depth scan (THE-272), Sam's backtest of these rules (THE-273), Nadia's decisions on the draft (THE-274), Thierry's sleeve indication (THE-270), Nadia's sizing changes (THE-282), and David's scope change adding a paper-only DEX cohort (THE-267, 2026-10-24; `risk-policy.md` §1a). Drafted on THE-269 (rev 3); DEX cohort on THE-295.

**Not in this file, by design:** risk limits, halt levels, capital and the paper→live promotion test (`risk-policy.md`); watchlist criteria and revocation triggers (`watchlist-criteria.md`, Hugo); order mechanics (the `order-placement` skill).

## 0. Thesis and what the book has to do

Thierry's thesis (THE-261): lose on most positions, and make it back on a few very large winners. The book is a basket of small, equal, fully-losable bets on watchlisted $5M–$50M tokens. Exits are staged so that a winner first returns its cost, then banks profit at higher multiples, and leaves a residual to ride the tail.

**Random entries don't clear 1× in today's market under any exit design.** Sam backtested the rev 2 rules on every in-band token-week from 2017 to April 2025 (144k entries, dead tokens included, 1.5% cost per side, weekly closes; THE-273). Mean multiple per position, with the regime filter on:

| Entries | Rev 2 rules | Buy-and-hold, same window | No ladder, same trail | **These rules (40% trail)** | Share reaching T1 | Median position |
|---|---|---|---|---|---|---|
| 2017–21 | 2.16× | 2.55× | 2.48× | **2.28×** | 48% | 0.54× |
| 2022–25 | 0.84× | 0.85× | 0.81× | **0.89×** | 16% | 0.38× |

What that says:
- **Exits can't fix it.** Every exit variant Sam ran lands between 0.63× and 0.92× for 2022–25 entries. Exit design moves the result by about ±0.1×. The missing +0.1–0.15× has to come from selection.
- **Break-even is about 24% of positions reaching T1 at today's payoffs.** Positions that fill T1 average 2.9×; the rest average 0.42×. Random entries managed 15%. In 2017–21 the break-even was 19%, and random entries got 38%.
- **The ladder loses to holding in a bull and is a wash today.** In 2017–21 it gave up 0.39× against buy-and-hold (90% CI −0.59 to −0.21). In 2022–25 it was −0.01× against buy-and-hold and +0.03× against no ladder. What it reliably buys is **less dependence on one name**: the top 1% of positions supply 9–12% of payoff with the ladder, against 21–30% without it. Its median outcome is also a little higher. The ladder stays (Nadia, THE-274): Thierry asked for staged exits, and halving one-ticket dependence is what makes a 40-entry paper sample readable. What it costs is measured in paper by a no-ladder shadow on every entry (§7).
- **Losers recover more than I assumed.** Positions that never reach 3× recovered 0.47× of cost in 2022–25 and 0.33× in 2017–21, mostly through the 12-month time stop.
- **The regime filter is worth keeping.** It nearly doubles the 2017–21 result (1.23× to 2.16×) and adds about 0.05× today. It doesn't make today profitable on its own.
- **Biases cut both ways.** Weekly closes understate an hourly-close ladder by about +0.03× to +0.12× today. Costs of 1.5% per side are probably light for this band, and 3% would take about 0.03× off. CMC-only data misses the DEX-only left tail.

So the book only works today if **Hugo's gate plus my entry triggers lift the share reaching 3× from about 15% to about 24%.** History can't test that, because the backtest is random entry, not this strategy. Paper is where it gets tested (§7).

## 1. Universe

- **Only tokens approved on the strategy's watchlist, as merged on the default branch.** Hugo's gate (`watchlist-criteria.md`). A token I like that isn't on it goes to Hugo as an issue.
- Market cap $5M–$50M at entry. A held token that grows out of the band stays in; the band applies to entries only.
- **Depth means credible depth on venues where we actually hold accounts and inventory**, summed across them. For the CEX cohort, DEX pool depth counts for zero: a position lives on one venue (§3), so a pool we can't exit into without a transfer doesn't help. DEX depth is in §1a. Credible venues per Hugo: Binance, Coinbase, Kraken, OKX, Bybit. Upbit counts only if we get access. Tier 2 (Bitget, KuCoin, Gate, MEXC) and wash venues (HTX, LBank, GroveX, BTCC…) count for zero.
- **Depth is the median of at least 3 snapshots on different days**, not one reading. Books move 2–3× within a day.
- **Depth floor: $50k summed credible ±2% bid depth.** This is a **market-quality filter**, not an exit-capacity limit: at a EUR 1,000 sleeve no position comes near needing that depth to exit (§3). What the floor screens out is manipulated or hollow markets, where a quoted price can't be traded. Hugo estimates ~30 tokens (20–45) pass the gate at that floor across the 5 credible venues, against the ~35 approvals needed to fill 20 slots over 12 weeks. That's tight but workable.
- **Venues:** one venue is enough to trade at this size, since each position lives on one venue (§3). Accounts on two or more of Binance, OKX, Bybit and Coinbase widen the watchlist, because only depth on our own venues counts. Kraken alone supports about 5 passing tokens, which isn't a book. Venues and custody are Thierry's call (THE-270).

Sample against the floor (Hugo's summed credible depth, one snapshot, 2026-10-16):

| Token | Summed credible ±2% bid depth | Clears $50k? | Hugo's preliminary gate read |
|---|---|---|---|
| SSV | ~$230k | Yes | Conditional (mint allowance, Labs wallet) |
| API3 | ~$153k | Yes | Fails (staking unlocks) |
| EUL | ~$100k | Yes | Fails on concentration unless the Safes are treasury |
| FLUX | ~$78k | Yes | Fails (team reserves to hot wallets) |
| MOG | ~$68k ($50k of it on Kraken) | Yes | Passes |

Depth is not what limits this sample; the gate is. None of the five is approved until Hugo's criteria merge.

## 1a. Two cohorts: CEX and DEX

DEX tokens are in scope **for paper only**, as a separate cohort (`risk-policy.md` §1a). Everything in this file applies to both cohorts unless a rule is marked CEX or DEX. The chain isn't chosen yet (Hugo's scan), so the DEX rules are written for any single chain that passes the 0.5% fixed-cost test (§6).

- **Own book.** The DEX cohort runs its own EUR 1,000 notional book, with its own N (20 target, 15–25), tranches, pace limits and NAV trim (§2, §3), all counted within that book. It is never pooled with the CEX book: neither funds, absorbs or offsets the other, and the two are reported apart.
- **Cohort assignment.** A token listed on a CEX we use (one where we hold an account, §1) is **CEX cohort**. It is DEX cohort **only if no CEX we use lists it**. The cohort is fixed at tranche 1 for the life of the position:
  - a DEX-cohort token that later lists on one of our CEXs keeps its open position on-chain, and exits there; its next new position, if any, is CEX cohort;
  - a CEX-cohort token delisted by our venue exits under the delisting rule (§5). It doesn't move to the DEX book.
- **Universe.** Same gate (Hugo's DEX criteria for the chosen chain), same $5M–$50M band.
- **One chain, one wallet.** Each DEX position is bought, held and sold on the one supported chain, through one router, from one wallet. No bridging; a bridge fails the 0.5% test and adds a contract risk.
- **DEX depth** is the ±2% bid depth computed from pool state, summed across the pools on the supported chain that the router routes through and that Hugo's gate counts (his LP-lock test, F8). It uses the same median of at least 3 snapshots on different days and the **same $50k floor**. The floor is there to screen out hollow markets, and that matters more on a DEX, not less. If too few tokens clear it, the cohort retires on supply (`risk-policy.md` §4); I don't lower the floor to fill a book.
- **Terms.** For the DEX cohort, "credible depth" and "credible volume" everywhere in this file mean DEX depth (this section) and organic volume (§2). That includes the depth floor and eligibility (§1, §2), the depth cap (§3), and the liquidity-collapse and dead-token rules (§5).
- **No venue minimum.** DEX swaps have no minimum order. The 0.5% fixed-cost test (§6) plays that role.

## 2. Entry

### Eligibility (all must hold at **each** entry tranche)
1. Approved on the merged watchlist, not suspended by Hugo, and strategy not halted.
2. Depth floor met (§1), and depth ≥ 2× the full target position.
3. No scheduled unlock or known treasury release above 2% of circulating supply within the next 30 days (matches Hugo's proposed revocation trigger).
4. **Regime on:** BTC's last weekly close is above its 30-week average. When it isn't, no new positions start and pending tranches 2–3 wait (cancelled if the regime is still off after 21 days). Open positions keep their exit rules.
5. Room in the book: position count and weekly pace limits (below).

### Trigger (one of)
- **A. Neglected base.** Price is in the bottom third of its 180-day range, 30-day realised volatility is below its 180-day median, and 30-day average credible volume is at least 0.8× its 90-day average. This buys quiet tokens that are still trading, before anyone cares.
- **B. Breakout from a base.** A daily close above the 90-day high, credible volume that day at least 2× its 30-day average, and price no more than 2.5× its 90-day low. This catches the start of a move without buying one that's already run.

### DEX cohort: volume and price inputs
DEX volume is cheap to fake: a wallet can trade with itself at the cost of the pool fee, and bots inflate both volume and trade counts. Both triggers lean on volume, so on the DEX cohort they use filtered inputs and B gets stricter. These are my read; none of it is backtested (§8).

- **Organic volume** replaces credible volume in both triggers. It is volume in the pools that count for depth (§1a), after excluding:
  - wallets whose buys and sells in the same UTC day net to less than 10% of their gross (round-trippers);
  - trades in the same block as an opposite trade from the same signer or bundle (self-trades and sandwiches).
  Aggregator-reported volume is never used raw.
- **Prices** for triggers, closes and ladder levels (§4) are the deepest counted pool's time-weighted price over the last 10 minutes of the period, not the last trade. One block can't then set a close.
- **Trigger A** also needs the 30-day average of daily unique trading wallets to be at least 0.8× its 90-day average. A quiet token has to still be traded by people, not just by volume.
- **Trigger B** also needs, on the breakout day:
  - unique net-buyer wallets at least 2× their 30-day daily average;
  - the top 5 wallets at no more than 50% of organic volume;
  - **confirmation:** the next daily close also above the prior 90-day high. This costs one day of the move. Painting one daily close is cheap on a DEX; painting two in a row is not.
  - **Tranche 1 is bought on the confirmation close**, not the breakout close. At that close the 2.5×-of-90-day-low cap and the "not a trigger" price rules (up more than 100% in 14 days, more than 3× the 90-day low) are checked again, on the confirmation close's price. If any fails, there's no entry: the extra day doesn't let in a token that has already run. Tranches 2–3 count their day ≥5 and day ≥10 from the confirmation close.
- **Listing date** for the 14-day exclusion is the token's first pool creation on any chain.
- **Sell check at each buy.** Before each DEX tranche, the router must also quote a sell of the full target position. If the sell won't quote, or shows a transfer tax, there's no buy, and the token goes to Hugo as a possible honeypot.

### Not a trigger
- Price up more than 100% in 14 days, or more than 3× its 90-day low. I don't chase.
- The first 14 days after a new listing, and listing-announcement pumps.
- Social or influencer hype on its own, or headline volume from wash venues.
- **Averaging down.** The only buys below cost are the scheduled entry tranches.
- Re-entering a token within 30 days of a loss exit on it.

### Spreading entries over time
- Each position is built in **3 equal tranches**: day 0, day ≥5 and day ≥10. Each tranche re-checks eligibility, but not the trigger.
- If price is more than 50% above tranche 1 before a later tranche, skip the rest. The position stays smaller rather than chase.
- **Book pace:** at most **2 new positions started per week**, and at most **10% of the sleeve deployed per week**, per cohort book. A full book takes at least 10 weeks, longer when the regime is off. It isn't filled on one day's mood.
- Undeployed sleeve may sit idle for months when the regime is off; that is accepted. Where it sits is a risk-policy and mandate question, not decided here.

## 3. Sizing and portfolio construction

- **Equal cost per position.** Each position can go to zero, so equal cost is equal risk. Target cost = sleeve ÷ N.
- **N = 20 target, minimum 15, maximum 25** (Hugo's supply at $50k supports ~20). Below 15 concurrent positions it isn't a lottery book, just a concentrated bet. If the watchlist can't supply 15, I say so instead of oversizing.
- **Depth cap:** position cost ≤ **50% of summed credible ±2% bid depth on our venues** at each tranche (`risk-policy.md` L2). Actual size = min(sleeve ÷ N, depth cap). At this sleeve size the cap never binds (below).
- **One venue per position.** Each position is bought, held and sold on **one venue**, with no cross-venue transfers. A transfer's fixed cost would fail the 0.5% test in §6 at this order size.
- **Venue choice per token:** where a token trades on more than one of our venues, use the one with the **cheapest base-tier taker fee**, provided its minimum order and depth pass. Base-tier taker fees are about 0.10% at Binance, OKX and Bybit, 0.40% at Kraken and 0.60% at Coinbase (checked on each venue's fee page at paper start). Coinbase's 0.60% alone uses 40% of the 1.5% per-side cost assumption from THE-273.
- **Impact caps per order** (set by Ingrid in `risk-policy.md`): buys **1.5%** from mid, normal exits (stage sells, trail, time stop, dead-token exit, trims, liquidity reductions) **2%**, forced exits (revocation, delisting) **5%**, emergency exits (exploit or contract compromise, venue insolvency signal) **10%**. Minimum gap between orders on the same venue: 1 hour, 15 minutes for emergency exits. A sell bigger than its cap is split over time, and across venues only where the position is held on more than one, which at this size it isn't. At EUR 50 a position, no sell comes near a cap.
- **Maximum share of the sleeve:** 5% of the sleeve at cost (1/20). Because winners grow, a market-value cap also applies: if one position goes above **20% of sleeve NAV**, trim it back to **15%** (proposed; Ingrid sets the actual limits).
- **Sleeve size** is set in `risk-policy.md`. Paper runs at **EUR 1,000**. Thierry's live indication is **EUR 1,000–2,000** (THE-270, non-binding). The strategy's **capacity ceiling stays at USD 500k**: a property of the watchlist's depth, not a plan.

What EUR 1,000 means per order (N = 20, 3 entry tranches, EUR/USD about 1.15):

| Item | Size |
|---|---|
| Position (sleeve ÷ 20) | about **EUR 50** |
| Entry tranche (position ÷ 3) | about **EUR 17 (≈ USD 19)** |
| Smallest normal stage sell (T1, ~34% of a 3× position) | about EUR 50 of value |
| ±2% depth needed for the depth cap | about USD 115, against a $50k floor |

**The depth cap never binds at this size**: every token that clears the $50k floor has over 400× the depth a position needs. What binds instead are venue minimum orders and fixed costs per order (§6). At EUR 2,000 the numbers double and the conclusion holds. At the USD 500k ceiling a position is USD 25k and needs USD 50k of depth, which is the floor; above that the floor would have to rise.

## 4. Staged exits on gains

Multiples are on the position's **average cost including fees** (on DEX that includes pool fee, gas and the MEV allowance). A level counts as hit on an **hourly close** on the main credible venue (DEX: the pool's time-weighted close, §2), not on a wick. The ladder, trail and stops are the same for both cohorts. DEX sells go through the same router as the buys. Tranche sizes are fractions of the original quantity.

| Stage | At | Sell | Cumulative proceeds (× cost) | Still held |
|---|---|---|---|---|
| T1 | **3×** | ~34% (enough to return full cost plus fees) | ~1.0× | 66% |
| T2 | **6×** | 20% | ~2.2× | 46% |
| T3 | **12×** | 15% | ~4.0× | 31% |
| T4 | **25×** | 10% | ~6.5× | **21% residual** |

**Trailing rule (from T1 onward, on everything still held), on weekly closes:** exit the rest on a weekly close at or below **60% of the highest weekly close** since entry (a 40% trail). Before T1 there's no trailing stop; §5 governs.

**Why these levels:**
- **T1 at 3×, not 2×.** Micro-caps often double and then round-trip. Selling half at 2× would bank more of those moves, but it halves the tail, and the tail carries the book. At 3×, selling about a third makes the rest free. Backtest: T1 at 2× changes nothing today (+0.00×) and costs 0.32× in a bull (CI −0.47 to −0.19). It does lift the median (1.01× vs 0.54× in 2017–21), but that isn't worth the mean.
- **T2–T4 roughly double each time,** so profit gets banked at each order of magnitude while 21% still rides beyond 25×.
- **The trail is 40%, on weekly closes.** In earlier drafts I set it wide (60%, then 50%) because half of the runs that went on to reach 10× fell 57% or more from a high along the way. The backtest says otherwise once the ladder has already banked cost: a 40% trail beat 60/50 in both eras, by +0.12× in 2017–21 (CI +0.05 to +0.19) and +0.05× in 2022–25 (CI +0.03 to +0.07). A 70% trail lost 0.04× today. It was tested only on weekly closes, so it can't trigger mid-week; I keep it weekly for that reason. Read it as "narrower than 60% is no worse", not as a precise optimum.
- **The trail is worth having at all.** Holding the residual with no trail lost 0.14× today.
- **The ladder, not the trail, does the profit-taking.** 9 in 10 tokens that peak give back half or more within a year. The tranches bank profit on the way up and the trail protects the remainder.
- **What the ladder costs.** In a 2020-type market it gives up about 13% of the mean (2.16× vs 2.48× with no ladder, CI −0.73 to +0.05). Today it adds +0.03×. Its real job is halving one-ticket dependence (§0). Paper measures the cost directly with a no-ladder shadow on every entry (§7).

**What outcomes look like (gross multiple of cost, before fees and slippage):**
- **Peaks at 2.5× then fades:** no tranche fills. The outcome is whatever §5 recovers. This is the accepted cost of the design.
- **Peaks at 3×, trails out at 1.8×:** 1.0 + 0.66 × 1.8 ≈ **2.2×**.
- **Peaks at 5×, trails out at 3×:** 1.0 + 0.66 × 3 ≈ **3.0×**.
- **10× outcome** (peaks at 10×, trails out at 6×): 1.0 + 1.2 + 0.46 × 6 ≈ **5.0×**. Marked at the 10× peak and still held: ≈ 6.8×.
- **50× outcome** (peaks at 50×, trails out at 30×): 1.0 + 1.2 + 1.8 + 2.5 + 0.21 × 30 ≈ **12.8×**. Marked at the peak: ≈ 17×.
- **100× peak, trails out at 60×:** ≈ 19×.

These assume a clean run up. With a 40% trail, a run that falls 40% on a weekly close between levels exits there, before reaching the next one.

The ladder gives up a lot of the very top in exchange for banking profit on the way up. That's the staged exit Thierry asked for.

## 5. Exits on losses or a broken thesis

| Event | Action |
|---|---|
| **Watchlist revocation** (Hugo's triggers include exploits, unscheduled mints, admin-key changes, a Binance Monitoring tag, insider moves to exchanges, ≥2% unlocks within 30 days) | Exit in full, starting immediately; done within 24h if the forced-exit impact cap allows, otherwise at the cap's pace. |
| **Watchlist suspension** (unconfirmed exploit, pending mint vote, missed re-check, depth below floor 1–2 days) | No new tranches; hold. Act on Hugo's re-check within 72h. |
| **Exploit or contract compromise** (protocol exploit, unexpected mint, ownership regained, blacklist/pause enabled, proxy upgrade, LP unlocked or pulled) | Exit in full immediately under the **emergency-exit cap: 10% impact per order, 15 minutes between orders on the same venue** (Ingrid, `risk-policy.md`). An exploited token can lose most of its value within hours, so speed is worth more than price. Don't wait for the revocation; notify Hugo and Ingrid. |
| **Delisting** announced on the venue I hold on, or on any venue with ≥30% of credible depth | Exit within 24h of the notice, well before the delisting date. |
| **Liquidity collapse:** summed credible ±2% bid depth below 2× the position's current value on 3 consecutive daily checks | Reduce until the position is ≤50% of depth. Exit in full if credible depth falls below $15k or 30-day credible volume falls below 30% of its level at entry. |
| **Time stop:** 12 months after tranche 1, T1 hasn't filled | Exit in full and recycle the capital. No extension. |
| **Six-month review:** T1 hasn't filled | Review with Hugo whether the token is still clean. No automatic sale. |
| **Dead-token check:** at 90 days, price below 0.3× cost **and** credible volume down more than 50% since entry | Exit and recover salvage value. |
| **DEX only: pool drained, or the router stops routing the token** | Forced exit at whatever liquidity is really there, through any route on the same chain, down to zero. |

Once T1 has filled, the time stop no longer applies; the trailing rule governs.

**Why 12 months:** a 10× typically took 8–9 months to reach its first 10× weekly close (median 259 days). A 180-day stop would have cut about two-thirds of them. The backtest supports 12 months and says not to go longer: in 2022–25, a 78-week stop cost 0.11× and no stop cost 0.21×, because losers keep bleeding. A 26-week stop was no better today and cost 0.18× in a bull. An extension to 18 months changed results by 0.03× or less, so there is none. The dead-token check is also worth 0.03× or less in the backtest. I keep it because it's cheap and it gets out of tokens heading for zero, which CMC data models poorly.

**Price stops: none.** Size already caps the loss at 100% of a small position. Micro-cap books wick through any stop, and half of eventual 10× runs fell 57%+ from a high along the way, so stops would mostly cut future winners. Instead, a **−70% drawdown from cost triggers a review**: I ask Hugo whether the token is still clean. If he revokes it, the revocation exit applies. A −70% move on its own doesn't trigger a sale.

## 6. Paper-trading realism

Paper has to be at least as hard as live, or it will flatter the strategy.

- **Fills walk the real book.** At each decision, capture the venue's L2 order book (CEX) or pool state (DEX) at least 60 seconds after the decision. The fill is the VWAP walking down the levels from best price; there are no mid-price fills, and orders larger than displayed depth inside the limit fill partially. Store the snapshot reference in the decision log.
- **No reused snapshots.** Two sells never fill against the same snapshot. The next sell uses a fresh one at least 1 hour later, so depth isn't double-counted.
- **Only our venues.** Paper fills only on venues where we'd actually hold accounts (§1), never on a venue we couldn't use live.
- **Resting limit orders** fill only if trades print *through* the level, not merely touch it.
- **Fees at our real tier:** taker fees per venue, with no VIP tiers assumed. On DEX: pool fee, gas at the block's price, and a MEV/sandwich allowance of 0.5% unless a private route is specified.
- **Forced exits use actual liquidity.** If a venue delists or a pool is drained, the paper position exits at whatever was really there, down to zero.
- **No look-ahead:** signals use only data available at the decision time, and daily/weekly closes only after the close.
- **No survivorship bias:** dead and delisted tokens stay in the record at their real outcome.
- **Venue minimum orders.** A sell below the venue's minimum order for the pair doesn't fill. The residual is carried as **dust** and marked at **zero** once it's unsellable. That is what would happen live. (A pair is traded on a venue only if its minimum is ≤ half an entry tranche; `risk-policy.md` §1.)
- **Fixed costs per order.** If any fixed cost of an order (gas, priority fee, transfer, withdrawal) is above **0.5% of the order's value**, the order isn't placed, on paper or live. At EUR 17 a tranche that's about USD 0.10. This rules out **Ethereum-mainnet DEX** at this size; DEX orders are allowed only on chains where a swap clears the test. A DEX tranche that fails it is skipped, as under the 50% rule (§2).
- **No transfers per position.** Each position stays on one venue (§3). The sleeve is funded once per venue, and that one-off conversion and transfer cost is charged to paper at the start.
- **DEX fills** (DEX cohort):
  - At each decision, capture a **pool-state snapshot** of every counted pool and a **router quote for our exact size**, both at least 60 seconds after the decision and from the same block. Both references go in the decision log.
  - Two fills are computed: the walk through the snapshot, net of the pool fee, and the router quote. **The worse of the two is the scored fill.** The pool fee is charged once (the quote already includes it).
  - On top: gas and priority fee at that block's price, and the **0.5% MEV allowance** unless the order uses a private route that the order-placement skill specifies.
  - Every DEX order is a swap at the router. There are no resting orders, so the resting-limit rule above doesn't apply.
  - The impact caps (§3) are measured on the scored fill against the pool's pre-trade price. A swap whose scored fill breaks its cap isn't placed; it's split over time, as on CEX.
  - **Dust:** a sell whose gas and priority fee fail the 0.5% test is treated like a CEX sell below the venue minimum. The residual is carried as dust and marked at zero once unsellable. If it later regains enough value to pass the test, it's sold under the normal exit rules.
  - The sell check at each buy (§2) uses the same quote source, logged with the buy.
- **Slippage audit:** keep a running comparison of modelled vs book-walked slippage, so the live/paper gap can be measured at promotion.

**Record-keeping gap:** the Crypto Book v1 allows one exit per entry, in full, with no partial exits. Staged exits don't fit that. I propose asking for partial-exit support in the Crypto Book (Nadia → David). Until then, the full tranche history lives in the order-placement log, and the Crypto Book gets the lot structure that skill defines.

## 7. What would show the edge isn't real

**The pre-paper gate failed.** In rev 2 of the draft I set a gate: redesign before paper if the ladder lost to buy-and-hold, or if the book stayed below 1× in 2022–2026 with the regime filter on. In the backtest (THE-273) the ladder lost to buy-and-hold in 2017–21 and tied it today, and the book stayed below 1× today. Both conditions were met. The gate failed.

I made the exit changes the backtest supports (§4, §5) and did not redesign further, because no exit variant clears 1× on random entries today; only selection can. **Nadia decided to go to paper anyway** (THE-274): paper puts no capital at risk, and the promotion test asks exactly the open question, whether selection beats random. The gate was mine and it failed; the decision to proceed is hers, and it is recorded here as such.

**The pass/fail tests and their thresholds live in `risk-policy.md` §3 (promotion) and §4 (retirement), not here**, so the two can't drift apart. Below is what I'd read as evidence against the edge, and where each is tested.

1. **Selection adds nothing.** Our T1 rate isn't clearly above the 5-draw random shadow control on the same dates. That is the core question; §0 shows the book only works if selection beats random. → `risk-policy.md` P5, and retirement §4.
2. **Hit rate below break-even.** Too few resolved entries reach T1 for the book to pay at today's payoffs, or the rate is below the random-entry base rate. → P4, and retirement §4.
3. **The ladder is destroying value.** The same entries do clearly better with no ladder. → the no-ladder shadow, pre-registered in `risk-policy.md` §2; reported, not pass/fail. As reported diagnostics I also track the same entries under alternative multiples (2×/4×/8×).
4. **One lucky ticket.** The result turns negative without the best one or two positions. That is luck so far, not evidence. → P6.
5. **Winners that couldn't be sold.** Stage sells that weren't fillable at the logged size within the impact cap. → P7, and retirement §4.
6. **Costs eat the edge.** Average cost per side too high, or modelled slippage consistently below book-walked slippage. → P8. As a diagnostic I also report the share of gross gains taken by fees and slippage.
7. **Benchmarks** (reported diagnostics): BTC buy-and-hold, and an equal-weight basket of the in-band universe. If the book underperforms these, the micro-cap risk isn't paid.
8. **Loser recovery** (reported diagnostic): positions that never reach T1 recover much less of cost than the backtest's 0.47× for 2022–25 entries.
9. **Supply** (reported diagnostic): the watchlist can't sustain at least 15 concurrent positions, so the book can't diversify (§3).
10. **Regime** (reported diagnostic): all the gain comes from one market-wide rally and is explained by BTC beta, not token selection. P2 requires the paper period to include a bad tape.

A material change to this file resets the paper clock for the part it touches (`risk-policy.md` §2).

## 8. Assumptions and open questions

- **Inputs used:** the brief (THE-267, THE-269); Sam's base rates, round-trip, drawdown, time-to-peak and regime figures (THE-271, as of 2026-10-16, CMC weekly closes, medium-high confidence on direction, low-medium on exact percentages); Hugo's supply and depth scan and proposed revocation triggers (THE-272, one snapshot 2026-10-16, pass rate a guess from 5 tokens); Sam's backtest of the rev 2 rules and its variants (THE-273, as of 2026-10-16; medium confidence on the direction of the comparisons, low on exact levels, because 2022–25 is only 14 calendar quarters); Hugo's five in-band Crypto Book analyses; Nadia's decisions (THE-274); my own read for the ladder levels and the entry triggers.
- **DEX cohort:** nothing about it is backtested. Sam's data has no DEX-only tokens, so the base rates, the 24% break-even and the ladder results in §0 and §4 are CEX-era numbers carried over. The volume filters and the B confirmation in §2 are my read. The DEX cohort's own sample and control (`risk-policy.md` §1a, §3) are the first test of any of it. What would show the filters are wrong: DEX trigger-B entries reaching T1 no more often than its random control, or most organic volume turning out to come from a few wallet clusters.
- **Known weaknesses:** Sam's data is weekly and CMC-only, so the DEX-only left tail is missing and the 40% trail hasn't been tested on intra-week moves. The backtest is random entry: the entry triggers, tranches, watchlist gate, depth rules, pace limits and NAV trim are all untested. Forced exits (revocation, exploit, delisting) aren't in the data. Results are per position, with no capital recycling.
- **Sizing assumptions:** EUR/USD about 1.15 and venue minimums about USD 5–10 per order, both checked at paper start. If the mandate is set above EUR 2,000, §3 and §6 are re-checked before live.
- **Open:** the DEX chain and router (Hugo's scan), and with them Hugo's DEX gate and whether enough tokens clear the $50k floor on pool depth; venues and the final live sleeve figure (THE-270); where idle cash sits (risk policy / mandate); the 20%/15% NAV trim (Ingrid); partial exits in the Crypto Book (Nadia with David).
