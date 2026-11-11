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


WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def weekday_heatmap(table: pd.DataFrame) -> go.Figure:
    """Average price per weekday and hour. Light = cheap, orange = expensive."""
    fig = go.Figure(
        go.Heatmap(
            z=table.values,
            x=[f"{h:02d}" for h in table.columns],
            y=WEEKDAYS,
            colorscale=[[0, "rgba(138, 144, 152, 0.14)"], [0.45, ORANGE_SOFT_STRONG], [1, ORANGE]],
            xgap=2,
            ygap=2,
            colorbar=dict(title=dict(text="ct", side="top"), thickness=10, len=0.9, outlinewidth=0),
            hovertemplate="%{y} %{x}:00<br><b>%{z:.1f} ct/kWh</b><extra></extra>",
        )
    )
    _layout(fig, height=300)
    fig.update_yaxes(autorange="reversed", gridcolor="rgba(0,0,0,0)", ticksuffix="")
    fig.update_xaxes(dtick=3)
    return fig


def monthly_overview(months: pd.DataFrame) -> go.Figure:
    """Bars: average price per month. Line: hours with a negative price that month."""
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=months["month"],
            y=months["mean"],
            name="Average price",
            marker_color=ORANGE_SOFT_STRONG,
            marker_line_width=0,
            customdata=months["spread"],
            hovertemplate="%{x|%b %Y}<br>avg <b>%{y:.1f} ct/kWh</b>"
            "<br>daily spread %{customdata:.1f} ct<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=months["month"],
            y=months["negative_hours"],
            name="Hours below zero",
            yaxis="y2",
            mode="lines+markers",
            line=dict(color=INK, width=1.8),
            marker=dict(size=5),
            hovertemplate="%{x|%b %Y}<br><b>%{y} hours</b> below zero<extra></extra>",
        )
    )
    _layout(fig)
    fig.update_layout(
        showlegend=True,
        legend=dict(orientation="h", y=1.1, x=0),
        yaxis2=dict(
            overlaying="y",
            side="right",
            showgrid=False,
            rangemode="tozero",
            title=None,
            ticksuffix=" h",
            tickformat="d",
        ),
    )
    fig.update_yaxes(ticksuffix=" ct", selector=dict(anchor="x"))
    fig.update_xaxes(tickformat="%b %y")
    return fig


def generation_week(gen: pd.DataFrame, tz: str = TZ) -> go.Figure:
    """Expected solar (orange) and wind (dark) power, stacked, for the coming days."""
    x = gen["ts"].dt.tz_convert(tz)
    fig = go.Figure()
    for col, color, fill, name in [
        ("wind_kw", PEAK, "rgba(74,70,64,0.18)", "Wind"),
        ("pv_kw", ORANGE, "rgba(232,89,12,0.22)", "Solar"),
    ]:
        fig.add_trace(
            go.Scatter(
                x=x,
                y=gen[col],
                name=name,
                stackgroup="gen",
                mode="lines",
                line=dict(color=color, width=1.4),
                fillcolor=fill,
                hovertemplate=f"{name} %{{x|%a %H:%M}}<br><b>%{{y:.0f}} kW</b><extra></extra>",
            )
        )
    _layout(fig, height=300)
    fig.update_layout(showlegend=True, legend=dict(orientation="h", y=1.1, x=0))
    fig.update_yaxes(ticksuffix=" kW")
    fig.update_xaxes(tickformat="%a %d", dtick=24 * 3600 * 1000)
    return fig


def forecast_vs_measured(days: pd.DataFrame) -> go.Figure:
    """Per day: solar energy the day-ahead forecast promised against what the satellite saw."""
    fig = go.Figure(
        [
            go.Bar(
                x=days["date"],
                y=days["forecast_kwh"],
                name="Forecast a day ahead",
                marker_color=ORANGE_SOFT_STRONG,
                marker_line_width=0,
                hovertemplate="%{x|%a %d %b}<br>forecast <b>%{y:.0f} kWh</b><extra></extra>",
            ),
            go.Bar(
                x=days["date"],
                y=days["measured_kwh"],
                name="Measured (satellite)",
                marker_color=ORANGE,
                marker_line_width=0,
                hovertemplate="%{x|%a %d %b}<br>measured <b>%{y:.0f} kWh</b><extra></extra>",
            ),
        ]
    )
    _layout(fig, height=280)
    fig.update_layout(showlegend=True, legend=dict(orientation="h", y=1.12, x=0), bargap=0.35)
    fig.update_yaxes(ticksuffix=" kWh")
    fig.update_xaxes(tickformat="%a %d", dtick=24 * 3600 * 1000)
    return fig
