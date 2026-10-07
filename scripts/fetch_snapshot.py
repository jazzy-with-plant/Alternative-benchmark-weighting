#!/usr/bin/env python3
"""Fetch matched Ethereum USDC borrow markets from DeFiLlama and Morpho public APIs."""
import csv
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

USDC = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
LLAMA_POOLS = "https://yields.llama.fi/pools"
LLAMA_LEND_BORROW = "https://yields.llama.fi/lendBorrow"
MORPHO_GRAPHQL = "https://api.morpho.org/graphql"
PROTOCOLS = {"aave-v3", "compound-v3", "sparklend"}
MAX_BORROW_APY_PCT = 500.0  # DeBOR's documented rate bound is 500%.


def get_json(url):
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "alternative-benchmark-weighting/1.0"})
    with urllib.request.urlopen(req, timeout=60) as response:
        received_at = datetime.now(timezone.utc).isoformat()
        return json.loads(response.read()), received_at


def post_graphql(query):
    payload = json.dumps({"query": query}).encode()
    req = urllib.request.Request(MORPHO_GRAPHQL, data=payload, headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "alternative-benchmark-weighting/1.0"})
    with urllib.request.urlopen(req, timeout=60) as response:
        received_at = datetime.now(timezone.utc).isoformat()
        result = json.loads(response.read())
    if result.get("errors"):
        raise RuntimeError(json.dumps(result["errors"]))
    return result["data"]["markets"], received_at


def fetch_morpho():
    all_markets, skip, total = [], 0, None
    while total is None or skip < total:
        query = f'''query {{ markets(first: 100, skip: {skip}, orderBy: SupplyAssetsUsd, orderDirection: Desc,
          where: {{ listed: true, chainId_in: [1], loanAssetAddress_in: ["{USDC}"] }}) {{
          items {{ marketId collateralAsset {{ symbol }} state {{ supplyAssetsUsd borrowAssetsUsd borrowApy utilization }} }}
          pageInfo {{ countTotal count }} }} }}'''
        result, received_at = post_graphql(query)
        items = result["items"]
        if total is None:
            total = result["pageInfo"]["countTotal"]
        all_markets.extend((item, received_at) for item in items)
        skip += len(items)
        if not items:
            break
    return all_markets


def main():
    pools, pools_at = get_json(LLAMA_POOLS)
    borrow_rows, borrow_at = get_json(LLAMA_LEND_BORROW)
    pools = pools.get("data", pools) if isinstance(pools, dict) else pools
    borrow_rows = borrow_rows.get("data", borrow_rows) if isinstance(borrow_rows, dict) else borrow_rows
    borrow_by_pool = {row.get("pool"): row for row in borrow_rows if row.get("pool")}

    rows, exclusions = [], []
    for pool in pools:
        if pool.get("project") not in PROTOCOLS or pool.get("chain") != "Ethereum" or pool.get("symbol") != "USDC":
            continue
        borrow = borrow_by_pool.get(pool.get("pool"))
        if not borrow:
            exclusions.append({"protocol": pool.get("project"), "source_id": pool.get("pool"), "reason": "no matching public lendBorrow row"})
            continue
        rate = borrow.get("apyBaseBorrow")
        debt = borrow.get("totalBorrowUsd")
        tvl = pool.get("tvlUsd")
        if not all(isinstance(x, (int, float)) for x in (rate, debt, tvl)):
            exclusions.append({"protocol": pool.get("project"), "source_id": pool.get("pool"), "reason": "missing borrow rate, debt, or TVL"})
            continue
        if debt <= 0 or tvl <= 0 or rate < 0 or rate > MAX_BORROW_APY_PCT:
            exclusions.append({"protocol": pool.get("project"), "source_id": pool.get("pool"), "reason": "zero/negative balance or rate outside 0-500%"})
            continue
        rows.append({"protocol": pool["project"], "chain": "Ethereum", "asset": "USDC", "source_id": pool["pool"],
                     "market_label": pool.get("poolMeta") or pool.get("symbol"), "observed_at_utc": borrow_at,
                     "rate_type": "base borrow APY, rewards excluded", "rate_pct": rate,
                     "tvl_usd": tvl, "outstanding_debt_usd": debt,
                     "total_supply_usd": borrow.get("totalSupplyUsd"), "rate_source": LLAMA_LEND_BORROW,
                     "weight_source": LLAMA_POOLS})

    morpho_markets = fetch_morpho()
    for market, observed_at in morpho_markets:
        state = market.get("state") or {}
        debt, supply, rate_fraction = (state.get("borrowAssetsUsd"), state.get("supplyAssetsUsd"), state.get("borrowApy"))
        if not all(isinstance(x, (int, float)) for x in (debt, supply, rate_fraction)):
            exclusions.append({"protocol": "morpho-blue", "source_id": market.get("marketId"), "reason": "missing Morpho market rate or balance"})
            continue
        tvl, rate = supply - debt, rate_fraction * 100
        if debt <= 0 or tvl <= 0 or rate < 0 or rate > MAX_BORROW_APY_PCT:
            exclusions.append({"protocol": "morpho-blue", "source_id": market["marketId"], "reason": "zero/negative balance or rate outside 0-500%"})
            continue
        rows.append({"protocol": "morpho-blue", "chain": "Ethereum", "asset": "USDC", "source_id": market["marketId"],
                     "market_label": market.get("collateralAsset", {}).get("symbol") or "unknown collateral",
                     "observed_at_utc": observed_at, "rate_type": "borrow APY (Morpho native)",
                     "rate_pct": rate, "tvl_usd": tvl, "outstanding_debt_usd": debt,
                     "total_supply_usd": supply, "rate_source": MORPHO_GRAPHQL, "weight_source": MORPHO_GRAPHQL})

    rows.sort(key=lambda row: (row["protocol"], row["source_id"]))
    out = Path("data/ethereum_usdc_borrow_snapshot.csv")
    out.parent.mkdir(exist_ok=True)
    fields = list(rows[0].keys())
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)
    metadata = {"scope": "Ethereum, USDC loan asset; borrow-positive pools/markets only", "pool_list_received_at_utc": pools_at,
                "lend_borrow_received_at_utc": borrow_at, "morpho_query_received_at_utc": sorted({t for _, t in morpho_markets}),
                "input_pool_count": len(rows), "counts_by_protocol": {p: sum(r["protocol"] == p for r in rows) for p in sorted({r["protocol"] for r in rows})},
                "excluded_count": len(exclusions), "excluded": exclusions,
                "rate_note": "DeFiLlama borrow APY excludes rewards; Morpho borrowApy fraction converted to percent.",
                "weight_note": "DeFiLlama lending tvlUsd is net supplied capital (totalSupplyUsd - totalBorrowUsd). Morpho net TVL is computed the same way."}
    Path("data/snapshot_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: metadata[k] for k in ("scope", "pool_list_received_at_utc", "lend_borrow_received_at_utc", "morpho_query_received_at_utc", "input_pool_count", "counts_by_protocol", "excluded_count")}, indent=2))

if __name__ == "__main__":
    main()
