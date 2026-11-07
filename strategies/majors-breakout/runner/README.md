# Majors Breakout runner

Order placement for Majors Breakout only (`../strategy.md` §3, §6–§9). Python 3 stdlib, no dependencies.

Three slices, `fast` 10/5, `med` 20/10 and `slow` 40/20, each with its own $666.67 ledger, positions, stops, 4-position cap and rules-only shadow book. A position is (slice, coin); one demo account holds the sum, reconciled every wake.

| File | What it does |
|---|---|
| `engine.py` | 8h candles from Bybit 4h klines; per-slice `hi`/`lo`, `sma90`, `atr14`; entry/exit decisions per slice. Matches `bt_active.py` |
| `bybit.py` | Public market data (keyless) and signed spot IOC orders, order status, fills and balances on Bybit Demo |
| `runner.py` | The wake: slice ledgers, risk checks, orders, shadow books, BTC benchmark, decision log, Crypto Book rows (slice in `reason`/`planned_exit`) |
| `config.json` | Universe, $2,000 sleeve, limits (per slice, plus sleeve-wide and an optional cross-slice coin cap), execution settings, credential names |
| `test_parity.py` | Replays the backtest with `engine.py` per slice: must give the same round trips (506 / 336 / 219) and end NAVs as `bt_active.py`, and the same 3-speed end NAV as `sweep3.py` (2.955x) |
| `test_wake.py` | Offline wakes against a fake venue: per-slice sizing and ledgers, one coin in several slices, refusals, cross-slice cap, partial fills, per-slice overlay, re-runs, halt, v1 state migration, Crypto Book |

## Use

```
python3 runner.py wake --dry-run                 # what this wake would do; places and saves nothing
python3 runner.py wake                            # act on the 8h candle that just closed
python3 runner.py wake --skip med:SOLUSDT="reason"        # overlay: skip a rules entry in one slice
python3 runner.py wake --skip SOLUSDT="reason"            # ... or in every slice that signals it
python3 runner.py wake --exit-early fast:ETHUSDT="reason"
python3 runner.py test-order --symbol DOGEUSDT --usdt 10
python3 runner.py status
python3 runner.py halt --by Ingrid --ref THE-xxx  # resume --by Nadia --ref THE-xxx
python3 runner.py set-log-issue THE-xxx
```

At each routine wake (00:05, 08:05, 16:05 UTC) Leo runs `wake --dry-run`, decides whether to use the overlay, then runs `wake` with any `--skip`/`--exit-early` and its written reason.

## What it enforces

- **Tradable only when merged:** no order unless `strategy.md` and `risk-policy.md` are on `origin/master`.
- **Refuses any order that breaks a limit** (`config.json` → `limits`, to be replaced by `risk-policy.md`): per slice, risk at the stop ≤ 1% of slice NAV, position ≤ 25% of slice NAV, ≤ 4 positions, within slice cash; across slices, demo USDT and the optional per-coin cap; at or above the venue minimum. No entries after a 4% fall of the sleeve in the UTC day, at sleeve NAV ≤ $1,600, or after 2 failed wakes in a row. No orders at all while halted, on a data failure, or more than 2 h after the close.
- **The overlay only removes:** a skipped entry's slot is not given to the next signal, an early exit doesn't free a slot, a call in one slice doesn't touch the others, and a reason is required.
- **Once per close:** a re-run for a close already acted on places nothing.

## State and secrets

- State (`state.json`, `logs/<bar>.md`) lives in `$MB_STATE_DIR`, default Leo's persistent workspace, not this repo.
- The Bybit Demo key is read from the env (`BYBIT_DEMO_API_KEY` / `BYBIT_DEMO_API_SECRET`) or from the Paperclip secrets `bybit_demo_api_key` / `bybit_demo_api_secret`. It is never printed, logged or written to disk. The key should be spot trading only, no withdrawals.

## Tests

```
cd ../backtest && python3 fetch.py BTCUSDT ETHUSDT SOLUSDT XRPUSDT DOGEUSDT ADAUSDT && python3 ../runner/test_parity.py
cd ../runner && python3 test_wake.py
```
