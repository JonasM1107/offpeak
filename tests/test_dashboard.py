import pytest

from offpeak import dashboard
from tests.test_cockpit import two_days


def hours_with_cheap_afternoon():
    buy = [30.0] * 48
    buy[13:16] = [10.0, 10.0, 10.0]  # Thursday 13-16 cheap
    buy[18:21] = [50.0, 50.0, 50.0]  # Thursday evening expensive
    h = two_days(buy)
    h["t"] = [1_700_000_000 + 3600 * i for i in range(48)]
    return h


def test_now_is_cheap_until_the_cheap_hours_end():
    s = dashboard.status_now(hours_with_cheap_afternoon(), now_index=13)
    assert s["level"] == "cheap" and s["price_ct"] == 10.0
    assert s["until"] == "16:00"
    assert s["next_cheap"] == "Thu 12 Nov · 13:00–16:00" and s["next_cheap_ct"] == 10.0


def test_now_is_expensive_in_the_evening_and_points_to_later():
    s = dashboard.status_now(hours_with_cheap_afternoon(), now_index=18)
    assert s["level"] == "expensive" and s["until"] == "21:00"
    assert (
        s["next_cheap_t"]
        > dashboard.status_now(hours_with_cheap_afternoon(), 18)["until_t"] - 3600 * 24
    )


def test_flat_prices_are_all_normal():
    s = dashboard.status_now(two_days([30.0] * 48) | {"t": list(range(48))}, now_index=5)
    assert s["level"] == "normal"


def test_actions_are_sorted_and_skip_what_does_not_fit():
    machines = [
        {"name": "Oven", "kw": 10, "hours": 2, "earliest": 0, "latest_end": 24, "usual_start": 19},
        {"name": "Late", "kw": 5, "hours": 3, "earliest": 22, "latest_end": 23, "usual_start": 22},
    ]
    todo = dashboard.actions(hours_with_cheap_afternoon(), machines, now_index=9)
    assert [a["name"] for a in todo] == ["Oven"]  # a 3 h job in a 1 h window never fits
    oven = todo[0]
    assert oven["when"] == "Thu 12 Nov · 13:00–15:00" and oven["end_t"] - oven["start_t"] == 7200
    assert oven["saving_eur"] == pytest.approx(2 * 10 * 0.40)  # usual 19:00 at 50 ct


def test_payload_adds_up_the_week_and_the_flex_value():
    machines = [
        {"name": "Oven", "kw": 10, "hours": 2, "earliest": 0, "latest_end": 24, "usual_start": 19}
    ]
    p = dashboard.payload(hours_with_cheap_afternoon(), 9, machines, saved=None)
    assert p["week_saving_eur"] == pytest.approx(8.0)
    assert p["month_saving_eur"] == pytest.approx(8 * 30 / 7, abs=0.01)
    assert len(p["ribbon"]["ct"]) == 36 and p["ribbon"]["level"][4] == "cheap"  # 13:00
    assert p["shift_ct_per_kwh"] > 0 and p["saved"] is None
