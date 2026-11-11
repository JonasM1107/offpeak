"""Analytics: how prices behaved over the last 30 days."""

from datetime import timedelta

import data
import streamlit as st
from ui import charts
from ui.components import card_title, header, kpi

from offpeak.analysis import daily_stats, hourly_profile
from offpeak.markets.energy_charts import PriceSourceError
from offpeak.sites import DEMO_CITY, DEMO_SITE
from offpeak.timeutils import market_today

DAYS = 30
end = market_today()
try:
    prices, _ = data.prices(end - timedelta(days=DAYS - 1), end)
except PriceSourceError:
    prices = None

header(
    f"{DEMO_SITE.name} · {DEMO_CITY} · {DEMO_SITE.zone}",
    "Analytics, last 30 days",
    live=prices is not None,
)
if prices is None or prices.empty:
    st.info("Price history could not be loaded right now. We try again in a few minutes.")
    st.stop()

daily = daily_stats(prices)
profile = hourly_profile(prices)
cheapest, dearest = daily.loc[daily["mean"].idxmin()], daily.loc[daily["mean"].idxmax()]
negative_share = (prices["eur_mwh"] < 0).mean()

c1, c2, c3, c4 = st.columns(4)
with c1:
    kpi("Average price", f"{daily['mean'].mean():.1f}", "ct/kWh", f"{len(prices)} slots")
with c2:
    kpi("Cheapest day", f"{cheapest['day']:%a %-d %b}", note=f"Avg {cheapest['mean']:.1f} ct/kWh")
with c3:
    kpi(
        "Most expensive day",
        f"{dearest['day']:%a %-d %b}",
        note=f"Avg {dearest['mean']:.1f} ct/kWh",
    )
with c4:
    kpi(
        "Slots below zero",
        f"{negative_share:.0%}",
        note="Share of all 15-minute slots",
        accent=True,
    )

st.write("")
left, right = st.columns(2, gap="medium")
with left, st.container(border=True, key="card_daily"):
    card_title("Daily price range", "Band = lowest to highest slot, line = daily average")
    st.plotly_chart(charts.daily_range(daily), config=charts.CONFIG)
    st.caption(
        f"Prices ranged from {round(daily['min'].min(), 1) + 0:.1f} to "
        f"{daily['max'].max():.1f} ct/kWh over the period. "
        "The wider a day's band, the more shifting a load is worth."
    )
with right, st.container(border=True, key="card_profile"):
    card_title("Typical day", "Average price per hour, German time")
    st.plotly_chart(charts.hour_profile(profile), config=charts.CONFIG)
    low_hour = int(profile.set_index("hour")["workday"].idxmin())
    st.caption(f"On workdays the cheapest hour on average starts at {low_hour:02d}:00.")
