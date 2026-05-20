import sqlite3
import pandas as pd
from shared.config import DB_PATH


def get_attribution_spine() -> pd.DataFrame:
    """Touchpoints joined with won opportunities — the input for all attribution models."""
    conn = sqlite3.connect(DB_PATH)
    try:
        return pd.read_sql_query(
            """
            SELECT
                t.touchpoint_id,
                t.opp_id,
                t.lead_id,
                t.touch_sequence,
                t.total_touches_in_journey,
                t.channel,
                t.touch_type,
                t.engagement_score,
                t.days_before_opp_creation,
                t.is_first_touch,
                t.is_last_touch,
                t.true_marginal_contribution,
                o.amount_brl
            FROM touchpoints t
            JOIN opportunities o ON t.opp_id = o.opp_id
            WHERE o.is_won = 1
            """,
            conn,
        )
    finally:
        conn.close()


def get_channel_spend() -> pd.DataFrame:
    """Total spend per channel aggregated over the full dataset period."""
    conn = sqlite3.connect(DB_PATH)
    try:
        return pd.read_sql_query(
            """
            SELECT channel, SUM(spend_brl) AS total_spend_brl
            FROM channel_spend
            GROUP BY channel
            """,
            conn,
        )
    finally:
        conn.close()


def get_leads() -> pd.DataFrame:
    """Lead table with MQL flag and first-touch channel for CPQL computation."""
    conn = sqlite3.connect(DB_PATH)
    try:
        return pd.read_sql_query(
            "SELECT lead_id, account_id, first_touch_channel, is_mql FROM leads",
            conn,
        )
    finally:
        conn.close()


def get_won_opps() -> pd.DataFrame:
    """Won opportunities with first-touch channel for CPO computation."""
    conn = sqlite3.connect(DB_PATH)
    try:
        return pd.read_sql_query(
            """
            SELECT opp_id, lead_id, first_touch_channel, amount_brl
            FROM opportunities
            WHERE is_won = 1
            """,
            conn,
        )
    finally:
        conn.close()
