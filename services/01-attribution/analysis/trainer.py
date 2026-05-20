import sys
from pathlib import Path

_SVC_DIR = Path(__file__).resolve().parent.parent
_REPO_DIR = _SVC_DIR.parent.parent
for _p in [str(_SVC_DIR), str(_REPO_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.preprocessing import OrdinalEncoder

from shared.config import MODEL_DIR, TRAIN_CUTOFF_DATE

CATEGORICAL_FEATURES = ["channel", "touch_type"]
NUMERIC_FEATURES = [
    "engagement_score",
    "touch_sequence",
    "total_touches_in_journey",
    "days_before_opp_creation",
    "is_first_touch",
    "is_last_touch",
]
FEATURE_NAMES = CATEGORICAL_FEATURES + NUMERIC_FEATURES
TARGET = "true_marginal_contribution"
MIN_TEST_OPPS = 50


def split_spine(spine: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split attribution spine by opportunity created_date.

    All touchpoints belonging to the same opportunity stay in the same partition.
    Train: opp_created_date < TRAIN_CUTOFF_DATE
    Test:  opp_created_date >= TRAIN_CUTOFF_DATE
    """
    cutoff = pd.Timestamp(TRAIN_CUTOFF_DATE)
    dates = pd.to_datetime(spine["opp_created_date"])
    train_mask = dates < cutoff
    train_spine = spine[train_mask].copy()
    test_spine = spine[~train_mask].copy()

    n_test_opps = test_spine["opp_id"].nunique()
    if n_test_opps < MIN_TEST_OPPS:
        raise ValueError(
            f"Test set has only {n_test_opps} opportunities (need ≥ {MIN_TEST_OPPS}). "
            "Re-generate the dataset or adjust TRAIN_CUTOFF_DATE."
        )

    return train_spine, test_spine


def _build_X(spine: pd.DataFrame, encoder: OrdinalEncoder) -> pd.DataFrame:
    cat = pd.DataFrame(
        encoder.transform(spine[CATEGORICAL_FEATURES]),
        columns=CATEGORICAL_FEATURES,
        index=spine.index,
    )
    num = spine[NUMERIC_FEATURES].astype("float32").copy()
    num.index = spine.index
    X = pd.concat([cat, num], axis=1)
    X[CATEGORICAL_FEATURES] = X[CATEGORICAL_FEATURES].astype("category")
    return X


def train_model(train_spine: pd.DataFrame) -> dict:
    """Train LightGBM regression on true_marginal_contribution; persist artifact."""
    encoder = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)
    encoder.fit(train_spine[CATEGORICAL_FEATURES])

    X_train = _build_X(train_spine, encoder)
    y_train = train_spine[TARGET].values.astype("float32")

    params = {
        "objective": "regression",
        "metric": "mae",
        "num_leaves": 31,
        "min_data_in_leaf": 5,
        "learning_rate": 0.05,
        "n_estimators": 200,
        "verbose": -1,
    }
    ds_train = lgb.Dataset(X_train, label=y_train, categorical_feature=CATEGORICAL_FEATURES, free_raw_data=False)
    booster = lgb.train(params, ds_train, num_boost_round=200)

    artifact = {
        "encoder": encoder,
        "booster": booster,
        "feature_names": FEATURE_NAMES,
        "train_cutoff": TRAIN_CUTOFF_DATE,
    }

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, MODEL_DIR / "attribution_lgbm.joblib")
    booster.save_model(str(MODEL_DIR / "attribution_lgbm.txt"))

    return artifact


def predict_weights(spine: pd.DataFrame, artifact: dict) -> np.ndarray:
    """Return raw (unnormalized) model predictions for spine rows."""
    X = _build_X(spine, artifact["encoder"])
    return artifact["booster"].predict(X)


def get_feature_importance(artifact: dict) -> pd.DataFrame:
    """Normalized gain-based feature importances from the trained booster."""
    booster: lgb.Booster = artifact["booster"]
    importances = booster.feature_importance(importance_type="gain")

    total = importances.sum()
    if total == 0:
        scores = np.ones(len(FEATURE_NAMES)) / len(FEATURE_NAMES)
    else:
        scores = importances / total

    df = pd.DataFrame(
        {
            "feature_name": FEATURE_NAMES,
            "importance_score": scores.round(6),
            "importance_type": "gain",
        }
    )
    df = df.sort_values("importance_score", ascending=False).reset_index(drop=True)
    df["rank"] = range(1, len(df) + 1)
    return df
