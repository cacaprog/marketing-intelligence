import sys
from pathlib import Path

import pandas as pd
import pytest

_SVC_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SVC_DIR))
sys.path.insert(0, str(_SVC_DIR.parent.parent))


@pytest.fixture
def mini_leads_df():
    """Six leads across two cohort months.

    Cohort 2023-01: leads L1–L4 (4 leads, channels: paid_search x2, linkedin_ads, None)
    Cohort 2023-02: leads L5–L6 (2 leads, channels: organic_search x2)
    """
    return pd.DataFrame(
        {
            "lead_id": ["L1", "L2", "L3", "L4", "L5", "L6"],
            "first_touch_channel": [
                "paid_search",
                "paid_search",
                "linkedin_ads",
                None,  # → "unknown" bucket (FR-007)
                "organic_search",
                "organic_search",
            ],
            "lead_date": pd.to_datetime(
                [
                    "2023-01-05",
                    "2023-01-10",
                    "2023-01-20",
                    "2023-01-25",
                    "2023-02-03",
                    "2023-02-14",
                ]
            ),
            "is_mql": [1, 1, 0, 1, 1, 0],
        }
    )


@pytest.fixture
def mini_opps_df():
    """Five opportunities with controlled close_date/amount/is_won values.

    O1: L1, won, closes 2023-01-20 → within W=1 for cohort 2023-01
    O2: L2, won, closes 2023-03-15 → within W=3 but outside W=1 for cohort 2023-01
    O3: L3, lost → does NOT count in revenue or won_count
    O4: L4, won, close_date 2023-01-01 BEFORE lead_date 2023-01-25 → anomaly, excluded
    O5: L5, won, closes 2023-03-01 → within W=3 for cohort 2023-02
                                      (NOT in W=1: [2023-02-01, 2023-03-01) is half-open)
    """
    return pd.DataFrame(
        {
            "opp_id": ["O1", "O2", "O3", "O4", "O5"],
            "lead_id": ["L1", "L2", "L3", "L4", "L5"],
            "amount_brl": [10_000.0, 25_000.0, 8_000.0, 15_000.0, 5_000.0],
            "close_date": pd.to_datetime(
                [
                    "2023-01-20",
                    "2023-03-15",
                    "2023-04-01",
                    "2023-01-01",  # anomaly: before L4.lead_date
                    "2023-03-01",
                ]
            ),
            "is_won": [1, 1, 0, 1, 1],
            "created_date": pd.to_datetime(
                [
                    "2023-01-10",
                    "2023-01-20",
                    "2023-02-01",
                    "2023-01-26",
                    "2023-02-10",
                ]
            ),
        }
    )


@pytest.fixture
def reference_date():
    return pd.Timestamp("2024-09-25")
