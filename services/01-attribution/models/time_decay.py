import sys
from pathlib import Path

_SVC_DIR = Path(__file__).resolve().parent.parent
_REPO_DIR = _SVC_DIR.parent.parent
for _p in [str(_SVC_DIR), str(_REPO_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np
import pandas as pd
from shared.config import TIME_DECAY_HALF_LIFE


def compute(spine: pd.DataFrame) -> pd.DataFrame:
    """Credits touchpoints exponentially more as they approach opportunity creation.

    Uses half-life from shared/config.py (default 14 days), matching the SCM
    decay parameter used in generate_dataset.py.
    """
    df = spine.copy()
    df["_raw"] = np.exp(-df["days_before_opp_creation"] / TIME_DECAY_HALF_LIFE)
    opp_sum = df.groupby("opp_id")["_raw"].transform("sum")
    df["weight"] = df["_raw"] / opp_sum
    df.drop(columns=["_raw"], inplace=True)
    return df
