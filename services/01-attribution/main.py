"""Media Attribution Service — CLI entry point.

Usage:
    python services/01-attribution/main.py [--output-dir PATH] [--budget-brl FLOAT]
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
from analysis.allocator import compute_allocation
from analysis.benchmark import benchmark_models
from analysis.compare_models import run_all_models, to_channel_table
from analysis.roas_calculator import compute_roas
from analysis.trainer import get_feature_importance, split_spine, train_model
from models import data_driven
from models.ground_truth import compute as gt_compute
from result_types import AttributionResult
from shared.config import MODEL_DIR, PROCESSED_DIR
from shared.db import get_attribution_spine, get_channel_spend, get_leads, get_won_opps


def main(output_dir: Path, budget_brl: float | None = None) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading attribution spine...")
    spine = get_attribution_spine()
    print(f"  {len(spine):,} touchpoints | {spine['opp_id'].nunique():,} won opportunities")

    # US1 — run all six heuristic attribution models
    print("\nRunning heuristic attribution models...")
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

    # US2 (original) — ground truth benchmark for heuristics
    print("\nRunning ground truth benchmark (heuristics)...")
    gt_weighted = gt_compute(spine)
    gt_results = to_channel_table(gt_weighted, "ground_truth")

    # US1 (data-driven) — temporal split + train + predict
    print("\nTraining data-driven attribution model...")
    train_spine, test_spine = split_spine(spine)
    print(f"  Train: {train_spine['opp_id'].nunique():,} opps | Test: {test_spine['opp_id'].nunique():,} opps")
    artifact = train_model(train_spine)
    print("  Model trained and saved to models/attribution_lgbm.joblib")

    dd_weighted = data_driven.compute(test_spine, artifact)
    dd_channel_results = to_channel_table(dd_weighted, "data_driven")
    all_ml_attr = dd_channel_results
    ml_attr_df = pd.DataFrame([vars(r) for r in all_ml_attr])
    ml_attr_df.to_parquet(output_dir / "ml_attribution_results.parquet", index=False)
    ml_attr_df.to_csv(output_dir / "ml_attribution_results.csv", index=False)
    total_dd = sum(r.attributed_revenue_brl for r in dd_channel_results)
    print(f"  data_driven              R$ {total_dd:>14,.0f}")
    print(f"Wrote ml_attribution_results ({len(ml_attr_df)} rows)")

    # Benchmark: all 7 models evaluated on test_spine so comparison is fair
    # (data_driven was trained on train_spine; evaluating all models on held-out test_spine
    #  puts heuristics and data_driven on equal footing — no leakage for either)
    heuristic_test = run_all_models(test_spine)
    heuristic_test_tables: dict[str, list[AttributionResult]] = {
        name: to_channel_table(ws, name) for name, ws in heuristic_test.items()
    }
    gt_test = gt_compute(test_spine)
    gt_test_results = to_channel_table(gt_test, "ground_truth")
    all_model_tables = {**heuristic_test_tables, "data_driven": dd_channel_results}
    benchmark = benchmark_models(all_model_tables, gt_test_results)

    bench_df = pd.DataFrame([vars(r) for r in benchmark])
    bench_df.to_parquet(output_dir / "benchmark_results.parquet", index=False)
    bench_df.to_csv(output_dir / "benchmark_results.csv", index=False)
    print("\nBenchmark (MAE vs. ground truth):")
    for r in benchmark:
        print(f"  Rank {r.rank}: {r.model_name:<24} MAE={r.mae:.4f}  r={r.pearson_r:.4f}")

    # US2 (original) — ROAS per paid channel (all heuristics + data_driven)
    print("\nComputing ROAS...")
    spend_df = get_channel_spend()
    leads_df = get_leads()
    opps_df = get_won_opps()
    all_combined_attr = all_attr + all_ml_attr
    roas_results = compute_roas(all_combined_attr, spend_df, leads_df, opps_df)

    roas_df = pd.DataFrame([vars(r) for r in roas_results])
    roas_df.to_parquet(output_dir / "roas_results.parquet", index=False)
    roas_df.to_csv(output_dir / "roas_results.csv", index=False)
    print(f"Wrote roas_results ({len(roas_df)} rows)")

    # US2 (new) — Feature importance
    print("\nExtracting feature importance...")
    fi_df = get_feature_importance(artifact)
    fi_df.to_parquet(output_dir / "feature_importance.parquet", index=False)
    fi_df.to_csv(output_dir / "feature_importance.csv", index=False)
    print(f"Wrote feature_importance ({len(fi_df)} rows)")
    print(f"  Top feature: {fi_df.iloc[0]['feature_name']} ({fi_df.iloc[0]['importance_score']:.3f})")

    # US3 — Media allocation recommendation
    print("\nComputing media allocation recommendation...")
    if budget_brl is None:
        budget_brl = float(spend_df["total_spend_brl"].sum())
    alloc_results = compute_allocation(dd_channel_results, spend_df, budget_brl)

    alloc_df = pd.DataFrame([vars(r) for r in alloc_results])
    alloc_df.to_parquet(output_dir / "allocation_recommendations.parquet", index=False)
    alloc_df.to_csv(output_dir / "allocation_recommendations.csv", index=False)
    print(f"Wrote allocation_recommendations ({len(alloc_df)} rows, budget=R${budget_brl:,.0f})")

    print("\nDone.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run media attribution models")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROCESSED_DIR / "01-attribution",
        help="Directory to write output files (default: data/processed/01-attribution/)",
    )
    parser.add_argument(
        "--budget-brl",
        type=float,
        default=None,
        help="Total budget for allocation recommendation in BRL (default: sum of historical spend)",
    )
    args = parser.parse_args()
    main(args.output_dir, args.budget_brl)
