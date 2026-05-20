import sys
from pathlib import Path

_SVC_DIR = Path(__file__).resolve().parent.parent
_REPO_DIR = _SVC_DIR.parent.parent
for _p in [str(_SVC_DIR), str(_REPO_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np
import pandas as pd

from result_types import AllocationRecommendation, AttributionResult

PAID_CHANNELS_EXCLUDE = {"organic_search", "direct"}


def compute_allocation(
    attribution_results: list[AttributionResult],
    spend_df: pd.DataFrame,
    budget_brl: float,
) -> list[AllocationRecommendation]:
    """Recommend per-channel budget split proportional to data-driven channel efficiency.

    Efficiency = attributed_revenue_brl / spend_brl for each paid channel.
    Channels with zero efficiency receive zero recommended spend.
    Budget sum is guaranteed exact via residual adjustment on the largest-allocation channel.
    """
    if budget_brl <= 0:
        raise ValueError(f"budget_brl must be > 0, got {budget_brl}")

    # Build spend lookup
    spend_lookup: dict[str, float] = dict(
        zip(spend_df["channel"], spend_df["total_spend_brl"].astype(float))
    )

    # Identify paid channels (those with spend > 0)
    paid_channels = {ch for ch, spend in spend_lookup.items() if spend > 0}
    paid_channels -= PAID_CHANNELS_EXCLUDE

    paid_attr = [r for r in attribution_results if r.channel in paid_channels]
    if not paid_attr:
        raise ValueError("No paid channel rows found in attribution_results.")

    attr_lookup: dict[str, float] = {r.channel: r.attributed_revenue_brl for r in paid_attr}

    # Ensure all paid channels have an entry (even if not in attribution results)
    for ch in paid_channels:
        attr_lookup.setdefault(ch, 0.0)

    channels = sorted(paid_channels)
    spends = np.array([spend_lookup[ch] for ch in channels], dtype=float)
    revenues = np.array([attr_lookup[ch] for ch in channels], dtype=float)

    efficiencies = np.where(spends > 0, revenues / spends, 0.0)
    total_efficiency = efficiencies.sum()

    if total_efficiency == 0.0:
        # All channels have zero efficiency — split evenly
        weights = np.ones(len(channels)) / len(channels)
    else:
        weights = efficiencies / total_efficiency

    recommended = np.round(weights * budget_brl, 2)

    # Residual adjustment: assign leftover cents to the channel with highest allocation
    diff = round(budget_brl - recommended.sum(), 2)
    if diff != 0.0:
        recommended[int(np.argmax(recommended))] += diff

    results = []
    for i, ch in enumerate(channels):
        rec_spend = float(recommended[i])
        eff = float(efficiencies[i])
        exp_rev = round(rec_spend * eff, 2)
        exp_roas = round(exp_rev / rec_spend, 4) if rec_spend > 0 else None
        results.append(
            AllocationRecommendation(
                channel=ch,
                current_spend_brl=round(float(spends[i]), 2),
                channel_efficiency=round(eff, 6),
                recommended_spend_brl=rec_spend,
                expected_revenue_brl=exp_rev,
                expected_roas=exp_roas,
                budget_input_brl=budget_brl,
                subpopulation_caveat=True,
            )
        )

    return results
