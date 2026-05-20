"""Media Attribution Dashboard — interactive model explorer.

Launch: streamlit run services/01-attribution/dashboard/app.py
Requires: data/processed/01-attribution/ parquet files (run main.py first)
"""

import sys
from pathlib import Path

_SVC_DIR = Path(__file__).resolve().parent.parent
_REPO_DIR = _SVC_DIR.parent.parent
for _p in [str(_SVC_DIR), str(_REPO_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pandas as pd
import plotly.express as px
import streamlit as st

from shared.config import PROCESSED_DIR
from shared.viz import apply_theme

DATA_DIR = PROCESSED_DIR / "01-attribution"

st.set_page_config(page_title="Media Attribution", layout="wide")
st.title("Media Attribution Model")
st.caption("B2B SaaS — 18-month synthetic dataset | 2023-01 → 2024-06")


@st.cache_data
def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    attr = pd.read_parquet(DATA_DIR / "attribution_results.parquet")
    bench = pd.read_parquet(DATA_DIR / "benchmark_results.parquet")
    roas = pd.read_parquet(DATA_DIR / "roas_results.parquet")
    return attr, bench, roas


try:
    attr_df, bench_df, roas_df = load_data()
except FileNotFoundError:
    st.error(
        "Output files not found. Run `python services/01-attribution/main.py` first."
    )
    st.stop()

models = sorted(attr_df["model_name"].unique())
selected_model = st.selectbox("Attribution Model", models)

col1, col2 = st.columns([3, 2])

with col1:
    st.subheader("Revenue by Channel")
    filtered = attr_df[attr_df["model_name"] == selected_model].sort_values(
        "attributed_revenue_brl", ascending=True
    )
    fig = px.bar(
        filtered,
        x="attributed_revenue_brl",
        y="channel",
        orientation="h",
        text=filtered["share_pct"].map(lambda v: f"{v:.1f}%"),
        labels={
            "attributed_revenue_brl": "Attributed Revenue (BRL)",
            "channel": "Channel",
        },
    )
    fig = apply_theme(fig)
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("ROAS by Channel")
    roas_filtered = (
        roas_df[roas_df["model_name"] == selected_model]
        .sort_values("roas", ascending=False)[
            ["channel", "roas", "total_spend_brl", "attributed_revenue_brl", "cpo"]
        ]
        .rename(
            columns={
                "total_spend_brl": "spend_brl",
                "attributed_revenue_brl": "revenue_brl",
            }
        )
    )
    st.dataframe(roas_filtered, use_container_width=True, hide_index=True)

st.subheader("Model Accuracy vs. Ground Truth")
st.caption("MAE and Pearson r computed against `true_marginal_contribution` (causal ground truth)")
bench_display = bench_df.sort_values("rank")[
    ["rank", "model_name", "mae", "pearson_r"]
].rename(columns={"model_name": "model", "pearson_r": "pearson r"})
st.dataframe(bench_display, use_container_width=True, hide_index=True)
