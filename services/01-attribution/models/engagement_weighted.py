import pandas as pd


def compute(spine: pd.DataFrame) -> pd.DataFrame:
    """Credits each touchpoint proportionally to its engagement_score."""
    df = spine.copy()
    opp_eng_sum = df.groupby("opp_id")["engagement_score"].transform("sum")
    df["weight"] = df["engagement_score"] / opp_eng_sum
    return df
