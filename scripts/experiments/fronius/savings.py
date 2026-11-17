"""Experiment: what the house would have paid on a fixed tariff, a dynamic tariff, and a
dynamic tariff with a battery that also charges from the grid when power is cheap.

Usage (repo root): uv run python savings.py <fronius_5min.csv> <prices.csv> <out.html>
Homeowner profile only: nothing here feeds any SME model.
"""

import sys

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy.optimize import linprog

csv, prices_csv, out = sys.argv[1:4]
TZ = "Europe/Berlin"
VAT = 1.19
FIXED_CT = 33.0  # gross, ct/kWh
# net ct/kWh on top of the spot price: supplier margin, grid fee, concession fee, CHP levy,
# offshore levy, § 19 levy, electricity tax (2026 rates, used for every year)
ADDERS_CT = 1.5 + 9.0 + 1.99 + 0.446 + 0.941 + 1.559 + 2.05
FEED_IN_CT = 8.2  # EEG 2023, ≤ 10 kWp, partial feed-in; paid also at negative prices
CAP, SOC_MIN = 9.6, 0.05 * 9.6  # usable kWh, measured from the data
P_CH, P_DIS = 6.0, 5.5  # kW
ETA = 0.96  # one way; about 92 % round trip

# ── 15-minute energy (kWh) ─────────────────────────────────────────────────
df = pd.read_csv(csv, parse_dates=["ts_utc"]).set_index("ts_utc").fillna(0)
q = (
    (df[["FromGen", "ToConsumer", "FromGridToConsumer", "FromGenToGrid"]] * 5 / 60 / 1000)
    .resample("15min")
    .sum()
)
q.columns = ["pv", "load", "imp_actual", "exp_actual"]

p = pd.read_csv(prices_csv, parse_dates=["ts"]).set_index("ts")["eur_mwh"]
p = p[~p.index.duplicated()].resample("15min").ffill()  # hourly prices hold for each quarter
q = q.join(p.rename("spot_eur_mwh"), how="inner").dropna()
q["dyn_ct"] = (q.spot_eur_mwh / 10 + ADDERS_CT) * VAT
q = q[q.index < pd.Timestamp("2026-11-17", tz="UTC")]


def cost(imp, exp, price):
    """Net euros: power bought at `price` minus feed-in earned (ct/kWh in, euros out)."""
    return (imp * price - exp * FEED_IN_CT).sum() / 100


# A and B: the house as it ran (its battery only stored solar power)
A = cost(q.imp_actual, q.exp_actual, FIXED_CT)
B = cost(q.imp_actual, q.exp_actual, q.dyn_ct)


# ── C: each day, the cheapest battery schedule with the known day-ahead prices ─
def day_plan(d: pd.DataFrame, soc0: float, keep: int):
    """Linear programme over today and tomorrow (tomorrow's prices are published at
    13:00 the day before), of which only today's first `keep` slots are carried out.
    Per slot: charge, discharge, import, export, state of charge. Export only from the
    panels, never from the battery."""
    n = len(d)
    # variable blocks: ch, dis, imp, exp, soc (each n)
    ch, dis, imp, exp, soc = (np.arange(n) + k * n for k in range(5))
    c = np.zeros(5 * n)
    c[imp] = d.dyn_ct.to_numpy()
    c[exp] = -FEED_IN_CT
    A_eq, b_eq = [], []
    net = (d.load - d.pv).to_numpy()
    for t in range(n):
        row = np.zeros(5 * n)  # imp - exp - ch + dis = load - pv
        row[imp[t]], row[exp[t]], row[ch[t]], row[dis[t]] = 1, -1, -1, 1
        A_eq.append(row)
        b_eq.append(net[t])
        row = np.zeros(5 * n)  # soc_t - soc_{t-1} - eta ch + dis / eta = 0
        row[soc[t]], row[ch[t]], row[dis[t]] = 1, -ETA, 1 / ETA
        if t:
            row[soc[t - 1]] = -1
        A_eq.append(row)
        b_eq.append(soc0 if t == 0 else 0)
    bounds = (
        [(0, P_CH * 0.25)] * n
        + [(0, P_DIS * 0.25)] * n
        + [(0, None)] * n
        + [(0, v) for v in d.pv.to_numpy()]
        + [(SOC_MIN, CAP)] * n
    )
    r = linprog(c, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="highs")
    if r.status != 0:
        raise RuntimeError(r.message)
    x = r.x
    return x[imp][:keep], x[exp][:keep], x[ch][:keep], x[soc][keep - 1]


local_day = q.index.tz_convert(TZ).date
days_total = len(set(local_day))
imp_c, exp_c, grid_ch = np.zeros(len(q)), np.zeros(len(q)), 0.0
soc = CAP / 2
pos = 0
groups = [g for _, g in q.groupby(local_day, sort=True)]
for k, d in enumerate(groups):
    window = pd.concat(groups[k : k + 2])  # today and tomorrow
    n = len(d)
    i, e, chg, soc = day_plan(window, soc, n)
    imp_c[pos : pos + n], exp_c[pos : pos + n] = i, e
    # charging beyond what the panels had left over came from the grid
    grid_ch += float(
        np.clip(chg - np.clip(d.pv.to_numpy() - d.load.to_numpy(), 0, None), 0, None).sum()
    )
    pos += n
q["imp_c"], q["exp_c"] = imp_c, exp_c
C = cost(q.imp_c, q.exp_c, q.dyn_ct)


# ── D: the same simulated battery, run by today's simple rule (store surplus, cover deficit)
def rule(pv, load):
    soc, imp, exp = CAP / 2, np.zeros(len(pv)), np.zeros(len(pv))
    for t, (gen, use) in enumerate(zip(pv, load, strict=True)):
        net = gen - use
        if net > 0:
            c = min(net, P_CH * 0.25, (CAP - soc) / ETA)
            soc += c * ETA
            exp[t] = net - c
        else:
            dch = min(-net, P_DIS * 0.25, (soc - SOC_MIN) * ETA)
            soc -= dch / ETA
            imp[t] = -net - dch
    return imp, exp


q["imp_d"], q["exp_d"] = rule(q.pv.to_numpy(), q.load.to_numpy())
D = cost(q.imp_d, q.exp_d, q.dyn_ct)
print(
    f"model check: simulated rule imports {q.imp_d.sum():.0f} kWh, "
    f"the real house {q.imp_actual.sum():.0f} kWh"
)
print(
    f"D (same simulated battery, simple rule, dynamic): {D:.0f} €"
    f"  ->  smart control saves {D - C:.0f} € "
    f"({(D - C) / days_total * 365:.0f} €/yr)"
)

year = q.index.tz_convert(TZ).year
per_year = pd.DataFrame(
    {
        "A fixed": q.groupby(year).apply(lambda g: cost(g.imp_actual, g.exp_actual, FIXED_CT)),
        "B dynamic": q.groupby(year).apply(lambda g: cost(g.imp_actual, g.exp_actual, g.dyn_ct)),
        "D dynamic, simple rule (sim)": q.groupby(year).apply(
            lambda g: cost(g.imp_d, g.exp_d, g.dyn_ct)
        ),
        "C dynamic + smart battery": q.groupby(year).apply(
            lambda g: cost(g.imp_c, g.exp_c, g.dyn_ct)
        ),
        "import actual kWh": q.groupby(year).imp_actual.sum(),
        "import C kWh": q.groupby(year).imp_c.sum(),
        "avg spot ct": q.groupby(year).spot_eur_mwh.mean() / 10,
    }
)
print(per_year.round(0).to_string())
days = q.index.tz_convert(TZ).normalize().nunique()
print(f"\nwhole period ({days} days): A {A:.0f} €, B {B:.0f} €, C {C:.0f} €")
print(
    f"B vs A: {A - B:.0f} €  |  C vs A: {A - C:.0f} €  |  "
    f"C vs B (smart battery alone): {B - C:.0f} €"
)
print(f"per year: C vs A {(A - C) / days * 365:.0f} €/yr, C vs B {(B - C) / days * 365:.0f} €/yr")
print(f"grid energy stored in the battery: {grid_ch:.0f} kWh")
print(
    f"avg price paid per kWh bought: fixed {FIXED_CT:.1f} ct, "
    f"dynamic {(q.imp_actual * q.dyn_ct).sum() / q.imp_actual.sum():.1f} ct, "
    f"smart {(q.imp_c * q.dyn_ct).sum() / q.imp_c.sum():.1f} ct"
)

py = per_year.drop(columns=["import actual kWh", "import C kWh", "avg spot ct"])
fig = go.Figure()
for col, colour in zip(py.columns, ["#C9C4BB", "#3A3733", "#8A847B", "#FF5F00"], strict=True):
    fig.add_bar(
        x=[str(y) for y in py.index],
        y=py[col].round(0),
        name=col,
        marker_color=colour,
        text=py[col].round(0),
        textposition="outside",
    )
fig.update_layout(
    template="plotly_white",
    barmode="group",
    title="Net electricity cost per year (€, after feed-in)",
    yaxis_title="€",
    font=dict(family="Inter, sans-serif"),
    height=520,
    legend=dict(orientation="h", y=1.1),
)
fig.write_html(out, include_plotlyjs="cdn")
print("chart:", out)
