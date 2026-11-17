"""Faster page changes: compressed answers, the site view's day planned once, the 90-day
savings replay prepared in the background."""

import sys
import tomllib
from datetime import date
from pathlib import Path

import pytest

from offpeak import components as C
from offpeak import demo_site
from offpeak.tariffs import germany_2026

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "app"))
TZ = "Europe/Berlin"


def test_the_server_compresses_what_it_sends():
    config = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text())
    assert config["server"]["enableWebsocketCompression"] is True


@pytest.fixture
def inputs():
    assets, _ = C.site_model(C.DEFAULT_COMPONENTS)
    tariff = germany_2026(pv_kwp=assets.pv_kwp)
    raw = demo_site.hourly_inputs(None, None, TZ, assets)
    return demo_site.apply_tariff(raw, tariff, date(2026, 11, 18))


def test_the_kept_day_is_the_same_as_planning_again(inputs):
    """data.site_day (kept between visits) gives exactly what the page computed before."""
    import data
    from ui import site_scene

    comps = list(C.DEFAULT_COMPONENTS)
    tariff = germany_2026(pv_kwp=C.site_model(comps)[0].pv_kwp)
    kept = data.site_day(inputs, data.setup_key(comps))
    site = {"name": "Demo site", "city": "Köln", "zone": "DE-LU", "date": "2026-11-18"}
    fresh = site_scene.payload(inputs, site, 12, tariff, comps)
    reused = site_scene.payload(inputs, site, 12, tariff, comps, kept)
    assert reused == fresh


def test_the_day_is_planned_again_when_components_change(inputs):
    import data

    comps = list(C.DEFAULT_COMPONENTS)
    fewer = [c for c in comps if c.kind != "furnace"]
    one = data.site_day(inputs, data.setup_key(comps))
    other = data.site_day(inputs, data.setup_key(fewer))
    assert {c["id"] for c in one["components"]} != {c["id"] for c in other["components"]}


def test_the_dashboards_replay_also_prepares_90_days(monkeypatch):
    """The background replay the dashboard starts (30 days) goes on with the 90 days the
    Savings page offers, so that click finds them ready."""
    import threading

    import data

    asked = []
    monkeypatch.setattr(data, "savings_replay", lambda end, n, setup: asked.append(n) or [])
    monkeypatch.setattr(data, "site_components", lambda: (list(C.DEFAULT_COMPONENTS), "demo"))
    started = []
    monkeypatch.setattr(
        threading, "Thread", lambda target, daemon: started.append(target) or _Ran(target)
    )
    data._REPLAYED.clear()
    data._RUNNING.clear()
    data._FAILED.clear()
    assert data.saved_recently(30) == (None, "running")
    assert asked == [30, 90]


class _Ran:
    """Stands in for a thread: runs its work at once, so the test sees what it did."""

    def __init__(self, target):
        self.target = target

    def start(self):
        self.target()
