# Majors Breakout runner

Order placement for Majors Breakout only (`../strategy.md` §3, §6–§9). Python 3 stdlib, no dependencies.

Three slices, `fast` 10/5, `med` 20/10 and `slow` 40/20, each with its own $666.67 ledger, positions, stops, 4-position cap and rules-only shadow book. A position is a slice-lot (slice, coin) with its own resting catastrophe stop; one demo account holds the sum, reconciled exactly every wake.

| File | What it does |
|---|---|
| `engine.py` | 8h candles from Bybit 4h klines; per-slice `hi`/`lo`, `sma90`, `atr14`; entry/exit decisions per slice. Matches `bt_active.py` |
| `bybit.py` | Public market data (keyless) and signed spot IOC orders, conditional stop-sells, cancels, order status, fills and balances on Bybit Demo |
| `runner.py` | The wake: slice ledgers, risk checks, orders, shadow books, BTC benchmark, decision log, Crypto Book rows (slice in `reason`/`planned_exit`) |
| `config.json` | Universe, $2,000 sleeve, limits (per slice, plus total-NAV limits and the cross-slice coin cap; Ingrid's THE-320 numbers until `risk-policy.md` merges), execution settings, credential names |
| `test_parity.py` | Replays the backtest with `engine.py` per slice: must give the same round trips (506 / 336 / 219) and end NAVs as `bt_active.py`, and the same 3-speed end NAV as `sweep3.py` (2.955x) |
| `test_wake.py` | Offline wakes against a fake venue: per-slice sizing and ledgers, one coin in several slices, refusals, coin cap shrink/skip, catastrophe stops (own stop per lot, cancel one alone, fired between wakes, rejected), lots-vs-venue mismatch halt, −10% day halt, HALT issue, partial fills, per-slice overlay, re-runs, halt, failed-wake accounting, v1 state migration, Crypto Book |

## Use

```
python3 runner.py wake --dry-run                 # what this wake would do; places and saves nothing
python3 runner.py wake                            # act on the 8h candle that just closed
python3 runner.py wake --skip med:SOLUSDT="reason"        # overlay: skip a rules entry in one slice
python3 runner.py wake --skip SOLUSDT="reason"            # ... or in every slice that signals it
python3 runner.py wake --exit-early fast:ETHUSDT="reason"
python3 runner.py test-order --symbol DOGEUSDT --usdt 18   # also tests two resting stops on one coin
python3 runner.py status
python3 runner.py halt --by Ingrid --ref THE-xxx  # resume --by Nadia --ref THE-xxx [--rebaseline]
python3 runner.py set-log-issue THE-xxx
```

At each routine wake (00:05, 08:05, 16:05 UTC) Leo runs `wake --dry-run`, decides whether to use the overlay, then runs `wake` with any `--skip`/`--exit-early` and its written reason.

## What it enforces

- **Tradable only when merged:** no order unless `strategy.md` and `risk-policy.md` are on `origin/master`.
- **Refuses any order that breaks a limit** (`config.json` → `limits`, to be replaced by `risk-policy.md`): per slice, risk at the stop ≤ 0.75% of slice NAV, position ≤ 25% of slice NAV, ≤ 4 positions, within slice cash; demo USDT; at or above the venue minimum. **Coin cap:** before each buy the coin's value in all slices is summed; a buy that would take it above 25% of sleeve NAV is shrunk to fit, or skipped if what is left is under 2% of sleeve NAV. No entries after a 4% fall of the sleeve in the UTC day, at sleeve NAV ≤ $1,600, after 2 failed wakes in a row, or if the HALT-issue check can't run. No orders at all while halted, while an issue titled `HALT — majors-breakout` or `HALT — desk` is open, on a data failure, or more than 2 h after the close.
- **The runner halts itself** on a −10% sleeve day, or when a coin's slice-lots plus the baseline (what the account held outside the sleeve at the first wake) don't equal the venue balance. Only Nadia resumes; `--rebaseline` resets the baseline after a reconciled mismatch.
- **Catastrophe stop:** every slice-lot gets its own resting venue stop-sell at entry − 4×ATR14. A slice cancels only its own stop before it sells; a partly sold lot gets a fresh stop for what is left; a stop that fired between wakes closes that lot at its fills. A stop the venue rejects is flagged and fails the wake. The shadow books apply the same level to each closed candle's low.
- **Failed wake:** a data or order error, a slice without its decision line, a log later than 60 min after the scheduled wake, or a log that couldn't be posted.
- **The overlay only removes:** a skipped entry's slot is not given to the next signal, an early exit doesn't free a slot, a call in one slice doesn't touch the others, and a reason is required.
- **Once per close:** a re-run for a close already acted on places nothing.

## State and secrets

- State (`state.json`, `logs/<bar>.md`) lives in `$MB_STATE_DIR`, default Leo's persistent workspace, not this repo.
- The Bybit Demo key is read from the env (`BYBIT_API_KEY` / `BYBIT_API_SECRET`) or from the Paperclip secrets `bybit_api_key` / `bybit_api_secret` (created in Bybit Demo Trading mode, so they only work on `api-demo.bybit.com`). It is never printed, logged or written to disk. The key should be spot trading only, no withdrawals.

## Tests

```
cd ../backtest && python3 fetch.py BTCUSDT ETHUSDT SOLUSDT XRPUSDT DOGEUSDT ADAUSDT && python3 ../runner/test_parity.py
cd ../runner && python3 test_wake.py
```
