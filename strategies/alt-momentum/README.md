# Alt Momentum

A desk strategy that rotates weekly into the 4 strongest of the 20 most liquid alts, and holds them only while BTC is above its 150-day average.

**Phase:** definition. No capital, no mandate, no trades. **The backtest fails both kill criteria. It is not proposed for paper** (`backtest.md`).

## Files

| File | Owner | What it holds |
|---|---|---|
| `strategy.md` | Leo (Majors Trader) | Universe, ranking, regime filter, cadence, costs |
| `backtest.md` | Leo | Method, results and verdict, 2019 → 2026-10 |
| `universe.md` | Leo | Current universe, sector tags, price sources |
| `backtest/` | Leo | Code (`report.py`, `halts.py`) and its output (`results.txt`, `halts.txt`) |
| `risk-policy.md` (PR #8) | Ingrid (Risk Manager), with Nadia's capital and promotion criteria | Limits, capital, kill switch, paper→live promotion criteria |

## Change rules

Every change goes through a PR. Nadia merges `strategy.md` and `backtest.md`. `risk-policy.md` merges only with Ingrid's and David's approval, and once live, Thierry's confirmation as well.
