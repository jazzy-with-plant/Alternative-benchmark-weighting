# Methodology and data contract

## Target comparison

For observations `i` drawn from the same asset, chain, timestamp, and market universe, calculate two benchmarks while holding each observed rate fixed:

- TVL-weighted: `R_T = sum(r_i * tvl_i) / sum(tvl_i)`
- Outstanding-debt-weighted: `R_D = sum(r_i * debt_i) / sum(debt_i)`

Use protocol-level aggregation before comparing if the target estimand is protocol influence. For Morpho, decide whether the unit is each market or the whole protocol before collecting data; these are different weighting questions. Do not mix protocol totals with individual market rows.

## Metrics

- **Benchmark rate:** weighted mean, in percentage points.
- **Cross-sectional disagreement:** weighted population standard deviation across rates for one observation time. This measures source disagreement, not realized time-series volatility.
- **Time-series volatility:** standard deviation of equally spaced benchmark changes over a declared window; requires repeated synchronized observations and must be reported separately.
- **Concentration:** HHI `sum(w_i^2)` and effective count `1 / HHI`, using normalized weights.
- **Weight-inflation sensitivity:** recompute after multiplying one source's weight by a stated factor, with all rates unchanged.
- **Rate-shock sensitivity:** recompute after adding a stated number of basis points to one source rate, with all weights unchanged.

The last two are mechanical stress tests, not evidence that the protocol is manipulable. To assess actual manipulation risk, model the cost and feasibility of moving the source rate and the data/oracle path.

## Required input columns

`protocol, chain, asset, observed_at_utc, market_id, rate_borrow_apy_pct, tvl_usd, outstanding_debt_usd, rate_source, balance_source`

All amounts must use USD at the same observation time. Borrow rate definition (APR/APY, base/reward-included, variable/fixed) and debt definition (principal vs accrued balance, included debt modes, bad debt) must be consistent or separately stratified. Exclude stale, paused, non-borrowable, or zero-debt markets under predeclared rules.

## Current snapshot audit

`data/defillama_snapshot.csv` is a frozen capture from the public DeFiLlama pool list on 2026-10-07. It contains the chosen Ethereum USDC supply-side APY and TVL observations for Aave V3, Compound V3, SparkLend, and one Morpho Blue USDC-loan market. DeFiLlama's endpoint did not expose debt balances or borrow APY in these rows. Therefore:

- the rate column is a **supply APY proxy**, not DeBOR's borrow-rate input;
- the Morpho observation is one market while the other rows are protocol pools;
- debt-weighted results are unavailable;
- one timestamp cannot support time-series volatility;
- the snapshot can demonstrate the calculation mechanics and data gaps, but cannot settle whether DeBOR should use TVL or debt weights.

Do not use the proxy output as an empirical finding about DeBOR. A complete study should collect matched on-chain borrow rates and debt balances, preferably at 30-minute intervals to align with the cadence described by DeBOR, for a declared lookback period.

## Primary references

- [DeBOR repository and methodology](https://github.com/capinhoooo/debor) (README: benchmark formula and data flow).
- [DeFiLlama Yields API](https://defillama.com/docs/api).
- [Morpho API documentation](https://docs.morpho.org/developers/api/morpho/) (market state, borrow assets, APY, and historical-state fields).
