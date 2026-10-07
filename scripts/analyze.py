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
    source_hhi = sum(w * w for w in normalized)
    protocol_weights = {}
    for row, weight in zip(rows, normalized):
        protocol_weights[row["protocol"]] = protocol_weights.get(row["protocol"], 0.0) + weight
    protocol_hhi = sum(w * w for w in protocol_weights.values())
    protocol_rates = {}
    for protocol in protocol_weights:
        selected = [(row, weight) for row, weight in zip(rows, weights) if row["protocol"] == protocol]
        protocol_rates[protocol] = sum(row["rate_pct"] * weight for row, weight in selected) / sum(weight for _, weight in selected)
    between_protocol_dispersion = math.sqrt(sum(protocol_weights[p] * (protocol_rates[p] - mean) ** 2 for p in protocol_weights))
    # Within-protocol aggregation uses the same weighting scheme; this gives one shock/sensitivity row per protocol.
    return {"benchmark_rate_pct": mean, "cross_sectional_dispersion_pp": dispersion,
            "cross_protocol_dispersion_pp": between_protocol_dispersion,
            "source_hhi": source_hhi, "effective_sources": 1 / source_hhi,
            "protocol_hhi": protocol_hhi, "effective_protocols": 1 / protocol_hhi,
            "protocol_weights": protocol_weights, "protocol_rates_pct": protocol_rates,
            "weights": normalized}


def run_sensitivities(rows, field, shock_pp=1.0, multiplier=2.0):
    base = weighted_metrics(rows, field)
    rate_shocks, weight_inflation = [], []
    for protocol in sorted({row["protocol"] for row in rows}):
        shocked = [dict(r) for r in rows]
        for row in shocked:
            if row["protocol"] == protocol:
                row["rate_pct"] += shock_pp
        rate_shocks.append({"protocol": protocol, "shock_pp": shock_pp,
                            "benchmark_delta_pp": weighted_metrics(shocked, field)["benchmark_rate_pct"] - base["benchmark_rate_pct"]})
        inflated = [dict(r) for r in rows]
        for row in inflated:
            if row["protocol"] == protocol:
                row[field] *= multiplier
        updated = weighted_metrics(inflated, field)
        weight_inflation.append({"protocol": protocol, "weight_multiplier": multiplier,
                                 "benchmark_delta_pp": updated["benchmark_rate_pct"] - base["benchmark_rate_pct"],
                                 "protocol_hhi": updated["protocol_hhi"], "effective_protocols": updated["effective_protocols"]})
    return {"base": base, "rate_shock_sensitivity": rate_shocks,
            "weight_inflation_sensitivity": weight_inflation}


def write_svg(tvl_result, debt_result, path):
    """Write protocol-level rate and weighting comparison as dependency-free SVG."""
    width, height = 1050, 450
    protocols = sorted(tvl_result["protocol_weights"])
    max_share = max(max(tvl_result["protocol_weights"].values()), max(debt_result["protocol_weights"].values()))
    max_rate = max(max(tvl_result["protocol_rates_pct"].values()), max(debt_result["protocol_rates_pct"].values()))
    bars = []
    for i, protocol in enumerate(protocols):
        y = 110 + i * 72
        tvl_share = tvl_result["protocol_weights"][protocol]
        debt_share = debt_result["protocol_weights"][protocol]
        tvl_rate = tvl_result["protocol_rates_pct"][protocol]
        debt_rate = debt_result["protocol_rates_pct"][protocol]
        tx = 275 + tvl_share / max_share * 300
        dx = 275 + debt_share / max_share * 300
        bars.append(f'<text x="255" y="{y+21}" text-anchor="end" class="label">{protocol}</text>')
        bars.append(f'<rect x="275" y="{y}" width="{tvl_share/max_share*300:.1f}" height="20" rx="3" fill="#3778c2"/><text x="{tx+8:.1f}" y="{y+15}" class="value">{tvl_share*100:.1f}% · {tvl_rate:.2f}% rate</text>')
        bars.append(f'<rect x="275" y="{y+27}" width="{debt_share/max_share*300:.1f}" height="20" rx="3" fill="#e27b3f"/><text x="{dx+8:.1f}" y="{y+42}" class="value">{debt_share*100:.1f}% · {debt_rate:.2f}% rate</text>')
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<style>text{{font-family:Inter,Arial,sans-serif;fill:#172033}}.title{{font-size:23px;font-weight:700}}.sub{{font-size:13px;fill:#4b5563}}.label{{font-size:14px}}.value{{font-size:12px}}.foot{{font-size:12px;fill:#5b6473}}</style>
<rect width="100%" height="100%" fill="#fff"/><text x="30" y="38" class="title">Ethereum USDC borrow benchmark: TVL vs outstanding-debt weights</text>
<text x="30" y="62" class="sub">Same market rates, 7 October 2026 UTC snapshot · rate labels show the corresponding weighted rate within each protocol</text>
<rect x="30" y="82" width="14" height="14" fill="#3778c2"/><text x="50" y="94" class="sub">Net TVL weight</text><rect x="155" y="82" width="14" height="14" fill="#e27b3f"/><text x="175" y="94" class="sub">Outstanding debt weight</text>
{''.join(bars)}<text x="30" y="{height-20}" class="foot">Benchmark: {tvl_result['benchmark_rate_pct']:.2f}% (TVL) vs {debt_result['benchmark_rate_pct']:.2f}% (debt). Results are an empirical snapshot, not a time-series backtest.</text></svg>'''
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
        caps = []
        for cap in (10, 15, 20, 25, 500):
            selected = [r for r in rows if r["rate_pct"] <= cap]
            tvl_rate = weighted_metrics(selected, "tvl_usd")["benchmark_rate_pct"]
            debt_rate = weighted_metrics(selected, "outstanding_debt_usd")["benchmark_rate_pct"]
            caps.append({"max_rate_pct": cap, "observations": len(selected),
                         "tvl_weighted_rate_pct": tvl_rate, "debt_weighted_rate_pct": debt_rate,
                         "difference_pp": debt_rate - tvl_rate})
        output["rate_cap_sensitivity"] = caps
    outpath = args.out / "snapshot_analysis.json"
    outpath.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if output["debt_weighted"]:
        write_svg(output["tvl_weighted"]["base"], output["debt_weighted"]["base"], args.out / "weighting_comparison.svg")
    base = output["tvl_weighted"]["base"]
    print(f"TVL-weighted rate: {base['benchmark_rate_pct']:.4f}%")
    print(f"Cross-source dispersion: {base['cross_sectional_dispersion_pp']:.4f} pp")
    print(f"Protocol HHI: {base['protocol_hhi']:.4f} (effective protocols: {base['effective_protocols']:.2f})")
    print(f"Debt-weighted: {output['debt_status']}")
    print(f"Wrote {outpath}")

if __name__ == "__main__":
    main()
