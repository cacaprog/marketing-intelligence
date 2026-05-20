import sys
from pathlib import Path

import pandas as pd
from pandas.tseries.offsets import DateOffset

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
from shared.config import COHORT_WINDOWS, DATASET_REFERENCE_DATE


def compute_cohort_revenue(
    leads_df: pd.DataFrame,
    opps_df: pd.DataFrame,
    reference_date: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Compute cumulative closed-won revenue per cohort × time-window.

    Observability rule: a (cohort, W) cell is observable iff
    cohort_start + DateOffset(months=W) <= reference_date.

    Observable zero-revenue cells use 0.0 (not null).
    Unobservable cells use None + is_observable=False.
    Opps with close_date < lead.lead_date are excluded from revenue (data quality).
    """
    if reference_date is None:
        reference_date = opps_df["close_date"].max()
    reference_date = pd.Timestamp(reference_date)

    leads = leads_df.copy()
    leads["cohort_month"] = leads["lead_date"].dt.to_period("M").astype(str)

    # Join to get lead_date on opps for anomaly detection
    opps = opps_df.merge(
        leads[["lead_id", "lead_date", "cohort_month"]],
        on="lead_id",
        how="inner",
    )
    # Exclude anomalous closes (close_date before lead's lead_date)
    opps = opps[opps["close_date"] >= opps["lead_date"]]
    won_opps = opps[opps["is_won"] == 1]

    cohort_sizes = leads.groupby("cohort_month")["lead_id"].count().rename("cohort_size")
    cohort_months = cohort_sizes.index.tolist()

    rows = []
    for cohort_month in cohort_months:
        cohort_start = pd.Timestamp(f"{cohort_month}-01")
        cohort_won = won_opps[won_opps["cohort_month"] == cohort_month]
        size = cohort_sizes[cohort_month]

        for w in COHORT_WINDOWS:
            window_end = cohort_start + DateOffset(months=w)
            is_observable = window_end <= reference_date

            if is_observable:
                mask = (cohort_won["close_date"] >= cohort_start) & (
                    cohort_won["close_date"] < window_end
                )
                revenue = float(cohort_won.loc[mask, "amount_brl"].sum())
            else:
                revenue = None

            rows.append(
                {
                    "cohort_month": cohort_month,
                    "months_since_acquisition": w,
                    "cumulative_revenue_brl": revenue,
                    "is_observable": is_observable,
                    "cohort_size": int(size),
                }
            )

    return pd.DataFrame(rows)
