"""Data & status: where the data comes from, how fresh it is, and the scheduled jobs."""

from datetime import UTC, datetime

import data
import pandas as pd
import streamlit as st
from ui.components import card_title, header, kpi, local, status_dot

from offpeak.config import ENERGY_CHARTS_ATTRIBUTION, OPEN_METEO_ATTRIBUTION, OPEN_METEO_MODEL
from offpeak.timeutils import market_today

TZ = "Europe/Berlin"
header("Setup", "Data & status", live=True)
s = data.data_status()


def ago(ts) -> str:
    """'12 min ago', '3 h ago' or a date, for a UTC timestamp."""
    if ts is None or pd.isna(ts):
        return "never"
    minutes = (datetime.now(UTC) - pd.Timestamp(ts).to_pydatetime()).total_seconds() / 60
    if minutes < 90:
        return f"{minutes:.0f} min ago"
    if minutes < 48 * 60:
        return f"{minutes / 60:.0f} h ago"
    return f"{local(ts):%-d %b %Y}"


if s is None:
    st.info(
        "No database connected. Add DATABASE_URL to .env or the Streamlit secrets; "
        "until then every page calls the APIs directly."
    )
elif "error" in s:
    st.warning("The database could not be read right now. Pages fall back to the APIs.")
else:
    first, last = s["price_first"], s["price_last"]
    tomorrow_stored = last is not None and local(last).date() > market_today()
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        since = f"Since {local(first):%-d %b %Y}" if first else "–"
        kpi("Prices stored", f"{s['price_rows']:,}".replace(",", " "), "rows", since)
    with c2:
        until = f"{local(last):%a %-d %b}" if last else "–"
        written = f"Last written {ago(s['price_written'])}" if last else ""
        kpi("Prices up to", until, note=written)
    with c3:
        runs = f"{s['weather_runs']} forecast runs stored"
        kpi("Weather forecast", ago(s["weather_last_run"]), note=runs)
    with c4:
        kpi(
            "Tomorrow's prices",
            "stored" if tomorrow_stored else "waiting",
            note="The plan uses them" if tomorrow_stored else "Published around 13:00 CET",
            accent=True,
        )

st.write("")
left, right = st.columns([1, 1.4], gap="medium")
with left, st.container(border=True, key="card_sources"):
    card_title("Data sources", "Free sources, credited as their licences require")
    ok = s is not None and "error" not in s
    st.html(
        f'<div class="op-row"><div><div class="name">Energy-Charts</div><div class="meta">'
        f"Day-ahead prices DE-LU, 15 minutes · {ENERGY_CHARTS_ATTRIBUTION}</div></div></div>"
        f'<div class="op-row"><div><div class="name">Open-Meteo</div><div class="meta">'
        f"Weather forecast, model {OPEN_METEO_MODEL} · {OPEN_METEO_ATTRIBUTION}</div></div></div>"
        f'<div class="op-row"><div><div class="name">Supabase</div><div class="meta">'
        f"Postgres in Frankfurt, filled by the scheduled jobs</div></div>"
        f'<span class="meta">{status_dot(ok)}{"connected" if ok else "not connected"}</span></div>'
    )
with right, st.container(border=True, key="card_jobs"):
    card_title("Scheduled jobs", "Last runs of the jobs that fill the database (German time)")
    runs = data.job_runs()
    if runs is None:
        st.caption("No database connected yet.")
    elif runs.empty:
        st.caption("Connected. No job has run yet.")
    else:
        st.dataframe(
            pd.DataFrame(
                {
                    "Job": runs["job"],
                    "Started": runs["started_at"].dt.tz_convert(TZ).dt.strftime("%a %d %b, %H:%M"),
                    "Status": runs["status"],
                    "Rows": runs["rows_written"],
                    "Note": runs["message"].fillna(""),
                }
            ),
            hide_index=True,
            width="stretch",
        )
    st.caption(
        "Prices: every 15 minutes from 12:45 to 15:00 CET until tomorrow is stored. "
        "Weather: every 3 hours. Both can be started by hand under GitHub → Actions."
    )
