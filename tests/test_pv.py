import pandas as pd

from offpeak.generation.pv import pv_kw


def test_full_sun_on_one_kwp_gives_085_kw():
    assert pv_kw(pd.Series([1000.0]), kwp=1).iloc[0] == 0.85


def test_scales_with_sunlight_and_size_and_keeps_gaps():
    out = pv_kw(pd.Series([0.0, 500.0, None]), kwp=60)
    assert out.iloc[0] == 0
    assert out.iloc[1] == 500 / 1000 * 60 * 0.85
    assert pd.isna(out.iloc[2])  # missing forecast stays missing, never 0
