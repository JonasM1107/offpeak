"""Tariff calculator: what a kWh really costs the demo site, and which tariff is cheaper."""

from html import escape

import data
import pandas as pd
import streamlit as st
from ui import charts
from ui.components import card_title, header, kpi, legend

from offpeak import demo_site
from offpeak.markets.energy_charts import PriceSourceError
from offpeak.sites import DEMO_CITY, DEMO_SITE
from offpeak.tariffs import germany_2026, portugal_bte_2026, slot_prices
from offpeak.timeutils import market_today

today = market_today()
title = st.empty()  # filled once the tariff and data source are known

with st.container(border=True, key="card_tariff_inputs"):
    card_title("Your tariff", "Change the settings to match a contract; everything below updates")
    c1, c2, c3, c4 = st.columns([1.25, 1.1, 1.5, 1.2], gap="medium")
    country = c1.segmented_control(
        "Market", ["Germany", "Portugal"], default="Germany", key="tariff_country"
    )
    country = country or "Germany"
    if country == "Germany":
        voltage = c2.segmented_control("Voltage level", ["Low", "Medium"], default="Low")
        metered = c3.toggle(
            "Load-profile meter (RLM)", value=True, help="Sites using over 100,000 kWh a year"
        )
        high_use = c3.toggle(
            "2,500+ full-load hours",
            value=True,
            help="Yearly kWh ÷ peak kW. Decides which grid price list applies.",
        )
        reduced_tax = c3.toggle(
            "Manufacturing or farming",
            value=False,
            help="Electricity tax 0.05 instead of 2.05 ct/kWh from 2026, on application",
        )
        margin = c4.number_input("Supplier margin, ct/kWh", 0.0, 10.0, 1.5, 0.1)
        fixed_ct = c4.number_input("Fixed offer, energy ct/kWh", 0.0, 60.0, 14.0, 0.5)

        def make(kind):
            return germany_2026(
                kind=kind,
                voltage="medium" if voltage == "Medium" else "low",
                load_metered=metered,
                high_utilisation=high_use,
                reduced_electricity_tax=reduced_tax,
                supplier_margin_ct=margin,
                fixed_energy_ct=fixed_ct,
                pv_kwp=demo_site.ASSETS.pv_kwp,
            )
    else:
        margin = c2.number_input("Supplier margin, ct/kWh", 0.0, 10.0, 0.8, 0.1)
        loss = c3.number_input(
            "Loss factor, %", 0.0, 30.0, 8.0, 0.5, help="Indexed contracts add grid losses"
        )
        fixed_ct = c4.number_input("Fixed offer, energy ct/kWh", 0.0, 60.0, 11.0, 0.5)

        def make(kind):
            return portugal_bte_2026(
                kind=kind,
                supplier_margin_ct=margin,
                loss_factor=loss / 100,
                fixed_energy_ct=fixed_ct,
            )


dynamic, fixed = make("dynamic"), make("fixed")

# Prices: Germany live, Portugal from the demo curve until the OMIE adapter exists
today_prices = None
if country == "Germany":
    try:
        today_prices, _, _, _ = data.today_and_tomorrow()
    except PriceSourceError:
        today_prices = None
weather, _, _, _ = data.weather()
base = demo_site.hourly_inputs(today_prices, weather, dynamic.tz)
live = bool(base["price_real"].all())

inputs = demo_site.apply_tariff(base, dynamic, today)
plan = demo_site.plan_day(inputs, dynamic)
bills = {
    "Usual times · dynamic": demo_site.day_bill(inputs, demo_site.USUAL, dynamic),
    "Offpeak plan · dynamic": demo_site.day_bill(inputs, plan, dynamic),
    "Usual times · fixed price": demo_site.day_bill(
        demo_site.apply_tariff(base, fixed, today), demo_site.USUAL, fixed
    ),
}

if today_prices is not None and not today_prices.empty:
    slots = slot_prices(today_prices, dynamic)  # 15-minute detail for the chart
else:  # hourly demo curve
    slots = slot_prices(
        pd.DataFrame({"ts": inputs["ts"], "eur_mwh": inputs["price_ct"] * 10}), dynamic
    )

with title.container():
    where = DEMO_CITY if country == "Germany" else "priced as if in Portugal"
    header(f"{DEMO_SITE.name} · {where} · {dynamic.name}", "Tariff calculator", live=live)
if not live:
    st.info(
        "Live prices for this market are not connected yet (the OMIE adapter comes next), so "
        "the page uses Offpeak's demo price curve. The tariff maths is the same."
    )

best = bills["Offpeak plan · dynamic"]
spot_share = (slots["energy_ct"] / slots["import_ct"]).clip(lower=0).mean()
cheap, dear = slots.loc[slots["import_ct"].idxmin()], slots.loc[slots["import_ct"].idxmax()]
local = slots["ts"].dt.tz_convert(dynamic.tz)
k1, k2, k3, k4 = st.columns(4)
with k1:
    kpi(
        "Your average price today",
        f"{best.ct_per_kwh:.1f}",
        "ct/kWh",
        "All-in per kWh bought, with the Offpeak plan",
        accent=True,
    )
with k2:
    kpi("Spot price share", f"{spot_share:.0%}", note="The rest is grid fees, levies and tax")
with k3:
    kpi(
        "Cheapest slot",
        f"{cheap['import_ct']:.1f}",
        "ct/kWh",
        f"{local[cheap.name]:%H:%M}, spot {cheap['spot_ct']:.1f} ct",
    )
with k4:
    kpi(
        "Most expensive slot",
        f"{dear['import_ct']:.1f}",
        "ct/kWh",
        f"{local[dear.name]:%H:%M}, spot {dear['spot_ct']:.1f} ct",
    )

st.write("")
with st.container(border=True, key="card_tariff_stack"):
    card_title("What one kWh costs today", "Each bar is one time slot, split into its parts")
    legend([(name, color) for _, name, color in charts.PRICE_PARTS])
    st.plotly_chart(charts.price_stack(slots, dynamic.tz), config=charts.CONFIG)
    fees = (slots["import_ct"] - slots["energy_ct"]).mean()
    st.caption(
        f"Grid fees, levies and tax add about {fees:.1f} ct to every kWh, whatever the time. "
        "Only the energy part moves, so shifting a load saves the spot difference, and lowering "
        "the peak saves the demand charge."
    )

with st.container(border=True, key="card_tariff_check"):
    card_title(
        "Tariff check for the demo site today",
        "Same machines and weather; only the tariff and the run times differ",
    )
    labels = {
        "energy": "Energy",
        "grid": "Grid fees per kWh",
        "levies": "Levies",
        "tax": "Tax",
        "demand": "Demand charge, day's share",
        "fixed": "Fixed fees, day's share",
        "export": "Feed-in earnings",
    }

    def eur(v: float) -> str:
        v = round(v, 2) + 0.0  # no "-0.00"
        return f"−€{abs(v):,.2f}" if v < 0 else f"€{v:,.2f}"

    totals = {name: b.total for name, b in bills.items()}
    winner = min(totals, key=totals.get)

    def heading(name: str) -> str:
        times, kind = name.split(" · ")
        return f'{escape(times)}<br><span class="kind">{escape(kind)}</span>'

    head = "".join(f'<th class="{"win" if n == winner else ""}">{heading(n)}</th>' for n in bills)
    body = "".join(
        f"<tr><td>{escape(label)}</td>"
        + "".join(f"<td>{eur(b.lines[key])}</td>" for b in bills.values())
        + "</tr>"
        for key, label in labels.items()
    )
    body += (
        "<tr class='total'><td>Total</td>"
        + "".join(
            f'<td class="{"win" if n == winner else ""}">{eur(b.total)}</td>'
            for n, b in bills.items()
        )
        + "</tr>"
    )
    body += "<tr><td>Peak</td>" + "".join(f"<td>{b.peak_kw:.0f} kW</td>" for b in bills.values())
    body += "</tr><tr><td>Average per kWh bought</td>" + "".join(
        f"<td>{b.ct_per_kwh:.1f} ct</td>" for b in bills.values()
    )
    st.html(
        "<style>.op-table{width:100%;border-collapse:collapse;font-size:.9rem}"
        ".op-table th,.op-table td{padding:9px 10px;border-bottom:1px solid #E7E4DE;"
        "text-align:right;white-space:nowrap}.op-table th:first-child,.op-table td:first-child"
        "{text-align:left;color:#6F6A62;white-space:normal}.op-table th{font-weight:600;"
        "font-size:.82rem;color:#1C1B19}.op-table tr.total td{font-weight:700;color:#1C1B19}"
        ".op-table .win{color:#E8590C}.op-table th .kind{font-weight:500;color:#6F6A62}"
        ".op-table th{white-space:normal;vertical-align:bottom}.op-wrap{overflow-x:auto}"
        "@media (max-width:640px){.op-table{font-size:.76rem}"
        ".op-table th,.op-table td{padding:7px 3px}}</style>"
        f'<div class="op-wrap"><table class="op-table"><tr><th></th>{head}</tr>{body}</tr>'
        "</table></div>"
    )
    vs_fixed = totals["Usual times · fixed price"] - totals["Offpeak plan · dynamic"]
    vs_usual = totals["Usual times · dynamic"] - totals["Offpeak plan · dynamic"]
    st.caption(
        f"Cheapest today: {winner}. The Offpeak plan saves {eur(vs_usual)} against the usual "
        f"run times and {'saves' if vs_fixed >= 0 else 'costs'} {eur(abs(vs_fixed))} against "
        "the fixed offer. One day says little; compare over a month before switching."
    )

with st.container(border=True, key="card_tariff_parts"):
    card_title("Price components", f"Net of VAT ({dynamic.vat:.0%}, deductible for businesses)")
    rows = []
    for c in dynamic.charges:
        value = (
            " / ".join(f"{v:.2f}" for v in c.by_period.values()) + " ct/kWh"
            if c.by_period
            else f"{c.ct_kwh:.3f} ct/kWh"
        )
        rows.append((c.name, value, c.source))
    rows += [(d.name, f"{d.eur_per_kw_year:,.2f} €/kW/year", d.source) for d in dynamic.demand]
    rows += [(f.name, f"{f.eur_year:,.2f} €/year", f.source) for f in dynamic.fixed]
    if dynamic.export.kind == "fixed":
        rows.append(
            ("Feed-in payment", f"{dynamic.export.ct_kwh:.2f} ct/kWh", dynamic.export.source)
        )
    elif dynamic.export.kind == "spot":
        rows.append(
            ("Feed-in payment", f"{dynamic.export.spot_share:.0%} of spot", dynamic.export.source)
        )
    rows.append(("Supplier margin", f"{dynamic.supplier_margin_ct:.2f} ct/kWh", "Your setting"))

    def link(src: str) -> str:
        if src.startswith("http"):
            return f'<a href="{escape(src)}" target="_blank">Source</a>'
        return escape(src)

    st.html(
        '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));'
        'column-gap:32px">'
        + "".join(
            f'<div class="op-row"><div><div class="name">{escape(n)}</div>'
            f'<div class="meta">{link(src)}</div></div>'
            f'<span class="op-chip grey">{escape(v)}</span></div>'
            for n, v, src in rows
        )
        + "</div>"
    )
    st.caption(" ".join(dynamic.notes))
