import pytest
import pandas as pd
from analysis.compare_models import to_channel_table
from analysis.roas_calculator import compute_roas
from models import last_touch

PAID_CHANNELS = {"paid_search", "linkedin_ads", "meta_ads", "email_marketing", "webinar_evento"}
FREE_CHANNELS = {"organic_search", "direct"}


@pytest.fixture
def sample_spend():
    return pd.DataFrame(
        {
            "channel": [
                "paid_search",
                "linkedin_ads",
                "meta_ads",
                "email_marketing",
                "webinar_evento",
                "organic_search",
                "direct",
            ],
            "total_spend_brl": [50_000.0, 30_000.0, 20_000.0, 5_000.0, 15_000.0, 0.0, 0.0],
        }
    )


@pytest.fixture
def sample_leads_roas():
    return pd.DataFrame(
        {
            "lead_id": ["L-1", "L-2"],
            "first_touch_channel": ["paid_search", "meta_ads"],
            "is_mql": [1, 1],
        }
    )


@pytest.fixture
def sample_opps_roas():
    return pd.DataFrame(
        {
            "opp_id": ["OPP-1", "OPP-2"],
            "first_touch_channel": ["paid_search", "meta_ads"],
            "amount_brl": [100_000.0, 80_000.0],
        }
    )


def test_only_paid_channels_in_output(sample_spine, sample_spend, sample_leads_roas, sample_opps_roas):
    attr = to_channel_table(last_touch.compute(sample_spine), "last_touch")
    results = compute_roas(attr, sample_spend, sample_leads_roas, sample_opps_roas)
    channels = {r.channel for r in results}
    assert channels.issubset(PAID_CHANNELS)


def test_zero_spend_channels_excluded(sample_spine, sample_spend, sample_leads_roas, sample_opps_roas):
    attr = to_channel_table(last_touch.compute(sample_spine), "last_touch")
    results = compute_roas(attr, sample_spend, sample_leads_roas, sample_opps_roas)
    channels = {r.channel for r in results}
    assert not channels & FREE_CHANNELS


def test_roas_formula_correct(sample_spine, sample_spend, sample_leads_roas, sample_opps_roas):
    attr = to_channel_table(last_touch.compute(sample_spine), "last_touch")
    results = compute_roas(attr, sample_spend, sample_leads_roas, sample_opps_roas)
    for r in results:
        expected = r.attributed_revenue_brl / r.total_spend_brl
        # roas is stored rounded to 4 decimal places
        assert abs(r.roas - expected) < 5e-5, f"ROAS mismatch for {r.channel}"
