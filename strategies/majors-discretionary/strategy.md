# Strategy — Majors Discretionary

**Owner:** Leo (Majors Trader). **Merges:** Nadia. **Phase:** definition. Paper on Bybit Demo starts once this file and `risk-policy.md` are merged and Thierry has approved [THE-319](/THE/issues/THE-319). No live capital.

Thierry's brief (THE-319, 16:23Z 9 Nov): the trade decision comes from the agent's analysis at each wake, not from a fixed signal. So **I decide every trade**, from a written read of the market, inside hard limits that code enforces. The 3-speed breakout from `strategies/majors-breakout/` keeps running beside me as a **rules-only shadow book**. It places no orders. Its job is to show whether my judgement beats the algorithm.

Where this file and `risk-policy.md` disagree on a number, `risk-policy.md` wins.

## 1. Universe and venue

- BTC, ETH, SOL, XRP, DOGE, ADA, each against USDT, **spot only**: long or cash, no leverage, no shorts.
- Bybit Demo (`api-demo.bybit.com`), $2,000 paper sleeve. Crypto Book `book` = `majors-discretionary`.

## 2. Wake procedure

Wakes at **00:05, 08:05 and 14:35 UTC**. The 14:35 wake lands after the 12:30/14:00 UTC US data releases and the 13:30 UTC equity open. Each wake runs these steps in order, and all of them go in one decision-log comment:

1. **Pull the inputs** (§3). The runner prints the data block. I read the news and calendar myself.
2. **Market read**, 3–5 lines: what changed since the last wake and why it matters. "Nothing changed" is a valid read if it is true.
3. **Forecasts:** for each of the 6 coins, the probability that its price is higher 24 h from this wake (close of the 8h candle containing wake + 24 h, against the price at the wake). One number per coin, from 0.05 to 0.95, logged before any order.
4. **Position review:** for each open position, is its thesis still valid? Has its invalidation happened? Hold, tighten the stop, or exit, with a reason. A stop can be tightened, never loosened.
5. **Decide:** either one or more **tickets** (§4), or **no trade, with the reason**. There is no trade quota. A forced trade is how fees eat a small book.
6. **Run the runner** with the tickets. It checks each ticket against the limits (§5), places what passes, rejects what doesn't with the reason, and posts the fills, the shadow book and the score block to the log.

Sam's daily brief (06:00 UTC: event calendar, overnight news, flow numbers) is an input to the 08:05 and 14:35 wakes. At 00:05 I do the news pass myself.

A wake fails if the log is missing, is posted more than 60 min after the scheduled time, or lacks a forecast for a coin or a review for an open position. Two failed wakes in a row halt the strategy (`risk-policy.md`).

## 3. Inputs

| Input | Source | How |
|---|---|---|
| Price, 8h candles, order book, breakout levels | Bybit public spot API | runner |
| Perp funding, open interest, long/short ratio | Bybit public linear API (`funding/history`, `open-interest`, `account-ratio`) | runner |
| Fear & Greed | alternative.me | runner |
| Stablecoin supply (USDT + USDC, 7-day change) | DefiLlama `stablecoins.llama.fi` | runner |
| News: listings, hacks, unlocks, regulation, ETF flows | web search and fetch (CoinDesk, The Block, issuer and exchange announcements, Farside for ETF flows) | me |
| Macro calendar: CPI, FOMC, jobs, other big releases | web search and fetch | me, plus Sam's brief |
| Cross-asset: S&P futures, DXY, US 10y | web fetch | me |
| My open positions, their theses and stops | runner state | runner |

Every source I cite in a thesis carries its timestamp. If a source is older than the previous wake it isn't news and can't be the "why now". No paid data in v1.

## 4. Tickets

A ticket is a JSON object in the wake's decision log. The runner reads the same JSON, so what I wrote is exactly what was traded.

**Entry ticket**

```json
{
  "type": "entry",
  "coin": "SOL",
  "risk_usd": 12.0,
  "entry": "touch",
  "stop": 182.40,
  "target": 205.00,
  "time_limit_utc": "2026-11-16T00:05Z",
  "forecast_24h": 0.62,
  "thesis": {
    "why_now": "...",
    "invalidated_if": "...",
    "sources": [{"what": "...", "url": "...", "at": "2026-11-13T07:40Z"}]
  }
}
```

- **Size comes from the stop.** `risk_usd` is what I lose if the stop fills at its price, at most the per-trade cap. The runner sets quantity = `risk_usd / (entry − stop)`, then cuts it to the per-coin cap. I don't give a quantity.
- `entry`: `"touch"` (IOC limit at the ask + 0.1%) or a limit price, valid until the next wake and then cancelled.
- `stop` is required and is placed as a resting stop-sell on Bybit as soon as the buy fills.
- At least one of `target` or `time_limit_utc` is required. At the target the runner places a resting limit sell, if Bybit allows it next to the stop on the same coin (the Demo test checks this). Otherwise I take the target at the next wake. At the time limit, I exit at the next wake unless that wake's review writes a new thesis and a new time limit.
- `forecast_24h` must equal that coin's forecast in step 3 of the same wake, and be above 0.5. I don't buy what I expect to fall.

**Exit or adjust ticket**

```json
{"type": "exit", "coin": "SOL", "lot": "L-0007", "fraction": 1.0, "reason": "..."}
{"type": "adjust", "coin": "SOL", "lot": "L-0007", "stop": 188.00, "reason": "..."}
```

Exits are IOC at the bid − 0.1%, after the runner cancels that lot's resting stop. An adjust can raise a stop, never lower it, and can move the target or the time limit.

**Adding to a position** is a new entry ticket with its own stop and thesis, and it counts against every limit like any entry. Averaging down below the first lot's stop is not allowed.

## 5. Limits the runner enforces

These are proposed until `risk-policy.md` merges ([THE-320](/THE/issues/THE-320)). I can't override them. A ticket that breaks one is rejected, and the rejection is logged.

- **Risk per trade:** ≤ 0.75% of sleeve NAV to the stop (about $15).
- **Per coin:** ≤ 25% of sleeve NAV, all lots in that coin together.
- **Positions:** ≤ 4 coins held at once.
- **Pace:** ≤ 2 new entries per wake.
- **Fee budget:** fees plus slippage against the touch ≤ 0.2% of NAV per week (Mon 00:00 UTC to Sun 23:59 UTC). Once it's spent, no new entries until Monday. Exits are always allowed.
- **Daily loss:** −4% of NAV within a UTC day means no new entries that day. −10% means a hard halt.
- **Halt:** NAV ≤ $1,600, two failed wakes in a row, an open `HALT — majors-discretionary` or `HALT — desk` issue, or a ledger that doesn't reconcile to the Demo balances. Ingrid halts, Nadia resumes.
- **No ticket, no order.** The runner places nothing on its own except the resting stops and targets that belong to a ticket.

## 6. Shadow book (rules only)

The merged 3-speed breakout (`strategies/majors-breakout/strategy.md`) runs on a virtual $2,000 from the first wake, at the backtest's cost of 0.15% per side, filled at 8h candle closes. It never places an order. Its positions and levels are printed in every log so I can see them, but they are one input among others, not a signal I must follow.

## 7. Scoring

Posted weekly to the log, and in full at the reviews.

1. **P&L, net of fees**, against:
   - (a) buy-and-hold BTC from the first wake;
   - (b) the rules-only shadow book: the real "AI vs algorithm" test;
   - (c) cash.
2. **Forecast skill:** Brier score of my 24 h forecasts, against:
   - a coin flip (0.5, Brier 0.25);
   - the base rate: each coin's share of up-24h windows over the prior 90 days;
   - the breakout's implied call: the historical up-24h rate when the shadow book is long that coin, and when it is flat, measured from the 2021–2026 data.
   I also report calibration (forecasts bucketed by 10 points against realised hit rates).
3. **Thesis audit:** for each closed trade, did it work, and did it work *for the reason I gave*? A win for the wrong reason counts as luck, not skill.
4. **Costs:** fees and slippage per trade against the touch, and the weekly fee budget used.

**Reviews:** 4 weeks (about 11 Dec): do the machinery and the forecasts work? 3 months (about 13 Feb): is there a P&L edge? Nadia's stop rule: stop if at 3 months my book trails the shadow book **and** my forecasts are no better than a coin flip.

## 8. Every decision is logged with

Strategy and phase; the market read; the six forecasts; each position's review; each ticket in full, or the no-trade reason; the runner's checks and fills; the shadow book; the score block. The decision log is a standing issue; entries and exits also go to the Crypto Book (`book` = `majors-discretionary`), with the thesis in `reason` and the stop / target / time limit in `planned_exit`.

## 9. What would kill it

- My book trails the shadow book after 3 months and my Brier score is no better than 0.25.
- Fees: if the weekly budget binds most weeks, I'm trading too much for a $2,000 book.
- Theses that don't survive the audit: winning trades that mostly worked for reasons other than the one I gave.

## 10. Where I disagree or want it watched

- **The forecast sample is smaller than it looks.** 18 forecasts a day × 28 days ≈ 500, but the six coins move with BTC and three 24 h windows a day overlap. The effective sample is closer to one independent call per day, so about 28 by 11 Dec and about 90 by 13 Feb. I'll report the Brier score with a block-bootstrap interval, so a lucky month doesn't read as skill.
- **The fee budget is tight.** 0.2% of $2,000 is $4 a week. A round trip on Bybit spot costs about 0.2% taker plus slippage, about 0.3% of the traded amount. So $4 buys about 6–7 round trips at 10% of NAV, or about 2–3 at 25%. That fits the 3–10 a week target only with small sizes. I think that's the right pressure, but it should be read as a deliberate cap, not a side effect.
- **Stops vs. sizing.** With $15 at risk and a 25% cap ($500), any stop tighter than 3% gives a full-size position. Tight stops on 8h noise will fill often. I'll mostly set stops at ≥ 1.5× ATR(14) of the 8h candles and size from there.
- **The same BTC bet, six times.** As with the breakout, the six coins are mostly one BTC bet. Three or four longs at once are one trade with four tickets. I'll say so in the read when it's true.
- **No backtest is possible** for my judgement, so the first weeks prove only that the machinery works. That's the 4-week review's job.
