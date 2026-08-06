"""Plotly charts for scheduling ops console.

统一使用 Plotly 内置 `plotly_white` 模板（依赖 Streamlit Light Theme），
保证所有文字/轴/图例/悬停标签自动为深色，避免单独逐字段设 color 时漏覆盖。
"""

from __future__ import annotations

from typing import Any, Sequence

import plotly.graph_objects as go
from plotly.subplots import make_subplots

TEAL = "#0f766e"
SLATE = "#0f172a"
CORAL = "#c2410c"
BLUE = "#1d4ed8"


def _apply_white_template(fig: go.Figure, title: str, height: int) -> None:
    """统一应用 plotly_white 模板 + 标题 + 高 + 透明度 + 主色调。"""
    fig.update_layout(
        template="plotly_white",
        title=title,
        height=height,
        margin=dict(l=40, r=40, t=48, b=40),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(248,250,252,0.9)",
        font=dict(color=SLATE, family="Microsoft YaHei, PingFang SC, sans-serif"),
        title_font=dict(color=SLATE),
        legend=dict(font=dict(color=SLATE)),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="#ffffff",
            font_size=12,
            font_color=SLATE,
            bordercolor="#cbd5e1",
        ),
    )


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
            name="在床患者",
            mode="lines+markers",
            line=dict(color=TEAL, width=3),
            fill="tozeroy",
            fillcolor="rgba(15,118,110,0.12)",
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Bar(x=steps, y=adm, name="入院", marker_color=BLUE, opacity=0.75),
        secondary_y=True,
    )
    fig.add_trace(
        go.Bar(x=steps, y=dis, name="出院", marker_color=CORAL, opacity=0.75),
        secondary_y=True,
    )
    fig.update_layout(barmode="group", legend=dict(orientation="h", y=1.12))
    _apply_white_template(fig, "滚动占用与入出转", 360)
    fig.update_xaxes(title_text="滚动步（每步 2 小时）", gridcolor="#e2e8f0", title_font=dict(color=SLATE), tickfont=dict(color=SLATE))
    fig.update_yaxes(title_text="在床患者数", secondary_y=False, gridcolor="#e2e8f0", title_font=dict(color=SLATE), tickfont=dict(color=SLATE))
    fig.update_yaxes(title_text="入院 / 出院人数", secondary_y=True, title_font=dict(color=SLATE), tickfont=dict(color=SLATE))
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
            y=["利用率"],
            colorscale=[[0, "#ecfdf5"], [0.5, "#5eead4"], [1, "#0f766e"]],
            zmin=0,
            zmax=100,
            hovertemplate="步=%{x}<br>利用率=%{z:.1f}%<extra></extra>",
            colorbar=dict(
                title="利用率(%)",
                title_font=dict(color=SLATE),
                tickfont=dict(color=SLATE),
            ),
        )
    )
    _apply_white_template(fig, "床位利用率热力（按滚动步）", 180)
    fig.update_xaxes(title_text="滚动步（每步 2 小时）", title_font=dict(color=SLATE), tickfont=dict(color=SLATE))
    fig.update_yaxes(title_text="床位利用率 (%)", title_font=dict(color=SLATE), tickfont=dict(color=SLATE))
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
            name="平均 SOFA",
        )
    )
    _apply_white_template(fig, "在床患者平均 SOFA", 280)
    fig.update_xaxes(title_text="滚动步（每步 2 小时）", gridcolor="#e2e8f0", title_font=dict(color=SLATE), tickfont=dict(color=SLATE))
    fig.update_yaxes(title_text="在床患者平均 SOFA（分）", gridcolor="#e2e8f0", title_font=dict(color=SLATE), tickfont=dict(color=SLATE))
    return fig
