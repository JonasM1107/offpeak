"""The two kinds of customer: a small or medium business, and a household.

Both see the same pages with the same market data and the same price forecast. What differs
is everything that depends on what they use: their site and components (offpeak/sites.py,
offpeak/components.py: one catalogue per role) and the words the pages use. An account has
exactly one role; it is chosen at the first sign-in and stored with the account.
"""

ROLES = ("home", "business")  # the order of the cards on the sign-in page

LABELS = {"home": "Homeowner", "business": "Business (SME)"}

# Short texts for the cards on the sign-in page
PITCH = {
    "home": "Your house, your solar, your car: run the washing machine, the heat pump and "
    "the wallbox when power is cheapest.",
    "business": "Your site and its machines: plan furnaces, chargers and cooling around "
    "tomorrow's prices and your own sun and wind.",
}

# The words that differ between the two portals. Pages use these, so there is one page per
# purpose, never one copy per role.
WORDS = {
    "business": {
        "site": "site",
        "Site": "Site",
        "view": "Site view",
        "setup": "Site & components",
        "planner": "Simulation cockpit",
        "machines": "machines",
        "Machines": "Machines",
        "machine": "machine",
    },
    "home": {
        "site": "home",
        "Site": "Home",
        "view": "Home view",
        "setup": "Home & devices",
        "planner": "Appliance planner",
        "machines": "devices",
        "Machines": "Devices",
        "machine": "device",
    },
}

# Templates for "Add" in the planner (simulation cockpit / appliance planner): name, kW,
# hours, earliest start, done by, usual start. Within the cockpit's limits (1-100 kW, 1-12 h).
PLANNER_PRESETS = {
    "business": [
        ["EV charging (fleet)", 22, 4, 7, 24, 17],
        ["Compressed air", 15, 3, 6, 20, 8],
        ["Industrial dishwasher", 9, 2, 6, 22, 13],
        ["Laundry (washers + dryers)", 18, 3, 6, 22, 9],
        ["Water heater", 6, 3, 0, 24, 6],
        ["Irrigation pump", 7, 2, 0, 24, 18],
        ["Cold store pre-cooling", 12, 2, 0, 24, 14],
        ["Kiln / oven batch", 30, 5, 5, 22, 7],
        ["Forklift charging", 8, 6, 0, 24, 18],
    ],
    "home": [
        ["Washing machine", 1, 2, 7, 23, 19],
        ["Dryer", 1.5, 2, 7, 23, 21],
        ["Dishwasher", 1.2, 2, 7, 23, 20],
        ["Wallbox", 11, 1, 0, 24, 18],
        ["Heat pump", 3, 5, 0, 24, 6],
        ["Hot water (heating rod)", 2, 2, 0, 24, 7],
        ["Pool pump", 1, 4, 8, 22, 12],
    ],
}

# The dashboard's "Shift & save" slider: how much energy a day could move to cheaper hours,
# in the sizes of each role (kWh a day), with typical examples to click.
SHIFT = {
    "business": {
        "max": 500,
        "step": 10,
        "value": 100,
        "presets": [
            ["EV fleet", 120],
            ["Heat pump", 60],
            ["Hot water", 25],
            ["Cold store pre-cooling", 80],
        ],
    },
    "home": {
        "max": 40,
        "step": 1,
        "value": 10,
        "presets": [["Wallbox", 11], ["Heat pump", 15], ["Washing machine", 2], ["Dryer", 3]],
    },
}


def normal_role(value) -> str | None:
    """The role if `value` is one, else None. Everything from a browser or a stored row goes
    through here before it is used."""
    role = str(value or "").strip().lower()
    return role if role in ROLES else None


def words(role: str) -> dict[str, str]:
    return WORDS[role]


def sign_in_role(chosen, stored) -> tuple[str | None, str | None]:
    """The role a sign-in gets, from the card the visitor chose and the role stored with the
    account (None if the account has none yet). Returns (role, problem):
    - no valid choice: (None, ask to choose);
    - first sign-in: (chosen, None), and the caller stores it with the account;
    - the stored role: (stored, None);
    - another role than the stored one: (None, say which one the account has).
    An account never changes its role by signing in with the other card."""
    chosen, stored = normal_role(chosen), normal_role(stored)
    if chosen is None:
        return None, "Choose Homeowner or Business first."
    if stored is not None and stored != chosen:
        return None, f"This account is a {LABELS[stored]} account. Choose {LABELS[stored]}."
    return chosen, None
