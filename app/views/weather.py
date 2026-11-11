"""Weather & solar: the 7-day forecast, what the site's solar and wind will produce, and how
good yesterday's solar forecast was."""

from html import escape

import data
import pandas as pd
import streamlit as st
from ui import charts
from ui.components import card_title, header, hhmm, kpi

from offpeak import components
from offpeak.config import OPEN_METEO_ATTRIBUTION, OPEN_METEO_MODEL
from offpeak.sites import DEMO_CITY
from offpeak.timeutils import market_today
from offpeak.weather.outlook import daily_outlook, generation, solar_accuracy

TZ = "Europe/Berlin"
header(f"{DEMO_CITY} · DWD ICON via Open-Meteo", "Weather & solar", live=True)

with st.spinner("Loading the forecast…"):
    weather, fetched, error, _ = data.weather(days=7)
if weather is None or weather.empty:
    st.info("The weather forecast is not available right now. We try again within the hour.")
    st.stop()

comps, _ = data.site_components()
assets, _ = components.site_model(comps)
pv_kwp, wind_kw = assets.pv_kwp, assets.turbine_kw * assets.turbines
gen = generation(weather, pv_kwp, wind_kw)
days = daily_outlook(weather, gen, TZ)
today = market_today()
days = days[days["date"] >= today].head(7).reset_index(drop=True)

# ── Headline numbers ────────────────────────────────────────────────────────
by_date = days.set_index("date")
t0 = by_date.iloc[0]
t1 = by_date.iloc[1] if len(by_date) > 1 else t0
best_day = days.loc[days["solar_kwh"].idxmax()]
c1, c2, c3, c4 = st.columns(4)
with c1:
    kpi(
        "Solar today",
        f"{t0['solar_kwh']:.0f}",
        "kWh",
        f"{t0['sun_hours']:.0f} sunny hours · {pv_kwp:g} kWp",
    )
with c2:
    kpi(
        "Solar tomorrow",
        f"{t1['solar_kwh']:.0f}",
        "kWh",
        f"Strongest {t1['best_solar']} · {t1['label'].lower()}",
    )
with c3:
    kpi("Wind tomorrow", f"{t1['wind_kwh']:.0f}", "kWh", f"{wind_kw:g} kW of turbines")
with c4:
    kpi(
        "Sunniest day this week",
        f"{best_day['date']:%a %-d %b}",
        note=f"{best_day['solar_kwh']:.0f} kWh solar: plan big jobs there",
        accent=True,
    )

# ── Seven days ──────────────────────────────────────────────────────────────
st.write("")
with st.container(border=True, key="card_week"):
    card_title("Next 7 days", "Weather around midday, temperature range and expected own power")
    top = max(days["solar_kwh"].max(), days["wind_kwh"].max(), 1)
    cards = []
    for _, d in days.iterrows():
        name = "Today" if d["date"] == today else f"{d['date']:%a}"
        sun_w, wind_w = d["solar_kwh"] / top * 100, d["wind_kwh"] / top * 100
        cards.append(
            f'<div class="op-day{" best" if d["date"] == best_day["date"] else ""}">'
            f'<div class="t">{name} <span>{d["date"]:%-d %b}</span></div>'
            f'<div class="cond">{escape(d["label"])}</div>'
            f'<div class="temp">{d["temp_max"]:.0f}°<span> / {d["temp_min"]:.0f}°</span></div>'
            f'<div class="kv"><span>Solar</span><b>{d["solar_kwh"]:.0f} kWh</b></div>'
            f'<div class="op-bar"><span style="width:{sun_w:.0f}%"></span></div>'
            f'<div class="kv"><span>Wind</span><b>{d["wind_kwh"]:.0f} kWh</b></div>'
            f'<div class="op-bar dark"><span style="width:{wind_w:.0f}%"></span></div>'
            f'<div class="kv"><span>Best solar</span><b>{d["best_solar"]}</b></div></div>'
        )
    st.html(f'<div class="op-days">{"".join(cards)}</div>')

st.write("")
with st.container(border=True, key="card_generation"):
    card_title(
        "Expected own power, hour by hour",
        f"All solar ({pv_kwp:g} kWp) and wind ({wind_kw:g} kW) on the site, stacked",
    )
    week = gen[gen["ts"] >= pd.Timestamp(today, tz=TZ).tz_convert("UTC")]
    st.plotly_chart(charts.generation_week(week), config=charts.CONFIG)
    st.caption(
        "Solar: irradiance on the panels × kWp × 0.85 for losses. Wind: a generic small-turbine "
        "power curve with the forecast wind scaled to hub height. Two days ahead the DWD runs its "
        "detailed 2 km model; further out the forecast gets coarser."
    )

# ── How good was the solar forecast? ───────────────────────────────────────
st.write("")
check = data.solar_check(7)
with st.container(border=True, key="card_accuracy"):
    card_title(
        "How good is the solar forecast?",
        "What the forecast said one day ahead, against satellite measurements",
    )
    if check is None or check.empty:
        st.caption("The comparison is not available right now.")
    else:
        past, summary = solar_accuracy(check, pv_kwp, TZ)
        left, right = st.columns([2.2, 1], gap="medium")
        with left:
            st.plotly_chart(charts.forecast_vs_measured(past), config=charts.CONFIG)
        with right:
            direction = "too much" if summary["bias_pct"] > 0 else "too little"
            st.html(
                f'<div class="op-row"><span class="meta">Days compared</span>'
                f"<b>{summary['days']}</b></div>"
                f'<div class="op-row"><span class="meta">Average daily error</span>'
                f"<b>{summary['mae_kwh']:.0f} kWh · {summary['mae_pct']:.0f} %</b></div>"
                f'<div class="op-row"><span class="meta">On balance the forecast promised</span>'
                f"<b>{abs(summary['bias_pct']):.0f} % {direction}</b></div>"
            )
            worst = past.loc[past["error_pct"].abs().idxmax()]
            st.caption(
                f"The biggest miss was {worst['date']:%a %-d %b} ({worst['error_pct']:+.0f} %). "
                "This is why the plan keeps a margin and the dashboard shows the latest forecast."
            )

st.caption(
    f"{OPEN_METEO_ATTRIBUTION}: forecast model {OPEN_METEO_MODEL}, earlier model runs and "
    f"satellite radiation. Forecast from {fetched:%-d %b}, {hhmm(fetched)} German time."
)
