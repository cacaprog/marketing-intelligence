import sys
from pathlib import Path

import pandas as pd
import pytest

_SVC_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SVC_DIR))
sys.path.insert(0, str(_SVC_DIR.parent.parent))

from models.cohort_funnel import compute_cohort_funnel

REQUIRED_COLUMNS = {
    "cohort_month",
    "lead_count",
    "mql_count",
    "opp_count",
    "won_count",
    "mql_rate",
    "opp_rate",
    "win_rate",
    "opp_to_win_rate",
}


def test_output_schema(mini_leads_df, mini_opps_df):
    df = compute_cohort_funnel(mini_leads_df, mini_opps_df)
    assert set(df.columns) == REQUIRED_COLUMNS


def test_one_row_per_cohort_month(mini_leads_df, mini_opps_df):
    df = compute_cohort_funnel(mini_leads_df, mini_opps_df)
    expected_months = set(
        mini_leads_df["lead_date"].dt.to_period("M").astype(str).unique()
    )
    assert set(df["cohort_month"].unique()) == expected_months
    assert len(df) == len(expected_months)


def test_rate_columns_are_in_bounds(mini_leads_df, mini_opps_df):
    df = compute_cohort_funnel(mini_leads_df, mini_opps_df)
    rate_cols = ["mql_rate", "opp_rate", "win_rate", "opp_to_win_rate"]
    for col in rate_cols:
        assert (df[col] >= 0).all(), f"{col} has negative values"
        assert (df[col] <= 1).all(), f"{col} exceeds 1.0"


def test_no_null_values_in_rate_columns(mini_leads_df, mini_opps_df):
    df = compute_cohort_funnel(mini_leads_df, mini_opps_df)
    rate_cols = ["mql_rate", "opp_rate", "win_rate", "opp_to_win_rate"]
    assert not df[rate_cols].isna().any().any(), "NaN found in rate columns"


def test_zero_safe_division_when_no_mqls(mini_leads_df, mini_opps_df):
    """Build a cohort with no MQLs: downstream rates must be 0.0, not NaN."""
    leads = pd.DataFrame(
        {
            "lead_id": ["ZL1", "ZL2"],
            "first_touch_channel": ["direct", "direct"],
            "lead_date": pd.to_datetime(["2023-05-01", "2023-05-10"]),
            "is_mql": [0, 0],
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
    df = compute_cohort_funnel(leads, opps)
    row = df[df["cohort_month"] == "2023-05"]
    assert not row.empty
    assert row["mql_rate"].iloc[0] == pytest.approx(0.0)
    assert row["opp_rate"].iloc[0] == pytest.approx(0.0)
    assert row["win_rate"].iloc[0] == pytest.approx(0.0)
    assert row["opp_to_win_rate"].iloc[0] == pytest.approx(0.0)


def test_zero_safe_when_no_opps(mini_leads_df, mini_opps_df):
    """Cohort with MQLs but zero opps: opp_to_win_rate must be 0.0, not NaN."""
    leads = pd.DataFrame(
        {
            "lead_id": ["ZL1", "ZL2"],
            "first_touch_channel": ["direct", "direct"],
            "lead_date": pd.to_datetime(["2023-06-01", "2023-06-10"]),
            "is_mql": [1, 0],
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
    df = compute_cohort_funnel(leads, opps)
    row = df[df["cohort_month"] == "2023-06"]
    assert row["opp_to_win_rate"].iloc[0] == pytest.approx(0.0)


def test_specific_scenario_from_spec(mini_leads_df, mini_opps_df):
    """US2 acceptance scenario: cohort 2023-01 has 4 leads, 3 MQLs (L1, L2, L4),
    2 won opps (O1=L1, O2=L2; O4=L4 is an anomaly but lead was MQL).
    mql_rate = 3/4 = 0.75; won_count counts won opps (not anomalous O4 excluded from
    revenue but counted in funnel). O4 IS a won opp, so won_count=3 (O1, O2, O4).
    wait: win_rate = won_count / lead_count.
    L1→O1(won), L2→O2(won), L4→O4(won but anomalous close). L3→O3(lost).
    All three won opps count in won_count for funnel purposes. win_rate = 3/4 = 0.75."""
    df = compute_cohort_funnel(mini_leads_df, mini_opps_df)
    row = df[df["cohort_month"] == "2023-01"]
    assert row["lead_count"].iloc[0] == 4
    assert row["mql_count"].iloc[0] == 3   # L1, L2, L4 are MQL
    assert row["won_count"].iloc[0] == 3   # O1, O2, O4 are won
    assert row["mql_rate"].iloc[0] == pytest.approx(0.75)
    assert row["win_rate"].iloc[0] == pytest.approx(0.75)


def test_cohort_2023_02_counts(mini_leads_df, mini_opps_df):
    """Cohort 2023-02: 2 leads (L5, L6). L5 is MQL, L6 is not. O5 (L5) is won."""
    df = compute_cohort_funnel(mini_leads_df, mini_opps_df)
    row = df[df["cohort_month"] == "2023-02"]
    assert row["lead_count"].iloc[0] == 2
    assert row["mql_count"].iloc[0] == 1
    assert row["won_count"].iloc[0] == 1
    assert row["mql_rate"].iloc[0] == pytest.approx(0.5)
    assert row["win_rate"].iloc[0] == pytest.approx(0.5)
