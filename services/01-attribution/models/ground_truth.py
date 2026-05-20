import pandas as pd


def compute(spine: pd.DataFrame) -> pd.DataFrame:
    """Uses true_marginal_contribution as the weight (causal ground truth from SCM)."""
    df = spine.copy()
    df["weight"] = df["true_marginal_contribution"]
    return df
