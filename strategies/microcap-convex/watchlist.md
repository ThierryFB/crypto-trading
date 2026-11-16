# Watchlist

Owner: Hugo. Criteria: `watchlist-criteria.md` rev 3 (PR #5, `2657744`). Changes merge only under the criteria on the default branch.

**Phase: definition.** No trading, paper or live.

## Approved

**None.** As of 2026-11-16, no token has passed every test in `watchlist-criteria.md` §3.

The random control draws from an empty list. Paper can't start until at least one token is approved here.

## Need more info

Not approved, and not tradeable. A token moves to Approved only after the open item is resolved and every §3 test passes, including the B1 depth median over 3 UTC days.

| Token | Chain | Open item | Other tests not run |
|---|---|---|---|
| PNUT | Solana | Six unlabelled wallets hold ≥2% each, 42.2% in total; the largest holds 10.59%. Under D5 they count as insiders, so D1–D3 fail unless the explorer labels them as exchanges. | D4; G3 (holders 11–20 not sanctions-screened) |
| CETUS | Sui | Unlabelled `0x7ab9…1cec` holds 22.58%. It also holds 381.9M SUI and looks like an exchange wallet, but under D5 it counts as an insider and fails D1–D3. With an exchange label the largest holder would be 3.75%. | D4, F1, F7, F8, G3 |

## Rejected: 2026-11-16 review

Screened from today's depth snapshot (`dd/2026-11-16/`): every token with a market cap of $5M–$50M and ±2% credible depth of at least $50k on one snapshot, 52 in all. The 81 other in-band candidates were below the depth floor and weren't reviewed.

Hard fails stop a review, so each verdict lists only the tests run up to that point. The full evidence, sources and UTC read times are in `dd/2026-11-16/verdict_<SYM>.json`.

A rejected token can be resubmitted from **2026-12-16** (§6), unless a later date is shown.

| Token | Failed | Key value |
|---|---|---|
| AEVO | D2, D3, D5 | Treasury Safe holds 18.71% |
| ALT | E1, D1–D3, D5, F3, F5 | Unlock on 11-25: 3.17%; 2-of-3 Safe controls pause with no timelock |
| ANIME | D2, D3, D5 | Unlabelled Safe holds 23.82% |
| API3 | D2, D3, D5 | DAO treasury Safe holds 10.63% |
| AVNT | E1, E2, D1–D3, D5, F3, F5 | Unlock on 12-09: 6.37%; EOA holds 20.8% |
| BAND | D2, D3, D5 | Unlabelled account holds 11.02% |
| BARD | D1–D3, D5, E1, E2 | EOA holds 63.0%; unlock on 11-18: 5.75% |
| BERA | E1 | 3.58% vests in 30 days |
| BIO | F2, F3, F8, D5 | Mint uncapped, no timelock; LP unlocked in an EOA |
| BOME | F8, D1, D2, D5 | Raydium LP (99.96%) unlocked in an EOA |
| BREV | D1–D3, D5 | Unlabelled 2-of-3 Safe holds 26.1% |
| CATI | D1–D3, D5 | Project multisig holds 21.2% |
| CFG | D2, D5 | Unlabelled EOA holds 27.9% |
| CT | §2 scope | First listed 2026-09-30, under 90 days; resubmit from 2026-12-29 |
| EDEN | E1 | Unlock on 11-30: 4.99% |
| ENSO | E1, E2, E3 | Unlock on 12-14: 17.4% |
| ERA | E1, E2 | Unlock on 11-17: 8.4–15.1% |
| EUL | D1–D3, D5 | Three holders over 10% (17.0%, 11.7%, 10.6%) |
| F | E1, E2 | 3.64% vests in 30 days |
| FLUX | D2 | Team reserve multisig holds 37.72%, no vesting |
| G | D2 | Unidentified EOA holds 43.05% |
| HOME | E1, E2 | Unlock on 12-10: 5.04% |
| KAT | D1–D3, D5 | Unlabelled EOA holds 28.6% |
| KII | G2, N3 | Core-protocol exploit and chain halt on 2026-08-22 |
| LA | E1, E2 | Unlock on 12-04: 6.55% |
| MANTA | E1 | Unlock on 11-17: 2.91% |
| MARSCOIN | §2 scope | First credible listing 2026-09-01, under 90 days; resubmit from 2026-11-30 |
| ME | E1, E2 | Unlock on 12-10: 3.52% |
| MOODENG | D1, D2, D5 | Unidentified wallet holds 10.80% |
| NIL | D1–D3, D5, E1 | Unidentified wallet holds 22.0%; unlock on 11-24: 4.40% |
| NOT | F8, D5 | STON.fi pool (~53% of liquidity) LP not locked |
| OGN | E1 | Treasury lockups of 28.1% expire by 12-15 |
| OPG | E1, E3 | Unlock on 11-21: 3.81%; 23.9% of max supply circulating |
| PEOPLE | D2, D3, D5, F8 | Unlabelled wallet holds 25.33%; Uniswap V3 LP unlocked |
| PHA | F3, F5, D1, D2, D5 | EOA owner can pause transfers |
| REZ | D1–D3, D5 | Unlabelled 2-of-3 Safe holds 12.90% |
| ROBO | D1–D3, D5, E3 | Unlabelled EOA holds about 102% of CoinGecko circulating |
| SAHARA | E1 | Unlock on 11-26: 3.60% |
| SAPIEN | D1–D3, D5, E1 | Top holder holds 93.2% of circulating; unlock on 11-20: 11.2% |
| SIGN | D1–D3, D5, E1–E3 | EOA holds 79.1%; unlock on 11-28: 10.6% |
| SKL | G2 | Validator-node compromise and bridge exploit on 2026-08-27, no full post-mortem |
| SOLV | E1 | Unlock on 11-17: 3.21% |
| SSV | D1, D2, D5, F2, F3 | 5-of-9 Safe can mint with no timelock |
| SXT | E1 | Unlock on 12-08: 2.42–3.53% of on-chain circulating |
| TOSHI | D1–D3, D5 | Dormant unlabelled EOA holds 15.32% |
| TRB | D3, D4, D5, F3, F4, F8 | Insiders sent 0.60% to Coinbase with no published schedule |
| TRUST | E1, E2, E3 | Unlock on 12-05: 14.3% |
| USUAL | E1, E2 | 12-15 emission step: 3.35% (2.51% on 3B-cap scaling; largest-figure rule) |
| XAN | E1, E2, E3 | Unlock on 11-23: 7.16% |
| ZBT | E1 | Unlock on 11-17: 4.80% |

## Not checked in this review

- **B1 median.** It needs 3 snapshots on 3 different UTC days, so no token could have passed B1 today. The 2026-11-16 snapshot is the first in the current 14-day window.
- **C1–C4 (fake volume).** Not run for any token here: every token failed or stopped at D–G first.
- **Crypto Book.** No analyses were updated in this review.

## Solana DEX

Waiting on the DEX gate (PR #12). This section starts once it merges.
