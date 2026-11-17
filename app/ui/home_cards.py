"""Cards only a home's dashboard shows. The numbers come from app/data.py (load_forecast:
offpeak/forecast/load_model.py); this file only draws them."""

import pandas as pd
import streamlit as st

from ui.components import card_title


def consumption_forecast(forecast: pd.DataFrame | None, learned_days: int = 0) -> None:
    """The home's consumption for the next 7 days: kWh per day as bars, the evening peak."""
    with st.container(border=True, key="card_home_forecast"):
        card_title(
            "Your consumption, the next 7 days",
            "Offpeak Intelligence, trained on this home's own measurements only",
        )
        if forecast is None:
            st.caption(
                "Needs four weeks of measurements. Add them under Setup → My data "
                "(from Fronius Solar.web)."
            )
            return
        daily = forecast.groupby("day")["kw"].sum()  # kW per hour summed = kWh per day
        top = float(daily.max()) or 1.0
        bars = "".join(
            f"<div class='d'><div class='b' style='height:{max(6, 100 * v / top):.0f}%'></div>"
            f"<b>{v:.1f}</b><span>{pd.Timestamp(day):%a}</span></div>"
            for day, v in daily.items()
        )
        peak = forecast.groupby("hour")["kw"].mean().idxmax()
        st.html(
            "<style>.lf{display:flex;gap:10px;align-items:flex-end;height:150px;padding:8px 2px}"
            ".lf .d{flex:1;display:flex;flex-direction:column;align-items:center;height:100%;"
            "justify-content:flex-end;font-size:.8rem;color:#8A847B}.lf .b{width:100%;"
            "border-radius:6px 6px 2px 2px;background:#FF5F00;opacity:.85}"
            ".lf b{color:#1C1B19;margin-top:4px;font-size:.85rem}</style>"
            f"<div class='lf'>{bars}</div>"
        )
        st.caption(
            f"kWh per day. About {daily.mean():.1f} kWh a day; the house uses most around "
            f"{peak:02d}:00. Learned from {learned_days:,} measured days; compared with the "
            "simple rules in a walk-forward test before it is shown."
        )
