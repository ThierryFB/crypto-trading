# Micro-cap Convex

Desk strategy for sub-$50M tokens. Convex thesis: most positions go to zero, a few large winners pay for them. Small, equal, pre-capped positions; entries only in tokens we can actually exit; staged profit-taking.

**Phase:** definition. No capital, no mandate, no trades. Paper waits on the `order-placement` skill.

## Files

| File | Owner | What it holds |
|---|---|---|
| `strategy.md` | Rafael (Micro-cap Trader) | Entry, sizing, exit and profit-taking rules |
| `risk-policy.md` | Ingrid (Risk Manager), with Nadia's capital and promotion criteria | Limits, capital, kill switch, paper→live promotion criteria |
| `watchlist-criteria.md` | Hugo (Token DD Analyst) | What makes a token eligible (liquidity/depth, venue, DD) |
| `watchlist.md` | Hugo (Token DD Analyst) | Current eligible tokens |

## Change rules

Every change goes through a PR. Nadia merges `strategy.md` and the watchlist files. `risk-policy.md` merges only with Ingrid's and David's approval, and once live, Thierry's confirmation as well.
