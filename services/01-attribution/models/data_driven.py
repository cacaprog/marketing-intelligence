import sys
from pathlib import Path

_SVC_DIR = Path(__file__).resolve().parent.parent
_REPO_DIR = _SVC_DIR.parent.parent
for _p in [str(_SVC_DIR), str(_REPO_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np
import pandas as pd

from analysis.trainer import predict_weights


def compute(spine: pd.DataFrame, model_artifact: dict) -> pd.DataFrame:
    """Assign attribution weights using the trained LightGBM model.

    Clips negative predictions to 0, normalizes per opp_id to sum = 1.0.
    Falls back to uniform weights for opportunities where all predictions are <= 0.
    """
    result = spine.copy()
    raw = predict_weights(spine, model_artifact)
    clipped = np.maximum(raw, 0.0)
    result["_raw_weight"] = clipped

    opp_sums = result.groupby("opp_id")["_raw_weight"].transform("sum")
    degenerate = opp_sums == 0.0
    n_touches = result.groupby("opp_id")["opp_id"].transform("count")

    weight = np.where(degenerate, 1.0 / n_touches, clipped / opp_sums)
    result["weight"] = weight
    result.drop(columns=["_raw_weight"], inplace=True)
    return result
