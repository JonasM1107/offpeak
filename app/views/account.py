"""Account: the signed-in person, their settings and plan, and whether every connection
(database tables and services) works. Signing in happens on the login screen in front of
the app (app/ui/account.py)."""

from html import escape

import data
import perf
import streamlit as st
from ui import account, assistant
from ui.components import card_title, header, local

from offpeak import auth, db, roles
from offpeak.sites import DEMO_CITY

who = account.editor()
here = data.site()
name = account.editor_name(who)
until = auth.expires_at(
    st.session_state.get("editor_token") or st.session_state.get("stored_token")
)

# what each table holds, in words
PARTS = {
    "prices_da": ("Market prices", "Day-ahead prices, every 15 minutes", "bolt"),
    "weather_fc": (
        "Weather forecasts",
        "Sun, wind and temperature for the site",
        "partly_cloudy_day",
    ),
    "price_outlook": (
        "Offpeak Intelligence",
        "The price outlook for the coming days",
        "online_prediction",
    ),
    "weather_drivers": ("Weather for the outlook", "Wind and sun across Germany", "air"),
    "site_components": (
        "Site components",
        "Solar, wind, battery and machines",
        "precision_manufacturing",
    ),
    "cockpit_machines": ("Cockpit machines", "The machines you plan in the cockpit", "tune"),
    "job_runs": ("Background jobs", "Log of the scheduled data updates", "schedule"),
}

header("Setup", "Account", live=True)

# ── Profile and plan ─────────────────────────────────────────────────────────
left, right = st.columns([1.15, 1], gap="medium")
with left, st.container(border=True, key="card_profile"):
    initials = "".join(w[0] for w in name.split()[:2]).upper() or "?"
    st.html(
        f'<div class="op-profile"><div class="op-avatar">{escape(initials)}</div><div>'
        f'<div class="op-name">{escape(name)}</div><div class="op-mail">{escape(who)}</div>'
        '<span class="op-chip">Editor</span></div></div>'
    )
    rows = {
        "Signed in until": f"{local(until):%a %-d %b, %H:%M}" if until else "–",
        "Language": "English",
        "Units": "ct/kWh, kWh, euros",
        "Time zone": "Europe/Berlin",
        # the signed-in role's own site: a homeowner has the demo home, not the business site
        roles.words(data.role())["Site"]: f"{here.name} · {DEMO_CITY} · {here.zone}",
    }
    st.html(
        "".join(
            f'<div class="op-row"><span class="meta">{k}</span><span>{escape(v)}</span></div>'
            for k, v in rows.items()
        )
    )
    if st.button("Sign out", icon=":material/logout:"):
        account.sign_out()
        st.rerun()

with right, st.container(border=True, key="card_plan"):
    card_title("Plan", "What this account includes")
    included = [
        "1 site with live prices and weather",
        "3 editors",
        "Offpeak Intelligence price outlook",
        "Ask Ollie, the energy assistant",
        "Savings replay and tariff calculator",
    ]
    st.html(
        '<div class="op-plan"><div><div class="op-plan-name">Pilot</div>'
        '<div class="op-mail">Free while offpeak is in its pilot phase</div></div>'
        '<div class="op-plan-price">€0<small>/month</small></div></div>'
        + "".join(f'<div class="op-incl">{escape(i)}</div>' for i in included)
        + '<div class="op-foot">No payment details are stored. '
        "Paid plans are not offered yet.</div>"
    )

st.write("")

# ── Connections ──────────────────────────────────────────────────────────────
with st.container(border=True, key="card_connections"):
    eng = data.engine()
    status = db.table_status(eng) if eng is not None else {}
    services = [
        ("Database", "Supabase, where everything above is stored", eng is not None),
        ("Sign-in", "Team emails and password set on the server", account.configured()),
        ("Ollie's AI", "Claude or Requesty key for the assistant", assistant.configured()),
    ]
    problems = [t for t, s in status.items() if not s["ok"]] + [
        n for n, _, ok in services if not ok
    ]
    if not problems:
        headline, sub, tone = "Everything is connected", "All data and services work.", "good"
    else:
        n = len(problems)
        headline = f"{n} connection{'s need' if n > 1 else ' needs'} attention"
        sub, tone = "See the red items below.", "bad"
    st.html(
        f'<div class="op-conn-head {tone}"><span class="op-conn-icon">'
        f'{"✓" if tone == "good" else "!"}</span><div><div class="op-name">{headline}</div>'
        f'<div class="op-mail">{sub}</div></div></div>'
    )

    def tile(title: str, text: str, ok: bool, detail: str) -> str:
        state = "Connected" if ok else "Not connected"
        return (
            f'<div class="op-tile2 {"ok" if ok else "bad"}"><div class="t">{escape(title)}</div>'
            f'<div class="d">{escape(text)}</div><div class="s"><span class="pill">{state}</span>'
            f'<span class="n">{escape(detail)}</span></div></div>'
        )

    tiles = [tile(n, t, ok, "") for n, t, ok in services]
    for table, (title, text, _) in PARTS.items():
        s = status.get(table, {"ok": False, "rows": None})
        detail = f"{s['rows']:,} entries" if s["ok"] else "table missing"
        tiles.append(tile(title, text, s["ok"], detail))
    st.html(f'<div class="op-tiles2">{"".join(tiles)}</div>')
    missing = [
        name
        for name, found in (
            ("DATABASE_URL", eng is not None),
            ("ANTHROPIC_API_KEY or REQUESTY_API_KEY", assistant.configured()),
            ("OFFPEAK_EDITORS, OFFPEAK_PASSWORD_HASH, OFFPEAK_AUTH_SECRET", account.configured()),
        )
        if not found
    ]
    if missing:
        st.caption(
            "Not found in the app's secrets (Streamlit Cloud → Manage app → Settings → "
            f"Secrets): **{'**, **'.join(missing)}**. Names must match exactly."
        )
    if any(not s["ok"] for s in status.values()):
        st.caption("A missing table usually means a file in db/migrations was not run in Supabase.")

st.write("")
with st.container(border=True, key="card_speed"):
    card_title("Speed", "Time the server needs to build each page (since the app last started)")
    timings = perf.summary()
    if not timings:
        st.caption("No pages measured yet.")
    else:
        st.html(
            "".join(
                f'<div class="op-row"><span>{escape(t["page"])}</span><span class="meta">'
                f"{t['median_s']:.2f} s typical · {t['last_s']:.2f} s last · {t['runs']} runs"
                "</span></div>"
                for t in timings
            )
        )
        st.caption(
            "The browser and Streamlit Cloud add a few seconds around this when a page opens."
        )
