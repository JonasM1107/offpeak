"""Dashboard: tomorrow's prices, the best windows for flexible loads, and the weather."""

from datetime import timedelta
from html import escape

import data
import pandas as pd
import streamlit as st
from ui import charts
from ui.components import (
    ORANGE,
    OTHER,
    PEAK,
    card_title,
    header,
    hhmm,
    kpi,
    legend,
    local,
    status_dot,
)

from offpeak.analysis import best_window, ct_kwh, current_price, window_mask
from offpeak.cockpit import Machine, describe_plan, week_plan
from offpeak.config import ENERGY_CHARTS_ATTRIBUTION, OPEN_METEO_ATTRIBUTION
from offpeak.markets.energy_charts import PriceSourceError
from offpeak.sites import DEMO_CITY, DEMO_SITE
from offpeak.timeutils import market_today
from offpeak.weather.codes import weather_label

now = data.now_utc()
try:
    today, tomorrow, prices_fetched, price_source = data.today_and_tomorrow()
    price_error = None
except PriceSourceError as err:  # the page still renders, with a clear message
    today = tomorrow = pd.DataFrame(columns=["ts", "eur_mwh", "resolution_min"])
    prices_fetched, price_error, price_source = None, str(err), "API"

published = not tomorrow.empty
tomorrow_date = market_today() + timedelta(days=1)

header(
    f"{DEMO_SITE.name} · {DEMO_CITY} · {DEMO_SITE.zone}",
    f"Tomorrow, {tomorrow_date:%A %-d %B}",
    live=price_error is None,
)
if price_error:
    st.warning("Prices could not be loaded right now. We try again in a few minutes.")

# ── KPI cards ────────────────────────────────────────────────────────────────
cheap3 = best_window(tomorrow, 3)
peak3 = best_window(tomorrow, 3, cheapest=False)
c1, c2, c3, c4 = st.columns(4)
with c1:
    row = current_price(today, now)
    if row is None:
        kpi("Price now", "–", note="No price for this slot")
    else:
        end = row["ts"] + timedelta(minutes=int(row["resolution_min"]))
        kpi(
            "Price now",
            f"{ct_kwh(row['eur_mwh']):.1f}",
            "ct/kWh",
            f"Slot {hhmm(row['ts'])}–{hhmm(end, True)}",
        )
with c2:
    if published:
        kpi(
            "Tomorrow average",
            f"{ct_kwh(tomorrow['eur_mwh'].mean()):.1f}",
            "ct/kWh",
            f"{len(tomorrow)} slots · checked {hhmm(prices_fetched)}",
        )
    else:
        kpi("Tomorrow average", "–", note="Waiting for prices (around 13:00 CET)")
with c3:
    if cheap3:
        kpi(
            "Cheapest 3-hour window",
            f"{hhmm(cheap3.start)}–{hhmm(cheap3.end, True)}",
            note=f"Avg {ct_kwh(cheap3.avg_eur_mwh):.1f} ct/kWh",
        )
    else:
        kpi("Cheapest 3-hour window", "–", note="Available once prices are out")
with c4:
    if published:
        low, high = ct_kwh(tomorrow["eur_mwh"].min()), ct_kwh(tomorrow["eur_mwh"].max())
        kpi(
            "Price spread tomorrow",
            f"{high - low:.1f}",
            "ct/kWh",
            f"From {low:.1f} to {high:.1f} ct/kWh",
            accent=True,
        )
    else:
        kpi("Price spread tomorrow", "–", note="Available once prices are out", accent=True)

st.write("")

# ── The plan for the coming days (filled in at the end: the forecast behind it takes about
# half a minute once a day, and the rest of the page should not wait for it) ───────────────
plan_box = st.empty()
with plan_box.container(border=True, key="card_plan_wait"):
    card_title("Your plan for the coming days", "When each machine should run")
    st.caption("Working out the plan…")

st.write("")

# ── Price chart and best windows ─────────────────────────────────────────────
left, right = st.columns([2.1, 1], gap="medium")
with left, st.container(border=True, key="card_prices"):
    head, toggle = st.columns([1.3, 1], vertical_alignment="center")
    with toggle:
        view = st.segmented_control(
            "View",
            ["Tomorrow", "Today", "7 days"],
            default="Tomorrow",
            label_visibility="collapsed",
            key="price_view",
        )
    view = view or "Tomorrow"
    with head:
        card_title(f"Day-ahead price, {view.lower()}", f"15-minute slots, ct/kWh, {DEMO_SITE.zone}")

    if view == "7 days":
        week, _, _ = data.prices(tomorrow_date - timedelta(days=6), tomorrow_date)
        st.plotly_chart(charts.price_line(week), config=charts.CONFIG)
        st.caption(
            "Seven market days up to tomorrow. Tomorrow appears once published (around 13:00 CET)."
        )
    else:
        shown = tomorrow if view == "Tomorrow" else today
        if shown.empty:
            st.info("Waiting for tomorrow's prices. They are published around 13:00 CET.")
        else:
            cheap, peak = best_window(shown, 3), best_window(shown, 3, cheapest=False)
            fig = charts.price_bars(
                shown,
                window_mask(shown, cheap),
                window_mask(shown, peak),
                now=now if view == "Today" else None,
            )
            st.plotly_chart(fig, config=charts.CONFIG)
            legend(
                [
                    ("Cheapest 3 hours", ORANGE),
                    ("Most expensive 3 hours", PEAK),
                    ("Other slots", OTHER),
                ]
            )

with right, st.container(border=True, key="card_windows"):
    card_title("Best time for flexible loads", "Cheapest block tomorrow, by run time")
    if not published:
        st.caption("Shown once tomorrow's prices are published (around 13:00 CET).")
    else:
        rows = []
        for hours in (1, 2, 3, 4):
            w = best_window(tomorrow, hours)
            saving = ct_kwh(peak3.avg_eur_mwh - w.avg_eur_mwh) if peak3 else 0
            rows.append(
                f'<div class="op-row"><div><div class="name">{hours}-hour job</div>'
                f'<div class="meta">avg {ct_kwh(w.avg_eur_mwh):.1f} ct/kWh · '
                f"{saving:.1f} ct below peak</div></div>"
                f'<span class="op-chip">{hhmm(w.start)}–{hhmm(w.end, True)}</span></div>'
            )
        if peak3:
            rows.append(
                f'<div class="op-row"><div><div class="name">Avoid</div><div class="meta">'
                f"peak 3 hours, avg {ct_kwh(peak3.avg_eur_mwh):.1f} ct/kWh</div></div>"
                f'<span class="op-chip grey">{hhmm(peak3.start)}–{hhmm(peak3.end, True)}</span>'
                "</div>"
            )
        st.html("".join(rows))
        st.caption("Your machines' plan for the whole week is at the top of this page.")

st.write("")

# ── Weather and data sources ─────────────────────────────────────────────────
weather, weather_fetched, weather_error, weather_source = data.weather()
left, right = st.columns([2.1, 1], gap="medium")
with left, st.container(border=True, key="card_weather"):
    card_title("Weather, next 24 hours", f"{DEMO_CITY} · DWD ICON via Open-Meteo")
    if weather is None:
        st.info("The weather forecast is not available right now. We try again within the hour.")
    else:
        hours = weather[weather["ts"].dt.minute == 0]
        nxt = hours[
            (hours["ts"] >= now.floor("h")) & (hours["ts"] < now.floor("h") + timedelta(hours=24))
        ]
        tiles = nxt.iloc[::3]
        sun = nxt["gti_wm2"].max() or 1
        best = tiles["gti_wm2"].idxmax() if tiles["gti_wm2"].max() > 0 else None
        html = []
        for idx, t in tiles.iterrows():
            share = 0 if pd.isna(t["gti_wm2"]) else min(100, round(100 * t["gti_wm2"] / sun))
            temp = "–" if pd.isna(t["temp_c"]) else f"{t['temp_c']:.0f}°"
            html.append(
                f'<div class="op-tile{" sunny" if idx == best else ""}">'
                f'<div class="t">{local(t["ts"]):%H:%M}</div><div class="temp">{temp}</div>'
                f'<div class="cond">{escape(weather_label(t["weather_code"]))}</div>'
                f'<div class="op-bar"><span style="width:{share}%"></span></div></div>'
            )
        st.html(f'<div class="op-tiles">{"".join(html)}</div>')
        st.html(
            '<div class="op-foot">Orange bar = sunshine on a 30° south-facing panel, '
            "relative to the next 24 hours' maximum.</div>"
        )

with right, st.container(border=True, key="card_sources"):
    card_title("Data sources")
    price_note = f"{hhmm(prices_fetched)} via {price_source}" if prices_fetched else "unavailable"
    weather_note = (
        "unavailable" if weather is None else f"{hhmm(weather_fetched)} via {weather_source}"
    )
    database = "connected" if data.engine() is not None else "not set up"
    st.html(
        f'<div class="op-row"><div><div class="name">Energy-Charts</div>'
        f'<div class="meta">Day-ahead prices {DEMO_SITE.zone}</div></div>'
        f'<span class="meta">{status_dot(price_error is None)}{price_note}</span></div>'
        f'<div class="op-row"><div><div class="name">Open-Meteo</div>'
        f'<div class="meta">Weather and irradiance</div></div>'
        f'<span class="meta">{status_dot(weather is not None)}{weather_note}</span></div>'
        f'<div class="op-row"><div><div class="name">Database</div>'
        f'<div class="meta">Supabase, filled by scheduled jobs</div></div>'
        f'<span class="meta">{status_dot(database == "connected")}{database}</span></div>'
        f'<div class="op-foot">{OPEN_METEO_ATTRIBUTION} · {ENERGY_CHARTS_ATTRIBUTION}</div>'
    )


# ── Fill in the plan ─────────────────────────────────────────────────────────


def eur(x: float) -> str:
    return f"€{x:,.2f}"


ahead = data.hours_ahead()
machines, _, _ = data.machines_to_plan()
with plan_box.container(border=True, key="card_plan"):
    if ahead is None:
        card_title("Your plan for the coming days", "When each machine should run")
        st.caption("Prices or the weather forecast could not be loaded right now.")
    elif not machines:
        card_title("Your plan for the coming days", "When each machine should run")
        st.caption("No machines set up yet. Add them in the Simulation cockpit.")
    else:
        hours, now_index = ahead
        fleet = [Machine(**m) for m in machines]
        plan = describe_plan(hours, week_plan(hours, fleet, now_index), fleet)
        head, link = st.columns([3, 1], vertical_alignment="center")
        with head:
            card_title(
                f"This week: run your machines at these times and save about {eur(plan['total'])}",
                f"Compared with their usual start times · {plan['compared']} of {len(fleet)} "
                "machines have one · later days use Offpeak Intelligence",
            )
        with link:
            st.page_link("views/cockpit.py", label="Adjust in the cockpit", icon=":material/tune:")
        rows = []
        for r in plan["rows"]:
            if r["when"] is None:
                rows.append(
                    f'<div class="op-row"><div><div class="name">{escape(r["name"])}</div>'
                    '<div class="meta">Does not fit its allowed hours in the coming days</div>'
                    '</div><span class="op-chip grey">–</span></div>'
                )
                continue
            meta = f"{eur(r['cost'])} per run"
            if r["usual"]:
                meta += f" · usually {r['usual']}"
            if r["forecast"]:
                meta += " · Offpeak Intelligence price"
            chip = (
                f'<span class="op-chip">saves {eur(r["saving"])}</span>'
                if r["saving"] is not None and r["saving"] > 0.005
                else '<span class="op-chip grey">usual time is best</span>'
                if r["saving"] is not None
                else '<span class="op-chip grey">no usual time</span>'
            )
            rows.append(
                f'<div class="op-row"><div><div class="name">{escape(r["name"])} · '
                f"{r['when']}</div>"
                f'<div class="meta">{meta}</div></div>{chip}</div>'
            )
        st.html("".join(rows))
