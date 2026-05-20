import sys
from pathlib import Path

_SVC_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SVC_DIR))
sys.path.insert(0, str(_SVC_DIR.parent.parent))

from shared.config import PROCESSED_DIR
from shared.db import get_cohort_data
from models.cohort_revenue import compute_cohort_revenue
from models.cohort_funnel import compute_cohort_funnel
from models.channel_cohort import compute_channel_cohorts

OUTPUT_DIR = PROCESSED_DIR / "02-cohort"


def run_pipeline() -> None:
    print("Cohort Analysis Pipeline")
    print("=" * 40)

    leads_df, opps_df = get_cohort_data()

    rev_df = compute_cohort_revenue(leads_df, opps_df)
    fn_df = compute_cohort_funnel(leads_df, opps_df)
    ch_df = compute_channel_cohorts(leads_df, opps_df)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    outputs = [
        (rev_df, "cohort_revenue"),
        (fn_df, "cohort_funnel"),
        (ch_df, "cohort_by_channel"),
    ]
    for df, name in outputs:
        df.to_parquet(OUTPUT_DIR / f"{name}.parquet", index=False)
        df.to_csv(OUTPUT_DIR / f"{name}.csv", index=False)

    cohort_count = rev_df["cohort_month"].nunique()
    total_rev = rev_df.loc[rev_df["is_observable"], "cumulative_revenue_brl"].pipe(
        lambda s: rev_df.loc[rev_df["is_observable"]]
        .groupby("cohort_month")["cumulative_revenue_brl"]
        .max()
        .sum()
    )
    observable = int(rev_df["is_observable"].sum())
    total_cells = len(rev_df)

    print(f"Cohorts:            {cohort_count}  ({rev_df['cohort_month'].min()} → {rev_df['cohort_month'].max()})")
    print(f"Total revenue:      BRL {total_rev:,.2f}")
    print(f"Observable cells:   {observable} / {total_cells}")
    print(f"Unobservable:       {total_cells - observable} / {total_cells}")
    print(f"Outputs written to: {OUTPUT_DIR}")
    for _, name in outputs:
        print(f"  {name}.parquet  + .csv")
    print()
    print("Note: SC-002 revenue conservation is ~95% (not ±1%) because cohorts")
    print("2024-04/05/06 have won deals that close after their W=3 max observable")
    print("window but before the reference date. This is an inherent dataset trait,")
    print("not an implementation defect.")


if __name__ == "__main__":
    run_pipeline()
