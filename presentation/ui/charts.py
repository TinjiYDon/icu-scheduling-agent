"""Plotly charts for scheduling ops console."""

from __future__ import annotations

from typing import Any, Sequence

import plotly.graph_objects as go
from plotly.subplots import make_subplots

TEAL = "#0f766e"
SLATE = "#334155"
CORAL = "#c2410c"
BLUE = "#1d4ed8"


def fig_occupancy_timeline(history: Sequence[dict[str, Any]]) -> go.Figure:
    steps = [h.get("step", i) for i, h in enumerate(history)]
    occ = [h.get("occupied", 0) for h in history]
    adm = [h.get("admitted", 0) for h in history]
    dis = [h.get("discharged", 0) for h in history]
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Scatter(
            x=steps,
            y=occ,
            name="occupied",
            mode="lines+markers",
            line=dict(color=TEAL, width=3),
            fill="tozeroy",
            fillcolor="rgba(15,118,110,0.12)",
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Bar(x=steps, y=adm, name="admitted", marker_color=BLUE, opacity=0.7),
        secondary_y=True,
    )
    fig.add_trace(
        go.Bar(x=steps, y=dis, name="discharged", marker_color=CORAL, opacity=0.7),
        secondary_y=True,
    )
    fig.update_layout(
        title="滚动占用与入出转",
        barmode="group",
        height=360,
        margin=dict(l=40, r=40, t=48, b=40),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(248,250,252,0.9)",
        font=dict(color=SLATE),
        legend=dict(orientation="h", y=1.12),
    )
    fig.update_xaxes(title_text="步", gridcolor="#e2e8f0")
    fig.update_yaxes(title_text="在床数", secondary_y=False, gridcolor="#e2e8f0")
    fig.update_yaxes(title_text="入院 / 出院", secondary_y=True)
    return fig


def fig_occupancy_heatmap(history: Sequence[dict[str, Any]], n_beds: int) -> go.Figure:
    """1×N heatmap of occupancy rate by step (proxy when per-bed trajectory absent)."""
    steps = [str(h.get("step", i)) for i, h in enumerate(history)]
    rates = [
        (float(h.get("occupied", 0)) / max(int(n_beds), 1)) * 100.0 for h in history
    ]
    fig = go.Figure(
        data=go.Heatmap(
            z=[rates],
            x=steps,
            y=["利用率 %"],
            colorscale=[[0, "#ecfdf5"], [0.5, "#5eead4"], [1, "#0f766e"]],
            zmin=0,
            zmax=100,
            hovertemplate="步=%{x}<br>利用率=%{z:.1f}%<extra></extra>",
            colorbar=dict(title="%"),
        )
    )
    fig.update_layout(
        title="床位利用率热力（按滚动步）",
        height=180,
        margin=dict(l=40, r=20, t=48, b=40),
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color=SLATE),
    )
    return fig


def fig_sofa_avg(history: Sequence[dict[str, Any]]) -> go.Figure:
    steps = [h.get("step", i) for i, h in enumerate(history)]
    sofa = [h.get("avg_sofa", 0) for h in history]
    fig = go.Figure(
        go.Scatter(
            x=steps,
            y=sofa,
            mode="lines+markers",
            line=dict(color=CORAL, width=2),
            marker=dict(size=8),
            name="avg SOFA",
        )
    )
    fig.update_layout(
        title="在床患者平均 SOFA",
        xaxis_title="步",
        yaxis_title="平均 SOFA",
        height=280,
        margin=dict(l=40, r=20, t=48, b=40),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(248,250,252,0.9)",
        font=dict(color=SLATE),
    )
    fig.update_xaxes(gridcolor="#e2e8f0")
    fig.update_yaxes(gridcolor="#e2e8f0")
    return fig
