import pandas as pd


def compute(spine: pd.DataFrame) -> pd.DataFrame:
    """40% first touch, 40% last touch, 20% split evenly among middle touches.

    Edge cases:
    - 1 touch: gets 100% (it is both first and last)
    - 2 touches: each gets 50% (no middle)
    """
    df = spine.copy()
    opp_n = df.groupby("opp_id")["touchpoint_id"].transform("count")
    df["weight"] = 0.0

    single = opp_n == 1
    df.loc[single, "weight"] = 1.0

    two = opp_n == 2
    df.loc[two & (df["is_first_touch"] == 1), "weight"] = 0.5
    df.loc[two & (df["is_last_touch"] == 1), "weight"] = 0.5

    multi = opp_n >= 3
    df.loc[multi & (df["is_first_touch"] == 1), "weight"] = 0.40
    df.loc[multi & (df["is_last_touch"] == 1), "weight"] = 0.40

    n_middle = (opp_n - 2).clip(lower=1)
    is_middle = multi & (df["is_first_touch"] == 0) & (df["is_last_touch"] == 0)
    df.loc[is_middle, "weight"] = (0.20 / n_middle)[is_middle]

    return df
