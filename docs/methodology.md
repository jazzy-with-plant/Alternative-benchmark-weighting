# Methodology

## Research question

Does weighting current borrowing rates by net TVL produce a materially different USDC benchmark from weighting by outstanding debt, when the sampled market rates are held fixed?

## Estimands

For the same sampled market observations `i`:

- `R_TVL = Σ(rate_i × netTVL_i) / Σ(netTVL_i)`
- `R_debt = Σ(rate_i × outstandingDebt_i) / Σ(outstandingDebt_i)`

`rate_i` is a base borrowing APY in percent. Rewards are excluded. Do not mix the weighting comparison with rate changes: the exact same `rate_i` values are used in both calculations.

## Market set and collection

Scope is Ethereum USDC as the loan asset. The collector reads DeFiLlama's public current pool list and lending/borrowing table, joining Aave V3, Compound V3 and SparkLend rows by the stable pool ID. It reads Morpho Blue's public GraphQL market table with `listed = true`, `chainId = 1` and USDC's Ethereum token address as loan asset. The two DeFiLlama responses and the paginated Morpho response are collected within a seven-second interval; each receipt timestamp is in `data/snapshot_metadata.json`.

Include a row when its rate, TVL and debt are present and finite; debt and net TVL are positive; and APY is between 0 and 500%. The 500% upper bound follows DeBOR's documented maximum rate. The script records every excluded candidate and reason in the metadata file. The frozen input contains 126 rows: Aave V3 (3), Compound V3 (1), SparkLend (1), Morpho Blue (121).

This is a market-level Ethereum panel. It is not the exact multi-chain DeBOR configuration. Morpho has many isolated USDC loan markets, while Aave, Compound and Spark expose aggregate pools in this data interface. The sample therefore supports a focused sensitivity study, not a general claim across every chain or a full replication of DeBOR's oracle.

## Weights and source definitions

DeFiLlama's lending-pool `tvlUsd` is `totalSupplyUsd − totalBorrowUsd`. It measures net supplied capital. The debt alternative uses `totalBorrowUsd`. Morpho's `netTvl` is computed from its API's `supplyAssetsUsd − borrowAssetsUsd`; `borrowAssetsUsd` is used as outstanding debt. Both measures are USD at the same API snapshot.

The comparison answers the specific question “net supplied capital versus outstanding debt.” It does not compare debt with gross deposits. If DeBOR uses another interpretation of TVL for its on-chain source weights, this analysis should be rerun with that exact input series.

## Metrics

- **Benchmark APY:** each source APY averaged by its normalized selected weight.
- **Cross-source rate dispersion:** weighted population standard deviation of source APYs at one snapshot. This is a point-in-time disagreement metric, not a time-series volatility estimate.
- **Protocol concentration:** sum source weights within each protocol, then compute `HHI = Σ(protocolWeight²)`. Effective protocol count is `1 / HHI`.
- **Rate-shock sensitivity:** add 100 basis points to every sampled source rate within one protocol, holding weights fixed.
- **Weight-inflation sensitivity:** multiply all weights within one protocol by 2, holding rates fixed.

Sensitivity results are mechanical; they do not model oracle cost, market depth, capital mobility or a feasible attack.

The analyzer also reports rate-cap robustness at 10%, 15%, 20%, 25% and 500%. The 15–500% cuts retain the roughly 4.80 pp benchmark difference; the 10% cut removes Aave's 13.72% reserve and reduces the difference to approximately −0.06 pp. The documented 500% protocol bound is the primary inclusion rule. The 10% case is reported to show how much the snapshot result depends on Aave's current high-rate reserve.

## API rate units

DeFiLlama's `apyBaseBorrow` is already expressed as APY percent. Morpho's GraphQL `state.borrowApy` is a fraction, so the collector multiplies by 100. Both are base borrow rates with rewards excluded. The market API values are not on-chain execution prices; they reflect the protocol's current rate state.

## Primary references

- [DeBOR README](https://github.com/capinhoooo/debor): TVL-weighted rate formula, source cadence and rate bounds.
- [DeFiLlama yield-server schema](https://github.com/DefiLlama/yield-server): lending TVL definition and borrow-pool fields.
- [Morpho API docs](https://docs.morpho.org/developers/api/morpho/): public REST/GraphQL market state, outstanding borrow and APY fields.
- [DeFiLlama Yields API docs](https://defillama.com/docs/api).
