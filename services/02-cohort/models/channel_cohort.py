import sys
from pathlib import Path

import numpy as np
import pandas as pd
from pandas.tseries.offsets import DateOffset

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
from shared.config import COHORT_WINDOWS, DATASET_REFERENCE_DATE


def _safe_rate(numer: pd.Series, denom: pd.Series) -> pd.Series:
    return np.where(denom > 0, numer / denom, 0.0).astype(float)


def compute_channel_cohorts(
    leads_df: pd.DataFrame,
    opps_df: pd.DataFrame,
    reference_date: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Compute cohort metrics segmented by first_touch_channel.

    Null channels become 'unknown' (FR-007).
    low_sample_flag=True when lead_count < 5 (FR-006).
    Revenue window columns are None when not yet observable.
    """
    if reference_date is None:
        if not opps_df.empty and opps_df["close_date"].notna().any():
            reference_date = opps_df["close_date"].max()
        else:
            reference_date = pd.Timestamp(DATASET_REFERENCE_DATE)
    reference_date = pd.Timestamp(reference_date)

    leads = leads_df.copy()
    leads["first_touch_channel"] = leads["first_touch_channel"].fillna("unknown")
    leads["cohort_month"] = leads["lead_date"].dt.to_period("M").astype(str)

    lead_lookup = leads[["lead_id", "cohort_month", "first_touch_channel", "lead_date"]]

    # Funnel counts per (cohort_month, channel)
    funnel = (
        leads.groupby(["cohort_month", "first_touch_channel"])
        .agg(lead_count=("lead_id", "count"), mql_count=("is_mql", "sum"))
        .reset_index()
        .rename(columns={"first_touch_channel": "channel"})
    )

    # Opps joined to leads to get cohort_month + channel + lead_date
    if not opps_df.empty:
        opps = opps_df.merge(
            lead_lookup.rename(columns={"first_touch_channel": "channel"}),
            on="lead_id",
            how="inner",
        )
        opp_counts = (
            opps.groupby(["cohort_month", "channel"])
            .agg(opp_count=("opp_id", "count"), won_count=("is_won", "sum"))
            .reset_index()
        )
        # Won opps with anomaly exclusion (close_date >= lead_date)
        won_opps = opps[
            (opps["is_won"] == 1) & (opps["close_date"] >= opps["lead_date"])
        ].copy()
    else:
        opp_counts = pd.DataFrame(
            columns=["cohort_month", "channel", "opp_count", "won_count"]
        )
        won_opps = pd.DataFrame(
            columns=["opp_id", "lead_id", "amount_brl", "close_date",
                     "cohort_month", "channel", "lead_date"]
        )

    result = funnel.merge(opp_counts, on=["cohort_month", "channel"], how="left")
    result["opp_count"] = result["opp_count"].fillna(0).astype(int)
    result["won_count"] = result["won_count"].fillna(0).astype(int)

    result["mql_rate"] = _safe_rate(result["mql_count"], result["lead_count"])
    result["opp_rate"] = _safe_rate(result["opp_count"], result["lead_count"])
    result["win_rate"] = _safe_rate(result["won_count"], result["lead_count"])
    result["opp_to_win_rate"] = _safe_rate(result["won_count"], result["opp_count"])
    result["low_sample_flag"] = result["lead_count"] < 5

    # Revenue per window per (cohort_month, channel)
    for w in COHORT_WINDOWS:
        col_name = f"revenue_{w}m_brl"
        revenue_map: dict[tuple, float | None] = {}

        for cohort_month in result["cohort_month"].unique():
            cohort_start = pd.Timestamp(f"{cohort_month}-01")
            window_end = cohort_start + DateOffset(months=w)
            is_observable = window_end <= reference_date

            cohort_channels = result.loc[
                result["cohort_month"] == cohort_month, "channel"
            ].tolist()

            if is_observable and not won_opps.empty:
                mask = (
                    (won_opps["cohort_month"] == cohort_month)
                    & (won_opps["close_date"] >= cohort_start)
                    & (won_opps["close_date"] < window_end)
                )
                channel_rev = won_opps[mask].groupby("channel")["amount_brl"].sum()
                for ch in cohort_channels:
                    revenue_map[(cohort_month, ch)] = float(channel_rev.get(ch, 0.0))
            else:
                for ch in cohort_channels:
                    revenue_map[(cohort_month, ch)] = None

        result[col_name] = result.apply(
            lambda row: revenue_map.get((row["cohort_month"], row["channel"])), axis=1
        )

    return result[
        [
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
        ]
    ]
