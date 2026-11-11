# Majors Discretionary runner (work in progress)

Ticket-driven runner for `strategies/majors-discretionary/` (THE-321). It reuses the Bybit client and the breakout signal engine from `../../majors-breakout/runner/`; the 3-speed breakout there becomes the shadow book.

**Built (this push):**

| File | What |
|---|---|
| `inputs.py` | `strategy.md` §3 data block: mid, 24 h / 7 d change, ATR14 on 8h candles, distance to sma90, perp funding / OI / long share (Bybit public linear), Fear & Greed, USDT + USDC supply (DefiLlama), each coin's 90-day up-24h base rate. Each source fails on its own. |
| `tickets.py` | The gate: L1, L2 (size from the stop), L3 (stops never loosened), L4 (shrink to fit, skip under 2%), L5, L6, L7, L8, L9, D1, halts (D2, D3, O1, halt issues), forecast = step 3 and > 0.5, thesis and source timestamps. Pure functions. |
| `forecasts.py` | Forecast store, resolution on the close of the 8h candle containing wake + 24 h, Brier score against 0.25 and the base rate, 10,000-resample bootstrap by UTC day, calibration buckets. |
| `mdisc.py` | CLI: `inputs`, `forecast WAKE.json`, `check WAKE.json` (places nothing), `score`. |
| `test_tickets.py` | 32 offline checks. |
| `config.json` | Limits from `risk-policy.md` (PR #16). Changing them is a risk-policy change (Ingrid's approval). |

**Not built yet:** order placement (IOC entry, resting stop-market, resting target where Bybit allows it, exits that cancel their lot's stop first), ticket-ID binding to the posted log comment (L10 / O3), reconciliation against the Demo balances, Crypto Book rows (`book` = `majors-discretionary`), the shadow book and BTC benchmark wiring, and the decision-log post. Until then nothing in this folder can place an order.

State lives in `$MD_STATE_DIR` (default: Leo's persistent workspace), never in the repo.
