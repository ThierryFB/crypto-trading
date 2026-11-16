# Majors Discretionary runner

Ticket-driven runner for `strategies/majors-discretionary/` (THE-321). **No ticket, no order.** Limits come from [`../risk-policy.md`](../risk-policy.md) (`limits_source` in `config.json`). The gate code (`tickets.py`, `execute.py`, the gates, halts and resume in `mdisc.py`) and `config.json` `limits` and `governance` are risk policy: changing them needs Ingrid's approval (risk-policy.md, Runner independence).

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
     - `strategy.md`, `risk-policy.md` and this runner are on `origin/master`, and the local runner is byte-identical to master (O7). If `git fetch` fails, this counts as not met;
     - the Demo key passes `query-api`;
     - the stop-market test has passed.
   - It is **re-checked** against every limit at the current touch, with the cash, positions, week cost and entries of this wake up to date (`tickets.py`).
   - **Under a halt:** no entries; an adjust may only tighten the stop; a discretionary exit runs only if `request_ref` is the id of a comment by Nadia or Ingrid on an open HALT issue (checked against the comment's author; `requested_by`, if given, must match).
   - **Before every buy** the HALT issues are read again; if Paperclip can't be read, the buy is refused.
   - **Entry:** IOC limit at the ask + 0.1% (or the ticket's lower limit: there are no resting buys, L9). Then the lot's **resting stop-market sell** for the full quantity (L3), and a resting target if `resting_target` is on. Then the Crypto Book entry (`book` = `majors-discretionary`, thesis in `reason`, stop/target/time limit in `planned_exit`).
   - **Exit:** it cancels only this lot's stop and target, then makes up to 3 IOC sells at the bid − 0.1%. A remainder gets its stop back. A lot that fully closes queues its Crypto Book exit (one exit per entry, at the VWAP of all its sells).
   - **Adjust:** it amends the stop upwards. If Bybit refuses the amend, it places the new stop first and then cancels the old one, so the lot is never without a stop. It never loosens a stop (L3).

   Then, on every run: it checks every open lot has its stop resting (O5: retry once; a lot still without a stop **halts**, because the hourly fallback isn't built), reconciles lots + dust + the baseline with each coin's Demo balance and the USDT baseline + (sleeve cash − $2,000) with the Demo USDT (O2: a mismatch halts), runs the shadow book, flushes the Crypto Book queue and posts the fills comment.

## Halts

Every runner halt **latches**: O1, O2 (a ledger mismatch, or NAV that can't be computed because a held coin has no price, which is never filled in), O3, O5, D2 and D3. It holds when NAV recovers or the day rolls over. The runner then opens a `HALT — majors-discretionary: <reason>` issue in this project, assigned to Nadia, with the reason, the evidence and the book. If Paperclip is down it retries every run, and the halt holds in the state meanwhile. A later reason is added to that issue as a comment. While the issue is open, no entry and no order change except exits.

`resume --ref <comment id>` is refused unless the halt's issue exists, the comment is **Nadia's**, on that issue, a comment by **Ingrid** (`governance.review_agent_id`) is on that issue after the last halt reason and before Nadia's comment, and **no** HALT issue (this one, another, or `HALT — desk`) is open. So the order is: Ingrid's written review on the issue, then Nadia's resume comment and her closing the issue, then `resume`. `halt --by X --ref Y` latches a manual halt the same way.

**Day and week NAV** (D1, D2, L8) are NAV at 00:00 UTC: the book as it stands at the first run of the day, before that run changes anything, marked at the opens of the Bybit 4h candles starting at 00:00. Between runs only resting stops and targets trade, and they're swept after this. A missed or late 00:05 wake therefore doesn't move the reference. **Not covered:** a stop that filled between the last run and 00:00 is marked at the 00:00 open rather than at its fill. If the candles can't be read, the first NAV seen is used and the book line says so; with neither, entries are refused.

The fills come in a second comment because the ticket must be in the log before its order (O3), and comments can't be edited.

**Paper starts at the first strategy order** (risk-policy.md §2). The shadow book (`shadow.py`: the merged 3-speed breakout, virtual, at 8h closes, 0.15%/side, catastrophe stop at entry − 4×ATR) and BTC buy-and-hold start at that run, from the same $2,000.

## Other commands

| Command | What |
|---|---|
| `key-check` | Read-only `/v5/user/query-api` on Demo; prints only `readOnly` and `permissions` (order gate item 3). |
| `test-order [--usdt 18]` | Order gate item 4, outside the sleeve. **Refused** while any halt holds or a HALT issue is open (or Paperclip can't be read), and unless the runner is merged and identical to `origin/master` (O7). It buys ≤ $20 DOGE and places a resting stop-market sell. It reads the stop back, places a resting target next to it (does Bybit accept both on one coin?), and amends the stop up. It cancels both and reads them back, then flattens to the pre-test balance. It leaves no lot, no Crypto Book row and nothing resting. A pass sets `stop_test` in the state. |
| `backfill THE-334` | Runs once, when this merges. It loads the forecasts of the hand-posted forecast-only wakes since Thu 12 Nov 00:05Z (the 11 Nov 14:35Z rehearsal is left out) into the store, with their on-time/late flags. Base rates missing from the first three logs are recomputed from Bybit 8h candles as of each wake. |
| `score` / `status` | Brier score (by-day bootstrap, calibration) / the state. |
| `halt --by X --ref Y` / `resume --ref NADIAS_COMMENT_ID [--rebaseline]` | See Halts. `--rebaseline` resets the venue baseline (coins and USDT) after a reconciled O2. |

## Files

| File | What |
|---|---|
| `mdisc.py` | CLI, the wake (post, execute), O1 accounting, halts, the Demo test, backfill. |
| `tickets.py` | The gate: L1–L9, D1, the halts, the forecast and thesis checks. Pure functions. |
| `execute.py` | Ticket integrity (L10/O3), order gate and O7, entries, exits, adjusts, stop sweep (O5), reconciliation (O2), Crypto Book. |
| `shadow.py` | Rules-only shadow book and the BTC benchmark (L11: no orders). |
| `inputs.py` | `strategy.md` §3 data block (keyless). |
| `forecasts.py` | Forecast store, resolution, Brier, bootstrap, calibration. |
| `test_tickets.py`, `test_execute.py` | 33 + 58 offline checks (fake Demo and fake Paperclip; no network). |

The Bybit client and helpers are shared with `../../majors-breakout/runner/` (`bybit.py`, `runner.py`, `engine.py`). State lives in `$MD_STATE_DIR` (default: Leo's persistent workspace), never in the repo. The Bybit key is read from the env or the Paperclip secrets `bybit_api_key` / `bybit_api_secret`, and is never printed or stored.

## Not built, and why

- **Hourly price-check fallback for L3.** It's only needed if the Demo test shows resting stop-market sells don't work (risk-policy.md, Before the first strategy order).
- **Resting targets** are off (`resting_target: false`). A resting PostOnly limit sell isn't an order type L9 allows, so switching them on needs an L9 amendment to `risk-policy.md` with Ingrid's approval, as well as the Demo test. Until then a target is taken at a wake, and the review flags a lot at or above its target.
- **The breakout's implied call** as a Brier benchmark (strategy.md §7.2). It isn't in the score block yet; it comes with the first weekly score post.
