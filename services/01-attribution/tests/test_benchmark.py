import pytest
from analysis.benchmark import benchmark_models
from analysis.compare_models import to_channel_table
from models import (
    engagement_weighted,
    first_touch,
    last_touch,
    linear,
    position_based,
    time_decay,
)
from models.ground_truth import compute as gt_compute


def _build_model_results(spine):
    return {
        "last_touch": to_channel_table(last_touch.compute(spine), "last_touch"),
        "first_touch": to_channel_table(first_touch.compute(spine), "first_touch"),
        "linear": to_channel_table(linear.compute(spine), "linear"),
        "time_decay": to_channel_table(time_decay.compute(spine), "time_decay"),
        "position_based": to_channel_table(position_based.compute(spine), "position_based"),
        "engagement_weighted": to_channel_table(
            engagement_weighted.compute(spine), "engagement_weighted"
        ),
    }


def test_benchmark_has_six_rows(sample_spine):
    gt = to_channel_table(gt_compute(sample_spine), "ground_truth")
    results = benchmark_models(_build_model_results(sample_spine), gt)
    assert len(results) == 6


def test_ranks_are_unique_1_to_6(sample_spine):
    gt = to_channel_table(gt_compute(sample_spine), "ground_truth")
    results = benchmark_models(_build_model_results(sample_spine), gt)
    assert sorted(r.rank for r in results) == list(range(1, 7))


def test_rank_1_has_lowest_mae(sample_spine):
    gt = to_channel_table(gt_compute(sample_spine), "ground_truth")
    results = benchmark_models(_build_model_results(sample_spine), gt)
    rank1 = next(r for r in results if r.rank == 1)
    assert all(rank1.mae <= r.mae for r in results)


def test_mae_non_negative(sample_spine):
    gt = to_channel_table(gt_compute(sample_spine), "ground_truth")
    results = benchmark_models(_build_model_results(sample_spine), gt)
    assert all(r.mae >= 0 for r in results)
