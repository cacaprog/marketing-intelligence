import sys
from pathlib import Path

import pandas as pd
import pytest

_SVC_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SVC_DIR))
sys.path.insert(0, str(_SVC_DIR.parent.parent))

from models.cohort_revenue import compute_cohort_revenue

REQUIRED_COLUMNS = {
    "cohort_month",
    "months_since_acquisition",
    "cumulative_revenue_brl",
    "is_observable",
    "cohort_size",
}
WINDOWS = {1, 3, 6, 9, 12}


def test_output_schema(mini_leads_df, mini_opps_df, reference_date):
    df = compute_cohort_revenue(mini_leads_df, mini_opps_df, reference_date)
    assert set(df.columns) == REQUIRED_COLUMNS


def test_windows_are_correct_values(mini_leads_df, mini_opps_df, reference_date):
    df = compute_cohort_revenue(mini_leads_df, mini_opps_df, reference_date)
    assert set(df["months_since_acquisition"].unique()) == WINDOWS


def test_all_cohort_window_combinations_present(
    mini_leads_df, mini_opps_df, reference_date
):
    df = compute_cohort_revenue(mini_leads_df, mini_opps_df, reference_date)
    cohort_months = set(
        mini_leads_df["lead_date"].dt.to_period("M").astype(str).unique()
    )
    expected_rows = len(cohort_months) * len(WINDOWS)
    assert len(df) == expected_rows


def test_observable_cells_have_non_negative_revenue(
    mini_leads_df, mini_opps_df, reference_date
):
    df = compute_cohort_revenue(mini_leads_df, mini_opps_df, reference_date)
    observable = df[df["is_observable"]]
    assert observable["cumulative_revenue_brl"].notna().all()
    assert (observable["cumulative_revenue_brl"] >= 0).all()


def test_unobservable_cells_have_null_revenue(
    mini_leads_df, mini_opps_df, reference_date
):
    df = compute_cohort_revenue(mini_leads_df, mini_opps_df, reference_date)
    unobservable = df[~df["is_observable"]]
    if not unobservable.empty:
        assert unobservable["cumulative_revenue_brl"].isna().all()


def test_observable_cell_with_revenue_is_not_null(
    mini_leads_df, mini_opps_df, reference_date
):
    """W=3 for cohort 2023-02 is observable; O5 closes 2023-03-01 which is within
    [2023-02-01, 2023-05-01). Result must be 5000.0, not null."""
    df = compute_cohort_revenue(mini_leads_df, mini_opps_df, reference_date)
    row = df[(df["cohort_month"] == "2023-02") & (df["months_since_acquisition"] == 3)]
    assert not row.empty
    assert row["is_observable"].iloc[0]
    assert pd.notna(row["cumulative_revenue_brl"].iloc[0])
    assert row["cumulative_revenue_brl"].iloc[0] == pytest.approx(5_000.0)


def test_bad_close_date_excluded_from_revenue(
    mini_leads_df, mini_opps_df, reference_date
):
    """O4 has close_date 2023-01-01 but L4 has lead_date 2023-01-25 (anomaly).
    W=1 for cohort 2023-01 should only count O1 (10000), not O4."""
    df = compute_cohort_revenue(mini_leads_df, mini_opps_df, reference_date)
    row_w1 = df[
        (df["cohort_month"] == "2023-01") & (df["months_since_acquisition"] == 1)
    ]
    assert row_w1["cumulative_revenue_brl"].iloc[0] == pytest.approx(10_000.0)


def test_revenue_is_monotone_non_decreasing(
    mini_leads_df, mini_opps_df, reference_date
):
    df = compute_cohort_revenue(mini_leads_df, mini_opps_df, reference_date)
    for cohort in df["cohort_month"].unique():
        cohort_df = df[df["cohort_month"] == cohort].sort_values(
            "months_since_acquisition"
        )
        observable = cohort_df[cohort_df["is_observable"]]
        revenues = observable["cumulative_revenue_brl"].tolist()
        for i in range(len(revenues) - 1):
            assert revenues[i] <= revenues[i + 1], (
                f"Non-monotone revenue for cohort {cohort}: {revenues}"
            )


def test_cohort_size_equals_lead_count(mini_leads_df, mini_opps_df, reference_date):
    df = compute_cohort_revenue(mini_leads_df, mini_opps_df, reference_date)
    row_jan = df[
        (df["cohort_month"] == "2023-01") & (df["months_since_acquisition"] == 1)
    ]
    assert row_jan["cohort_size"].iloc[0] == 4
    row_feb = df[
        (df["cohort_month"] == "2023-02") & (df["months_since_acquisition"] == 1)
    ]
    assert row_feb["cohort_size"].iloc[0] == 2


def test_w1_and_w3_revenue_values_for_cohort_2023_01(
    mini_leads_df, mini_opps_df, reference_date
):
    """O1 closes 2023-01-20 in W=1 window [2023-01-01, 2023-02-01): 10000.
    O2 closes 2023-03-15 in W=3 window [2023-01-01, 2023-04-01): cumulative 35000."""
    df = compute_cohort_revenue(mini_leads_df, mini_opps_df, reference_date)
    w1 = df[
        (df["cohort_month"] == "2023-01") & (df["months_since_acquisition"] == 1)
    ]["cumulative_revenue_brl"].iloc[0]
    w3 = df[
        (df["cohort_month"] == "2023-01") & (df["months_since_acquisition"] == 3)
    ]["cumulative_revenue_brl"].iloc[0]
    assert w1 == pytest.approx(10_000.0)
    assert w3 == pytest.approx(35_000.0)
