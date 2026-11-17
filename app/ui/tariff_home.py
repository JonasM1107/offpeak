"""The tariff calculator for a home: fixed, dynamic, or dynamic with the § 14a time-variable
grid fee. The numbers come from offpeak/home_tariffs.py; this file only draws them."""

from html import escape

import data
import streamlit as st

from offpeak import components, demo_site, home_tariffs
from offpeak.config import MARKET_TZ
from offpeak.markets.energy_charts import PriceSourceError
from offpeak.sites import DEMO_CITY
from offpeak.tariffs.defaults import RHEINNETZ_MODULE3_CT
from offpeak.timeutils import market_today
from ui.components import card_title, header, kpi

NEEDS = " · needs a heat pump or wallbox"


def eur(v: float) -> str:
    return f"−€{abs(v):,.2f}" if v < 0 else f"€{v:,.2f}"


def show() -> None:
    try:
        today_prices, _, _, _ = data.today_and_tomorrow()
    except PriceSourceError:
        today_prices = None  # the day falls back to the demo price curve
    header(
        f"{data.site().name} · {DEMO_CITY} · household tariffs 2026",
        "Tariff calculator",
        live=today_prices is not None and not today_prices.empty,
    )
    weather, _, _, _ = data.weather()
    comps, _ = data.site_components()
    assets, _ = components.site_model(comps)
    base = demo_site.hourly_inputs(today_prices, weather, MARKET_TZ, assets)
    rows = home_tariffs.options(base, comps, market_today())
    best, fixed = rows[0], next(r for r in rows if r["key"] == "fixed")

    k1, k2, k3 = st.columns(3)
    with k1:
        kpi("Cheapest for your home today", best["name"], note=best["plan"], accent=True)
    with k2:
        kpi(
            "Saved vs fixed price, today",
            eur(fixed["eur_day"] - best["eur_day"]),
            note="same day, same weather",
        )
    with k3:
        kpi(
            "Roughly per year",
            eur((fixed["eur_day"] - best["eur_day"]) * 365),
            note="one day × 365: a rough guide",
        )

    with st.container(border=True, key="card_home_tariffs"):
        card_title(
            "Fixed, dynamic, or dynamic with § 14a",
            "Today's bill for your home, including VAT and the day's share of base price and meter",
        )
        cells = "".join(
            f"<tr class='{'' if r['available'] else 'off'}'><td><b>{escape(r['name'])}</b>"
            f"<br><small>{escape(r['plan'])}{'' if r['available'] else NEEDS}</small></td>"
            f"<td class='n'>{eur(r['eur_day'])}</td><td class='n'>{eur(r['eur_year'])}</td></tr>"
            for r in rows
        )
        st.html(
            "<style>.ht{width:100%;border-collapse:collapse;font-size:.95rem}"
            ".ht td{padding:10px 8px;border-bottom:1px solid #EEE9E2}.ht .n{text-align:right;"
            "font-variant-numeric:tabular-nums}.ht tr.off{opacity:.45}.ht th{text-align:left;"
            "color:#8A847B;font-weight:500;padding:6px 8px}.ht th.n{text-align:right}</style>"
            "<table class='ht'><tr><th>Tariff</th><th class='n'>Today</th>"
            f"<th class='n'>× 365</th></tr>{cells}</table>"
        )
        st.caption(
            "Negative means the solar power you sell earns more than the power you buy costs. "
            "A dynamic tariff needs a smart meter (price cap about 30 € a year); § 14a also a "
            "control box (about 50 € a year) and gives a flat reduction of 95.58 € a year."
        )

    with st.container(border=True, key="card_module3"):
        card_title(
            "§ 14a time-variable grid fee (Modul 3, RheinNetz 2026)",
            "For homes with a heat pump or wallbox that the grid operator may dim when it is full",
        )
        nt, st_, ht = (RHEINNETZ_MODULE3_CT[k] * 1.19 for k in ("NT", "ST", "HT"))
        c1, c2, c3 = st.columns(3)
        with c1:
            kpi("Low (NT) · 23:45–05:45", f"{nt:.2f}", "ct/kWh", note="grid fee incl. VAT")
        with c2:
            kpi(
                "Standard (ST) · rest of the day", f"{st_:.2f}", "ct/kWh", note="grid fee incl. VAT"
            )
        with c3:
            kpi("High (HT) · 17:00–19:30", f"{ht:.2f}", "ct/kWh", note="grid fee incl. VAT")
        st.caption(
            "Charging the car or running the heat pump at night saves on the grid fee on top of "
            "cheaper spot prices; Offpeak's plan already avoids the evening high window. "
            "Source: RheinNetz price sheet 2026, Preisblatt 3."
        )
