# Risk policy

Owner: Ingrid, with capital and promotion criteria from Nadia. Merges only with Ingrid and David approving (and, once live, Thierry's confirmation).

**Phase: definition.** Nothing merges before Thierry approves the discretionary version of [THE-319](/THE/issues/THE-319). The desk-wide limits in [`../desk-risk-policy.md`](../desk-risk-policy.md) also apply, and the tighter limit wins.

## Limits and halt levels

*Drafted by Ingrid.* Written against Nadia's revised THE-319 proposal (9 Nov 16:26Z, §3). Leo decides every trade from his own analysis at three wakes a day (00:05, 08:05 and 14:35 UTC). A rules-only 3-speed breakout runs beside him as a shadow book that places no orders. `strategy.md` for this folder doesn't exist yet. Where a limit depends on it, the limit says so.

**There is no backtest of the trader.** The limits are calibrated on a **zero-skill null model** instead: a trader who enters at random under these limits on Bybit 8h data, Oct 2021 → Nov 2026. It uses random stops of 1.5–3× ATR, exits at the stop or at a random 1–7 day time limit, pays 0.15% per side, and is measured over every 13-week window (the 3-month review). Script: [`risk/null_model.py`](risk/null_model.py). A trader with skill should do better than this. Anything much worse is what the halts are for.

### Definitions

- **Sleeve:** a virtual **$2,000** in USDT on Bybit Demo, tracked by the runner whatever the demo balance is.
- **NAV:** USDT plus every position marked at mid on Bybit spot. Unless stated otherwise, it is measured at each wake and at 00:00 UTC.
- **Day:** a UTC day. Day P&L is NAV against NAV at 00:00 UTC.
- **Week:** Monday 00:00 UTC to Sunday 24:00 UTC.
- **HWM:** the highest daily NAV since the first trade.
- **Ticket:** the order request Leo posts to the decision log *before* the order. It gives the coin, the size, the entry limit, the stop, a target or time limit, and the thesis: why now, what would prove it wrong, and the sources with timestamps.
- **Risk of a trade:** (entry price − stop) × quantity, at the moment it is placed.
- **Cost:** fees plus slippage. Slippage is the fill price measured against the mid at the moment the order was sent.
- **Hard limit:** the runner refuses the order, and a breach means a halt. **Review trigger:** I write a note within 24 h, and nothing halts.

### Position and exposure limits (hard, enforced by the runner)

| # | Limit | Level | Why |
|---|---|---|---|
| L1 | Instruments | **Spot only:** BTC, ETH, SOL, XRP, DOGE, ADA against USDT on Bybit Demo. Long or cash. No leverage, margin, borrowing, perps, shorting, lending or earn products. Cash is never negative. Perp data (funding, open interest) is an **input only**. | The universe is the one the shadow book and the null model use. Perp data is the obvious route to a "small hedge". It isn't allowed. |
| L2 | Risk per trade | ≤ **0.75% of NAV** to the ticket's stop (about $15). | This is the same total open risk as my 3-speed ruling: 4 × 0.75% here against 12 × 0.25% there, 3% of NAV in both. Zero-skill null model, 13 weeks: median max DD −11 to −12%, p5 −20 to −21%, and NAV ≤ $1,600 in **3–4%** of windows. At 0.5% that is 0.3–0.5%, which would make the floor almost unreachable for a trader with no edge. At 0.75% it stays a real alarm, which is what it's for. |
| L3 | Stop | Every entry carries a stop price on its ticket. Right after the fill, the runner places it on Bybit as a **resting stop-market sell** for the full quantity. The stop may only move **towards** the price, never away from it. It is cancelled only as part of closing the position. | The stop is what makes L2 true. A stop-limit can skip through a fast market, and a stop that gets widened later makes L2 meaningless. |
| L4 | Per coin | ≤ **25% of NAV** in one coin, measured at entry. A buy that would cross the cap is **shrunk to fit**, or skipped if what's left is under 2% of NAV. There is no forced trim after entry. | Same rule as the 3-speed book. With a tight stop, L2 alone would allow far more than 25%. |
| L5 | One position per coin; no averaging down | One open position per coin. Leo may add to it only with a new ticket, only once the existing stop sits at or above its entry, and the combined position must still pass L2 and L4. **Never add below the average entry price.** | Averaging down a losing position is the commonest way a discretionary book breaks its own risk limit without technically breaching it. |
| L6 | Positions | ≤ **4** open positions. | With the six coins all moving with BTC, four is already nearly one bet. |
| L7 | Pace | ≤ **2 new entries per wake**. Adds under L5 count as entries. | This bounds a single bad read of the market to 1.5% of NAV at risk. |
| L8 | Cost budget | Cost ≤ **0.2% of start-of-week NAV per week**. Once it's used up, no new entries until Monday 00:00 UTC. Exits and stop-outs still run, and their cost counts towards the budget. | **This is the control that matters most against drift.** In the null model, a trader who always buys the maximum size as often as allowed hits $1,600 in **11%** of 13-week windows without the budget, and in 4% with it. The budget binds on 18–32% of wakes and holds the book to about 6 round trips a week, inside Nadia's 3–10 target. |
| L9 | Orders | Limit IOC at the touch ±0.1% for entries and discretionary exits. Stop-market for L3. Nothing else: no resting buy orders, transfers or withdrawals. | A resting buy would fill when nobody is awake to check it. |
| L10 | Tickets | **No ticket, no order.** The runner places an order only against a ticket ID that is already in the decision log, and only for that ticket's coin, side, a size no larger than the ticket's, and its stop. | Every position has to trace back to a thesis written before the trade. |
| L11 | Shadow book | The rules-only breakout book places **no orders**. It has its own ledger, marked at the same prices. | An order from the shadow book would mix two records that are meant to be compared. |

**Exits are always allowed.** That covers a thesis exit, a time limit, or a stop, at any time, including while a pause is on. Under a halt, only exits Nadia or I ask for, plus the resting stops, run (see Halt levels).

### Daily and drawdown limits

| # | Trigger | Action | Why |
|---|---|---|---|
| D1 | NAV down ≥ **4%** in a day | **No new entries** until 00:00 UTC. | A tripwire. In the null model it fires on fewer than 1 day per quarter. |
| D2 | NAV down ≥ **10%** in a day | **Halt** until the day is reconciled. | The null model's worst day across 378 windows is −7.2%, with all stops resting. −10% means a crash that gapped through the stops, or a bad mark. |
| D3 | NAV ≤ **$1,600** | **Halt.** I also escalate to David. | 20% of the sleeve. A zero-skill trader gets here in 3–4% of quarters, so reaching it is evidence against the trader, not bad luck. |
| D4 | NAV ≤ **85% of HWM** | Review trigger | The null model's median quarterly drawdown is −11%. Beyond −15%, I want to see the theses. |
| D5 | **6 losing trades in a row**, or **10 stop-outs in a week** | Review trigger, with the drift check below | A losing streak is where size creeps up and theses get thinner. |

### Halt levels

A halt stops **all new entries** and every change to an order except exits. Resting stops stay on the exchange. Discretionary exits during a halt need Nadia or me to ask for them on the halt issue, and the runner logs them. A halt is recorded as an open `HALT — majors-discretionary` issue in this project. The runner checks for it, and for `HALT — desk`, before every buy. If it can't read Paperclip, it refuses the buy. Only Nadia resumes, after my written review. Nothing here limits my authority to halt for reasons not listed.

**Operational**

| # | Trigger | Action |
|---|---|---|
| O1 | **Failed wakes:** 2 in a row. A wake fails if it has no decision log within 60 min of its scheduled time (market read, the 6 forecasts, and either a ticket or "no trade" with the reason), or if it hits a data or order error that it didn't resolve. | **Halt** |
| O2 | **Unreconciled record:** at my 00:30 check, the runner's ledger, the Bybit Demo balances and fills, and the Crypto Book (`book` = `majors-discretionary`) disagree on any quantity or cash, or NAV can't be computed. | **Halt** |
| O3 | **Ticket integrity:** a ticket posted after its order, or edited or deleted after its order went out (the Paperclip comment's `updatedAt` is later than its `createdAt`), or an order whose size, coin or stop differs from its ticket. | **Halt** |
| O4 | **Order outside the runner:** any order or fill on the Demo account with no ticket, an instrument outside L1, or any leverage. | **Kill** (desk kill-switch rules) |
| O5 | **Stop missing:** a position with no resting stop on the venue at my check, or a stop that was moved away from the price. | **Halt.** The runner retries placing the stop first; if the venue refuses, the hourly fallback below applies, and only then is a missing stop a halt. |
| O6 | **Rule breach:** any hard limit above that the runner failed to refuse. | **Halt.** It's also a runner defect. |
| O7 | **Unreviewed change** to this file, to `strategy.md`, or to the runner's limit config or gate code (see Runner independence). | **Halt** |
| O8 | **Fills:** average slippage above **0.15% per side** over the first 10 fills, or over any 20 after that. | Review trigger. L8 and the scoring both assume 0.15% all-in. |

### Discretionary drift: my 00:30 check

Nadia asked whether I want a drift check. **Yes, I do.** The limits above stop the worst cases. Drift is what happens inside them: size, frequency or conviction creeping up, and theses that get thinner or are written to fit the trade. I recompute these from the decision log, the fills and the Crypto Book, **not from the runner's own report**, and post them each week on the daily-review issue:

1. **Ticket before order.** For every fill, the ticket's `createdAt` is earlier than the order time, and the ticket was never edited. A failure is O3.
2. **Size creep.** Share of entries at the L2 or L4 cap, and average risk per trade, compared with the first two weeks. Review trigger if more than half of the entries in a week are at the cap.
3. **Pace creep.** Entries per week, and how often L7 and L8 bind. Review trigger if L8 binds 3 weeks in a row: that means trading for the sake of trading.
4. **Stops.** No stop ever moved away from the price. Share of positions closed at the stop against closed on thesis. A falling share of stop exits alongside time-limit overruns means stops are being avoided.
5. **Re-entries.** Re-entering a coin within 24 h of being stopped out of it needs a ticket that says what changed. If it doesn't, that's a review trigger.
6. **Time limits.** A position kept past its ticket's time limit without a new ticket is a review trigger.
7. **Forecast log.** Missing or late forecasts (not 6 per wake) are a review trigger, because the 4-week skill read depends on them.
8. **Thesis audit.** For each closed trade: did the exit match the thesis's "what would prove it wrong"? I report this with Nadia's scoring. It isn't a limit.
9. **Sources.** The theses rely on web news and social sentiment, which can be wrong or written to manipulate. A ticket whose only source is a single unverified post is a review trigger. The code limits are what contain a thesis built on a false story.

Review triggers go to Nadia as a note. Two drift triggers in the same week, or the same one 3 weeks running, and I ask Nadia to review the trader before the next week's first entry.

### Runner independence

Leo trades the book and also writes the runner that limits him. So:

- The limit values (`limits` in the runner config), the gate code (L2–L10, D1–D3, the halt-issue check) and the ticket check are **risk-policy changes**. They need a PR with my approval, like this file.
- The Bybit Demo key is used **only by the runner**. An order placed any other way is O4.
- I check every limit from the record myself, at 00:30.

### Before the first strategy order

- This file and `strategies/majors-discretionary/strategy.md` are merged on `master`. `strategy.md` covers the wake procedure, the ticket format and the scoring.
- The runner is ticket-driven, enforces L1–L11 and D1–D3, refuses buys while a halt issue is open, and points `limits_source` at this file. I review that PR (THE-321).
- **A resting stop-market sell is tested on Bybit Demo:** placed, triggered or cancelled, and read back. If Demo doesn't support it, the fallback is an **hourly price check in the runner** that sells at the stop without waking an agent, and L3 is met by that check instead. Leo tells me which one before the first entry.
- The decision-log issue is named, and the Crypto Book `book` value is set to `majors-discretionary`.

### Assumptions and what I could not verify

- **Strategy and phase:** Majors Discretionary, definition. No orders placed.
- **Inputs:** Nadia's THE-319 revision (9 Nov 16:26Z) and her THE-320 note. My null model ran on Bybit spot 4h candles fetched 9 Nov, built into 8h bars over 21 Oct 2021 → 9 Nov 2026 (the dates all six pairs have data), with 126 start dates two weeks apart × 3 seeds = 378 windows.
- **Not verified:** the null model fills stops at the stop price, or at the open if price gapped through. Real stop-market fills in a crash will be worse. Bybit Demo's handling of resting spot stops is untested. Demo fill quality against the real book is untested. The null model can't show what a skilled trader, or one whose judgement is consistently wrong, does. That's what D3 and the drift check are for.
- **Desk fit (needs Nadia and David):** the merged desk policy covers a $1,000 sleeve across three other strategies. For paper I treat this $2,000 sleeve as **outside desk NAV**, while the desk operational halts (DO1–DO4) and the kill switch still apply. Cash in USDT rather than USDC (desk C4) is accepted for paper only.
- **Review:** when `strategy.md` merges, after the first 10 fills, and at the 4-week review (about 11 Dec).

## Capital and promotion criteria

*To be drafted by Nadia* (paper capital is $2,000, from THE-319; scoring and stop criteria are in THE-319 §4). I'll review them on this PR.
