"""Tests for trainer.py: split_spine, train_model, get_feature_importance."""
import sys
from pathlib import Path

_SVC_DIR = Path(__file__).resolve().parent.parent
_REPO_DIR = _SVC_DIR.parent.parent
for _p in [str(_SVC_DIR), str(_REPO_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np
import pandas as pd
import pytest

from analysis.trainer import (
    FEATURE_NAMES,
    MIN_TEST_OPPS,
    get_feature_importance,
    split_spine,
    train_model,
)
from models import data_driven
from shared.config import TRAIN_CUTOFF_DATE


@pytest.fixture
def large_spine():
    """Attribution spine with enough opportunities to span the train/test cutoff.

    280 opps spread over 18 months → ~62 fall after 2024-03-01 (≥ MIN_TEST_OPPS=50).
    """
    rng = np.random.default_rng(42)
    n_opps = 280
    rows = []
    for i in range(n_opps):
        n_touches = rng.integers(1, 5)
        # spread dates across 2023-01 to 2024-06
        day_offset = int(i * (365 + 180) / n_opps)
        opp_date = pd.Timestamp("2023-01-01") + pd.Timedelta(days=day_offset)
        contrib = rng.dirichlet(np.ones(n_touches)).tolist()
        for j, c in enumerate(contrib):
            rows.append(
                {
                    "touchpoint_id": f"TP-{i}-{j}",
                    "opp_id": f"OPP-{i}",
                    "opp_created_date": str(opp_date.date()),
                    "touch_sequence": j + 1,
                    "total_touches_in_journey": n_touches,
                    "channel": rng.choice(["paid_search", "organic_search", "linkedin_ads",
                                           "meta_ads", "email_marketing", "webinar_evento", "direct"]),
                    "touch_type": rng.choice(["click", "content_view", "demo_request",
                                              "impression", "form_fill", "sales_call"]),
                    "engagement_score": int(rng.integers(1, 101)),
                    "days_before_opp_creation": int(rng.integers(0, 90)),
                    "is_first_touch": 1 if j == 0 else 0,
                    "is_last_touch": 1 if j == n_touches - 1 else 0,
                    "true_marginal_contribution": c,
                    "amount_brl": float(rng.integers(50_000, 500_000)),
                }
            )
    return pd.DataFrame(rows)


# --- split_spine tests ---

def test_split_no_opp_straddles_boundary(large_spine):
    train, test = split_spine(large_spine)
    cutoff = pd.Timestamp(TRAIN_CUTOFF_DATE)
    for opp_id, group in train.groupby("opp_id"):
        dates = pd.to_datetime(group["opp_created_date"])
        assert (dates < cutoff).all(), f"Train opp {opp_id} has touches on or after cutoff"
    for opp_id, group in test.groupby("opp_id"):
        dates = pd.to_datetime(group["opp_created_date"])
        assert (dates >= cutoff).all(), f"Test opp {opp_id} has touches before cutoff"


def test_split_lengths_sum_to_total(large_spine):
    train, test = split_spine(large_spine)
    assert len(train) + len(test) == len(large_spine)


def test_split_raises_when_test_too_small(large_spine):
    # Force all opportunities into train by using a very late cutoff
    late_spine = large_spine.copy()
    late_spine["opp_created_date"] = "2022-01-01"
    with pytest.raises(ValueError, match="Test set has only"):
        split_spine(late_spine)


def test_split_test_has_enough_opps(large_spine):
    _, test = split_spine(large_spine)
    assert test["opp_id"].nunique() >= MIN_TEST_OPPS


# --- train_model + weight-sum tests ---

def test_trained_model_weight_sum_invariant(large_spine):
    train, test = split_spine(large_spine)
    artifact = train_model(train)
    result = data_driven.compute(test, artifact)
    opp_sums = result.groupby("opp_id")["weight"].sum()
    np.testing.assert_allclose(opp_sums.values, 1.0, atol=1e-9)


def test_trained_model_weights_non_negative(large_spine):
    train, test = split_spine(large_spine)
    artifact = train_model(train)
    result = data_driven.compute(test, artifact)
    assert (result["weight"] >= 0).all()


def test_artifact_has_required_keys(large_spine):
    train, _ = split_spine(large_spine)
    artifact = train_model(train)
    assert set(artifact.keys()) == {"encoder", "booster", "feature_names", "train_cutoff"}
    assert artifact["feature_names"] == FEATURE_NAMES
    assert artifact["train_cutoff"] == TRAIN_CUTOFF_DATE


# --- get_feature_importance tests ---

def test_feature_importance_has_eight_rows(large_spine):
    train, _ = split_spine(large_spine)
    artifact = train_model(train)
    fi = get_feature_importance(artifact)
    assert len(fi) == 8


def test_feature_importance_scores_sum_to_one(large_spine):
    train, _ = split_spine(large_spine)
    artifact = train_model(train)
    fi = get_feature_importance(artifact)
    np.testing.assert_allclose(fi["importance_score"].sum(), 1.0, atol=1e-9)


def test_feature_importance_scores_non_negative(large_spine):
    train, _ = split_spine(large_spine)
    artifact = train_model(train)
    fi = get_feature_importance(artifact)
    assert (fi["importance_score"] >= 0).all()


def test_feature_importance_ranks_unique_1_to_8(large_spine):
    train, _ = split_spine(large_spine)
    artifact = train_model(train)
    fi = get_feature_importance(artifact)
    assert sorted(fi["rank"].tolist()) == list(range(1, 9))
