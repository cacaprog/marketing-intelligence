import sys
from pathlib import Path

_SVC_DIR = Path(__file__).resolve().parent.parent
_REPO_DIR = _SVC_DIR.parent.parent
for _p in [str(_SVC_DIR), str(_REPO_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np
from scipy.stats import pearsonr
from result_types import AttributionResult, BenchmarkResult


def benchmark_models(
    model_results: dict[str, list[AttributionResult]],
    ground_truth: list[AttributionResult],
) -> list[BenchmarkResult]:
    """Rank all models by MAE vs. ground truth channel-level revenue shares.

    Returns list sorted by MAE ascending (rank 1 = best model).
    """
    channels = sorted({r.channel for r in ground_truth})
    gt_shares = {r.channel: r.share_pct for r in ground_truth}
    gt_arr = np.array([gt_shares.get(ch, 0.0) for ch in channels])

    results: list[BenchmarkResult] = []
    for model_name, attr_results in model_results.items():
        model_shares = {r.channel: r.share_pct for r in attr_results}
        model_arr = np.array([model_shares.get(ch, 0.0) for ch in channels])

        mae = float(np.mean(np.abs(model_arr - gt_arr)))

        try:
            pearson_val, _ = pearsonr(model_arr, gt_arr)
            pearson_val = 0.0 if np.isnan(pearson_val) else float(pearson_val)
        except Exception:
            pearson_val = 0.0

        results.append(
            BenchmarkResult(
                model_name=model_name,
                mae=round(mae, 4),
                pearson_r=round(pearson_val, 4),
                rank=0,
            )
        )

    results.sort(key=lambda r: r.mae)
    for i, r in enumerate(results):
        r.rank = i + 1

    return results
