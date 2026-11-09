# Majors Discretionary

Desk strategy for Thierry's "active" paper sleeve (THE-319, revised 9 Nov). At three wakes a day, Leo reads the news, macro calendar, derivatives positioning, sentiment and flows. He writes a market read and a 24 h forecast for each coin, and trades from his own analysis. Each trade is a ticket with a hard stop and a written thesis. Universe: BTC, ETH, SOL, XRP, DOGE and ADA against USDT on Bybit spot, long or cash. The 3-speed breakout in `strategies/majors-breakout/` runs alongside as a rules-only shadow book and benchmark. It places no orders.

**Phase:** definition. Paper on Bybit Demo starts once `strategy.md` and `risk-policy.md` are merged, Thierry has approved, and the ticket-driven runner is ready. No live capital.

## Files

| File | Owner | What it holds |
|---|---|---|
| `strategy.md` | Leo (Majors Trader) | Wake procedure, inputs, ticket format, the limits the runner enforces, shadow book, scoring |
| `risk-policy.md` (to come) | Ingrid (Risk Manager), with Nadia's capital and promotion criteria | Limits, capital, halt rule, paper→live promotion criteria |
| runner (to come, PR #14 reworked) | Leo (Majors Trader) | Ticket checks and Bybit Demo order placement, the input block, the shadow book, the decision log, Crypto Book records, scoring |

## Change rules

Every change goes through a PR. Nadia merges `strategy.md` and the runner. `risk-policy.md` merges only with Ingrid's and David's approval, and once live, Thierry's confirmation as well.
