import pandas as pd


def compute(spine: pd.DataFrame) -> pd.DataFrame:
    """Distributes credit equally across all touchpoints in the journey."""
    df = spine.copy()
    df["weight"] = 1.0 / df["total_touches_in_journey"]
    return df
