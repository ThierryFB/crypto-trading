# Strategy — Majors Breakout

Owner: Leo (Majors Trader). Merged by Nadia. Capital, limits and the halt rule live in `risk-policy.md` (Ingrid); where the two disagree, the risk policy wins.

**One line:** on six liquid Bybit spot majors, buy when an 8h close breaks above the previous 20 candles' high while above its 30-day average, and sell when a close breaks below the previous 10 candles' low or below a fixed 2×ATR stop; long or cash, never leveraged.

**Phase:** definition → paper on Bybit Demo once this and `risk-policy.md` are merged. No live capital.

The rules below are exactly what `backtest/bt.py` tests as `run(U6, REGIME=False)` (3.21x, −32% max drawdown, 1.20 round trips/week, Jul 2021 → 7 Nov 2026, 0.15%/side). Where this file and `bt.py` differ, `bt.py` is the tested rule and this file is wrong; fix it by PR.

## 1. Universe

- **BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, DOGEUSDT, ADAUSDT**, Bybit spot. Nothing else.
- Long or cash. No leverage, margin, perps, shorting, lending or staking.
- Quote currency is USDT. Uninvested capital is USDT.

## 2. Candles

- **8h candles closing at 00:00, 08:00 and 16:00 UTC**, built from Bybit's public spot 4h klines (`/v5/market/kline`, `interval=240`): each 8h candle is the two 4h candles starting at 00/04, 08/12 or 16/20 UTC. Open = first open, high = max, low = min, close = second close.
- Only **closed** candles count. Bybit returns the forming candle first; it is dropped.
- Each close is one decision point. A decision reads the candle that has just closed.

## 3. Signals

With `H` the closed 8h candles of a coin, newest last (`H[-1]` is the candle that just closed):

| Level | Definition (as in `bt.py`) |
|---|---|
| `hi20` | highest high of the **previous 20** candles, `H[-21:-1]` (the current candle excluded) |
| `lo10` | lowest low of the **previous 10** candles, `H[-11:-1]` |
| `sma90` | simple average of the last **90 closes**, current included (30 days) |
| `atr14` | simple average of the last **14 true ranges**, current included; TR = max(high−low, \|high−prev close\|, \|low−prev close\|) |

- **Entry:** `close > hi20` **and** `close > sma90`, the coin is not held, and it has at least 91 candles of history.
- **Stop:** set once, at the decision: `stop = close − 2 × atr14`. It does not trail.
- **Exit:** `close < lo10` **or** `close < stop`. Both are checked on the **close only**; a wick through the stop between closes does nothing.
- No BTC regime filter. (THE-319 §1 rejected it: higher Sharpe, but 60% of weeks idle.)

## 4. Sizing and slots

- **Risk per trade 1% of NAV:** weight = `min(25%, 1% ÷ (2 × atr14 ÷ close))` of sleeve NAV, so a trade that hits its stop loses about 1% of NAV.
- **At most 25% of NAV in one position. At most 4 positions.**
- NAV = virtual sleeve cash + every held coin marked at the price of the trade. A buy never exceeds the sleeve's cash.
- **Exits first, then entries.** A coin exited at this close can't be re-entered at the same close, but its slot is free for another coin.
- **More signals than free slots:** take them in order of breakout strength, `(close − hi20) ÷ atr14`, strongest first.
- **Runner rounding (differs from `bt.py`):** `bt.py` fills at the next open; the runner fills a few minutes after the close at the touch. If the fill price is above the signal close, the quantity is trimmed so that `qty × (limit price − stop) ≤ 1% of NAV`, keeping the per-trade risk limit binding. The effect is a few basis points of size.

## 5. Cadence

- **Three wakes a day: 00:05, 08:05 and 16:05 UTC**, one per 8h close, as a Paperclip routine.
- Each wake: read the closed candle, the sleeve ledger and the demo balances; apply §3–§4; place the orders; log the decision; record fills in the Crypto Book.
- **A wake that finds nothing to do still logs**, with each coin's close, `hi20`, `lo10`, `sma90` and, for held coins, the stop.
- A decision point is acted on once. A re-run for the same close logs and places nothing.
- A missed wake is not made up later with stale levels. The next wake reads its own close.

## 6. Overlay (my discretion)

Inside the rules, I may:
- **skip an entry**, or
- **exit a held position early**,

each with a written reason in that wake's log, stated before the order goes out. I may **not** add a trade the rules didn't signal, enlarge one, re-enter a coin the rules have exited, or move a stop.

The runner keeps a **rules-only shadow book** from the first wake: the same signals with no overlay, filled at the same price as the real book where both traded, else at the touch with a 0.1% fee. Every overlay call is scored against it. If after 4 weeks the overlay has cost money net, I stop using it until I can show why it would help.

## 7. Execution

- **Venue:** Bybit Demo (`api-demo.bybit.com`): real API, fake money. Demo fills are the paper record (THE-319 §3).
- **Sleeve:** a virtual **$2,000** ledger kept by the runner, whatever the demo account holds. Orders are sized from the ledger, not from the demo balance. Each wake checks the demo account holds at least the ledger's coins and enough USDT for the buy; if not, the order is refused and logged.
- **Order:** limit, immediate-or-cancel, at the touch ± 0.1% (buy at ask × 1.001, sell at bid × 0.999), rounded to the venue's tick and lot size.
- **Unfilled entry:** the remainder is dropped, not chased; the position is whatever filled. Entries below the venue's minimum order are skipped and logged.
- **Unfilled exit:** re-sent at a fresh touch up to 3 times in the same wake, then retried at the next wake.
- **Fills and fees** are read back from the venue (`/v5/execution/list`) and are the record. Fees paid in the coin reduce the coin held.
- **Cost assumption:** 0.15%/side in the backtest (0.1% taker fee + slippage). The real number comes from the demo fills and is reported weekly.
- Only the runner (`runner/`, the order-placement for this strategy) places orders. It refuses any order that breaks a `risk-policy.md` limit, and places no orders while the strategy is halted.

## 8. Every decision is logged with

Strategy and phase; the decision time and the candle it read; per coin: close, `hi20`, `lo10`, `sma90`, `atr14`, and for held coins entry and stop; the action (buy, sell, skip, hold, no trade) and the rule or overlay reason; for orders: limit price, quantity, fill, fee; NAV of the sleeve, the shadow book and buy-and-hold BTC; and what would invalidate the trade (for an entry: a close below `lo10` or the stop).

The log is a comment on the standing decision-log issue, on every wake. Entries and exits also go to the Crypto Book, `book` = `majors-breakout`.

## 9. Scoring

Against buy-and-hold BTC bought with the same $2,000 at the first wake's ask. Weekly: NAV, max drawdown, round trips, wakes logged (target 100%), average fee and slippage per side, and overlay vs shadow book. First review after 4 weeks (about 10 Dec 2026) checks the plumbing, not the edge; an edge read needs about 3 months and 15+ round trips.

## 10. What would kill it

- **Before paper:** nothing; it beat buy-and-hold BTC on drawdown (−32% vs −77%) and Sharpe (0.90 vs 0.55 on the same 8h bars) over 5.3 years (`backtest/results.txt`), but see §11.
- **In paper:** the halt and promotion criteria in `risk-policy.md`. As evidence for changing this file I'll watch for a drawdown deeper than the backtest's −32%, real costs above 0.5%/side (where the backtest falls to 2.1x), or a losing streak longer than 14 round trips in a row (the backtest's worst; the win rate is 34%, so long streaks are normal). Any of these goes to Nadia as a PR with the numbers.

## 11. Where I disagree or want it watched

1. **The edge is mostly 2024.** Excluding 2024 the yearly results are −5%, +33%, +11%, +1%. 2026 to date is flat. Paper will tell us little about the edge in 4 weeks; it should be judged on plumbing first.
2. **The stop is a close-only stop.** A coin can fall well through its stop between two closes, so a 1%-risk trade can lose 2–3% in a crash. A resting venue stop would cap that, but it is not what was tested and it would fire on wicks the backtest ignored. I'd keep the tested rule for paper and let Ingrid decide whether a wide catastrophe stop (e.g. 2× the stop distance) belongs in `risk-policy.md`.
3. **The six coins are one bet.** All move with BTC. Four positions at 1% risk each is effectively up to 4% at risk on one factor. The −4% daily-loss rule covers part of this.
4. **Fill timing.** The backtest fills at the next candle's open; the runner fills about 5 minutes after the close. Close to the same price in normal markets; the weekly cost report will show if it isn't.
