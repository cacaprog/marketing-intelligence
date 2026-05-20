import numpy as np
import pytest
from models import (
    engagement_weighted,
    first_touch,
    last_touch,
    linear,
    position_based,
    time_decay,
)

MODELS = [last_touch, first_touch, linear, time_decay, position_based, engagement_weighted]
MODEL_IDS = ["last_touch", "first_touch", "linear", "time_decay", "position_based", "engagement_weighted"]


@pytest.mark.parametrize("model", MODELS, ids=MODEL_IDS)
def test_weights_sum_to_one_per_opp(model, sample_spine):
    result = model.compute(sample_spine)
    opp_sums = result.groupby("opp_id")["weight"].sum()
    np.testing.assert_allclose(opp_sums.values, 1.0, atol=1e-9)


@pytest.mark.parametrize("model", MODELS, ids=MODEL_IDS)
def test_revenue_conservation(model, sample_spine):
    result = model.compute(sample_spine)
    result = result.copy()
    result["rev"] = result["amount_brl"] * result["weight"]
    expected = sample_spine.drop_duplicates("opp_id")["amount_brl"].sum()
    actual = result.groupby("opp_id")["rev"].sum().sum()
    np.testing.assert_allclose(actual, expected, atol=1.0)


@pytest.mark.parametrize("model", MODELS, ids=MODEL_IDS)
def test_weights_non_negative(model, sample_spine):
    result = model.compute(sample_spine)
    assert (result["weight"] >= 0).all(), f"{model.__name__} produced negative weights"


@pytest.mark.parametrize("model", MODELS, ids=MODEL_IDS)
def test_row_count_unchanged(model, sample_spine):
    result = model.compute(sample_spine)
    assert len(result) == len(sample_spine)


@pytest.mark.parametrize("model", MODELS, ids=MODEL_IDS)
def test_original_spine_not_mutated(model, sample_spine):
    original_cols = set(sample_spine.columns)
    _ = model.compute(sample_spine)
    assert set(sample_spine.columns) == original_cols
