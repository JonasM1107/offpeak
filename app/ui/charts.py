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


def solar_hours(ts: pd.Series, kw: pd.Series) -> go.Figure:
    """Expected solar power over several days, as a filled area."""
    fig = go.Figure(
        go.Scatter(
            x=ts.dt.tz_convert(TZ),
            y=kw,
            mode="lines",
            line=dict(color=ORANGE, width=1.4),
            fill="tozeroy",
            fillcolor="rgba(232,89,12,0.15)",
            hovertemplate="%{x|%a %d %b, %H:%M}<br><b>%{y:.1f} kW</b><extra></extra>",
        )
    )
    fig.update_xaxes(tickformat="%a %d", dtick=24 * 3600 * 1000)
    fig.update_yaxes(ticksuffix=" kW", rangemode="tozero")
    return _layout(fig, height=260)


def temp_wind(weather: pd.DataFrame) -> go.Figure:
    """Temperature (left axis) and wind speed (right axis), hourly."""
    hours = weather[weather["ts"].dt.minute == 0]
    x = hours["ts"].dt.tz_convert(TZ)
    temp = go.Scatter(
        x=x,
        y=hours["temp_c"],
        name="Temperature",
        mode="lines",
        line=dict(color=ORANGE, width=2, shape="spline"),
        hovertemplate="%{x|%a %H:%M}<br><b>%{y:.0f} °C</b><extra></extra>",
    )
    wind = go.Scatter(
        x=x,
        y=hours["wind_ms"],
        name="Wind",
        yaxis="y2",
        mode="lines",
        line=dict(color=PEAK, width=1.4, dash="dot"),
        hovertemplate="%{x|%a %H:%M}<br><b>%{y:.1f} m/s</b><extra></extra>",
    )
    fig = _layout(go.Figure([temp, wind]), height=260)
    fig.update_layout(
        showlegend=True,
        legend=dict(orientation="h", y=1.1, x=0),
        yaxis=dict(ticksuffix=" °C"),
        yaxis2=dict(
            overlaying="y", side="right", showgrid=False, ticksuffix=" m/s", tickformat=".0f"
        ),
    )
    fig.update_xaxes(tickformat="%a %d", dtick=24 * 3600 * 1000)
    return fig


def _price_bars_hourly(joined: pd.DataFrame) -> go.Bar:
    return go.Bar(
        x=joined["ts"].dt.tz_convert(TZ),
        y=joined["ct_kwh"],
        name="Price",
        marker_color=OTHER,
        marker_line_width=0,
        hovertemplate="%{x|%a %H:%M}<br><b>%{y:.1f} ct/kWh</b><extra></extra>",
    )


def price_and_wind(joined: pd.DataFrame | None, drivers: pd.DataFrame) -> go.Figure:
    """Hourly price as bars (left axis) and wind in northern Germany as a line (right axis).
    The wind line runs on past the last published price, into the forecast. Without prices
    (joined is None) only the wind is drawn."""
    traces = []
    if joined is not None:
        traces.append(_price_bars_hourly(joined))
    wind = go.Scatter(
        x=drivers["ts"].dt.tz_convert(TZ),
        y=drivers["wind_north_ms"],
        name="Wind, north Germany",
        yaxis="y2",
        mode="lines",
        line=dict(color=ORANGE, width=2.2, shape="spline"),
        hovertemplate="%{x|%a %H:%M}<br><b>%{y:.1f} m/s</b><extra></extra>",
    )
    traces.append(wind)
    fig = _layout(go.Figure(traces), height=300)
    fig.update_layout(
        showlegend=True,
        legend=dict(orientation="h", y=1.1, x=0),
        bargap=0.1,
        yaxis=dict(ticksuffix=" ct"),
        yaxis2=dict(
            overlaying="y",
            side="right",
            showgrid=False,
            ticksuffix=" m/s",
            tickformat=".0f",
            rangemode="tozero",
        ),
    )
    fig.update_xaxes(tickformat="%a %d", dtick=24 * 3600 * 1000)
    return fig


def wind_bands(bands: pd.DataFrame) -> go.Figure:
    """Average price in calm, moderate and windy hours. Columns: band, hours, ct_kwh."""
    colour = {"calm": PEAK, "moderate": OTHER, "windy": ORANGE}
    shades = [colour[band.split(",")[0]] for band in bands["band"]]
    fig = go.Figure(
        go.Bar(
            x=bands["band"],
            y=bands["ct_kwh"],
            customdata=bands["hours"],
            marker_color=shades,
            marker_line_width=0,
            text=[f"{v:.1f} ct" for v in bands["ct_kwh"]],
            textposition="outside",
            hovertemplate="%{x}<br><b>%{y:.1f} ct/kWh</b> over %{customdata} hours<extra></extra>",
        )
    )
    fig.update_yaxes(ticksuffix=" ct", rangemode="tozero")
    return _layout(fig, height=300)
