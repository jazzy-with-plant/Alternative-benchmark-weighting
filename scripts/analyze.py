#!/usr/bin/env python3
"""Calculate matched weighted-rate metrics from a CSV snapshot; standard library only."""
import argparse
import csv
import json
import math
from pathlib import Path
from statistics import pstdev


def parse_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit("Input CSV has no observations")
    for row in rows:
        for field in ("rate_pct", "tvl_usd"):
            try:
                row[field] = float(row[field])
            except (KeyError, TypeError, ValueError):
                raise SystemExit(f"Missing or invalid {field} for {row.get('protocol', 'row')}")
            if not math.isfinite(row[field]) or row[field] < 0:
                raise SystemExit(f"{field} must be finite and non-negative")
        raw_debt = row.get("outstanding_debt_usd", "").strip()
        try:
            row["outstanding_debt_usd"] = float(raw_debt) if raw_debt else None
        except ValueError:
            raise SystemExit(f"Invalid outstanding_debt_usd for {row.get('protocol', 'row')}")
    return rows


def weighted_metrics(rows, weight_field):
    weights = [r[weight_field] for r in rows]
    total = sum(weights)
    if total <= 0:
        raise ValueError(f"Total {weight_field} must be positive")
    normalized = [w / total for w in weights]
    rates = [r["rate_pct"] for r in rows]
    mean = sum(w * x for w, x in zip(normalized, rates))
    dispersion = math.sqrt(sum(w * (x - mean) ** 2 for w, x in zip(normalized, rates)))
    hhi = sum(w * w for w in normalized)
    return {"benchmark_rate_pct": mean, "cross_sectional_dispersion_pp": dispersion,
            "hhi": hhi, "effective_sources": 1 / hhi, "weights": normalized}


def run_sensitivities(rows, field, shock_pp=1.0, multiplier=2.0):
    base = weighted_metrics(rows, field)
    rate_shocks, weight_inflation = [], []
    for idx, row in enumerate(rows):
        shocked = [dict(r) for r in rows]
        shocked[idx]["rate_pct"] += shock_pp
        rate_shocks.append({"protocol": row["protocol"], "shock_pp": shock_pp,
                            "benchmark_delta_pp": weighted_metrics(shocked, field)["benchmark_rate_pct"] - base["benchmark_rate_pct"]})
        inflated = [dict(r) for r in rows]
        inflated[idx][field] *= multiplier
        updated = weighted_metrics(inflated, field)
        weight_inflation.append({"protocol": row["protocol"], "weight_multiplier": multiplier,
                                 "benchmark_delta_pp": updated["benchmark_rate_pct"] - base["benchmark_rate_pct"],
                                 "hhi": updated["hhi"], "effective_sources": updated["effective_sources"]})
    return {"base": base, "rate_shock_sensitivity": rate_shocks,
            "weight_inflation_sensitivity": weight_inflation}


def write_svg(rows, metrics, path):
    """Write a small dependency-free chart of observed proxy APY and TVL share."""
    width, height = 960, 520
    left, right, top, bottom = 250, 40, 85, 70
    plot_w, plot_h = width - left - right, height - top - bottom
    max_rate = max(r["rate_pct"] for r in rows) or 1
    max_rate = math.ceil(max_rate / 2) * 2
    bars = []
    for i, row in enumerate(rows):
        y = top + i * (plot_h / len(rows))
        bar_w = row["rate_pct"] / max_rate * plot_w
        share = metrics["weights"][i] * 100
        bars.append(f'<text x="{left-12}" y="{y+28:.1f}" text-anchor="end" class="label">{row["protocol"]}</text>')
        bars.append(f'<rect x="{left}" y="{y+6:.1f}" width="{bar_w:.1f}" height="30" rx="4" fill="#3767c7"/>')
        bars.append(f'<text x="{left+bar_w+10:.1f}" y="{y+27:.1f}" class="value">{row["rate_pct"]:.2f}% APY · {share:.1f}% TVL share</text>')
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<style>text{{font-family:Inter,Arial,sans-serif;fill:#172033}}.title{{font-size:24px;font-weight:700}}.sub{{font-size:13px;fill:#4b5563}}.label{{font-size:14px}}.value{{font-size:13px}}.foot{{font-size:12px;fill:#5b6473}}</style>
<rect width="100%" height="100%" fill="#fff"/><text x="32" y="40" class="title">Ethereum USDC lending pools: supply APY and TVL share</text>
<text x="32" y="64" class="sub">DeFiLlama snapshot · one selected pool per venue · supply-side proxy, not DeBOR borrow rates</text>
{''.join(bars)}<text x="32" y="{height-26}" class="foot">Outstanding debt is unavailable in this endpoint; no debt-weighted comparison is inferred.</text></svg>'''
    path.write_text(svg, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--out", type=Path, default=Path("results"))
    args = parser.parse_args()
    rows = parse_rows(args.csv)
    args.out.mkdir(parents=True, exist_ok=True)
    rate_type = sorted({r.get("rate_type", "unspecified") for r in rows})
    output = {"input": str(args.csv), "observations": len(rows), "rate_types": rate_type,
              "tvl_weighted": run_sensitivities(rows, "tvl_usd"),
              "debt_weighted": None,
              "debt_status": "unavailable: outstanding_debt_usd must be populated for every matched observation"}
    debts = [r["outstanding_debt_usd"] for r in rows]
    if all(d is not None and d >= 0 for d in debts) and sum(debts) > 0:
        output["debt_weighted"] = run_sensitivities(rows, "outstanding_debt_usd")
        output["debt_status"] = "calculated"
    outpath = args.out / "snapshot_analysis.json"
    outpath.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_svg(rows, output["tvl_weighted"]["base"], args.out / "snapshot.svg")
    base = output["tvl_weighted"]["base"]
    print(f"TVL-weighted rate: {base['benchmark_rate_pct']:.4f}%")
    print(f"Cross-sectional dispersion: {base['cross_sectional_dispersion_pp']:.4f} pp")
    print(f"HHI: {base['hhi']:.4f} (effective sources: {base['effective_sources']:.2f})")
    print(f"Debt-weighted: {output['debt_status']}")
    print(f"Wrote {outpath}")

if __name__ == "__main__":
    main()
