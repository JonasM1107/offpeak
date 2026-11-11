"""Prices: how day-ahead prices behaved, from the last 30 days up to two years.

(The file keeps its old name, analytics.py, so links and tests stay valid.)
"""

from datetime import timedelta

import data
import streamlit as st
from ui import charts
from ui.components import card_title, header, kpi

from offpeak.analysis import daily_stats, hourly_profile, monthly_stats, price_summary, weekday_hour
from offpeak.markets.energy_charts import PriceSourceError
from offpeak.sites import DEMO_SITE
from offpeak.timeutils import market_today

PERIODS = {"30 days": 30, "90 days": 90, "1 year": 365, "2 years": 730}

header(f"Day-ahead market · {DEMO_SITE.zone}", "Prices", live=True)
period = st.segmented_control(
    "Period", list(PERIODS), default="30 days", key="price_period", label_visibility="collapsed"
)
days = PERIODS[period or "30 days"]
end = market_today()
try:
    with st.spinner("Loading prices…"):
        prices, _, source = data.prices(end - timedelta(days=days - 1), end)
except PriceSourceError:
    prices = None
if prices is None or prices.empty:
    st.info("Price history could not be loaded right now. We try again in a few minutes.")
    st.stop()

s = price_summary(prices)
st.write("")
c1, c2, c3, c4 = st.columns(4)
with c1:
    kpi("Average price", f"{s['mean_ct']:.1f}", "ct/kWh", f"{s['days']} days, spot price")
with c2:
    kpi(
        "Average daily spread",
        f"{s['avg_spread_ct']:.1f}",
        "ct/kWh",
        "Dearest minus cheapest hour of a day",
    )
with c3:
    kpi(
        "Cheapest day",
        f"{s['cheapest_day']:%a %-d %b}",
        note=f"Avg {s['cheapest_day_ct']:.1f} ct · dearest {s['dearest_day']:%-d %b} "
        f"({s['dearest_day_ct']:.0f} ct)",
    )
with c4:
    kpi(
        "Hours below zero",
        f"{s['negative_hours']}",
        "h",
        f"{s['negative_hours'] / s['hours']:.1%} of all hours: paid to use power",
        accent=True,
    )

st.write("")
left, right = st.columns([1.15, 1], gap="medium")
with left, st.container(border=True, key="card_heatmap"):
    card_title("When is power cheap?", "Average price per weekday and hour, German time")
    table = weekday_hour(prices)
    st.plotly_chart(charts.weekday_heatmap(table), config=charts.CONFIG)
    cheapest = table.stack().idxmin()
    st.caption(
        f"Cheapest on average: {charts.WEEKDAYS[cheapest[0]]} at {cheapest[1]:02d}:00. "
        "Light cells are the hours to plan flexible loads into."
    )
with right, st.container(border=True, key="card_profile"):
    card_title("Typical day", "Average price per hour, workdays against weekends")
    profile = hourly_profile(prices)
    st.plotly_chart(charts.hour_profile(profile), config=charts.CONFIG)
    low_hour = int(profile.set_index("hour")["workday"].idxmin())
    high_hour = int(profile.set_index("hour")["workday"].idxmax())
    st.caption(
        f"On workdays the cheapest hour starts at {low_hour:02d}:00 and the dearest at "
        f"{high_hour:02d}:00."
    )

st.write("")
left, right = st.columns([1, 1.15], gap="medium")
with left, st.container(border=True, key="card_daily"):
    card_title("Daily price range", "Band = cheapest to dearest slot, line = daily average")
    daily = daily_stats(prices)
    st.plotly_chart(charts.daily_range(daily), config=charts.CONFIG)
    st.caption("The wider a day's band, the more moving a load to the right hour is worth.")
with right, st.container(border=True, key="card_monthly"):
    card_title("Month by month", "Average price and hours with a negative price")
    if days < 60:
        st.caption("Choose 90 days or longer to compare months.")
    else:
        months = monthly_stats(prices)
        st.plotly_chart(charts.monthly_overview(months), config=charts.CONFIG)
        st.caption(
            "Negative hours come with strong sun and wind and low demand, mostly on spring "
            "and summer weekends."
        )

st.caption(
    f"Spot prices without fees or taxes (those are on the Tariff calculator page). "
    f"Before 1 Oct 2025 the auction was hourly, after that every 15 minutes; all charts use "
    f"hourly averages. Data: Energy-Charts / Bundesnetzagentur, via {source.lower()}."
)
