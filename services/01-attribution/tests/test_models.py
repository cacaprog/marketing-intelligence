import functools
import numpy as np
import pytest
from models import (
    engagement_weighted,
    first_touch,
    last_touch,
    linear,
    position_based,
    time_decay,
    data_driven,
)
from analysis.trainer import train_model

HEURISTIC_MODELS = [last_touch, first_touch, linear, time_decay, position_based, engagement_weighted]
HEURISTIC_IDS = ["last_touch", "first_touch", "linear", "time_decay", "position_based", "engagement_weighted"]


@pytest.fixture
def trained_artifact(sample_spine):
    """Train a minimal model artifact on the sample spine for data_driven tests."""
    return train_model(sample_spine)


def _data_driven_compute(spine, artifact):
    return data_driven.compute(spine, artifact)


@pytest.mark.parametrize("model", HEURISTIC_MODELS, ids=HEURISTIC_IDS)
def test_weights_sum_to_one_per_opp(model, sample_spine):
    result = model.compute(sample_spine)
    opp_sums = result.groupby("opp_id")["weight"].sum()
    np.testing.assert_allclose(opp_sums.values, 1.0, atol=1e-9)


def test_data_driven_weights_sum_to_one_per_opp(sample_spine, trained_artifact):
    result = data_driven.compute(sample_spine, trained_artifact)
    opp_sums = result.groupby("opp_id")["weight"].sum()
    np.testing.assert_allclose(opp_sums.values, 1.0, atol=1e-9)


@pytest.mark.parametrize("model", HEURISTIC_MODELS, ids=HEURISTIC_IDS)
def test_revenue_conservation(model, sample_spine):
    result = model.compute(sample_spine)
    result = result.copy()
    result["rev"] = result["amount_brl"] * result["weight"]
    expected = sample_spine.drop_duplicates("opp_id")["amount_brl"].sum()
    actual = result.groupby("opp_id")["rev"].sum().sum()
    np.testing.assert_allclose(actual, expected, atol=1.0)


@pytest.mark.parametrize("model", HEURISTIC_MODELS, ids=HEURISTIC_IDS)
def test_weights_non_negative(model, sample_spine):
    result = model.compute(sample_spine)
    assert (result["weight"] >= 0).all()


def test_data_driven_weights_non_negative(sample_spine, trained_artifact):
    result = data_driven.compute(sample_spine, trained_artifact)
    assert (result["weight"] >= 0).all()


@pytest.mark.parametrize("model", HEURISTIC_MODELS, ids=HEURISTIC_IDS)
def test_row_count_unchanged(model, sample_spine):
    result = model.compute(sample_spine)
    assert len(result) == len(sample_spine)


@pytest.mark.parametrize("model", HEURISTIC_MODELS, ids=HEURISTIC_IDS)
def test_original_spine_not_mutated(model, sample_spine):
    original_cols = set(sample_spine.columns)
    _ = model.compute(sample_spine)
    assert set(sample_spine.columns) == original_cols
