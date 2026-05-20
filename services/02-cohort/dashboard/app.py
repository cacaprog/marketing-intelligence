import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

_SVC_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SVC_DIR))
sys.path.insert(0, str(_SVC_DIR.parent.parent))

from shared.config import COHORT_WINDOWS, PROCESSED_DIR

COHORT_DIR = PROCESSED_DIR / "02-cohort"
REVENUE_FILE = COHORT_DIR / "cohort_revenue.parquet"
CHANNEL_FILE = COHORT_DIR / "cohort_by_channel.parquet"
FUNNEL_FILE = COHORT_DIR / "cohort_funnel.parquet"

st.set_page_config(page_title="Cohort Analysis", layout="wide")
st.title("Cohort Analysis Dashboard")


@st.cache_data
def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if not REVENUE_FILE.exists():
        return None, None, None
    rev = pd.read_parquet(REVENUE_FILE)
    ch = pd.read_parquet(CHANNEL_FILE)
    fn = pd.read_parquet(FUNNEL_FILE)
    return rev, ch, fn


rev_df, ch_df, fn_df = load_data()

if rev_df is None:
    st.error(
        "Pipeline output not found. Run `python services/02-cohort/main.py` first."
    )
    st.stop()

# --- Sidebar controls ---
st.sidebar.header("Controls")

metric = st.sidebar.radio(
    "Metric", ["Revenue", "Funnel Conversion"], index=0
)

channel_options = ["All"] + sorted(ch_df["channel"].unique().tolist())
channel_filter = st.sidebar.selectbox("Channel", channel_options, index=0)

if metric == "Revenue":
    window_label = st.sidebar.selectbox(
        "Time Window", [f"{w}m" for w in COHORT_WINDOWS], index=2
    )
    selected_window = int(window_label.replace("m", ""))
else:
    rate_metric = st.sidebar.selectbox(
        "Conversion Rate",
        ["mql_rate", "win_rate", "opp_to_win_rate"],
        format_func=lambda x: {
            "mql_rate": "Lead → MQL Rate",
            "win_rate": "Lead → Won Rate",
            "opp_to_win_rate": "Opp → Won Rate",
        }[x],
    )

# --- Build heatmap data ---
if metric == "Revenue":
    if channel_filter == "All":
        plot_df = rev_df[rev_df["months_since_acquisition"] == selected_window].copy()
        plot_df["value"] = plot_df["cumulative_revenue_brl"]
        plot_df["tooltip_size"] = plot_df["cohort_size"]
    else:
        col = f"revenue_{selected_window}m_brl"
        plot_df = ch_df[ch_df["channel"] == channel_filter].copy()
        plot_df["value"] = plot_df[col]
        plot_df["is_observable"] = plot_df[col].notna()
        plot_df["tooltip_size"] = plot_df["lead_count"]
        plot_df["months_since_acquisition"] = selected_window

    pivot_val = plot_df.pivot_table(
        index="cohort_month", columns="months_since_acquisition", values="value"
    )
    pivot_obs = plot_df.pivot_table(
        index="cohort_month", columns="months_since_acquisition", values="is_observable"
    ) if "is_observable" in plot_df.columns else (pivot_val.notna())

else:
    if channel_filter == "All":
        plot_df = fn_df.copy()
        plot_df["value"] = plot_df[rate_metric]
    else:
        plot_df = ch_df[ch_df["channel"] == channel_filter].copy()
        plot_df["value"] = plot_df[rate_metric]
    plot_df["months_since_acquisition"] = rate_metric
    pivot_val = plot_df.pivot_table(
        index="cohort_month", columns="months_since_acquisition", values="value"
    )
    pivot_obs = pivot_val.notna()

# Sort cohort rows chronologically
pivot_val = pivot_val.sort_index()

# Build z matrix and customdata for hovertext
z = pivot_val.values.tolist()
col_labels = [str(c) for c in pivot_val.columns]
row_labels = pivot_val.index.tolist()

# Grey mask: None → grey in heatmap
z_plot = [
    [v if pd.notna(v) else None for v in row]
    for row in z
]

colorscale = "Blues" if metric == "Revenue" else "Greens"
title_suffix = (
    f" — {selected_window}m Revenue" if metric == "Revenue"
    else f" — {rate_metric.replace('_', ' ').title()}"
)
if channel_filter != "All":
    title_suffix += f" ({channel_filter})"

fig = go.Figure(
    go.Heatmap(
        z=z_plot,
        x=col_labels,
        y=row_labels,
        colorscale=colorscale,
        colorbar=dict(title="BRL" if metric == "Revenue" else "Rate"),
        zmin=None,
        zmax=None,
        hoverongaps=False,
        hovertemplate=(
            "Cohort: %{y}<br>"
            "Window: %{x}<br>"
            "Value: %{z:,.0f}<br>"
            "<extra></extra>"
        ),
    )
)

fig.update_layout(
    title=f"Cohort Heatmap{title_suffix}",
    xaxis_title="Months Since Acquisition" if metric == "Revenue" else "Metric",
    yaxis_title="Acquisition Cohort",
    height=600,
)

st.plotly_chart(fig, use_container_width=True)

# --- Summary stats ---
col1, col2, col3 = st.columns(3)
total_cells = pivot_val.size
observable_cells = int(pivot_val.notna().sum().sum())
with col1:
    st.metric("Cohorts", len(row_labels))
with col2:
    st.metric("Observable Cells", f"{observable_cells}/{total_cells}")
with col3:
    if metric == "Revenue":
        total = pivot_val.stack().sum()
        st.metric("Total Revenue (shown)", f"BRL {total:,.0f}")

# --- Funnel table ---
with st.expander("Funnel Table"):
    display_fn = fn_df if channel_filter == "All" else ch_df[ch_df["channel"] == channel_filter]
    st.dataframe(display_fn, use_container_width=True)
