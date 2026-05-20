import plotly.graph_objects as go

_COLORS = [
    "#4361EE", "#3A0CA3", "#7209B7", "#F72585",
    "#4CC9F0", "#4895EF", "#560BAD", "#B5179E",
]

_LAYOUT = dict(
    font=dict(family="Inter, Arial, sans-serif", size=13),
    plot_bgcolor="white",
    paper_bgcolor="white",
    colorway=_COLORS,
    margin=dict(l=60, r=20, t=40, b=40),
    hoverlabel=dict(bgcolor="white", font_size=12),
)


def apply_theme(fig: go.Figure) -> go.Figure:
    fig.update_layout(**_LAYOUT)
    fig.update_xaxes(showgrid=True, gridcolor="#f0f0f0", linecolor="#e0e0e0")
    fig.update_yaxes(showgrid=False, linecolor="#e0e0e0")
    return fig


def brand_color(index: int = 0) -> str:
    return _COLORS[index % len(_COLORS)]
