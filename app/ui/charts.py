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
        hoverlabel=dict(bgcolor="#FFFFFF", font_color="#16171A", bordercolor="#E4E6E9"),
    )
    fig.update_yaxes(
        gridcolor=LINE, zerolinecolor="rgba(138, 144, 152, 0.45)", ticksuffix=" ", title=None
    )
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
            fillcolor="rgba(255,95,0,0.10)",
            hovertemplate="%{x|%a %d %b, %H:%M}<br><b>%{y:.1f} ct/kWh</b><extra></extra>",
        )
    )
    fig.update_xaxes(tickformat="%a %d", dtick=24 * 3600 * 1000)
    fig.update_yaxes(ticksuffix=" ct")
    return _layout(fig)


def daily_range(daily: pd.DataFrame) -> go.Figure:
    """Daily min-max as a band, daily average as a line. Columns: day, min, mean, max (ct)."""
    band = go.Bar(
        x=daily["day"],
        y=daily["max"] - daily["min"],
        base=daily["min"],
        customdata=daily["max"],
        marker_color=ORANGE_SOFT_STRONG,
        marker_line_width=0,
        hovertemplate="%{x|%a %d %b}<br>%{base:.1f}–%{customdata:.1f} ct/kWh<extra></extra>",
    )
    avg = go.Scatter(
        x=daily["day"],
        y=daily["mean"],
        mode="lines+markers",
        line=dict(color=ORANGE, width=2),
        marker=dict(size=5),
        hovertemplate="average <b>%{y:.1f} ct/kWh</b><extra></extra>",
    )
    fig = go.Figure([band, avg])
    fig.update_yaxes(ticksuffix=" ct")
    return _layout(fig)


def hour_profile(profile: pd.DataFrame) -> go.Figure:
    """Average price per local hour, workdays against weekends. Columns: hour, workday, weekend."""
    fig = go.Figure()
    for col, color, name in [("workday", ORANGE, "Mon–Fri"), ("weekend", PEAK, "Sat–Sun")]:
        fig.add_trace(
            go.Scatter(
                x=profile["hour"],
                y=profile[col],
                name=name,
                mode="lines",
                line=dict(color=color, width=2.2, shape="spline"),
                hovertemplate=f"{name}, %{{x}}:00<br><b>%{{y:.1f}} ct/kWh</b><extra></extra>",
            )
        )
    _layout(fig)
    fig.update_layout(showlegend=True, legend=dict(orientation="h", y=1.08, x=0))
    fig.update_xaxes(
        tickvals=list(range(0, 24, 3)), ticktext=[f"{h:02d}:00" for h in range(0, 24, 3)]
    )
    return fig


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
