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
def load_data():
    attr = pd.read_parquet(DATA_DIR / "attribution_results.parquet")
    bench = pd.read_parquet(DATA_DIR / "benchmark_results.parquet")
    roas = pd.read_parquet(DATA_DIR / "roas_results.parquet")
    return attr, bench, roas


@st.cache_data
def load_ml_data():
    ml_attr = pd.read_parquet(DATA_DIR / "ml_attribution_results.parquet")
    fi = pd.read_parquet(DATA_DIR / "feature_importance.parquet")
    alloc = pd.read_parquet(DATA_DIR / "allocation_recommendations.parquet")
    return ml_attr, fi, alloc


try:
    attr_df, bench_df, roas_df = load_data()
except FileNotFoundError:
    st.error("Output files not found. Run `python services/01-attribution/main.py` first.")
    st.stop()

has_ml = (DATA_DIR / "ml_attribution_results.parquet").exists()
if has_ml:
    ml_attr_df, fi_df, alloc_df = load_ml_data()

# Build model list: heuristics from attribution_results + data_driven if available
heuristic_models = sorted(attr_df["model_name"].unique().tolist())
all_models = heuristic_models + (["data_driven"] if has_ml else [])
selected_model = st.selectbox("Attribution Model", all_models)

is_data_driven = selected_model == "data_driven"

# --- Revenue by Channel ---
col1, col2 = st.columns([3, 2])

with col1:
    st.subheader("Revenue by Channel")
    if is_data_driven and has_ml:
        chart_data = ml_attr_df.sort_values("attributed_revenue_brl", ascending=True)
    else:
        chart_data = attr_df[attr_df["model_name"] == selected_model].sort_values(
            "attributed_revenue_brl", ascending=True
        )
    fig = px.bar(
        chart_data,
        x="attributed_revenue_brl",
        y="channel",
        orientation="h",
        text=chart_data["share_pct"].map(lambda v: f"{v:.1f}%"),
        labels={
            "attributed_revenue_brl": "Attributed Revenue (BRL)",
            "channel": "Channel",
        },
    )
    fig = apply_theme(fig)
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, use_container_width=True)

with col2:
    if is_data_driven and has_ml:
        st.subheader("Feature Importance")
        fi_display = fi_df.sort_values("rank")[["rank", "feature_name", "importance_score"]]
        fig_fi = px.bar(
            fi_display,
            x="importance_score",
            y="feature_name",
            orientation="h",
            labels={
                "importance_score": "Importance (gain, normalized)",
                "feature_name": "Feature",
            },
        )
        fig_fi = apply_theme(fig_fi)
        st.plotly_chart(fig_fi, use_container_width=True)
    else:
        st.subheader("ROAS by Channel")
        roas_filtered = (
            roas_df[roas_df["model_name"] == selected_model]
            .sort_values("roas", ascending=False)[
                ["channel", "roas", "total_spend_brl", "attributed_revenue_brl", "cpo"]
            ]
            .rename(columns={"total_spend_brl": "spend_brl", "attributed_revenue_brl": "revenue_brl"})
        )
        st.dataframe(roas_filtered, use_container_width=True, hide_index=True)

# --- Benchmark ---
st.subheader("Model Accuracy vs. Ground Truth")
st.caption("MAE and Pearson r vs. `true_marginal_contribution` (causal ground truth)")
bench_display = bench_df.sort_values("rank")[["rank", "model_name", "mae", "pearson_r"]].rename(
    columns={"model_name": "model", "pearson_r": "pearson r"}
)
st.dataframe(bench_display, use_container_width=True, hide_index=True)

# --- Media Allocation (data_driven only) ---
if is_data_driven and has_ml:
    st.subheader("Budget Allocation Recommendation")
    st.caption(
        ":warning: Recommendation is a flat per-channel average. "
        "Subpopulation heterogeneity (channel × industry × size) is not modelled."
    )

    default_budget = float(alloc_df["budget_input_brl"].iloc[0])
    budget_input = st.number_input(
        "Total budget (BRL)",
        min_value=10_000.0,
        max_value=10_000_000.0,
        value=default_budget,
        step=10_000.0,
        format="%.2f",
    )

    # Recompute allocation in-browser from efficiency ratios stored in the parquet
    budget_ratio = budget_input / default_budget if default_budget > 0 else 1.0
    alloc_display = alloc_df.copy()
    alloc_display["recommended_spend_brl"] = (
        alloc_display["recommended_spend_brl"] * budget_ratio
    ).round(2)
    # Residual adjustment so displayed values sum exactly to budget_input
    diff = round(budget_input - alloc_display["recommended_spend_brl"].sum(), 2)
    if diff != 0.0:
        idx_max = alloc_display["recommended_spend_brl"].idxmax()
        alloc_display.loc[idx_max, "recommended_spend_brl"] += diff

    alloc_display["expected_revenue_brl"] = (
        alloc_display["recommended_spend_brl"] * alloc_display["channel_efficiency"]
    ).round(2)
    alloc_display["expected_roas"] = (
        alloc_display["expected_revenue_brl"] / alloc_display["recommended_spend_brl"]
    ).round(4)

    st.dataframe(
        alloc_display[
            ["channel", "current_spend_brl", "recommended_spend_brl",
             "expected_revenue_brl", "expected_roas"]
        ].sort_values("recommended_spend_brl", ascending=False),
        use_container_width=True,
        hide_index=True,
    )
