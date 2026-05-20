import sys
from pathlib import Path

import pandas as pd
import pytest

_SVC_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SVC_DIR))
sys.path.insert(0, str(_SVC_DIR.parent.parent))

from models.channel_cohort import compute_channel_cohorts
from models.cohort_revenue import compute_cohort_revenue

REQUIRED_COLUMNS = {
    "cohort_month",
    "channel",
    "lead_count",
    "mql_count",
    "opp_count",
    "won_count",
    "mql_rate",
    "opp_rate",
    "win_rate",
    "opp_to_win_rate",
    "revenue_1m_brl",
    "revenue_3m_brl",
    "revenue_6m_brl",
    "revenue_9m_brl",
    "revenue_12m_brl",
    "low_sample_flag",
}


def test_output_schema(mini_leads_df, mini_opps_df, reference_date):
    df = compute_channel_cohorts(mini_leads_df, mini_opps_df, reference_date)
    assert set(df.columns) == REQUIRED_COLUMNS


def test_null_channel_becomes_unknown(mini_leads_df, mini_opps_df, reference_date):
    """L4 has null first_touch_channel → must appear as channel='unknown', not dropped."""
    df = compute_channel_cohorts(mini_leads_df, mini_opps_df, reference_date)
    assert "unknown" in df["channel"].values
    assert df["channel"].isna().sum() == 0


def test_low_sample_flag_when_lead_count_below_5(
    mini_leads_df, mini_opps_df, reference_date
):
    """All channel groups in mini fixture have < 5 leads → all should be flagged."""
    df = compute_channel_cohorts(mini_leads_df, mini_opps_df, reference_date)
    assert (df[df["lead_count"] < 5]["low_sample_flag"] == True).all()


def test_no_low_sample_flag_when_lead_count_5_or_more(reference_date):
    """Build a fixture with 5+ leads per channel."""
    leads = pd.DataFrame(
        {
            "lead_id": [f"L{i}" for i in range(10)],
            "first_touch_channel": ["paid_search"] * 10,
            "lead_date": pd.to_datetime(["2023-03-01"] * 10),
            "is_mql": [1] * 10,
        }
    )
    opps = pd.DataFrame(
        {
            "opp_id": pd.Series([], dtype=str),
            "lead_id": pd.Series([], dtype=str),
            "amount_brl": pd.Series([], dtype=float),
            "close_date": pd.Series([], dtype="datetime64[ns]"),
            "is_won": pd.Series([], dtype=int),
            "created_date": pd.Series([], dtype="datetime64[ns]"),
        }
    )
    df = compute_channel_cohorts(leads, opps, reference_date)
    row = df[(df["cohort_month"] == "2023-03") & (df["channel"] == "paid_search")]
    assert not row.empty
    assert row["lead_count"].iloc[0] == 10
    assert row["low_sample_flag"].iloc[0] == False


def test_rate_columns_in_bounds(mini_leads_df, mini_opps_df, reference_date):
    df = compute_channel_cohorts(mini_leads_df, mini_opps_df, reference_date)
    rate_cols = ["mql_rate", "opp_rate", "win_rate", "opp_to_win_rate"]
    for col in rate_cols:
        assert (df[col] >= 0).all()
        assert (df[col] <= 1).all()
        assert not df[col].isna().any()


def test_channel_revenue_sums_to_cohort_total(
    mini_leads_df, mini_opps_df, reference_date
):
    """SC-005: sum of channel revenues per window must equal total cohort revenue (±0.01)."""
    ch_df = compute_channel_cohorts(mini_leads_df, mini_opps_df, reference_date)
    rev_df = compute_cohort_revenue(mini_leads_df, mini_opps_df, reference_date)

    window_cols = {
        1: "revenue_1m_brl",
        3: "revenue_3m_brl",
        6: "revenue_6m_brl",
        9: "revenue_9m_brl",
        12: "revenue_12m_brl",
    }

    for cohort_month in rev_df["cohort_month"].unique():
        for w, col in window_cols.items():
            rev_row = rev_df[
                (rev_df["cohort_month"] == cohort_month)
                & (rev_df["months_since_acquisition"] == w)
            ]
            if rev_row.empty or not rev_row["is_observable"].iloc[0]:
                continue
            total_rev = rev_row["cumulative_revenue_brl"].iloc[0]
            channel_sum = (
                ch_df[ch_df["cohort_month"] == cohort_month][col]
                .fillna(0)
                .sum()
            )
            assert abs(total_rev - channel_sum) < 0.01, (
                f"Conservation violated for {cohort_month} W={w}: "
                f"total={total_rev}, channel_sum={channel_sum}"
            )


def test_all_channels_appear_for_each_cohort(mini_leads_df, mini_opps_df, reference_date):
    """Every channel present in leads appears in output for each cohort month."""
    # cohort 2023-01 has channels: paid_search, linkedin_ads, unknown
    df = compute_channel_cohorts(mini_leads_df, mini_opps_df, reference_date)
    cohort_01 = df[df["cohort_month"] == "2023-01"]
    assert "paid_search" in cohort_01["channel"].values
    assert "linkedin_ads" in cohort_01["channel"].values
    assert "unknown" in cohort_01["channel"].values
