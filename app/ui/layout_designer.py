"""The "Edit site" layout designer: the 3D site scene in edit mode, as a two-way component.

The scene (site_scene.html with `edit`) shows the site on a 64 x 64 grid with Jonas's
Blender models, a parts list and drag and drop. Every action (add, move, remove, select)
comes back here; the page passes it to offpeak/layout.py, which decides whether it is
allowed. The component's frame (models/index.html) is served from the models folder, so
the browser loads each model file once.
"""

import hashlib
import json

import streamlit.components.v1 as components

from ui import site_scene

_designer = components.declare_component("offpeak_site_editor", path=str(site_scene.MODELS))


def rebuild_key(draft) -> str:
    """Changes when the scene must be drawn again: a part added or removed, renamed or
    resized. Moving a part does not change it; the frame just moves the model."""
    parts = [
        [c.id, c.kind, c.name, {k: v for k, v in c.params.items() if k not in ("col", "row")}]
        for c in draft
    ]
    return hashlib.sha1(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()


def show(data: dict, draft, selected: str | None, key: str) -> dict | None:
    """Draw the designer for the scene data `data` (site_scene.payload with edit=True);
    returns the latest action from the browser, or None before the first one."""
    height = site_scene.height_for(data)
    return _designer(
        html=site_scene.render_html(data),
        key=key,
        default=None,
        squares=site_scene.squares(draft),
        selected=selected,
        height=height,
        scene_key=rebuild_key(draft),  # not "key": that name is Streamlit's widget key
    )
