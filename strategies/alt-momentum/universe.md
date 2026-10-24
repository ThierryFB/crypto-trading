# Alt Momentum: universe

**Refresh:** 2026-10-04 (first weekly rebalance of October 2026). **Next:** 2026-11-01. The rule is in `strategy.md` §1. This list was produced by `backtest/data.py` `universe()` on the CMC snapshot of that date. Before paper, the venue-volume and depth tests replace the CMC volume test (`strategy.md` §1.4).

## Sector tags

Every member carries one tag. Ingrid's L4 limit caps any one tag at 50% of NAV after a rebalance (`risk-policy.md`, PR #8). The tags are fixed. A new one needs a PR.

| Tag | Covers |
|---|---|
| `l1` | General smart-contract base layers |
| `payments` | Coins built mainly for transfers and settlement, without a general smart-contract platform |
| `privacy` | Privacy coins |
| `exchange` | Tokens of an exchange or trading venue |
| `meme` | Memecoins |
| `infra` | Oracles, data and middleware |
| `defi` | DeFi application tokens |

A coin that doesn't clearly fit one tag stays out of the ranking until a PR tags it.

## Members, 2026-10-04

| Rank | Coin | CMC id | Market cap | 4-week median volume (CMC) | Cost tier | Sector |
|---|---|---|---|---|---|---|
| 1 | BNB | 1839 | $105.9B | $1,171M | 1 | `exchange` |
| 2 | XRP | 52 | $95.9B | $2,025M | 1 | `payments` |
| 3 | SOL | 5426 | $71.5B | $2,539M | 1 | `l1` |
| 4 | TRX | 1958 | $31.9B | $331M | 1 | `l1` |
| 5 | ZEC | 1437 | $22.9B | $1,307M | 1 | `privacy` |
| 6 | HYPE | 32196 | $22.7B | $688M | 1 | `exchange` |
| 7 | DOGE | 74 | $15.0B | $843M | 1 | `meme` |
| 8 | LINK | 1975 | $10.7B | $283M | 1 | `infra` |
| 9 | XMR | 328 | $10.3B | $90M | 1 | `privacy` |
| 10 | ADA | 2010 | $9.5B | $449M | 1 | `l1` |
| 11 | RAIN | 38341 | $8.0B | $33M | 2 | **untagged, pending review** |
| 12 | XLM | 512 | $7.8B | $156M | 2 | `payments` |
| 13 | NEAR | 6535 | $6.4B | $1,110M | 2 | `l1` |
| 14 | BCH | 1831 | $6.4B | $161M | 2 | `payments` |
| 15 | UNI | 7083 | $5.7B | $502M | 2 | `defi` |
| 16 | LTC | 2 | $5.5B | $292M | 2 | `payments` |
| 17 | SUI | 20947 | $5.0B | $915M | 2 | `l1` |
| 18 | AVAX | 5805 | $4.9B | $379M | 2 | `l1` |
| 19 | HBAR | 4642 | $4.6B | $80M | 2 | `l1` |
| 20 | GRAM | 11419 | $4.3B | $50M | 2 | `l1` |

`l1` holds 8 of the 20 coins and `payments` holds 4. With a top-4 book, L4 binds whenever three of the four picks share a tag; the slot then goes to the next-ranked coin with another tag, or to cash. **The backtest doesn't apply L4.** Doing that would mean tagging all 86 coins that were ever members since 2019. I'll do it only if Nadia keeps the strategy alive.

RAIN has a large market cap on thin volume (a 4-week median of $33M against an $8.0B cap), and I couldn't place it in a sector. It's untagged, so it isn't ranked. It probably fails the venue-volume test anyway.

## Price sources

| Use | Source |
|---|---|
| **Primary** (ranking, NAV, fills) | The trading venue's own spot daily candles for the traded pair, close at 00:00 UTC. Weekly scores use the Sunday close. |
| **Cross-check** | CoinMarketCap daily close for the same date (the keyless `data-api/v3/cryptocurrency/historical` endpoint the backtest uses). |

At each weekly slot, the 4-week returns and the ranking are computed on both sources and logged. If the two rankings place any universe coin more than one rank apart, that rotation is skipped (Ingrid's O3). The venue isn't chosen yet. Until it is, the primary source can't be named more precisely.
