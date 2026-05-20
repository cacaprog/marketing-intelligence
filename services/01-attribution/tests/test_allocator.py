import sys
from pathlib import Path

_SVC_DIR = Path(__file__).resolve().parent.parent
_REPO_DIR = _SVC_DIR.parent.parent
for _p in [str(_SVC_DIR), str(_REPO_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pandas as pd
import pytest
from analysis.allocator import compute_allocation
from result_types import AttributionResult

PAID_CHANNELS = ["paid_search", "linkedin_ads", "meta_ads", "email_marketing", "webinar_evento"]


@pytest.fixture
def sample_attribution():
    return [
        AttributionResult("data_driven", ch, rev, opps, round(rev / 500_000 * 100, 2))
        for ch, rev, opps in [
            ("paid_search", 120_000.0, 5),
            ("linkedin_ads", 80_000.0, 3),
            ("meta_ads", 60_000.0, 2),
            ("email_marketing", 40_000.0, 2),
            ("webinar_evento", 200_000.0, 8),
            ("organic_search", 150_000.0, 6),
            ("direct", 50_000.0, 2),
        ]
    ]


@pytest.fixture
def sample_spend():
    return pd.DataFrame(
        {
            "channel": PAID_CHANNELS + ["organic_search", "direct"],
            "total_spend_brl": [50_000.0, 30_000.0, 25_000.0, 10_000.0, 20_000.0, 0.0, 0.0],
        }
    )


def test_budget_sum_equals_input(sample_attribution, sample_spend):
    budget = 200_000.0
    results = compute_allocation(sample_attribution, sample_spend, budget)
    total = sum(r.recommended_spend_brl for r in results)
    assert abs(total - budget) <= 0.01, f"Budget sum {total} != {budget}"


def test_no_negative_spend(sample_attribution, sample_spend):
    results = compute_allocation(sample_attribution, sample_spend, 100_000.0)
    assert all(r.recommended_spend_brl >= 0 for r in results)


def test_subpopulation_caveat_always_true(sample_attribution, sample_spend):
    results = compute_allocation(sample_attribution, sample_spend, 100_000.0)
    assert all(r.subpopulation_caveat is True for r in results)


def test_raises_on_zero_budget(sample_attribution, sample_spend):
    with pytest.raises(ValueError, match="budget_brl must be > 0"):
        compute_allocation(sample_attribution, sample_spend, 0.0)


def test_raises_on_negative_budget(sample_attribution, sample_spend):
    with pytest.raises(ValueError):
        compute_allocation(sample_attribution, sample_spend, -1_000.0)


def test_zero_efficiency_channel_gets_zero_spend(sample_spend):
    """A channel with zero attributed revenue should receive zero recommended spend."""
    attr = [
        AttributionResult("data_driven", "paid_search", 100_000.0, 5, 50.0),
        AttributionResult("data_driven", "linkedin_ads", 0.0, 0, 0.0),
        AttributionResult("data_driven", "meta_ads", 100_000.0, 5, 50.0),
        AttributionResult("data_driven", "email_marketing", 0.0, 0, 0.0),
        AttributionResult("data_driven", "webinar_evento", 0.0, 0, 0.0),
    ]
    results = compute_allocation(attr, sample_spend, 100_000.0)
    zero_channels = {r.channel for r in results if r.recommended_spend_brl == 0.0}
    assert "linkedin_ads" in zero_channels


def test_only_paid_channels_in_output(sample_attribution, sample_spend):
    """organic_search and direct must not appear in output."""
    results = compute_allocation(sample_attribution, sample_spend, 100_000.0)
    channels = {r.channel for r in results}
    assert "organic_search" not in channels
    assert "direct" not in channels
    assert channels.issubset(set(PAID_CHANNELS))
