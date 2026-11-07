# Strategy — Majors Breakout (3-speed)

Owner: Leo (Majors Trader). Merged by Nadia. Capital, limits and the halt rule live in `risk-policy.md` (Ingrid); where the two disagree, the risk policy wins.

**One line:** on six liquid Bybit spot majors, run the same 8h Donchian breakout at three speeds, each on its own third of the sleeve. Buy when an 8h close breaks above the previous *N* candles' high while above its 30-day average. Sell when a close breaks below the previous *N/2* candles' low or below a fixed 2×ATR stop. Long or cash, never leveraged.

**Phase:** definition → paper on Bybit Demo once this and `risk-policy.md` are merged. No live capital.

The rules below are exactly what `backtest/sweep3.py` tests as **"3-speed 10/5 + 20/10 + 40/20"**: three `bt_active.run(U6, breakout(n_in, n_out, 90))` books combined at ⅓ each by `bt_active.combine`. At 0.15%/side, Jul 2021 → 7 Nov 2026, it gives **2.96x, −30% max drawdown, 3.8 round trips a week (median 3), ≥3 round trips in 52% of weeks and none in 26%** (`backtest/results_active.txt`). Where this file and `bt_active.py` differ, `bt_active.py` is the tested rule and this file is wrong; fix it by PR.

## 1. Universe

- **BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, DOGEUSDT, ADAUSDT**, Bybit spot. Nothing else.
- Long or cash. No leverage, margin, perps, shorting, lending or staking.
- Quote currency is USDT. Uninvested capital is USDT.

## 2. Candles

- **8h candles closing at 00:00, 08:00 and 16:00 UTC**, built from Bybit's public spot 4h klines (`/v5/market/kline`, `interval=240`): each 8h candle is the two 4h candles starting at 00/04, 08/12 or 16/20 UTC. Open = first open, high = max, low = min, close = second close.
- Only **closed** candles count. Bybit returns the forming candle first; it is dropped.
- Each close is one decision point, shared by all three slices. A decision reads the candle that has just closed.

## 3. Slices

The sleeve is split into three **independent sub-books ("slices")**, one per channel length:

| Slice | Entry channel `N_in` | Exit channel `N_out` | Starting ledger | Backtest alone (0.15%/side) |
|---|---|---|---|---|
| `fast` | 10 candles (3⅓ days) | 5 | ⅓ of the sleeve ($666.67) | 2.45x, −32%, 1.8 RT/wk |
| `med` | 20 (6⅔ days) | 10 | ⅓ ($666.67) | 3.21x, −32%, 1.2 RT/wk |
| `slow` | 40 (13⅓ days) | 20 | ⅓ ($666.67) | 3.21x, −37%, 0.8 RT/wk |

- Each slice has its **own cash, positions, stops, position cap and NAV**. Nothing moves between slices: no rebalancing, no lending cash, no sharing slots.
- **The same coin can be held by more than one slice at once.** A position is identified by (slice, coin). Each slice's position has its own entry, stop and exit.
- The 30-day average filter, ATR and the 2× ATR stop are the same for all slices.
- The demo account holds the sum of the three slices. The runner keeps the account's coin and USDT balances reconciled to that sum (§8).

## 4. Signals (per slice)

With `H` the closed 8h candles of a coin, newest last (`H[-1]` is the candle that just closed):

| Level | Definition (as in `bt_active.py`) |
|---|---|
| `hi` | highest high of the **previous `N_in`** candles, `H[-N_in-1:-1]` (the current candle excluded) |
| `lo` | lowest low of the **previous `N_out`** candles, `H[-N_out-1:-1]` |
| `sma90` | simple average of the last **90 closes**, current included (30 days) |
| `atr14` | simple average of the last **14 true ranges**, current included; TR = max(high−low, \|high−prev close\|, \|low−prev close\|) |

- **Entry:** `close > hi` **and** `close > sma90`, the coin is not held **by this slice**, and it has at least 91 candles of history.
- **Stop:** set once, at the decision: `stop = close − 2 × atr14`. It does not trail.
- **Exit:** `close < lo` **or** `close < stop`. Both are checked on the **close only**; a wick through the stop between closes does nothing.
- No BTC regime filter. (THE-319 §1 rejected it: higher Sharpe, but too many idle weeks.)

## 5. Sizing and slots (per slice)

- **Risk per trade 1% of the slice's NAV:** weight = `min(25%, 1% ÷ (2 × atr14 ÷ close))` of slice NAV. A trade that hits its stop loses about 1% of its slice, which is ⅓% of the sleeve.
- **At most 25% of the slice's NAV in one position. At most 4 positions per slice.** A coin held by all three slices is therefore at most 25% of the sleeve; the sleeve can hold up to 12 positions with about 4% of sleeve NAV at risk.
- Slice NAV = slice cash + every coin the slice holds, marked at the last close. A buy never exceeds the slice's cash.
- **Exits first, then entries.** A coin a slice exits at this close can't be re-entered by that slice at the same close, but its slot is free for another coin.
- **More signals than free slots:** take them in order of breakout strength, `(close − hi) ÷ atr14`, strongest first.
- **Runner rounding (differs from `bt_active.py`):** `bt_active.py` fills at the next open; the runner fills a few minutes after the close at the touch. If the fill price is above the signal close, the quantity is trimmed so that `qty × (limit price − stop) ≤ 1% of slice NAV`, keeping the per-trade risk limit binding. The effect is a few basis points of size.
- A cross-slice cap per coin, if any, is set in `risk-policy.md` (THE-320) and enforced by the runner on top of these rules.

## 6. Cadence

- **Three wakes a day: 00:05, 08:05 and 16:05 UTC**, one per 8h close, as a Paperclip routine. One wake decides all three slices.
- Each wake: read the closed candle, the three slice ledgers and the demo balances; apply §4–§5 per slice; place the orders; log the decision; record fills in the Crypto Book.
- **A wake that finds nothing to do still logs**, with each coin's close, `sma90`, `atr14`, each slice's `hi`/`lo` and, for held positions, the stop.
- A decision point is acted on once. A re-run for the same close logs and places nothing.
- A missed wake is not made up later with stale levels. The next wake reads its own close.

## 7. Overlay (my discretion)

Inside the rules, per (slice, coin) position, I may:
- **skip an entry**, or
- **exit a held position early**,

each with a written reason in that wake's log, stated before the order goes out. I may **not** add a trade the rules didn't signal, enlarge one, re-enter a coin the rules have exited, move a stop, or move capital or slots between slices. A skip or early exit in one slice does not change what the other slices do.

The runner keeps a **rules-only shadow book per slice** from the first wake: the same signals with no overlay, filled at the same price as the real book where both traded, else at the touch with a 0.1% fee. Every overlay call is scored against its slice's shadow book. If after 4 weeks the overlay has cost money net, I stop using it until I can show why it would help.

## 8. Execution

- **Venue:** Bybit Demo (`api-demo.bybit.com`): real API, fake money. Demo fills are the paper record (THE-319 §3).
- **Sleeve:** a virtual **$2,000** ledger kept by the runner as three slice ledgers, whatever the demo account holds. Orders are sized from the slice ledger, not from the demo balance. Each wake checks that the demo account holds at least the sum of the slices' coins and enough USDT for the buys; if not, the order is refused and logged.
- **Order:** limit, immediate-or-cancel, at the touch ± 0.1% (buy at ask × 1.001, sell at bid × 0.999), rounded to the venue's tick and lot size. One order per (slice, coin): two slices buying the same coin at the same close send two orders.
- **Unfilled entry:** the remainder is dropped, not chased; the position is whatever filled. Entries below the venue's minimum order are skipped and logged.
- **Unfilled exit:** re-sent at a fresh touch up to 3 times in the same wake, then retried at the next wake.
- **Fills and fees** are read back from the venue (`/v5/execution/list`) and are the record. Fees paid in the coin reduce the coin held.
- **Cost assumption:** 0.15%/side in the backtest (0.1% taker fee + slippage). The real number comes from the demo fills and is reported weekly.
- Only the runner (`runner/`, the order-placement for this strategy) places orders. It refuses any order that breaks a `risk-policy.md` limit, and places no orders while the strategy is halted.

## 9. Every decision is logged with

Strategy and phase; the decision time and the candle it read; per coin: close, `sma90`, `atr14`, and per slice `hi`, `lo`, and for held positions entry and stop; the action per (slice, coin) (buy, sell, skip, hold, no trade) and the rule or overlay reason; for orders: slice, limit price, quantity, fill, fee; NAV of each slice, each slice's shadow book, the sleeve and buy-and-hold BTC; and what would invalidate the trade (for an entry: a close below the slice's `lo` or the stop).

The log is a comment on the standing decision-log issue, on every wake. Entries and exits also go to the Crypto Book, `book` = `majors-breakout`, with the slice in the row (the API has no slice field, so the `reason` and `planned_exit` start with `[fast]`, `[med]` or `[slow]`).

## 10. Scoring

Against buy-and-hold BTC bought with the same $2,000 at the first wake's ask. Weekly, for the sleeve and per slice: NAV, max drawdown, round trips, wakes logged (target 100%), average fee and slippage per side, and overlay vs shadow book. First review after 4 weeks (about 10 Dec 2026) checks the plumbing, not the edge; an edge read needs about 3 months and 40+ round trips.

## 11. What would kill it

- **Before paper:** nothing; it beat buy-and-hold BTC on drawdown (−30% vs −77%) over 5.3 years, but see §12.
- **In paper:** the halt and promotion criteria in `risk-policy.md`. As evidence for changing this file I'll watch for a sleeve drawdown deeper than the backtest's −30%, real costs above 0.3%/side (where the 3-speed backtest falls to 2.45x and the `fast` slice earns little), or a losing streak longer than 25 round trips in a row across slices (the backtest's worst; the win rate is 34%, so long streaks are normal). Any of these goes to Nadia as a PR with the numbers.

## 12. Where I disagree or want it watched

1. **The edge is mostly 2023–2024.** By year the 3-speed sleeve is 0.97x (2022), 1.33x, 2.15x, 1.10x, 1.00x (2026 to date). More trades a week do not make 4 weeks of paper say more about the edge; judge it on plumbing first.
2. **`fast` is the most cost-sensitive slice.** Alone it falls from 3.25x gross to 2.45x at 0.15%/side and 1.85x at 0.30%/side. If demo costs come in above 0.15%/side, `fast` is the first thing to revisit.
3. **The stop is a close-only stop.** A coin can fall well through its stop between two closes, so a 1%-risk trade can lose 2–3% of its slice in a crash. A resting venue stop would cap that, but it is not what was tested. I'd keep the tested rule for paper and let Ingrid decide whether a wide catastrophe stop belongs in `risk-policy.md`.
4. **The slices overlap.** A strong move often triggers all three slices on the same coin within a few closes, so the three speeds are less diversified than three strategies would be, and all six coins move with BTC. Up to 12 positions at ⅓% risk each is still about 4% of the sleeve at risk on one factor. The −4% daily-loss rule covers part of this.
5. **Fill timing.** The backtest fills at the next candle's open; the runner fills about 5 minutes after the close. Close to the same price in normal markets; the weekly cost report will show if it isn't.
