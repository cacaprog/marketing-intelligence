import sys
from pathlib import Path

_SVC_DIR = Path(__file__).resolve().parent.parent
_REPO_DIR = _SVC_DIR.parent.parent
for _p in [str(_SVC_DIR), str(_REPO_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pandas as pd
from models import last_touch, first_touch, linear, time_decay, position_based, engagement_weighted
from result_types import AttributionResult

MODEL_REGISTRY: dict = {
    "last_touch": last_touch,
    "first_touch": first_touch,
    "linear": linear,
    "time_decay": time_decay,
    "position_based": position_based,
    "engagement_weighted": engagement_weighted,
}


def run_all_models(spine: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Run all six attribution models; returns dict of model_name → weighted spine."""
    return {name: mod.compute(spine) for name, mod in MODEL_REGISTRY.items()}


def to_channel_table(weighted_spine: pd.DataFrame, model_name: str) -> list[AttributionResult]:
    """Aggregate a weighted spine to channel-level AttributionResult objects."""
    df = weighted_spine.copy()
    df["attributed_revenue_brl"] = df["amount_brl"] * df["weight"]

    agg = (
        df.groupby("channel")
        .agg(
            attributed_revenue_brl=("attributed_revenue_brl", "sum"),
            attributed_opps=("opp_id", "nunique"),
        )
        .reset_index()
    )

    total_rev = agg["attributed_revenue_brl"].sum()
    agg["share_pct"] = (agg["attributed_revenue_brl"] / total_rev * 100).round(4)

    return [
        AttributionResult(
            model_name=model_name,
            channel=row["channel"],
            attributed_revenue_brl=round(row["attributed_revenue_brl"], 2),
            attributed_opps=int(row["attributed_opps"]),
            share_pct=float(row["share_pct"]),
        )
        for _, row in agg.iterrows()
    ]
