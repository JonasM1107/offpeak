import pandas as pd
import pytest

from offpeak.tariffs import bill, germany_2026, portugal_bte_2026, slot_prices
from offpeak.tariffs.defaults import eeg_partial_feed_in_ct, portugal_period

DAY_15MIN = pd.date_range("2026-11-10 23:00", periods=96, freq="15min", tz="UTC")  # Berlin day
DAY_HOURS = pd.date_range("2026-11-10 23:00", periods=24, freq="h", tz="UTC")

# Per-kWh charges on top of energy for a low-voltage load-metered site with >= 2,500 h:
# grid 1.84 + concession 0.11 + KWKG 0.446 + offshore 0.941 + § 19 1.559 + tax 2.05
GERMAN_CHARGES_CT = 6.946


def prices(eur_mwh, ts=DAY_15MIN):
    return pd.DataFrame({"ts": ts, "eur_mwh": eur_mwh})


def test_german_dynamic_price_is_spot_plus_margin_plus_charges():
    p = slot_prices(prices(100.0), germany_2026(supplier_margin_ct=1.5))
    assert p["spot_ct"].eq(10.0).all()
    assert p["import_ct"].round(6).eq(round(10.0 + 1.5 + GERMAN_CHARGES_CT, 6)).all()
    assert p["grid_ct"].round(6).eq(1.84).all()
    assert p["levies_ct"].round(6).eq(round(0.11 + 0.446 + 0.941 + 1.559, 6)).all()
    assert p["tax_ct"].round(6).eq(2.05).all()


def test_fixed_tariff_ignores_the_spot_price():
    p = slot_prices(
        prices([50.0] * 48 + [300.0] * 48), germany_2026(kind="fixed", fixed_energy_ct=14)
    )
    assert p["energy_ct"].eq(14.0).all()
    assert p["import_ct"].nunique() == 1


def test_reduced_electricity_tax_saves_two_cents():
    full = slot_prices(prices(100.0), germany_2026())["import_ct"].iloc[0]
    reduced = slot_prices(prices(100.0), germany_2026(reduced_electricity_tax=True))
    assert full - reduced["import_ct"].iloc[0] == pytest.approx(2.0)


def test_small_site_pays_base_price_instead_of_demand_charge():
    t = germany_2026(load_metered=False)
    assert t.demand == ()
    assert slot_prices(prices(0.0), t)["grid_ct"].iloc[0] == pytest.approx(3.78)
    assert sum(f.eur_year for f in t.fixed) == pytest.approx(150.0)


def test_feed_in_is_not_paid_at_negative_prices():
    p = slot_prices(prices([-20.0] * 48 + [80.0] * 48), germany_2026(pv_kwp=60))
    assert p["export_ct"].iloc[0] == 0
    assert p["export_ct"].iloc[-1] == pytest.approx(eeg_partial_feed_in_ct(60))


@pytest.mark.parametrize(
    ("kwp", "ct"),
    [(8, 7.70), (40, (10 * 7.70 + 30 * 6.66) / 40), (60, (10 * 7.70 + 30 * 6.66 + 20 * 5.44) / 60)],
)
def test_eeg_rate_blends_the_size_bands(kwp, ct):
    assert eeg_partial_feed_in_ct(kwp) == pytest.approx(ct, abs=1e-4)


def test_bill_adds_up_energy_demand_fixed_and_export():
    t = germany_2026(supplier_margin_ct=0.0)
    p = slot_prices(prices(100.0, DAY_HOURS), t)
    grid_kw = pd.Series([100.0] * 23 + [-10.0])  # buys 100 kW for 23 h, sells 10 kWh at the end
    b = bill(grid_kw, p, t)
    assert b.kwh_bought == pytest.approx(2300)
    assert b.lines["energy"] == pytest.approx(2300 * 0.10)
    assert b.lines["demand"] == pytest.approx(100 * 172.43 / 365)
    assert b.lines["fixed"] == pytest.approx((221.28 + 219.24) / 365)
    assert b.lines["export"] == pytest.approx(-10 * eeg_partial_feed_in_ct(60) / 100)
    assert b.total == pytest.approx(sum(b.lines.values()))
    assert b.peak_kw == 100


def test_bill_handles_quarter_hours():
    t = germany_2026()
    p = slot_prices(prices(100.0), t)
    b = bill(pd.Series([40.0] * 96), p, t)
    assert b.kwh_bought == pytest.approx(40 * 24)


def test_lower_peak_means_lower_demand_charge():
    t = germany_2026()
    p = slot_prices(prices(100.0, DAY_HOURS), t)
    flat = bill(pd.Series([50.0] * 24), p, t)
    spiky = bill(pd.Series([25.0] * 12 + [75.0] * 12), p, t)
    assert flat.kwh_bought == spiky.kwh_bought
    assert flat.lines["demand"] < spiky.lines["demand"]


@pytest.mark.parametrize(
    ("local", "period"),
    [
        ("2026-11-11 10:00", "ponta"),  # winter weekday morning peak
        ("2026-11-11 19:00", "ponta"),  # winter weekday evening peak
        ("2026-11-11 14:00", "cheias"),
        ("2026-11-11 06:30", "vazio_normal"),
        ("2026-11-11 03:00", "super_vazio"),
        ("2026-11-14 10:00", "cheias"),  # Saturday
        ("2026-11-15 10:00", "vazio_normal"),  # Sunday
        ("2026-07-15 10:00", "ponta"),  # summer weekday
        ("2026-07-15 19:00", "cheias"),  # no evening peak in summer
    ],
)
def test_portugal_weekly_cycle(local, period):
    assert portugal_period(pd.Timestamp(local, tz="Europe/Lisbon")) == period


def test_portugal_price_applies_losses_and_period_tariff():
    lisbon_day = pd.date_range("2026-11-11 00:00", periods=24, freq="h", tz="UTC")
    t = portugal_bte_2026(supplier_margin_ct=1.0, loss_factor=0.1)
    p = slot_prices(prices(100.0, lisbon_day), t)
    ten = p[p["ts"] == pd.Timestamp("2026-11-11 10:00", tz="UTC")].iloc[0]
    assert ten["period"] == "ponta"
    assert ten["energy_ct"] == pytest.approx((10 + 1) * 1.1)
    assert ten["import_ct"] == pytest.approx(11 * 1.1 + 3.97 + 0.1)


def test_portugal_peak_hour_power_uses_average_kw_in_peak_hours():
    lisbon_day = pd.date_range("2026-11-11 00:00", periods=24, freq="h", tz="UTC")
    t = portugal_bte_2026()
    p = slot_prices(prices(100.0, lisbon_day), t)
    kw = pd.Series([80.0 if per == "ponta" else 20.0 for per in p["period"]])
    b = bill(kw, p, t)
    assert b.lines["demand"] == pytest.approx(80 * 0.5521 + 80 * 0.0563)
