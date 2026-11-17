"""Household tariffs (offpeak/tariffs/defaults.py: germany_2026_home) and the comparison a
home sees on the tariff page (offpeak/home_tariffs.py)."""

from dataclasses import replace
from datetime import date

import pandas as pd
import pytest

from offpeak import components as C
from offpeak import demo_site, home_tariffs
from offpeak.tariffs import bill, germany_2026_home, slot_prices, tariff_for
from offpeak.tariffs.defaults import RHEINNETZ_MODULE3_CT, module3_period

TZ = "Europe/Berlin"


def day_prices(eur_mwh: float = 100.0, day: str = "2026-11-18") -> pd.DataFrame:
    ts = pd.date_range(day, periods=24, freq="h", tz=TZ).tz_convert("UTC")
    return pd.DataFrame({"ts": ts, "eur_mwh": eur_mwh})


@pytest.mark.parametrize(
    ("hhmm", "period"),
    [
        ("16:59", "ST"),
        ("17:00", "HT"),
        ("19:29", "HT"),
        ("19:30", "ST"),
        ("23:44", "ST"),
        ("23:45", "NT"),
        ("02:00", "NT"),
        ("05:44", "NT"),
        ("05:45", "ST"),
    ],
)
def test_module3_time_windows(hhmm, period):
    assert module3_period(pd.Timestamp(f"2026-11-18 {hhmm}", tz=TZ)) == period


def test_a_household_pays_vat_on_every_kwh():
    t = germany_2026_home(supplier_margin_ct=1.5)
    s = slot_prices(day_prices(100.0), t)
    net = 10 + 1.5 + 3.78 + 2.39 + 0.446 + 0.941 + 1.559 + 2.05  # spot, margin, grid, levies, tax
    assert s["import_ct"].iloc[0] == pytest.approx(net * 1.19)


def test_the_fixed_household_price_is_about_33_cents():
    s = slot_prices(day_prices(500.0), germany_2026_home(kind="fixed"))  # spot does not matter
    assert s["import_ct"].round(1).unique().tolist() == [32.9]


def test_module3_grid_fee_follows_the_clock():
    s = slot_prices(day_prices(), germany_2026_home(module3=True))
    by = s.set_index(s["ts"].dt.tz_convert(TZ).dt.hour)["grid_ct"]
    assert by[3] == pytest.approx(RHEINNETZ_MODULE3_CT["NT"] * 1.19)
    assert by[12] == pytest.approx(RHEINNETZ_MODULE3_CT["ST"] * 1.19)
    assert by[18] == pytest.approx(RHEINNETZ_MODULE3_CT["HT"] * 1.19)


def test_module3_needs_a_dynamic_tariff():
    with pytest.raises(ValueError):
        germany_2026_home(kind="fixed", module3=True)


def test_yearly_charges_include_vat_and_the_14a_reduction():
    plain, m3 = germany_2026_home(), germany_2026_home(module3=True)
    zero = pd.Series(0.0, index=range(24))
    b_plain = bill(zero, slot_prices(day_prices(), plain), plain)
    b_m3 = bill(zero, slot_prices(day_prices(), m3), m3)
    # a day without power: only the day's share of the yearly charges, with VAT
    assert b_plain.total == pytest.approx((150 + 30 / 1.19) / 365 * 1.19)
    assert b_m3.total == pytest.approx((150 + 30 / 1.19 + 50 / 1.19 - 95.58) / 365 * 1.19)


def test_an_old_plant_is_paid_at_negative_prices_a_new_one_not():
    old = slot_prices(day_prices(-50.0), germany_2026_home(feed_in_ct=8.2))
    new = slot_prices(day_prices(-50.0), germany_2026_home(pv_kwp=8))
    assert (old["export_ct"] == 8.2).all() and (new["export_ct"] == 0).all()


def test_tariff_for_picks_by_profile_and_devices():
    home = tariff_for("home", C.DEFAULT_HOME_COMPONENTS)  # has a heat pump and a wallbox
    assert home.gross and home.period_of is module3_period
    plain = [c for c in C.DEFAULT_HOME_COMPONENTS if c.kind not in ("heat_pump", "ev_charger")]
    assert tariff_for("home", plain).period_of is None
    business = tariff_for("business", C.DEFAULT_COMPONENTS)
    assert not business.gross and business.demand  # a business keeps its RLM tariff


def test_options_rank_the_tariffs_for_a_home():
    assets, _ = C.site_model(C.DEFAULT_HOME_COMPONENTS)
    base = demo_site.hourly_inputs(None, None, TZ, assets)
    rows = home_tariffs.options(base, C.DEFAULT_HOME_COMPONENTS, date(2026, 11, 18))
    assert {r["key"] for r in rows} == {"fixed", "dynamic", "module3"}
    days = [r["eur_day"] for r in rows if r["available"]]
    assert days == sorted(days)  # cheapest first
    assert next(r for r in rows if r["key"] == "fixed")["plan"] == "usual times"


def test_options_mark_14a_unavailable_without_a_steerable_device():
    plain = [c for c in C.DEFAULT_HOME_COMPONENTS if c.kind not in ("heat_pump", "ev_charger")]
    assets, _ = C.site_model(plain)
    base = demo_site.hourly_inputs(None, None, TZ, assets)
    rows = home_tariffs.options(base, plain, date(2026, 11, 18))
    assert rows[-1]["key"] == "module3" and not rows[-1]["available"]


def test_options_refuse_a_business_site():
    base = demo_site.hourly_inputs(None, None, TZ)
    with pytest.raises(ValueError):
        home_tariffs.options(base, C.DEFAULT_COMPONENTS, date(2026, 11, 18))


def test_a_home_without_solar_still_works():
    no_pv = [replace(c) for c in C.DEFAULT_HOME_COMPONENTS if c.kind != "pv_roof"]
    assets, _ = C.site_model(no_pv)
    base = demo_site.hourly_inputs(None, None, TZ, assets)
    assert home_tariffs.options(base, no_pv, date(2026, 11, 18))
