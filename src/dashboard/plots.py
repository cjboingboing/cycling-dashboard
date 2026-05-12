"""
plots.py
--------
Plotly chart functions for the Streamlit dashboard.
Each function takes a DataFrame and returns a plotly Figure.
"""

import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd


COLOURS = {
    "ctl":      "#4f90f7",   # electric blue
    "atl":      "#f45b3b",   # red-orange
    "tsb":      "#2bc48a",   # emerald
    "hrv":      "#c084fc",   # violet
    "baseline": "#4a4a72",   # muted purple-grey
    "bar":      "#e8541a",   # orange accent
}

_BG        = "#09090f"
_SURFACE   = "#111120"
_BORDER    = "#1e1e38"
_GRID      = "#161628"
_TEXT      = "#9090b8"
_TEXT_DIM  = "#50507a"

_LAYOUT = dict(
    paper_bgcolor = _SURFACE,
    plot_bgcolor  = _SURFACE,
    font          = dict(family="Inter, -apple-system, sans-serif", color=_TEXT, size=11),
    margin        = dict(l=52, r=24, t=44, b=44),
    hovermode     = "x unified",
    hoverlabel    = dict(
        bgcolor    = "#1a1a30",
        bordercolor= _BORDER,
        font       = dict(color="#ffffff", size=12),
    ),
    legend = dict(
        orientation = "h",
        yanchor     = "bottom",
        y           = 1.02,
        xanchor     = "right",
        x           = 1,
        bgcolor     = "rgba(0,0,0,0)",
        font        = dict(color=_TEXT, size=11),
    ),
)

_AXIS = dict(
    gridcolor     = _GRID,
    zerolinecolor = _GRID,
    tickfont      = dict(color=_TEXT_DIM, size=10),
    linecolor     = _BORDER,
    showgrid      = True,
)


def plot_pmc(pmc_df: pd.DataFrame) -> go.Figure:
    """PMC chart: CTL, ATL, TSB on dual axes."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(go.Scatter(
        x=pmc_df["date"], y=pmc_df["ctl"],
        name="CTL — Fitness",
        line=dict(color=COLOURS["ctl"], width=2),
        hovertemplate="%{y:.1f}",
    ), secondary_y=False)

    fig.add_trace(go.Scatter(
        x=pmc_df["date"], y=pmc_df["atl"],
        name="ATL — Fatigue",
        line=dict(color=COLOURS["atl"], width=2),
        hovertemplate="%{y:.1f}",
    ), secondary_y=False)

    fig.add_trace(go.Scatter(
        x=pmc_df["date"], y=pmc_df["tsb"],
        name="TSB — Form",
        line=dict(color=COLOURS["tsb"], width=1.5, dash="dot"),
        fill="tozeroy",
        fillcolor="rgba(43,196,138,0.06)",
        hovertemplate="%{y:.1f}",
    ), secondary_y=True)

    fig.add_hline(y=0, line_dash="solid", line_color=_GRID, line_width=1, secondary_y=True)

    _axis_no_grid = {k: v for k, v in _AXIS.items() if k != "showgrid"}
    fig.update_layout(**_LAYOUT)
    fig.update_xaxes(**_AXIS)
    fig.update_yaxes(**_AXIS, title_text="CTL / ATL", secondary_y=False)
    fig.update_yaxes(**_axis_no_grid, title_text="TSB", secondary_y=True, showgrid=False)

    return fig


def plot_weekly_tss(pmc_df: pd.DataFrame) -> go.Figure:
    """Bar chart of weekly TSS totals."""
    df = pmc_df.copy()
    df["week"] = df["date"].dt.to_period("W").dt.start_time
    weekly = df.groupby("week")["daily_tss"].sum().reset_index()
    weekly.columns = ["week", "tss"]

    fig = go.Figure(go.Bar(
        x=weekly["week"],
        y=weekly["tss"],
        marker=dict(
            color=COLOURS["bar"],
            opacity=0.85,
            line=dict(width=0),
        ),
        hovertemplate="<b>%{x|%d %b}</b><br>TSS: %{y:.0f}<extra></extra>",
    ))

    fig.update_layout(
        **_LAYOUT,
        xaxis_title="Week",
        yaxis_title="TSS",
        bargap=0.25,
    )
    fig.update_xaxes(**_AXIS)
    fig.update_yaxes(**_AXIS)

    return fig


def plot_zone_distribution(zones_df: pd.DataFrame) -> go.Figure:
    """Horizontal bar chart of time-in-zone."""
    zone_colours = [
        "#3b82f6", "#60a5fa", "#f59e0b",
        "#f97316", "#f45b3b", "#dc2626", "#7f1d1d",
    ]

    fig = go.Figure()
    for i, row in zones_df.iterrows():
        color = zone_colours[i % len(zone_colours)]
        fig.add_trace(go.Bar(
            y=[row["zone"]],
            x=[row["duration_hours"]],
            orientation="h",
            marker=dict(color=color, line=dict(width=0)),
            text=f"{row['pct']:.0f}%",
            textposition="outside",
            textfont=dict(color=_TEXT, size=10),
            name=row["zone"],
            showlegend=False,
            hovertemplate=f"<b>{row['zone']}</b><br>{row['duration_hours']:.1f} h ({row['pct']:.0f}%)<extra></extra>",
        ))

    fig.update_layout(
        **_LAYOUT,
        xaxis_title="Hours",
        yaxis_title="",
        barmode="overlay",
    )
    fig.update_layout(margin=dict(l=90, r=48, t=24, b=44))
    fig.update_xaxes(**_AXIS)
    fig.update_yaxes(**{**_AXIS, "showgrid": False})

    return fig


def plot_power_curve(curve_df: pd.DataFrame, ftp: float | None = None) -> go.Figure:
    """Log-scale power curve with optional FTP reference line."""
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=curve_df["duration_s"],
        y=curve_df["best_power_w"],
        mode="lines+markers",
        name="Best Power",
        line=dict(color=COLOURS["ctl"], width=2.5),
        marker=dict(size=5, color=COLOURS["ctl"], line=dict(width=0)),
        fill="tozeroy",
        fillcolor="rgba(79,144,247,0.07)",
        hovertemplate="<b>%{text}</b><br>%{y:.0f} W<extra></extra>",
        text=curve_df.get("duration_label", curve_df["duration_s"].astype(str)),
    ))

    if ftp is not None:
        fig.add_hline(
            y=ftp,
            line_dash="dot",
            line_color=_TEXT_DIM,
            line_width=1,
            annotation_text=f"FTP {ftp} W",
            annotation_position="bottom right",
            annotation_font=dict(color=_TEXT_DIM, size=10),
        )

    tick_vals  = curve_df["duration_s"].tolist()
    tick_texts = curve_df["duration_label"].tolist()

    fig.update_layout(
        **_LAYOUT,
        xaxis=dict(
            **_AXIS,
            type="log",
            tickvals=tick_vals,
            ticktext=tick_texts,
            title="Duration",
        ),
        yaxis_title="Power (W)",
    )
    fig.update_yaxes(**_AXIS)

    return fig


def plot_hrv_trend(recovery_df: pd.DataFrame) -> go.Figure:
    """HRV RMSSD trend with rolling baseline."""
    fig = go.Figure()

    if "hrv_baseline" in recovery_df.columns:
        fig.add_trace(go.Scatter(
            x=recovery_df["date"],
            y=recovery_df["hrv_baseline"],
            name="7-day baseline",
            line=dict(color=COLOURS["baseline"], width=1.5, dash="dash"),
            hovertemplate="%{y:.1f} ms",
        ))

    fig.add_trace(go.Scatter(
        x=recovery_df["date"],
        y=recovery_df["hrv_rmssd"],
        name="HRV (RMSSD)",
        line=dict(color=COLOURS["hrv"], width=2.5),
        mode="lines+markers",
        marker=dict(size=4, color=COLOURS["hrv"], line=dict(width=0)),
        fill="tozeroy",
        fillcolor="rgba(192,132,252,0.06)",
        hovertemplate="%{y:.1f} ms",
    ))

    fig.update_layout(
        **_LAYOUT,
        yaxis_title="RMSSD (ms)",
    )
    fig.update_xaxes(**_AXIS)
    fig.update_yaxes(**_AXIS)

    return fig
