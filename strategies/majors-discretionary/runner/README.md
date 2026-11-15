# Majors Discretionary runner

Ticket-driven runner for `strategies/majors-discretionary/` (THE-321). **No ticket, no order.** Limits come from [`../risk-policy.md`](../risk-policy.md) (`limits_source` in `config.json`). The gate code (`tickets.py`, `execute.py`, the gates in `mdisc.py`) and `config.json` limits are risk policy: changing them needs Ingrid's approval (risk-policy.md, Runner independence).

## A wake

```
mdisc.py inputs                 # step 1: the §3 data block; I add the news pass and write WAKE.json
mdisc.py wake WAKE.json         # = post, then execute
```

1. **`post`** (steps 2–5). It checks WAKE.json and refuses to post (so I fix it inside the hour) if any of these is missing: the market read, all six forecasts in 0.05–0.95, a review for every open lot, tickets or a no-trade reason. It sweeps resting stops and targets that filled since the last run, so the review is written against the real book. Then it posts **one decision-log comment** on THE-334 with the halts, the order gate, the inputs, the read, the forecasts and their resolution time, the position review, each ticket as a fenced JSON block with its id (`T-YYYYMMDD-HHMM-n`) and its pre-check at the touch, and the book, shadow book and score block. The six forecasts are recorded at the mid when the comment is posted. Each wake posts once only. A wake whose log comes more than 60 min after its slot, or a slot with no log at all, counts as failed (O1).
2. **`execute`** (step 6). For each pending ticket of the last wake:
   - **L10 / O3:** it re-reads the log comment and refuses the ticket unless the comment is there, is neither edited (`updatedAt` = `createdAt`) nor deleted, and contains the same ticket (SHA-256 of the canonical JSON). An edited or changed ticket **halts** the runner.
   - It is placed within 60 min of its comment, or it expires.
   - **Order gate** (Nadia, 11 Nov):
     - `strategy.md`, `risk-policy.md` and this runner are on `origin/master`, and the local runner is byte-identical to master (O7);
     - the Demo key passes `query-api`;
     - the stop-market test has passed.
   - It is **re-checked** against every limit at the current touch, with the cash, positions, week cost and entries of this wake up to date (`tickets.py`).
   - **Under a halt:** no entries; an exit needs `requested_by` and `request_ref`; an adjust may only tighten the stop.
   - **Entry:** IOC limit at the ask + 0.1% (or the ticket's lower limit: there are no resting buys, L9). Then the lot's **resting stop-market sell** for the full quantity (L3), and a resting target if `resting_target` is on. Then the Crypto Book entry (`book` = `majors-discretionary`, thesis in `reason`, stop/target/time limit in `planned_exit`).
   - **Exit:** it cancels only this lot's stop and target, then makes up to 3 IOC sells at the bid − 0.1%. A remainder gets its stop back. A lot that fully closes queues its Crypto Book exit (one exit per entry, at the VWAP of all its sells).
   - **Adjust:** it amends the stop upwards. If Bybit refuses the amend, it places the new stop first and then cancels the old one, so the lot is never without a stop. It never loosens a stop (L3).

   Then, on every run: it checks every open lot has its stop resting (O5: retry once, else the lot is flagged and the wake fails), reconciles lots + dust + the baseline with the Demo balances (O2: a mismatch halts), runs the shadow book, flushes the Crypto Book queue and posts the fills comment.

The fills come in a second comment because the ticket must be in the log before its order (O3), and comments can't be edited.

**Paper starts at the first strategy order** (risk-policy.md §2). The shadow book (`shadow.py`: the merged 3-speed breakout, virtual, at 8h closes, 0.15%/side, catastrophe stop at entry − 4×ATR) and BTC buy-and-hold start at that run, from the same $2,000.

## Other commands

| Command | What |
|---|---|
| `key-check` | Read-only `/v5/user/query-api` on Demo; prints only `readOnly` and `permissions` (order gate item 3). |
| `test-order [--usdt 18]` | Order gate item 4, outside the sleeve. It buys ≤ $20 DOGE and places a resting stop-market sell. It reads the stop back, places a resting target next to it (does Bybit accept both on one coin?), and amends the stop up. It cancels both and reads them back, then flattens to the pre-test balance. It leaves no lot, no Crypto Book row and nothing resting. A pass sets `stop_test` in the state. |
| `backfill THE-334` | Runs once, when this merges. It loads the forecasts of the hand-posted forecast-only wakes since Thu 12 Nov 00:05Z (the 11 Nov 14:35Z rehearsal is left out) into the store, with their on-time/late flags. Base rates missing from the first three logs are recomputed from Bybit 8h candles as of each wake. |
| `score` / `status` | Brier score (by-day bootstrap, calibration) / the state. |
| `halt --by X --ref Y` / `resume --by Nadia --ref Y [--rebaseline]` | Only Nadia resumes. `--rebaseline` resets the venue baseline after a reconciled O2. |

## Files

| File | What |
|---|---|
| `mdisc.py` | CLI, the wake (post, execute), O1 accounting, halts, the Demo test, backfill. |
| `tickets.py` | The gate: L1–L9, D1, the halts, the forecast and thesis checks. Pure functions. |
| `execute.py` | Ticket integrity (L10/O3), order gate and O7, entries, exits, adjusts, stop sweep (O5), reconciliation (O2), Crypto Book. |
| `shadow.py` | Rules-only shadow book and the BTC benchmark (L11: no orders). |
| `inputs.py` | `strategy.md` §3 data block (keyless). |
| `forecasts.py` | Forecast store, resolution, Brier, bootstrap, calibration. |
| `test_tickets.py`, `test_execute.py` | 32 + 35 offline checks (fake Demo and fake Paperclip; no network). |

The Bybit client and helpers are shared with `../../majors-breakout/runner/` (`bybit.py`, `runner.py`, `engine.py`). State lives in `$MD_STATE_DIR` (default: Leo's persistent workspace), never in the repo. The Bybit key is read from the env or the Paperclip secrets `bybit_api_key` / `bybit_api_secret`, and is never printed or stored.

## Not built, and why

- **Hourly price-check fallback for L3.** It's only needed if the Demo test shows resting stop-market sells don't work (risk-policy.md, Before the first strategy order).
- **Resting targets** are off (`resting_target: false`) until the Demo test shows a target can rest next to the stop. Until then a target is taken at a wake, and the review flags a lot at or above its target.
- **The breakout's implied call** as a Brier benchmark (strategy.md §7.2). It isn't in the score block yet; it comes with the first weekly score post.
- **Day NAV** is the first NAV seen in the UTC day (the 00:05 wake), not a 00:00 snapshot.
