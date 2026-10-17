# Watchlist criteria: Micro-cap Convex

**Owner:** Hugo (Token DD Analyst). **Merged by:** Nadia. **Applies to:** this strategy only.
**Status:** rev 1, 2026-10-17. **Phase: definition.** No trading.

This file says what a token must pass to go on `watchlist.md`, what makes it eligible on a given day, and what suspends or revokes it. `strategy.md` (Rafael) decides whether to trade an eligible token. Changes to this file go through a PR that Nadia merges. Changes to `watchlist.md` are Hugo's and merge only under the criteria in force on the default branch.

**Default is no.** Passing every test below means the token cleared the checks listed here. It does not mean the token is safe. One failed hard test is enough to reject. A test that can't be run counts as not passed: the verdict is *need-more-info*, not approval.

## 1. Definitions

- **Credible venues:** Binance, Coinbase, Kraken, OKX, Bybit. Upbit counts only if the desk gets access. Once THE-270 settles which venues we hold accounts on, only those count. Until then, all five count.
- **Zero-weight venues:** tier 2 (Bitget, KuCoin, Gate, MEXC) and wash venues (HTX, LBank, GroveX, BTCC, and any venue added here by PR). Their depth and volume count for zero.
- **DEX pools:** count for zero until the order-placement skill supports that chain and router.
- **Depth snapshot:** one public REST L2 order-book read per credible venue (USD, USDT or USDC pair; the deepest one if there are several). Mid is (best bid + best ask) / 2. **±2% depth** is the USD value of bids at or above 0.98 × mid; **±5% depth** is the same at 0.95 × mid. A book that doesn't reach 0.95 × mid is re-read deeper. If it still doesn't, that venue's snapshot fails.
- **Credible depth:** ±2% (or ±5%) bid depth summed across credible venues for one snapshot.
- **Depth median:** the median credible depth over at least 3 snapshots taken on 3 different UTC days. At approval, these come from the last 14 days. For daily eligibility, it's the last 3 daily snapshots.
- **Market cap:** CoinGecko circulating market cap, cross-checked against CoinMarketCap. If the two differ by more than 25%, use the higher one for the $50M ceiling and the lower one for the $5M floor.
- **Circulating supply** for the ratio tests below: the CoinGecko figure, unless on-chain evidence shows it's wrong. In that case, use the on-chain figure and say so in the verdict.
- **Insider wallets:** team, foundation, treasury, early-investor and market-maker wallets. These are labelled on an explorer or in the project's disclosures, or identified with high confidence (funded from or sending to a labelled insider wallet, a deployer, or a vesting contract). An unidentified wallet holding ≥2% of circulating supply counts as an insider until shown otherwise.

## 2. Out of scope (rejected without a full review)

Stablecoins; wrapped, bridged, staked, liquid-staking or restaking tokens; tokenised equities, ETFs or other RWA wrappers (e.g. Binance's `…B` stock tokens); leveraged tokens; and tokens first listed on any credible venue fewer than 90 days ago.

## 3. Approval: every test must pass

Each test gets a pass or fail, its source and a UTC timestamp in the verdict.

### A. Market cap
| # | Test | Pass |
|---|---|---|
| A1 | Market cap at approval | $5M–$50M |

### B. Credible depth
| # | Test | Pass |
|---|---|---|
| B1 | ±2% credible depth median (≥3 snapshots, ≥3 different days, within 14 days) | **≥ $50,000** |
| B2 | ±5% credible depth median ÷ ±2% credible depth median | **≥ 1.5×** |
| B3 | Credible venues with depth | ≥ 1 venue other than Kraken alone, unless the desk only holds Kraken |

The **$25,000 fallback floor** (with positions capped at $12.5k, per `strategy.md`) applies only once Nadia writes it into this file by PR. It doesn't switch on automatically.

### C. Fake volume
Volumes are 30-day averages from CoinGecko tickers.

| # | Test | Pass | If it fails |
|---|---|---|---|
| C1 | Daily volume across all venues ÷ market cap | ≤ 1.0× | Reject |
| C2 | Credible-venue share of all-venue volume | ≥ 25% | Reject |
| C3 | On each credible venue: 24h volume ÷ ±2% depth, against the median of in-band tokens on the same venue | ≤ 10× that median | Need-more-info, then a manual trade-print review |
| C4 | Trade prints on the deepest credible venue (24h public trades): share of trade count taken by the 3 most frequent trade sizes | ≤ 30% | Need-more-info, then a manual review |

### D. Holder concentration, treasury and insider wallets
Read from the chain explorers for every chain holding ≥10% of supply. These are **excluded** from holder counts:
- labelled exchange wallets;
- burn addresses;
- bridge escrows (count the bridged supply on the destination chain instead);
- vesting or timelock contracts whose release schedule is readable on-chain.

| # | Test | Pass |
|---|---|---|
| D1 | Top 10 non-excluded holders, % of circulating supply | ≤ 35% |
| D2 | Largest single non-excluded holder | ≤ 10% |
| D3 | Liquid insider holdings (insider wallets not in a vesting or timelock contract), % of circulating | ≤ 20% |
| D4 | Insider wallets to exchange deposit addresses, last 90 days, outside a schedule published in advance | < 0.5% of circulating supply |
| D5 | Every non-excluded wallet holding ≥2% of circulating supply is identified | Yes. Otherwise it counts as an insider under D3, and the token gets need-more-info if that changes the result |

### E. Unlocks and treasury releases
Sources: Tokenomist, CryptoRank, the project's tokenomics docs, and the vesting contracts on-chain. If they disagree, use the largest figure.

| # | Test | Pass |
|---|---|---|
| E1 | Any scheduled unlock, emission step or announced treasury release in the next 30 days | < 2% of circulating supply |
| E2 | All new supply scheduled in the next 180 days (unlocks plus emissions plus staking rewards) | ≤ 20% of circulating supply |
| E3 | Circulating supply ÷ max supply (or total supply if there's no max) | ≥ 30%, unless the rest is provably burned or locked with no release schedule |
| E4 | Unlock schedule known | Yes. An unknown schedule means need-more-info |

### F. Contract risk
Checked on every deployment holding ≥10% of supply, from verified source code on the explorer plus read-only scanners (GoPlus, honeypot.is, De.Fi). No wallet is connected and nothing is signed.

| # | Test | Pass |
|---|---|---|
| F1 | Source verified on the explorer | Yes |
| F2 | **Mint:** no mint path except a fixed on-chain schedule, or governance behind a timelock of ≥48h | Yes |
| F3 | **Admin keys:** owner and admin roles are renounced, or held by a multisig with ≥3 signers or by on-chain governance, behind a ≥48h timelock for anything that touches supply, balances or transfers | Yes. **An EOA holding any such power fails** |
| F4 | **Proxy:** not upgradeable, or the upgrade admin meets F3 | Yes |
| F5 | **Blacklist / pause / freeze:** absent, or behind F3-grade control | Yes. A multisig without a timelock means need-more-info |
| F6 | Transfer taxes, max-transaction limits or trading toggles that can be changed | None |
| F7 | Honeypot or cannot-sell flag in any scanner | None |
| F8 | **LP lock:** any DEX pool holding ≥20% of the token's on-chain liquidity has its LP tokens burned, or locked past the next re-check date plus 90 days, or held by a contract with no withdrawal path for the team | Yes |
| F9 | A public audit of the token contract, or an unmodified standard implementation (OpenZeppelin ERC-20, SPL token with mint authority revoked) | Yes. Otherwise need-more-info |

**Native L1 or L2 coins** replace F1–F9 with these checks:
- the emission schedule is set in the protocol;
- who can change it, and whether one entity can push a hard fork alone (if so, need-more-info);
- no unplanned chain halt or rollback in the last 12 months.

### G. Venue, incident and legal flags
| # | Test | Pass |
|---|---|---|
| G1 | Binance Monitoring tag, or a delisting announced on any credible venue | None |
| G2 | An exploit of the token contract, the core protocol, or a bridge holding ≥10% of supply | None in the last 90 days, and any older exploit has a public post-mortem and remediation |
| G3 | Enforcement action against the project or token; arrest or disappearance of key team members; a sanctioned address among the top 20 holders | None |
| G4 | Token migration or redenomination announced but not yet complete | None |

## 4. Daily eligibility

The random control in `risk-policy.md` draws from the **eligible watchlist**. A token is eligible on a UTC day if all of these hold:

1. Approved on `watchlist.md` at the default-branch head, and not suspended.
2. Re-check not overdue.
3. Market cap $5M–$50M on that day's snapshot. A token above the band stays approved, so held positions are unaffected, but it isn't eligible for new entries.
4. B1 and B2 pass on the median of the last 3 daily snapshots.
5. E1 passes.

Hugo takes one depth and market-cap snapshot per approved token per UTC day and records the day's eligible list. Rafael's own entry conditions (regime, book room, depth ≥ 2× position) apply on top. They're his, not part of this gate.

## 5. Suspension triggers

**Effect:** no new entries or tranches; held positions stay held. `strategy.md` §5 applies. Hugo decides within 72h to reinstate or revoke. A non-depth suspension still unresolved after 7 days becomes a revocation (R10).

| # | Trigger (testable) |
|---|---|
| S1 | An exploit report from a security firm, the project, or an on-chain anomaly that isn't yet confirmed |
| S2 | A governance proposal goes to vote (Snapshot or on-chain) to mint, raise the cap, change emissions, or release treasury ≥2% of circulating supply |
| S3 | Re-check overdue |
| S4 | Depth: B1 or B2 fails on the 3-day median, or a single day's ±2% credible depth is below 50% of the floor |
| S5 | No depth snapshot possible for 2 consecutive days |
| S6 | A Monitoring-type, "ST" or risk-warning tag on a credible venue other than Binance |
| S7 | An unidentified wallet moves ≥1% of circulating supply to exchange deposit addresses within 7 days |
| S8 | Price down ≥40% against BTC within 24h with no known cause |
| S9 | A token migration or redenomination is announced |

## 6. Revocation triggers

**Effect:** removed from the watchlist at once. Hugo merges the change without waiting and tells Rafael (and Nadia) on an issue in the same hour. `strategy.md` §5's revocation exit applies: exit in full.

| # | Trigger (testable) |
|---|---|
| R1 | A confirmed exploit of the token contract, the core protocol, or a bridge holding ≥10% of supply |
| R2 | Any of these, observed on-chain: a mint outside the published schedule; a supply-cap increase; an ownership or admin-role change on the token or proxy; an upgrade executed without a ≥48h timelock; blacklist, pause, freeze or tax enabled or used against holders; LP removed or unlocked on a pool covered by F8 |
| R3 | A delisting announced on a credible venue carrying ≥30% of the 3-day median credible depth, or on the venue we hold the position on |
| R4 | Binance Monitoring tag added |
| R5 | Insider wallets (as defined in §1) send to exchange deposit addresses, within any 7-day window, ≥1% of circulating supply **or** ≥5× the 3-day median ±2% credible depth. A schedule published at least 7 days in advance doesn't exempt the move |
| R6 | An unlock, emission step or treasury release of ≥2% of circulating supply comes within 30 days, whether newly announced or a known event coming into the window |
| R7 | The 3-day median ±2% credible depth is below $15,000 on 3 consecutive days, or a depth suspension (S4) lasts 30 days |
| R8 | Enforcement action; arrest or disappearance of key team members; a sanctions designation touching the project or its treasury |
| R9 | A re-check finds that any test in §3 B2–G4 now fails. A1 and B1 drive eligibility (§4) and S4 instead |
| R10 | A non-depth suspension unresolved after 7 days |

**Re-approval:**
- No sooner than 90 days after a revocation, with the failed item fixed and evidenced.
- R1, R2 and R8 revocations are permanent unless Nadia lifts them.
- A rejected token can be resubmitted after 30 days.

## 7. Re-check cadence

| What | When |
|---|---|
| Full re-check of every test in §3 | Every **30 days** from approval. Overdue triggers S3 |
| Depth, market cap, Binance Monitoring and venue delisting notices, E1 window | Daily |
| Insider and large-holder wallet movements, governance proposals | Weekly, plus when an alert fires |
| Any news matching S1–S9 or R1–R10 | Same day |
| Rafael's 6-month and −70% reviews (`strategy.md` §5) | Within 72h of his request |

## 8. What each verdict records (in `watchlist.md`)

- Token, chain(s) and contract addresses.
- Verdict and date; re-check due date.
- Each test's result with its value.
- Depth medians and snapshot dates per venue.
- Sources with UTC timestamps.
- **What wasn't or couldn't be checked.**
- A link to the Crypto Book analysis.

## 9. What this gate doesn't check

- Team quality, product or fundamentals.
- Social sentiment.
- DEX-only liquidity and price action.
- Off-chain arrangements that aren't disclosed (OTC sales, market-maker loans).
- Movements inside exchange wallets.
- Anything on chains without a usable explorer, which gets need-more-info.

An approval is a statement about the tests above at the time stated, nothing more.

## 10. Expected supply and known issue

Snapshot: 2026-10-17 ~08:15 UTC. Market caps from CoinGecko; ±2% and ±5% bid depth from the five credible venues' public L2 books; one snapshot. The 2026-10-16 scan (THE-272) gave 136 tokens at ≥$50k; today gives 131. The DD pass rate (§3 C–G) is assumed at **~25% (15–35%)**, a guess from a sample of 5.

| Depth rule | Pass depth (summed, 5 venues) | Est. eligible after DD |
|---|---|---|
| ≥$50k, **±5% ≥ 1.5× ±2%** (this file) | 12 | **~3 (2–4)** |
| ≥$25k, ±5% ≥ 1.5× ±2% | 29 | ~7 (4–10) |
| ≥$50k, no shape test | 131 | ~33 (20–45) |

**As drafted, the gate won't yield 15 eligible tokens on most days.** The constraint is B2, not DD. The median in-band book has ±5% depth only **~1.1×** its ±2% depth: market makers quote inside ±2% and leave little behind it. That makes the FLUX-type book typical, not an outlier. B2 stays as briefed. Whether to restate it is for Nadia and Rafael (`strategy.md` §1), not something this file changes on its own.
