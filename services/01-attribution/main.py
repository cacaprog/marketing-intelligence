"""Media Attribution Service — CLI entry point.

Usage:
    python services/01-attribution/main.py [--output-dir PATH]
"""

import argparse
import sys
from pathlib import Path

_SVC_DIR = Path(__file__).resolve().parent
_REPO_DIR = _SVC_DIR.parent.parent
for _p in [str(_SVC_DIR), str(_REPO_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pandas as pd
from analysis.benchmark import benchmark_models
from analysis.compare_models import run_all_models, to_channel_table
from analysis.roas_calculator import compute_roas
from models.ground_truth import compute as gt_compute
from result_types import AttributionResult
from shared.config import PROCESSED_DIR
from shared.db import get_attribution_spine, get_channel_spend, get_leads, get_won_opps


def main(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Loading attribution spine...")
    spine = get_attribution_spine()
    print(f"  {len(spine):,} touchpoints | {spine['opp_id'].nunique():,} won opportunities")

    # US1 — run all six attribution models
    print("\nRunning attribution models...")
    model_weighted = run_all_models(spine)

    all_attr: list[AttributionResult] = []
    model_channel_tables: dict[str, list[AttributionResult]] = {}
    for model_name, weighted_spine in model_weighted.items():
        channel_results = to_channel_table(weighted_spine, model_name)
        model_channel_tables[model_name] = channel_results
        all_attr.extend(channel_results)
        total = sum(r.attributed_revenue_brl for r in channel_results)
        print(f"  {model_name:<24} R$ {total:>14,.0f}")

    attr_df = pd.DataFrame([vars(r) for r in all_attr])
    attr_df.to_parquet(output_dir / "attribution_results.parquet", index=False)
    attr_df.to_csv(output_dir / "attribution_results.csv", index=False)
    print(f"\nWrote attribution_results ({len(attr_df)} rows)")

    # US2 — ground truth benchmark
    print("\nRunning ground truth benchmark...")
    gt_weighted = gt_compute(spine)
    gt_results = to_channel_table(gt_weighted, "ground_truth")
    benchmark = benchmark_models(model_channel_tables, gt_results)

    bench_df = pd.DataFrame([vars(r) for r in benchmark])
    bench_df.to_parquet(output_dir / "benchmark_results.parquet", index=False)
    bench_df.to_csv(output_dir / "benchmark_results.csv", index=False)
    for r in benchmark:
        print(f"  Rank {r.rank}: {r.model_name:<24} MAE={r.mae:.4f}  r={r.pearson_r:.4f}")

    # US3 — ROAS per paid channel
    print("\nComputing ROAS...")
    spend_df = get_channel_spend()
    leads_df = get_leads()
    opps_df = get_won_opps()
    roas_results = compute_roas(all_attr, spend_df, leads_df, opps_df)

    roas_df = pd.DataFrame([vars(r) for r in roas_results])
    roas_df.to_parquet(output_dir / "roas_results.parquet", index=False)
    roas_df.to_csv(output_dir / "roas_results.csv", index=False)
    print(f"Wrote roas_results ({len(roas_df)} rows)")
    print("\nDone.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run media attribution models")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROCESSED_DIR / "01-attribution",
        help="Directory to write output files (default: data/processed/01-attribution/)",
    )
    args = parser.parse_args()
    main(args.output_dir)
