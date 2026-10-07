# Issue draft: TVL vs outstanding-debt weights for USDC borrow rates

**Title:** Research question: should the USDC borrow benchmark also be measured with outstanding-debt weights?

## Summary

I compared a TVL-weighted USDC borrow-rate benchmark with an outstanding-debt-weighted version using the same observed market APYs and a matched Ethereum USDC snapshot. Only the weights change.

| Metric | Net-TVL weights | Outstanding-debt weights |
|---|---:|---:|
| Weighted borrow APY | 5.7835% | 10.5826% |
| Cross-source weighted rate dispersion | 2.4053 pp | 4.1843 pp |
| Protocol HHI | 0.5301 | 0.4752 |
| Effective protocol count | 1.89 | 2.10 |

The benchmark moves by **+4.80 percentage points (+83%)** under debt weighting. Aave V3's share rises from 6.3% of net-TVL weight to 63.0% of debt weight; Morpho Blue falls from 69.0% to 26.2%.

The result follows the distinction between net supplied capital and the gross amount borrowed. In this snapshot, Aave USDC reserves carry a large share of debt relative to their remaining net TVL. This is a sensitivity result for one chain, asset and snapshot, not a claim that debt weighting is always the better benchmark.

## Data and reproducibility

- Scope: Ethereum USDC loan markets, collected 2026-10-07 around 00:39 UTC.
- 126 borrow-positive observations: 3 Aave V3 pools, 1 Compound V3 pool, 1 SparkLend pool, and 121 listed Morpho Blue markets.
- Rates are base borrow APY with rewards excluded. The exact same rate vector is used for both calculations.
- Net TVL uses DeFiLlama's lending-pool definition (`totalSupplyUsd - totalBorrowUsd`); Morpho net TVL is computed as `supplyAssetsUsd - borrowAssetsUsd`.
- Candidates with missing data, zero balances, or APY outside DeBOR's documented 0–500% bounds are excluded and listed in metadata.
- The gap remains 4.80 pp after excluding rates above 15%. With a 10% cap, the gap disappears because Aave's 13.72% reserve is excluded; the main result uses DeBOR's documented 500% cap.

This is not a reconstruction of DeBOR's configured multi-chain source universe. In particular, the Ethereum Morpho market set is broad, while the other protocols are represented by the public aggregate pools available from the data endpoints. I would be glad to rerun against the exact configured source list if that is the preferred comparison.

## Questions

1. Is the intended `tvlUsd` weight net supplied capital, or another TVL measure?
2. Would a debt-weighted diagnostic or side-by-side methodology comparison be useful for the borrow benchmark, given how much the weighting basis can change source shares and the resulting rate?

## Artifacts

- [Full study and limitations](https://github.com/jazzy-with-plant/Alternative-benchmark-weighting/blob/main/README.md)
- [Frozen market-level input data](https://github.com/jazzy-with-plant/Alternative-benchmark-weighting/blob/main/data/ethereum_usdc_borrow_snapshot.csv)
- [Collection timestamps and excluded markets](https://github.com/jazzy-with-plant/Alternative-benchmark-weighting/blob/main/data/snapshot_metadata.json)
- [Analysis code](https://github.com/jazzy-with-plant/Alternative-benchmark-weighting/blob/main/scripts/analyze.py) and [snapshot collector](https://github.com/jazzy-with-plant/Alternative-benchmark-weighting/blob/main/scripts/fetch_snapshot.py)
- [Results JSON](https://github.com/jazzy-with-plant/Alternative-benchmark-weighting/blob/main/results/snapshot_analysis.json)
- [Comparison chart](https://github.com/jazzy-with-plant/Alternative-benchmark-weighting/blob/main/results/weighting_comparison.svg)
