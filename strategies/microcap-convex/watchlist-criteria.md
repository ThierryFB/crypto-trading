# Watchlist criteria: Micro-cap Convex

**Owner:** Hugo (Token DD Analyst). **Merged by:** Nadia. **Applies to:** this strategy only.
**Status:** rev 4, 2026-10-24 (sized for a EUR 1,000 paper sleeve, `risk-policy.md` §1; adds the DEX cohort gate, §11). **Phase: definition.** No trading.

This file says what a token must pass to go on `watchlist.md`, what makes it eligible on a given day, and what suspends or revokes it. `strategy.md` (Rafael) decides whether to trade an eligible token. Changes to this file go through a PR that Nadia merges. Changes to `watchlist.md` are Hugo's and merge only under the criteria in force on the default branch.

**Default is no.** Passing every test below means the token cleared the checks listed here. It does not mean the token is safe. One failed hard test is enough to reject. A test that can't be run counts as not passed: the verdict is *need-more-info*, not approval.

## 1. Definitions

- **Credible venues:** Binance, Coinbase, Kraken, OKX, Bybit. Upbit counts only if the desk gets access. Once THE-270 settles which venues we hold accounts on, only those count. Until then, all five count.
- **Zero-weight venues:** tier 2 (Bitget, KuCoin, Gate, MEXC) and wash venues (HTX, LBank, GroveX, BTCC, and any venue added here by PR). Their depth and volume count for zero.
- **DEX pools:** count for zero, with one exception: **Solana pools for DEX-cohort tokens, under §11 only.** They never count toward B1–B4 for a CEX-cohort token. Every other chain's pools count for zero until a PR adds that chain (`risk-policy.md` §1a).
- **Cohort:** a token with a usable pair (B4) on any credible venue is in the **CEX cohort** and is gated by §3. A token with none is in the **DEX cohort** and is gated by §11 (`risk-policy.md` §1a, mixed listings).
- **Venue minimum:** the smallest order the venue accepts on a pair, in USD: the larger of its minimum notional and its minimum quantity × mid. **Half an entry tranche** is set in `risk-policy.md` §1 (about USD 9 at EUR 1,000).
- **Usable pair:** a USD, USDT or USDC pair on a credible venue whose venue minimum is ≤ half an entry tranche (B4). A pair above that doesn't count as one of our venues for that token: its depth counts for zero.
- **Depth snapshot:** one public REST L2 order-book read per credible venue, on a usable pair (the deepest one if there are several). Mid is (best bid + best ask) / 2. **±2% depth** is the USD value of bids at or above 0.98 × mid; **±5% depth** is the same at 0.95 × mid. A book that doesn't reach 0.95 × mid is re-read deeper. If it still doesn't, that venue's snapshot fails.
- **Credible depth:** ±2% (or ±5%) bid depth summed across usable pairs on credible venues for one snapshot.
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
| B2 | ±5% ÷ ±2% credible depth, per snapshot | **Recorded, not a test** (removed in rev 2) |
| B3 | Credible venues with depth | ≥ 1 venue other than Kraken alone, unless the desk only holds Kraken |
| B4 | Venue minimum on each pair counted in B1 and B3 | ≤ half an entry tranche. A pair above it is dropped from B1 and B3, not failed |

**Why B1 stays at $50k.** At EUR 1,000 a position is about EUR 50 and needs about USD 115 of depth (`risk-policy.md` L2), so the floor no longer sizes exits. It filters out hollow or thin books that one wallet can move. A lower floor would admit exactly those books.

**Why B2 is a diagnostic.** It guarded against the next fill falling off a cliff when a position is a sizeable share of depth. At EUR 50 a position is never near that. The ratio is still recorded per snapshot in `watchlist.md`, so a book thinning behind ±2% is visible.

**Single walls.** One cancellable wall (say $45k at −1.8% in a $50k book) passes B1 and its median, and C3 only catches it if the volume is fake too. The largest-level share (§8) records this per snapshot. It's a diagnostic for now, not a test.

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
4. B1 passes on the median of the last 3 daily snapshots, counting only usable pairs (B4).
5. E1 passes.

Hugo takes one depth and market-cap snapshot per approved token per UTC day and records the day's eligible list. Rafael's own entry conditions (regime, book room, depth ≥ 2× position) apply on top. They're his, not part of this gate.

## 5. Suspension triggers

**Effect:** no new entries or tranches; held positions stay held. `strategy.md` §5 applies. Hugo decides within 72h to reinstate or revoke. A non-depth suspension still unresolved after 7 days becomes a revocation (R10).

| # | Trigger (testable) |
|---|---|
| S1 | An exploit report from a security firm, the project, or an on-chain anomaly that isn't yet confirmed |
| S2 | A governance proposal goes to vote (Snapshot or on-chain) to mint, raise the cap, change emissions, or release treasury ≥2% of circulating supply |
| S3 | Re-check overdue |
| S4 | Depth: B1 fails on the 3-day median, or a single day's ±2% credible depth is below 50% of the floor, or no credible venue has a usable pair (B4) |
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
| R9 | A re-check finds that B3 or any test in §3 C1–G4 now fails. A1, B1 and B4 drive eligibility (§4) and S4 instead |
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
- Depth medians and snapshot dates per venue, with the ±5% ÷ ±2% ratio for each snapshot.
- **Largest-level share**, per snapshot: the USD value of the largest single bid price level within ±2% on any one usable pair, ÷ that snapshot's ±2% credible depth, with its venue and distance from mid. A level is one price as the venue's REST L2 returns it, not aggregated across venues or ticks. **Recorded, not a test:** no threshold until Nadia reviews the distribution after the first 10 approvals. If the share is ≥ 50% on every snapshot behind the B1 median, the verdict carries a **single-wall flag** for Nadia's review. The flag doesn't reject or delay approval.
- Each pair's venue minimum (USD), source and UTC timestamp, and whether it's usable (B4).
- Sources with UTC timestamps.
- **What wasn't or couldn't be checked.**
- A link to the Crypto Book analysis.

## 9. What this gate doesn't check

- Team quality, product or fundamentals.
- Social sentiment.
- DEX-only liquidity and price action, except Solana DEX-cohort tokens under §11.
- Off-chain arrangements that aren't disclosed (OTC sales, market-maker loans).
- Movements inside exchange wallets.
- Anything on chains without a usable explorer, which gets need-more-info.

An approval is a statement about the tests above at the time stated, nothing more.

## 10. Expected supply

Snapshot: 2026-10-17 ~08:15 UTC. Market caps from CoinGecko; ±2% and ±5% bid depth from the five credible venues' public L2 books; one snapshot. The 2026-10-16 scan (THE-272) gave 136 tokens at ≥$50k; today gives 131. The DD pass rate (§3 C–G) is assumed at **~25% (15–35%)**, a guess from a sample of 5.

| Depth rule | Pass depth (summed, 5 venues) | Est. eligible after DD |
|---|---|---|
| **≥$50k, no shape test (this file, rev 2)** | **131** | **~33 (20–45)** |
| ≥$50k, ±5% ≥ 1.5× ±2% (rev 1, dropped) | 12 | ~3 (2–4) |
| ≥$25k, ±5% ≥ 1.5× ±2% (not adopted) | 29 | ~7 (4–10) |

That covers N = 20 at the central estimate, not at the low end. B4 wasn't applied in the scan. Binance's 511 trading USDT pairs all have a minimum notional of $1 or $5 (exchangeInfo, 2026-10-17 16:03 UTC), so B4 removes nothing there. Coinbase, Kraken, OKX and Bybit minimums weren't checked. They're checked per pair at approval.

## 11. DEX cohort: Solana

`risk-policy.md` §1a puts DEX tokens in a separate paper cohort, on one chain. The chain is **Solana** (THE-293 scan, 2026-10-24: 16 in-band, DEX-only tokens passed a first cut on Solana and none on Base). This section is the gate for that cohort. Everything above still applies unless this section replaces it.

On a CEX, the venue stands between us and the token. On a DEX nothing does. The tests below are what protects the book from theft: a mint, a freeze, a pulled pool or an unsellable token. P11 (`risk-policy.md` §3) reviews every such loss against what these tests recorded at entry, so every test here is run from public data and leaves a stored record (§11.8).

### 11.1 Definitions (DEX cohort only)

- **Counted pool:** a Solana pool that pairs the token with SOL (wrapped SOL), USDC or USDT, on Raydium (AMM v4, CPMM, CLMM), Meteora (DLMM, DAMM v1/v2), Orca Whirlpools or PumpSwap, and that Jupiter routes through. A pool against any other token counts for zero. That rule filters hollow pools: liquidity priced in a token the project also controls isn't depth. Adding a program to this list is a PR.
- **Quote reserve:** the USD value of the SOL/USDC/USDT side of a counted pool, read from pool state. For concentrated pools (CLMM, DLMM, Whirlpools), only the liquidity within ±10% of the current price counts.
- **Locked liquidity:** quote reserve in a counted pool whose LP is:
  - burned (LP tokens sent to the incinerator, or burned at PumpSwap graduation); or
  - locked in a named locker contract (for example Raydium's LP lock, Meteora's permanent lock, Streamflow or Jupiter Lock) until at least the next re-check date plus 90 days; or
  - held by a program with no withdrawal path for the team.

  A concentrated-liquidity position held by a wallet is **unlocked**, however long it has sat there.
- **Mid:** the USDC out per token for a USD 10 Jupiter sell quote.
- **Sell cost at size *s*:** 1 − (USDC out for a Jupiter sell quote of USD *s* ÷ (*s* × mid)), routed only through counted pools.
- **−2% sell depth:** the largest USD *s* on the ladder 58 / 500 / 1,000 / 2,000 / 5,000 / 10,000 whose sell cost is ≤ 2%. The ladder starts at about one position (EUR 50).
- **DEX snapshot:** one read of all the above (pool list, quote reserves, LP state, the quote ladder), plus the mint account and holder list, taken together and stored (§11.8).
- **Pool age:** the age of the oldest counted pool. It replaces §2's "first listed on a credible venue" for the 90-day rule.

### 11.2 Which tests apply

| §3 block | DEX cohort |
|---|---|
| A (market cap) | A1 applies. If CoinMarketCap doesn't list the token, CoinGecko's figure is checked against on-chain supply × mid instead, and the verdict says so |
| B (credible depth) | **Replaced** by DP1–DP3 |
| C (fake volume) | **Replaced** by DW1–DW4 |
| D (holders) | Applies, with the extra exclusions in DH1. DH2 adds a test |
| E (unlocks) | Applies |
| F (contract) | **Replaced** by DA1–DA4, DL1–DL2 and DS1–DS2 |
| G (flags) | G2–G4 apply. G1 is replaced by DS2's scanner flags |

### 11.3 Approval tests (all must pass)

Each test gets a pass or fail, its value, its source and a UTC timestamp (and the Solana slot where there is one).

**Authorities and token program** (from `getAccountInfo` on the mint, cross-checked with RugCheck):

| # | Test | Pass |
|---|---|---|
| DA1 | Mint authority | None (null) |
| DA2 | Freeze authority | None (null) |
| DA3 | Token program | SPL Token; or Token-2022 with **none** of: permanent delegate, transfer hook, pausable, default account state = frozen, non-transferable, confidential transfers, a transfer fee above 0, or a transfer-fee config authority that isn't null |
| DA4 | Mint created by a launchpad or deployer that RugCheck or GoPlus flags as a known rug source | No |

Metadata update authority is recorded, not tested. Changing a name or logo can't move funds.

**Liquidity lock** (pool state, RugCheck lockers, the locker contract):

| # | Test | Pass |
|---|---|---|
| DL1 | Locked liquidity ÷ quote reserve across counted pools | ≥ 50% |
| DL2 | The counted pool with the largest quote reserve is locked liquidity | Yes |

The verdict records, per counted pool: program, quote reserve, locked share, locker (name and address) and unlock date.

**Sell check:**

| # | Test | Pass |
|---|---|---|
| DS1 | **Sell simulation at our size.** A Jupiter swap transaction selling USD 58 of the token for USDC, built for an existing non-insider holder's address, run through RPC `simulateTransaction` with signature verification off. Nothing is signed or sent, and no wallet of ours is involved. The simulation must succeed, and its USDC out must be within 1% of the quote | Yes |
| DS2 | RugCheck, GoPlus (Solana) and De.Fi flag no honeypot, rug, freeze or "cannot sell" risk | None |

**Holders:**

| # | Test | Pass |
|---|---|---|
| DH1 | D1–D5, also excluding: counted pool vaults, locker escrows, launchpad bonding-curve accounts and the incinerator. The deployer wallet and any wallet it funded before launch are insider wallets | As D1–D5 |
| DH2 | Wallets RugCheck groups as one insider or bundle network, taken together, % of circulating supply | ≤ 10%. Counted under D3 either way |

**Pool depth (replaces B1–B4):**

| # | Test | Pass |
|---|---|---|
| DP1 | Quote reserve across counted pools, median of ≥3 DEX snapshots on 3 different UTC days within 14 days | ≥ **$100,000** |
| DP2 | −2% sell depth, median of the same snapshots | ≥ **$2,000** |
| DP3 | Pool age | ≥ 90 days |

**Why these floors, and not $50k of −2% depth like B1.**
- **Our size doesn't need them.** A EUR 50 position needs about USD 115 of depth (`risk-policy.md` L2). On 2026-10-24, a USD 58 sell cost at most 0.23% on every token that passed the first cut. So, as with B1 at this size, the floors are there to filter out bad markets, not to size exits.
- **A pool can't be hollow the way a book can.** Pool liquidity can't be cancelled the way a wall can. It can only be withdrawn, and DL1–DL2 make sure at least half of it can't be. The DEX ways to fake depth are different, and the tests aim at them:
  - **liquidity paired against a token the project controls:** counts for zero (§11.1). On 2026-10-24 one Base token showed $9M of "liquidity", all against about 30 junk tokens;
  - **unlocked liquidity that can be pulled:** DL1–DL2, R2-style revocation (DR2);
  - **concentrated liquidity parked far from the price:** only ±10% counts.
- **Why $100k and $2,000.** A CEX-style $50k at −2% would need a full-range pool of about $5M quote reserve. On 2026-10-24 only two DEX-only Solana tokens that passed the contract checks had that much, and one wallet holds over 85% of the supply in both. The cohort retirement trigger (`risk-policy.md` §4) is about 10 eligible tokens, so that floor would kill the cohort before it starts. With $100k of quote reserve and ≥50% locked, at least $50k can't be withdrawn. The $2,000 floor is about 35 positions: one wallet with a few thousand dollars moves a pool like that 2% either way, and DW1–DW4 check whether someone is doing it. Of the 16 first-cut tokens, all cleared $2,000 at one snapshot and 9 cleared $5,000.

**Wash volume (replaces C1–C4).** Volumes count counted pools only. "Trades" means the last 300 swaps on the counted pool with the largest quote reserve, read from GeckoTerminal's public trades feed or from the chain.

| # | Test | Pass | If it fails |
|---|---|---|---|
| DW1 | 7-day average daily volume ÷ market cap | ≤ 1.0× | Reject |
| DW2 | 7-day average daily volume ÷ quote reserve, against the median of DEX-cohort candidates in the same snapshot | ≤ 5× that median | Need-more-info, then a manual trade review |
| DW3 | In the trades: the 5 most active signer wallets' share of USD volume, and the share of volume from wallets that buy and sell within 60 seconds of each other | ≤ 50%, and ≤ 25% | Need-more-info, then a manual review |
| DW4 | In the trades: share of trade count taken by the 3 most frequent trade sizes (rounded to USD 1) | ≤ 30% | Need-more-info, then a manual review |

### 11.4 Daily eligibility (DEX cohort)

§4 applies with these substitutions. Hugo takes one DEX snapshot per approved DEX token per UTC day.
- Item 4 becomes: DP1 and DP2 pass on the median of the last 3 daily DEX snapshots, **and** DL1, DL2 and DA1–DA3 pass on today's.
- Added: DS1 passed within the last 24 hours.
- Added: the token still has no usable pair on a credible venue. Once it gets one, it leaves the DEX cohort for new entries (`risk-policy.md` §1a). Held DEX positions are unaffected. The token can be submitted to §3 for the CEX cohort.

### 11.5 Suspension triggers (DEX cohort)

§5 applies, with S4 and S5 replaced:

| # | Trigger (testable) |
|---|---|
| DS-S1 | DP1 or DP2 fails on the 3-day median, or a single day's quote reserve is below $50,000 |
| DS-S2 | No DEX snapshot possible for 2 consecutive days |
| DS-S3 | A DS1 simulation fails once. Hugo re-runs it within 1 hour. If the re-run fails too, DR3 applies |
| DS-S4 | Quote reserve across counted pools falls ≥ 30% within 24h through withdrawals rather than price |
| DS-S5 | A locker unlock date comes within 30 days of the next re-check |

### 11.6 Revocation triggers (DEX cohort)

§6 applies, and these are added. Each takes effect at once: Hugo merges the watchlist change without waiting and tells Rafael (and Nadia) on an issue within the hour, as for the CEX triggers.

| # | Trigger (testable, on-chain) |
|---|---|
| DR1 | Any authority or extension change on the mint: a mint or freeze authority appears, a Token-2022 extension or fee config listed in DA3 is set or changed, or an account holding the token is frozen |
| DR2 | Locked liquidity is withdrawn, or a lock expires or is extended to a wallet, on any counted pool, **or** DL1 or DL2 fails on any daily snapshot |
| DR3 | DS1 fails twice in a row (DS-S3), or any scanner in DS2 newly flags honeypot, rug or cannot-sell |
| DR4 | The deployer, or a wallet DH1 or DH2 counts as insider, removes liquidity from a counted pool, or sells ≥ 1% of circulating supply within 7 days |
| DR5 | A depth suspension (DS-S1) lasts 30 days, or the quote reserve is below $30,000 on 3 consecutive days |

DR1–DR3 revocations are permanent, as R1, R2 and R8 are.

### 11.7 Re-check cadence (DEX cohort)

§7 applies. Added: a daily DEX snapshot covering DA1–DA3, DL1–DL2, DS1 and DP1–DP2 (§11.4). DH and DW tests run weekly as well as at the 30-day re-check.

### 11.8 What each DEX verdict and snapshot records (for P11)

Each verdict records everything in §8 except the CEX-only items, plus:
- the mint address, token program and every extension, with the authority values and the slot they were read at;
- per counted pool: address, program, quote reserve, locked share, locker and unlock date;
- the quote ladder: each size, its USDC out, its sell cost, and the route;
- the DS1 simulation: the holder address used, the slot, success or failure, and the USDC out;
- the RugCheck, GoPlus and De.Fi responses, stored raw;
- DH1 and DH2 holder shares, with the wallets excluded and why.

Each daily DEX snapshot is stored the same way and gets an ID. An entry or tranche logs the ID of the day's snapshot. P11 can then show what the gate saw at entry and whether it should have caught the loss.

### 11.9 What §11 doesn't check

As §9, plus:
- MEV and sandwich risk at the moment of our fill. The 0.5% MEV allowance in `strategy.md` §6 covers it on paper.
- RPC or Jupiter errors that report a wrong pool state. Two sources (RugCheck and the chain) are cross-checked for authorities and LP. The quote ladder relies on Jupiter alone.
- Off-chain promises about locks. Only on-chain locks count.
- Wallet-clustering beyond what RugCheck and the funding trail show. A deployer who funds wallets through a mixer or a CEX withdrawal won't be caught by DH1.
- Tokens without a CoinGecko listing. They can't pass A1.

### 11.10 Expected supply (DEX cohort)

Snapshot: 2026-10-24, 10:37–11:22 UTC. One snapshot, not a 3-day median. The first cut covered DA1–DA3, DL1, D1–D2, DP1 (using all pool liquidity, not the ±10% concentrated rule), a DEX volume of $10k/day to 1× market cap, and DP3.

| | Solana | Base (not chosen) |
|---|---|---|
| In band, contract on chain (CoinGecko) | 280 | 253 |
| In scope (§2) and on no credible venue | 129 | 118 |
| Pass the first cut | **16** | 0 |

All 16 are memecoins, most of them pump.fun graduates. DS1, DH2, DW1–DW4, D3–D5, E and G weren't run. If those remove a third to a half, about **8–11** are eligible, close to the retirement trigger of about 10 (`risk-policy.md` §4).
