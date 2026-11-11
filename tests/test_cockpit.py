import pytest

from offpeak.cockpit import Machine, best_start, job_cost, plan

FLAT = [30.0] * 48


def test_cost_uses_surplus_first():
    m = Machine("EV", kw=10, hours=2, earliest=0, latest_end=24, usual_start=0)
    surplus = [4.0] * 48
    # 4 kW own power at 8 ct, 6 kW bought at 30 ct, for 2 hours
    assert job_cost(0, m, FLAT, [8.0] * 48, surplus) == pytest.approx(2 * (4 * 0.08 + 6 * 0.30))


def test_best_start_finds_the_cheap_hours_inside_the_window():
    buy = [30.0] * 24 + [30.0] * 24
    buy[13:16] = [5.0, 5.0, 5.0]  # cheap 13-16 on day one
    m = Machine("Furnace", kw=40, hours=3, earliest=8, latest_end=18, usual_start=8)
    start, cost = best_start(0, m, buy, [8.0] * 48, [0.0] * 48)
    assert start == 13 and cost == pytest.approx(40 * 3 * 0.05)
    tight = Machine("Furnace", kw=40, hours=3, earliest=8, latest_end=12, usual_start=8)
    assert best_start(0, tight, buy, [8.0] * 48, [0.0] * 48)[0] in range(8, 10)


def test_job_that_does_not_fit_returns_none():
    m = Machine("Kiln", kw=10, hours=10, earliest=20, latest_end=24, usual_start=20)
    assert best_start(0, m, FLAT, FLAT, [0.0] * 48) is None


def test_plan_shares_surplus_without_counting_it_twice():
    surplus = [0.0] * 48
    surplus[12] = 10.0  # one sunny hour with 10 kW to spare
    a = Machine("A", kw=10, hours=1, earliest=0, latest_end=24, usual_start=0)
    b = Machine("B", kw=8, hours=1, earliest=0, latest_end=24, usual_start=0)
    result = {r["name"]: r for r in plan([b, a], 0, FLAT, [8.0] * 48, surplus)}
    assert result["A"]["start"] == 12  # the larger machine gets the sun
    assert result["A"]["cost"] == pytest.approx(10 * 0.08)
    assert result["B"]["cost"] == pytest.approx(8 * 0.30)  # nothing left for B
    assert result["A"]["saving"] == pytest.approx(10 * 0.30 - 10 * 0.08)


def test_horizon_joins_published_and_forecast_hours():
    import pandas as pd

    from offpeak.cockpit import horizon
    from offpeak.tariffs import germany_2026

    tz = "Europe/Berlin"
    today = pd.Timestamp("2026-11-11").date()
    start = pd.Timestamp(today, tz=tz).tz_convert("UTC")
    pub_idx = pd.date_range(start, periods=48, freq="h")
    published = pd.Series(10.0, index=pub_idx)  # today and tomorrow
    fc_idx = pd.date_range(start + pd.Timedelta(hours=48), periods=24 * 5, freq="h")
    forecast = pd.DataFrame({"ts": fc_idx, "p10": 5.0, "p50": 20.0, "p90": 40.0})
    gen_idx = pd.date_range(start, periods=24 * 7 * 4, freq="15min")
    gen = pd.DataFrame({"ts": gen_idx, "pv_kw": 30.0, "wind_kw": 0.0})
    h = horizon(published, forecast, gen, base_kw=15, tariff=germany_2026(), tz=tz, today=today)
    assert len(h["t"]) == 24 * 7
    assert h["kind"][:48] == ["published"] * 48 and set(h["kind"][48:]) == {"forecast"}
    assert h["buy"][0] > 10  # fees on top of the spot price
    assert h["buy_lo"][60] < h["buy"][60] < h["buy_hi"][60]
    assert h["buy_lo"][0] == h["buy"][0] == h["buy_hi"][0]  # published: no range
    assert h["surplus"][0] == 15  # 30 kW own power minus 15 kW base load
    assert [d["start"] for d in h["days"]] == [0, 24, 48, 72, 96, 120, 144]


def test_no_start_in_the_past():
    m = Machine("EV", kw=10, hours=2, earliest=0, latest_end=24, usual_start=0)
    buy = [5.0] * 10 + [30.0] * 38  # cheapest early in the day, but it is already 14:00
    start, _ = best_start(0, m, buy, [8.0] * 48, [0.0] * 48, not_before=14)
    assert start >= 14


def test_clean_machines_keeps_values_inside_the_slider_ranges():
    from offpeak.cockpit import MAX_MACHINES, clean_machines

    raw = [
        {
            "name": " Oven ",
            "kw": 500,
            "hours": 3,
            "earliest": 22,
            "latest_end": 24,
            "usual_start": 7,
        },
        {"name": "", "kw": "x", "hours": None},
        "not a machine",
    ]
    oven, blank = clean_machines(raw)
    assert oven["name"] == "Oven"
    assert oven["kw"] == 100  # capped at the slider's maximum
    # 3 h does not fit between 22:00 and midnight, so the start moves earlier
    assert (oven["earliest"], oven["latest_end"]) == (21, 24)
    assert blank["name"] == "Machine" and blank["kw"] == 10 and blank["hours"] == 2
    assert clean_machines("nonsense") == []
    assert len(clean_machines([{}] * 50)) == MAX_MACHINES


def two_days(buy: list[float], surplus: list[float] | None = None) -> dict:
    """A horizon() result for two local days of 24 hours."""
    return {
        "buy": buy,
        "sell": [5.0] * 48,
        "surplus": surplus or [0.0] * 48,
        "kind": ["published"] * 24 + ["forecast"] * 24,
        "hour": list(range(24)) * 2,
        "days": [{"name": "Thu 12 Nov", "start": 0}, {"name": "Fri 13 Nov", "start": 24}],
    }


def test_week_plan_picks_the_cheapest_day_and_compares_with_the_usual_run():
    from offpeak.cockpit import describe_plan, week_plan

    buy = [30.0] * 48
    buy[24 + 13 : 24 + 15] = [10.0, 10.0]  # Friday 13-15 is cheap
    oven = Machine("Oven", kw=10, hours=2, earliest=6, latest_end=22, usual_start=8)
    (p,) = week_plan(two_days(buy), [oven], now_index=9)  # 09:00 Thursday
    assert (p["start"], p["end"]) == (37, 39)
    assert p["cost"] == pytest.approx(2 * 10 * 0.10)
    assert p["usual_start"] == 24 + 8  # Thursday 08:00 has passed: the next usual run is Friday
    assert p["saving"] == pytest.approx(2 * 10 * 0.30 - 2.0)
    assert p["forecast"] is True
    plan = describe_plan(two_days(buy), [p], [oven])
    assert plan["rows"][0]["when"] == "Fri 13 Nov · 13:00–15:00"
    assert plan["rows"][0]["usual"] == "Fri 13 Nov · 08:00–10:00"
    assert plan["total"] == pytest.approx(4.0) and plan["compared"] == 1


def test_week_plan_shares_surplus_largest_first_and_never_starts_in_the_past():
    from offpeak.cockpit import week_plan

    surplus = [0.0] * 48
    surplus[12] = 20.0  # one sunny hour, Thursday noon
    big = Machine("Big", kw=20, hours=1, earliest=0, latest_end=24, usual_start=0)
    small = Machine("Small", kw=5, hours=1, earliest=0, latest_end=24, usual_start=0)
    small_plan, big_plan = week_plan(two_days([30.0] * 48, surplus), [small, big], now_index=3)
    assert big_plan["start"] == 12  # the largest machine gets the sun
    assert small_plan["start"] != 12 and small_plan["start"] >= 3
    late = Machine("Late", kw=5, hours=3, earliest=20, latest_end=23, usual_start=20)
    (p,) = week_plan(two_days([30.0] * 48), [late], now_index=47)
    assert p["start"] is None  # no time left in the horizon


def test_site_machines_counts_every_charge_point():
    from offpeak.cockpit import site_machines
    from offpeak.components import DEFAULT_COMPONENTS

    machines = site_machines(DEFAULT_COMPONENTS)
    flexible = [c for c in DEFAULT_COMPONENTS if c.spec.role == "flexible"]
    assert [m["name"] for m in machines] == [c.name for c in flexible]
    ev = next(c for c in flexible if c.kind == "ev_charger")
    assert next(m for m in machines if m["name"] == ev.name)["kw"] == ev.p("kw") * ev.p("count")
