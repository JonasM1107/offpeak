"""Plotly charts in the offpeak style. Prices arrive in EUR/MWh and UTC; charts show
ct/kWh and German local time."""

import pandas as pd
import plotly.graph_objects as go

from ui.components import INK, LINE, MUTED, ORANGE, ORANGE_SOFT_STRONG, OTHER, PEAK, TZ

CONFIG = {"displayModeBar": False, "responsive": True}


def _layout(fig: go.Figure, height: int = 320) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", size=12, color=MUTED),
        showlegend=False,
        bargap=0.25,
        hoverlabel=dict(bgcolor="#fff", font_color=INK, bordercolor=LINE),
    )
    fig.update_yaxes(gridcolor=LINE, zerolinecolor="#BDB8B0", ticksuffix=" ", title=None)
    fig.update_xaxes(showgrid=False, title=None)
    return fig


def price_bars(prices: pd.DataFrame, cheap: pd.Series, peak: pd.Series, now=None) -> go.Figure:
    """One bar per slot: recommended window orange, peak window dark, the rest grey."""
    x = prices["ts"].dt.tz_convert(TZ)
    colors = [ORANGE if c else PEAK if p else OTHER for c, p in zip(cheap, peak, strict=True)]
    fig = go.Figure(
        go.Bar(
            x=x,
            y=prices["eur_mwh"] / 10,
            marker_color=colors,
            marker_line_width=0,
            hovertemplate="%{x|%H:%M}<br><b>%{y:.1f} ct/kWh</b><extra></extra>",
        )
    )
    if now is not None:
        fig.add_vline(
            x=pd.Timestamp(now).tz_convert(TZ), line_color=INK, line_width=1.5, line_dash="dot"
        )
    fig.update_xaxes(tickformat="%H:%M", dtick=3 * 3600 * 1000)
    fig.update_yaxes(ticksuffix=" ct")
    return _layout(fig)


def price_line(prices: pd.DataFrame) -> go.Figure:
    """Several days of prices as a stepped line."""
    fig = go.Figure(
        go.Scatter(
            x=prices["ts"].dt.tz_convert(TZ),
            y=prices["eur_mwh"] / 10,
            mode="lines",
            line=dict(color=ORANGE, width=1.6, shape="hv"),
            fill="tozeroy",
            fillcolor="rgba(232,89,12,0.08)",
            hovertemplate="%{x|%a %d %b, %H:%M}<br><b>%{y:.1f} ct/kWh</b><extra></extra>",
        )
    )
    fig.update_xaxes(tickformat="%a %d", dtick=24 * 3600 * 1000)
    fig.update_yaxes(ticksuffix=" ct")
    return _layout(fig)


PRICE_PARTS = [
    ("energy_ct", "Energy (spot + supplier)", ORANGE),
    ("grid_ct", "Grid fees", PEAK),
    ("levies_ct", "Levies", OTHER),
    ("tax_ct", "Tax", ORANGE_SOFT_STRONG),
]


def price_stack(prices: pd.DataFrame, tz: str) -> go.Figure:
    """What one bought kWh costs per slot, stacked by part. Columns from tariffs.slot_prices."""
    x = prices["ts"].dt.tz_convert(tz)
    fig = go.Figure(
        [
            go.Bar(
                x=x,
                y=prices[col],
                name=name,
                marker_color=color,
                marker_line_width=0,
                hovertemplate=f"%{{x|%H:%M}} · {name}<br><b>%{{y:.2f}} ct/kWh</b><extra></extra>",
            )
            for col, name, color in PRICE_PARTS
        ]
    )
    fig.add_trace(
        go.Scatter(
            x=x,
            y=prices["import_ct"],
            mode="markers",
            marker=dict(size=0.1, color="rgba(0,0,0,0)"),
            hovertemplate="%{x|%H:%M}<br>total <b>%{y:.1f} ct/kWh</b><extra></extra>",
        )
    )
    fig.update_layout(barmode="relative", bargap=0.2)
    fig.update_xaxes(tickformat="%H:%M", dtick=3 * 3600 * 1000)
    fig.update_yaxes(ticksuffix=" ct")
    return _layout(fig)
