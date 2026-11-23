"""The demo sites (offpeak/sites.py): which site a role gets, and a roof's direction in words."""

import pytest

from offpeak.sites import DEMO_HOME, DEMO_SITE, facing, site_for


def test_each_role_has_its_own_site():
    assert site_for("business") is DEMO_SITE
    assert site_for("home") is DEMO_HOME


@pytest.mark.parametrize("role", ["admin", "", None, "HOME"])
def test_a_role_that_is_not_one_is_refused(role):
    with pytest.raises(ValueError):
        site_for(role)


@pytest.mark.parametrize(
    "bearing, words",
    [
        (180, "south"),  # the business site
        (145, "south-east"),  # the demo home's roof: not "south"
        (0, "north"),
        (90, "east"),
        (270, "west"),
        (225, "south-west"),
    ],
)
def test_facing_names_the_nearest_compass_direction(bearing, words):
    assert facing(bearing) == words


@pytest.mark.parametrize("bearing, words", [(360, "north"), (359, "north"), (-90, "west")])
def test_facing_wraps_around_the_circle(bearing, words):
    assert facing(bearing) == words
