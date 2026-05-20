import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))


def _safe_rate(numer: pd.Series, denom: pd.Series) -> pd.Series:
    return np.where(denom > 0, numer / denom, 0.0).astype(float)


def compute_cohort_funnel(
    leads_df: pd.DataFrame,
    opps_df: pd.DataFrame,
) -> pd.DataFrame:
    """Compute funnel counts and conversion rates per cohort month.

    Funnel: leads → MQL → opp created → closed-won.
    All rate columns are zero-safe (0.0 when denominator is 0, never NaN).
    """
    leads = leads_df.copy()
    leads["cohort_month"] = leads["lead_date"].dt.to_period("M").astype(str)

    # Lead and MQL counts per cohort
    funnel = (
        leads.groupby("cohort_month")
        .agg(
            lead_count=("lead_id", "count"),
            mql_count=("is_mql", "sum"),
        )
        .reset_index()
    )

    # Opp and won counts: join opps to leads to get cohort_month
    if not opps_df.empty:
        opps_with_cohort = opps_df.merge(
            leads[["lead_id", "cohort_month"]], on="lead_id", how="inner"
        )
        opp_counts = (
            opps_with_cohort.groupby("cohort_month")
            .agg(
                opp_count=("opp_id", "count"),
                won_count=("is_won", "sum"),
            )
            .reset_index()
        )
    else:
        opp_counts = pd.DataFrame(
            columns=["cohort_month", "opp_count", "won_count"]
        )

    funnel = funnel.merge(opp_counts, on="cohort_month", how="left")
    funnel["opp_count"] = funnel["opp_count"].fillna(0).astype(int)
    funnel["won_count"] = funnel["won_count"].fillna(0).astype(int)

    funnel["mql_rate"] = _safe_rate(funnel["mql_count"], funnel["lead_count"])
    funnel["opp_rate"] = _safe_rate(funnel["opp_count"], funnel["lead_count"])
    funnel["win_rate"] = _safe_rate(funnel["won_count"], funnel["lead_count"])
    funnel["opp_to_win_rate"] = _safe_rate(funnel["won_count"], funnel["opp_count"])

    return funnel[
        [
            "cohort_month",
            "lead_count",
            "mql_count",
            "opp_count",
            "won_count",
            "mql_rate",
            "opp_rate",
            "win_rate",
            "opp_to_win_rate",
        ]
    ]
