"""The "Edit site" layout designer: a two-way component (web/layout/index.html).

Python sends the draft site and the grid; the browser draws it and sends back one action
at a time (add, move, remove, select). The page passes that action to offpeak/layout.py,
which decides whether it is allowed. Same technique as the sign-in helper (web/token).
"""

from pathlib import Path

import streamlit.components.v1 as components

from offpeak import components as site_components
from offpeak import layout

_designer = components.declare_component(
    "offpeak_layout", path=str(Path(__file__).with_name("web") / "layout")
)

ROLES = (
    ("generation", "Generation"),
    ("storage", "Storage"),
    ("flexible", "Flexible machines"),
    ("base", "Always on"),
)


def args(draft, selected: str | None) -> dict:
    """Everything the browser needs to draw the site; plain JSON, no calculations there."""
    return {
        "grid": layout.GRID,
        "centre": layout.CENTRE,
        "ground": [list(sq) for sq in layout.ground_squares()],
        "fixed": {
            key: {"label": label, "cells": [list(sq) for sq in cells]}
            for key, (label, cells) in layout.FIXED.items()
        },
        "footprint": {kind: list(layout.footprint(kind)) for kind in site_components.CATALOGUE},
        "roof_kinds": sorted(layout.ON_ROOF),
        "roof_count": sum(1 for c in draft if c.kind in layout.ON_ROOF),
        "roles": [list(r) for r in ROLES],
        "kinds": [
            {"key": k.key, "label": k.label, "role": k.role, "description": k.description}
            for k in site_components.CATALOGUE.values()
        ],
        "items": [_item(c) for c in draft],
        "selected": selected,
    }


def _item(c) -> dict:
    """One component as the browser draws it; col and row are None when it has no square."""
    pos = layout.position(c)
    return {
        "id": c.id,
        "kind": c.kind,
        "name": c.name,
        "col": pos[0] if pos else None,
        "row": pos[1] if pos else None,
    }


def show(draft, selected: str | None, key: str) -> dict | None:
    """Draw the designer; returns the browser's latest action (or None before the first)."""
    return _designer(layout=args(draft, selected), key=key, default=None)
