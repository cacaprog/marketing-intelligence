import sys
from pathlib import Path

_SVC_DIR = Path(__file__).resolve().parent.parent
_REPO_DIR = _SVC_DIR.parent.parent
for _p in [str(_SVC_DIR), str(_REPO_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pandas as pd
from result_types import AttributionResult, RoasResult


def compute_roas(
    attribution_results: list[AttributionResult],
    spend_df: pd.DataFrame,
    leads_df: pd.DataFrame,
    opps_df: pd.DataFrame,
) -> list[RoasResult]:
    """Compute ROAS, CPQL, and CPO for all paid channels (spend > 0) per model."""
    spend_map: dict[str, float] = spend_df.set_index("channel")["total_spend_brl"].to_dict()
    paid_channels = {ch for ch, spend in spend_map.items() if spend > 0}

    mql_counts: dict[str, int] = (
        leads_df[leads_df["is_mql"] == 1]
        .groupby("first_touch_channel")
        .size()
        .to_dict()
    )
    won_counts: dict[str, int] = (
        opps_df.groupby("first_touch_channel").size().to_dict()
    )

    attr_df = pd.DataFrame([vars(r) for r in attribution_results])
    attr_df = attr_df[attr_df["channel"].isin(paid_channels)]

    results: list[RoasResult] = []
    for _, row in attr_df.iterrows():
        channel = row["channel"]
        spend = spend_map[channel]
        rev = float(row["attributed_revenue_brl"])
        mql_n = mql_counts.get(channel, 0)
        won_n = won_counts.get(channel, 0)

        results.append(
            RoasResult(
                model_name=row["model_name"],
                channel=channel,
                attributed_revenue_brl=rev,
                total_spend_brl=spend,
                roas=round(rev / spend, 4),
                cpql=round(spend / mql_n, 2) if mql_n > 0 else 0.0,
                cpo=round(spend / won_n, 2) if won_n > 0 else 0.0,
            )
        )

    return results
