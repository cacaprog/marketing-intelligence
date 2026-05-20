import sys
from pathlib import Path

_SVC_DIR = Path(__file__).resolve().parent.parent
_REPO_DIR = _SVC_DIR.parent.parent
for _p in [str(_SVC_DIR), str(_REPO_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest
import pandas as pd


@pytest.fixture
def sample_spine() -> pd.DataFrame:
    """Minimal attribution spine for unit tests (no DB required)."""
    return pd.DataFrame(
        {
            "touchpoint_id": ["TP-1", "TP-2", "TP-3", "TP-4", "TP-5"],
            "opp_id": ["OPP-1", "OPP-1", "OPP-1", "OPP-2", "OPP-2"],
            "lead_id": ["L-1", "L-1", "L-1", "L-2", "L-2"],
            "touch_sequence": [1, 2, 3, 1, 2],
            "total_touches_in_journey": [3, 3, 3, 2, 2],
            "channel": [
                "paid_search",
                "organic_search",
                "linkedin_ads",
                "meta_ads",
                "email_marketing",
            ],
            "touch_type": [
                "click",
                "content_view",
                "demo_request",
                "impression",
                "form_fill",
            ],
            "engagement_score": [25, 35, 85, 10, 65],
            "days_before_opp_creation": [30, 15, 1, 20, 5],
            "is_first_touch": [1, 0, 0, 1, 0],
            "is_last_touch": [0, 0, 1, 0, 1],
            "true_marginal_contribution": [0.2, 0.3, 0.5, 0.4, 0.6],
            "amount_brl": [100_000.0, 100_000.0, 100_000.0, 80_000.0, 80_000.0],
        }
    )
