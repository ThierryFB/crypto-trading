# Majors Breakout runner

Order placement for Majors Breakout only (`../strategy.md` §5–§8). Python 3 stdlib, no dependencies.

| File | What it does |
|---|---|
| `engine.py` | 8h candles from Bybit 4h klines; `hi20`, `lo10`, `sma90`, `atr14`; entry/exit decisions. Matches `bt.py` |
| `bybit.py` | Public market data (keyless) and signed spot IOC orders, order status, fills and balances on Bybit Demo |
| `runner.py` | The wake: ledger, risk checks, orders, shadow book, BTC benchmark, decision log, Crypto Book rows |
| `config.json` | Universe, $2,000 sleeve, limits, execution settings, credential names |
| `test_parity.py` | Replays the backtest with `engine.py`: must give the same 336 round trips and end NAV as `bt.py run(U6, REGIME=False)` |
| `test_wake.py` | Offline wakes against a fake venue: sizing, refusals, partial fills, overlay, re-runs, halt, Crypto Book |

## Use

```
python3 runner.py wake --dry-run                 # what this wake would do; places and saves nothing
python3 runner.py wake                            # act on the 8h candle that just closed
python3 runner.py wake --skip SOLUSDT="reason"    # overlay: skip a rules entry
python3 runner.py wake --exit-early ETHUSDT="reason"
python3 runner.py test-order --symbol DOGEUSDT --usdt 10
python3 runner.py status
python3 runner.py halt --by Ingrid --ref THE-xxx  # resume --by Nadia --ref THE-xxx
python3 runner.py set-log-issue THE-xxx
```

At each routine wake (00:05, 08:05, 16:05 UTC) Leo runs `wake --dry-run`, decides whether to use the overlay, then runs `wake` with any `--skip`/`--exit-early` and its written reason.

## What it enforces

- **Tradable only when merged:** no order unless `strategy.md` and `risk-policy.md` are on `origin/master`.
- **Refuses any order that breaks a limit** (`config.json` → `limits`, to be replaced by `risk-policy.md`): risk at the stop ≤ 1% NAV, position ≤ 25% NAV, ≤ 4 positions, within sleeve cash and demo USDT, at or above the venue minimum. No entries after a 4% fall in the UTC day, at NAV ≤ $1,600, or after 2 failed wakes in a row. No orders at all while halted, on a data failure, or more than 2 h after the close.
- **The overlay only removes:** a skipped entry's slot is not given to the next signal, an early exit doesn't free a slot, and a reason is required.
- **Once per close:** a re-run for a close already acted on places nothing.

## State and secrets

- State (`state.json`, `logs/<bar>.md`) lives in `$MB_STATE_DIR`, default Leo's persistent workspace, not this repo.
- The Bybit Demo key is read from the env (`BYBIT_DEMO_API_KEY` / `BYBIT_DEMO_API_SECRET`) or from the Paperclip secrets `bybit_demo_api_key` / `bybit_demo_api_secret`. It is never printed, logged or written to disk. The key should be spot trading only, no withdrawals.

## Tests

```
cd ../backtest && python3 fetch.py BTCUSDT ETHUSDT SOLUSDT XRPUSDT DOGEUSDT ADAUSDT && python3 ../runner/test_parity.py
cd ../runner && python3 test_wake.py
```
