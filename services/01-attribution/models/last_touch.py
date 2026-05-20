import pandas as pd


def compute(spine: pd.DataFrame) -> pd.DataFrame:
    """Assigns 100% credit to the final touchpoint before opportunity creation."""
    df = spine.copy()
    df["weight"] = df["is_last_touch"].astype(float)
    opp_sum = df.groupby("opp_id")["weight"].transform("sum")
    zero_mask = opp_sum == 0
    if zero_mask.any():
        count = df.groupby("opp_id")["touchpoint_id"].transform("count")
        df.loc[zero_mask, "weight"] = 1.0 / count[zero_mask]
    return df
