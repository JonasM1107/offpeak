"""Build the detailed 3D models of the site view in Blender and export one GLB file each.

Run (Blender without its window), from the repository root:

    /Applications/Blender.app/Contents/MacOS/Blender --background \
        --python scripts/blender/build_models.py -- app/ui/models

Every model is built from code, so it can be changed and rebuilt at any time. The page
(app/ui/site_scene.html) reads two things from each model:
- each object's custom property "part" (exported as glTF extras): the same part names
  the fact sheets use (shell, container, condensers, ...), so clicking a part still
  lights it up. Objects without a part are plain scenery.
- each material's name (white, clay, roof, ...): the page swaps it for its own material
  of that name, so every model matches the rest of the scene. "door" glows while the
  furnace runs, "windows" at night, "screen" while a charger charges.

Moving parts (fans, rotor blades, the battery's charge bar, charger screens) are drawn
by the page itself, because they change with the hour.

Units are metres. Most models are written in the page's own coordinates (three.js:
x right, y up, z towards the camera) with the t_* helpers, so numbers can be compared
with the page directly. The furnace hall was written first, in Blender's coordinates
(z up, -y towards the camera), with the b_* helpers.
"""

import math
import sys
from collections import defaultdict
from pathlib import Path

import bpy

OUT_DIR = Path(sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "app/ui/models")

# Colours only matter for previews in Blender; the page uses its own materials by name.
COLOURS = {
    "white": (0.96, 0.96, 0.95),
    "clay": (0.9, 0.87, 0.83),
    "roof": (0.78, 0.74, 0.69),
    "frame": (0.62, 0.58, 0.52),
    "concrete": (0.75, 0.72, 0.68),
    "asphalt": (0.68, 0.66, 0.63),
    "steel": (0.58, 0.55, 0.5),
    "ink": (0.05, 0.05, 0.045),
    "orange": (1.0, 0.11, 0.0),
    "glassDark": (0.03, 0.03, 0.03),
    "door": (0.05, 0.05, 0.045),
    "windows": (0.03, 0.03, 0.03),
    "screen": (0.7, 0.67, 0.62),
}
MATS = {}


def reset():
    """An empty scene with fresh materials, before each model."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    MATS.clear()
    for name, rgb in COLOURS.items():
        m = bpy.data.materials.new(name)
        m.diffuse_color = (*rgb, 1)
        MATS[name] = m


def finish(obj, material, part, bevel):
    """Give an object its material and part, and soften its edges a little."""
    if bevel > 0.005:
        mod = obj.modifiers.new("bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 2 if bevel >= 0.1 else 1  # small parts: one bevel step is enough
        mod.limit_method = "ANGLE"
    obj.data.materials.append(MATS[material])
    if part:
        obj["part"] = part
    return obj


# ── Blender coordinates: x right, y away from the camera, z up ──────────────
def b_box(sx, sy, sz, x, y, z, material, part, bevel=0.04, rot=(0, 0, 0)):
    """A box sx × sy × sz centred on (x, y, z)."""
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, z))
    obj = bpy.context.active_object
    obj.scale = (sx, sy, sz)
    obj.rotation_euler = rot
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    return finish(obj, material, part, min(bevel, sx / 2.2, sy / 2.2, sz / 2.2))


def b_cyl(r_bottom, r_top, h, x, y, z, material, part, seg=20, axis="z"):
    """A cylinder (or cone) of height h centred on (x, y, z), standing along `axis`."""
    rot = {"z": (0, 0, 0), "x": (0, math.pi / 2, 0), "y": (math.pi / 2, 0, 0)}[axis]
    bpy.ops.mesh.primitive_cone_add(
        vertices=seg, radius1=r_bottom, radius2=r_top, depth=h, location=(x, y, z), rotation=rot
    )
    obj = bpy.context.active_object
    bpy.ops.object.transform_apply(rotation=True)
    return finish(obj, material, part, 0)


def b_prism(width, depth, rise, z0, material, part, bevel=0.06):
    """A pitched roof: the ridge runs along y, at height z0 + rise."""
    w, d = width / 2, depth / 2
    verts = [
        (-w, -d, z0),
        (w, -d, z0),
        (0, -d, z0 + rise),
        (-w, d, z0),
        (w, d, z0),
        (0, d, z0 + rise),
    ]
    faces = [(0, 1, 2), (5, 4, 3), (0, 3, 4, 1), (1, 4, 5, 2), (2, 5, 3, 0)]
    mesh = bpy.data.meshes.new("prism")
    mesh.from_pydata(verts, [], faces)
    obj = bpy.data.objects.new("prism", mesh)
    bpy.context.collection.objects.link(obj)
    return finish(obj, material, part, bevel)


# ── Page coordinates (three.js): x right, y up, z towards the camera ───────
def t_box(w, h, d, x, y, z, material, part=None, bevel=0.04, rz=0.0, ry=0.0):
    """A box w (x) × h (up) × d (z) centred on (x, y, z) in page coordinates; rz and ry
    turn it about the page's z and y axes, like mesh.rotation.z / .y on the page."""
    return b_box(w, d, h, x, -z, y, material, part, bevel, rot=(0, -rz, ry))


def t_cyl(r_bottom, r_top, h, x, y, z, material, part=None, seg=20, axis="y"):
    """A cylinder in page coordinates; axis 'y' stands up, 'x' and 'z' lie down."""
    return b_cyl(
        r_bottom, r_top, h, x, -z, y, material, part, seg, {"y": "z", "x": "x", "z": "y"}[axis]
    )


def wheel(x, y, z, r=0.36, width=0.26):
    """A tyre with a hub cap, axle along x."""
    t_cyl(r, r, width, x, y, z, "ink", None, 16, axis="x")
    t_cyl(r * 0.55, r * 0.55, width + 0.02, x, y, z, "steel", None, 12, axis="x")


def export(name):
    """Apply the bevels, join objects with the same part and material, write name.glb."""
    groups = defaultdict(list)
    for obj in bpy.context.scene.objects:
        groups[(obj.get("part"), obj.data.materials[0].name)].append(obj)
    for (part, material), objs in groups.items():
        for obj in objs:
            bpy.context.view_layer.objects.active = obj
            for mod in list(obj.modifiers):
                bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.ops.object.select_all(action="DESELECT")
        for obj in objs:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = objs[0]
        if len(objs) > 1:
            bpy.ops.object.join()
        joined = bpy.context.view_layer.objects.active
        joined.name = f"{part or 'scenery'}_{material}"
        if part:
            joined["part"] = part
    path = OUT_DIR / f"{name}.glb"
    bpy.ops.export_scene.gltf(
        filepath=str(path),
        export_format="GLB",
        export_apply=True,
        export_extras=True,
        export_yup=True,
        export_texcoords=False,  # no textures, so no texture coordinates: a smaller file
    )
    print("exported", path, path.stat().st_size // 1024, "KB")


# ── The models ──────────────────────────────────────────────────────────────
def furnace_hall():
    """The electric furnace: an 8 m × 9 m annex with a glowing roller door and a chimney.
    Parts: shell, lining, chimney, busbars, elements."""
    W, D = 8.0, 9.0
    PLINTH, WALL = 0.5, 5.6
    TOP = PLINTH + WALL
    b_box(W + 0.3, D + 0.3, PLINTH, 0, 0, PLINTH / 2, "concrete", "shell", 0.06)
    b_box(W, D, WALL, 0, 0, PLINTH + WALL / 2, "white", "shell", 0.12)
    for side in (-1, 1):
        for i in range(12):  # trapezoid sheet ribs
            y = -D / 2 + 0.55 + i * (D - 1.1) / 11
            b_box(
                0.1,
                0.12,
                WALL - 0.3,
                side * (W / 2 + 0.04),
                y,
                PLINTH + WALL / 2,
                "clay",
                "shell",
                0.02,
            )
        b_box(0.08, D - 1.6, 0.7, side * (W / 2 + 0.06), 0, TOP - 0.9, "windows", "shell", 0.03)
    b_box(W + 0.25, D + 0.25, 0.25, 0, 0, TOP + 0.12, "frame", "shell", 0.04)
    for side in (-1, 1):
        b_cyl(
            0.1, 0.1, D + 0.4, side * (W / 2 + 0.35), 0, TOP + 0.1, "steel", "shell", 10, axis="y"
        )
    b_prism(W + 0.7, D + 0.6, 1.4, TOP + 0.24, "roof", "shell")
    ridge = TOP + 0.24 + 1.4
    b_box(1.3, D - 2.0, 0.55, 0, 0, ridge + 0.15, "roof", "shell", 0.06)
    for i in range(9):
        for side in (-1, 1):
            b_box(
                0.06,
                0.5,
                0.3,
                side * 0.68,
                -D / 2 + 1.6 + i * 0.72,
                ridge + 0.15,
                "glassDark",
                "shell",
                0.01,
            )
    front = -D / 2
    b_box(4.2, 0.18, 4.5, 0, front - 0.05, PLINTH + 2.25, "roof", "lining", 0.06)
    b_box(3.3, 0.12, 3.6, 0, front - 0.15, PLINTH + 1.8, "door", "lining", 0.03)
    for i in range(10):
        b_box(3.2, 0.06, 0.05, 0, front - 0.23, PLINTH + 0.25 + i * 0.36, "ink", "lining", 0.01)
    b_box(5.0, 1.5, 0.16, 0, front - 0.75, PLINTH + 4.7, "frame", "shell", 0.04)
    for side in (-1, 1):
        b_box(0.1, 1.3, 0.1, side * 2.3, front - 0.65, PLINTH + 4.45, "steel", "shell", 0.02)
        b_cyl(0.18, 0.18, 0.9, side * 2.7, front - 1.4, 0.45, "white", "shell", 16)
        b_cyl(0.19, 0.19, 0.15, side * 2.7, front - 1.4, 0.82, "orange", "shell", 16)
    b_box(1.6, 0.8, 2.2, -3.2, front - 0.35, 1.1, "clay", "busbars", 0.1)
    b_box(1.62, 0.82, 0.14, -3.2, front - 0.35, 1.75, "orange", "busbars", 0.03)
    b_box(0.5, 0.05, 0.6, -3.2, front - 0.77, 1.2, "ink", "busbars", 0.02)
    b_cyl(0.09, 0.09, TOP - 2.2, -3.6, front - 0.12, 2.2 + (TOP - 2.2) / 2, "steel", "busbars", 10)
    for i in range(5):
        y = -3.0 + i * 1.5
        b_cyl(0.22, 0.18, 0.6, 0, y, ridge + 0.72, "orange", "elements", 16)
        b_cyl(0.26, 0.26, 0.08, 0, y, ridge + 1.04, "ink", "elements", 16)
    cx, cy, cb, ct = 2.0, 2.0, TOP, 17.0
    b_cyl(0.9, 0.72, ct - cb, cx, cy, (cb + ct) / 2, "white", "chimney", 24)
    for z in (10.0, 13.5):
        r = 0.9 - (z - cb) / (ct - cb) * 0.18
        b_cyl(r + 0.04, r + 0.04, 0.35, cx, cy, z, "clay", "chimney", 24)
    b_cyl(0.8, 0.8, 0.35, cx, cy, ct + 0.1, "ink", "chimney", 24)
    pz = 14.8
    b_cyl(1.35, 1.35, 0.1, cx, cy, pz, "steel", "chimney", 24)
    for k in range(8):
        a = k * math.pi / 4
        b_cyl(
            0.04,
            0.04,
            0.9,
            cx + math.cos(a) * 1.3,
            cy + math.sin(a) * 1.3,
            pz + 0.45,
            "steel",
            "chimney",
            6,
        )
    for side in (-1, 1):
        b_cyl(
            0.035, 0.035, pz - cb, cx + 0.92, cy + side * 0.22, (cb + pz) / 2, "steel", "chimney", 6
        )
    for i in range(int((pz - cb) / 0.45)):
        b_cyl(
            0.025, 0.025, 0.44, cx + 0.92, cy, cb + 0.3 + i * 0.45, "steel", "chimney", 6, axis="y"
        )
    b_box(0.12, 1.2, 2.2, W / 2 + 0.06, 2.6, PLINTH + 1.1, "clay", "shell", 0.04)
    b_box(0.8, 1.6, 0.25, W / 2 + 0.45, 2.6, 0.12, "concrete", "shell", 0.03)
    b_box(0.5, 1.6, 0.25, W / 2 + 0.3, 2.6, 0.37, "concrete", "shell", 0.03)


def main_hall():
    """The production hall, 22 m × 14 m. The sawtooth roof keeps the old positions, so the
    rooftop solar drawn by the page still sits on it. No parts: it is scenery."""
    t_box(22.4, 0.5, 14.4, 0, 0.25, 0, "concrete", bevel=0.06)
    t_box(22, 7.6, 14, 0, 4.3, 0, "white", bevel=0.3)
    for i in range(4):  # sawtooth roof with north-light glazing, as on the page
        t_box(5.2, 2.4, 13.6, -7.8 + i * 5.2, 9, 0, "roof", bevel=0.2, rz=0.32)
        t_box(0.6, 1.9, 13, -5.6 + i * 5.2, 9.2, 0, "glassDark", bevel=0.02, rz=0.32)
    t_box(22.3, 0.3, 14.3, 0, 8.15, 0, "frame", bevel=0.05)  # eave band
    for side in (-1, 1):
        t_cyl(0.11, 0.11, 22.6, 0, 8.0, side * 7.35, "steel", seg=10, axis="x")  # gutters
        for i in range(13):  # trapezoid sheet ribs on the gable ends
            t_box(0.12, 7.0, 0.1, side * 11.04, 4.4, -6.3 + i * 1.05, "clay", bevel=0.02)
        t_cyl(0.08, 0.08, 7.6, side * 10.7, 4.2, 7.18, "steel", seg=8)  # downpipes
    for i in range(5):  # front windows (light up at night) with sills
        t_box(2.4, 1.6, 0.2, -8 + i * 4, 5.2, 7.02, "windows", bevel=0.06)
        t_box(2.6, 0.12, 0.35, -8 + i * 4, 4.35, 7.12, "frame", bevel=0.03)
    t_box(4.4, 5.0, 0.3, -6, 2.5, 7.05, "roof", bevel=0.08)  # loading door surround
    for i in range(7):
        t_box(4.2, 0.08, 0.32, -6, 0.6 + i * 0.65, 7.1, "frame", bevel=0.02)
    t_box(5.6, 0.18, 2.2, -6, 5.4, 8.1, "frame", bevel=0.04)  # canopy
    for side in (-1, 1):
        t_box(0.12, 0.12, 2.0, -6 + side * 2.6, 5.2, 8.0, "steel", bevel=0.02)
        t_box(0.35, 0.9, 0.35, -6 + side * 2.4, 0.45, 7.45, "ink", bevel=0.05)  # dock bumpers
    t_box(1.2, 2.4, 0.15, 3.0, 1.7, 7.08, "clay", bevel=0.04)  # staff door
    t_box(2.2, 0.15, 1.0, 3.0, 3.1, 7.6, "frame", bevel=0.03)
    t_box(1.6, 0.3, 1.2, 3.0, 0.15, 7.6, "concrete", bevel=0.03)
    for i in range(3):  # outdoor units and a duct at the back
        t_box(2.0, 1.4, 1.2, -6 + i * 3.4, 1.2, -7.8, "clay", bevel=0.12)
        t_cyl(0.42, 0.42, 0.06, -6 + i * 3.4, 1.3, -8.42, "ink", seg=16, axis="z")
    t_cyl(0.3, 0.3, 8.0, -2.6, 2.4, -7.6, "steel", seg=12, axis="x")
    for i in range(10):  # ladder to the roof on the east end
        t_box(0.05, 0.05, 0.5, 11.15, 0.8 + i * 0.7, 3.0, "steel", bevel=0.01)
    for dz in (-0.25, 0.25):
        t_box(0.06, 7.4, 0.06, 11.15, 4.3, 3.0 + dz, "steel", bevel=0.01)


def cold_store():
    """The cold store, 12 m × 9 m. Parts: panels, door, condensers (fans: the page)."""
    t_box(12.3, 0.4, 9.3, 0, 0.2, 0, "concrete", "panels", 0.05)
    t_box(12, 5.1, 9, 0, 2.95, 0, "white", "panels", 0.35)
    for i in range(1, 10):  # insulated panel joints, front and back
        for z in (4.52, -4.52):
            t_box(0.05, 4.9, 0.05, -6 + i * 1.2, 2.95, z, "frame", "panels", 0.01)
    for i in range(1, 7):  # joints on the ends
        for x in (-6.02, 6.02):
            t_box(0.05, 4.9, 0.05, x, 2.95, -4.5 + i * 1.28, "frame", "panels", 0.01)
    t_box(12.2, 0.25, 9.2, 0, 5.6, 0, "frame", "panels", 0.04)  # roof edge
    t_box(2.9, 3.7, 0.2, 3.4, 1.95, 4.55, "roof", "door", 0.06)  # sliding cold-room door
    t_box(2.6, 3.4, 0.25, 3.4, 1.9, 4.62, "clay", "door", 0.08)
    t_box(0.08, 0.6, 0.12, 4.4, 1.9, 4.8, "ink", "door", 0.02)
    t_box(5.8, 0.1, 0.12, 4.9, 3.75, 4.7, "steel", "door", 0.02)  # door rail
    t_box(2.6, 0.12, 0.14, 3.4, 0.26, 4.72, "orange", "door", 0.02)  # threshold marking
    t_box(3.6, 0.15, 1.6, 3.4, 4.5, 5.3, "frame", "door", 0.03)  # canopy
    for side in (-1, 1):
        t_box(0.3, 0.8, 0.3, 3.4 + side * 1.6, 0.6, 4.75, "ink", "door", 0.04)  # bumpers
    for x in (-2.8, 2.8):  # condenser housings on the roof (the page adds the fans)
        t_box(3.6, 1.2, 2.6, x, 6.1, 0, "clay", "condensers", 0.2)
        t_cyl(0.9, 0.9, 0.12, x, 6.75, 0, "ink", "condensers", 24)
        for k in range(4):
            t_box(0.12, 0.5, 0.12, x - 1.6 + k * 1.07, 5.6, 1.15, "steel", "condensers", 0.02)
    for k in range(3):  # refrigerant pipes down the west end
        t_cyl(0.07, 0.07, 5.4, -6.15, 3.1, -1.0 + k * 0.3, "steel", "condensers", 8)


def battery_container():
    """One 20 ft battery container, 9 m × 2.4 m. Parts: container, cells. The page adds
    the state-of-charge bar on its front."""
    t_box(9, 2.5, 2.4, 0, 1.45, 0, "white", "container", 0.12)
    for i in range(22):  # corrugated sides
        for z in (1.22, -1.22):
            t_box(0.12, 2.25, 0.06, -4.2 + i * 0.4, 1.45, z, "clay", "container", 0.02)
    for x in (-4.4, 4.4):  # corner castings
        for z in (-1.1, 1.1):
            for y in (0.32, 2.62):
                t_box(0.22, 0.2, 0.22, x, y, z, "ink", "container", 0.03)
    t_box(0.05, 2.2, 0.08, 4.52, 1.45, -0.6, "ink", "container", 0.01)  # door bars
    t_box(0.05, 2.2, 0.08, 4.52, 1.45, 0.6, "ink", "container", 0.01)
    t_box(0.06, 0.5, 0.5, 4.53, 2.1, 0, "orange", "container", 0.02)  # hazard label
    for i in range(6):  # rack doors on the back
        t_box(1.0, 2.0, 0.05, -3.4 + i * 1.3, 1.45, -1.25, "ink", "cells", 0.01)
        t_box(0.6, 0.15, 0.05, -3.4 + i * 1.3, 2.25, -1.28, "steel", "cells", 0.01)
    for x in (-3.2, 3.2):  # skids
        t_box(0.5, 0.2, 2.5, x, 0.1, 0, "concrete", "container", 0.03)


def battery_hvac():
    """The battery's air conditioner. Part: hvac."""
    t_box(1.4, 1.2, 1.6, 0, 0.7, 0, "clay", "hvac", 0.15)
    t_cyl(0.45, 0.45, 0.08, -0.75, 0.8, 0, "ink", "hvac", 20, axis="x")
    for i in range(5):
        t_box(0.04, 0.8, 0.04, -0.8, 0.8, -0.4 + i * 0.2, "steel", "hvac", 0.01)
    t_box(1.5, 0.15, 1.7, 0, 0.05, 0, "concrete", "hvac", 0.03)


def battery_pcs():
    """The battery's power converter cabinet. Part: pcs."""
    t_box(1.6, 2.2, 1.2, 0, 1.2, 0, "clay", "pcs", 0.15)
    t_box(1.62, 0.14, 1.22, 0, 1.9, 0, "orange", "pcs", 0.03)
    for i in range(6):  # vent slots
        t_box(1.0, 0.04, 0.04, 0, 0.6 + i * 0.12, 0.62, "ink", "pcs", 0.01)
    t_box(0.35, 0.25, 0.04, 0.45, 1.5, 0.62, "ink", "pcs", 0.01)
    t_box(1.7, 0.1, 1.3, 0, 0.05, 0, "concrete", "pcs", 0.03)


def heat_pump_unit():
    """One outdoor heat pump unit, 2.4 m × 1.1 m, two fans (the page spins the blades).
    Parts: unit, fans."""
    t_box(2.4, 1.6, 1.1, 0, 0.95, 0, "white", "unit", 0.15)
    t_box(2.42, 0.18, 1.12, 0, 1.68, 0, "clay", "unit", 0.04)  # lid
    for k in (-0.55, 0.55):
        t_cyl(0.46, 0.46, 0.08, k, 1.0, 0.56, "frame", "fans", 24, axis="z")  # fan shroud
        t_cyl(0.42, 0.42, 0.06, k, 1.0, 0.58, "ink", "fans", 24, axis="z")
    for i in range(7):  # coil fins on the back
        t_box(2.0, 0.05, 0.04, 0, 0.45 + i * 0.17, -0.57, "steel", "unit", 0.01)
    for x in (-0.9, 0.9):  # feet
        t_box(0.2, 0.15, 1.0, x, 0.075, 0, "ink", "unit", 0.02)


def heat_tank():
    """The heat pump's buffer tank. Part: tank."""
    t_cyl(0.8, 0.8, 3.0, 0, 1.7, 0, "white", "tank", 28)
    t_cyl(0.84, 0.84, 0.4, 0, 2.6, 0, "clay", "tank", 28)
    t_cyl(0.82, 0.82, 0.12, 0, 0.95, 0, "clay", "tank", 28)
    t_cyl(0.55, 0.3, 0.3, 0, 3.35, 0, "white", "tank", 20)  # domed top
    for k in range(3):  # legs
        a = k * 2 * math.pi / 3
        t_cyl(0.06, 0.06, 0.35, math.cos(a) * 0.6, 0.17, math.sin(a) * 0.6, "steel", "tank", 6)
    t_box(0.3, 0.3, 0.06, 0, 1.9, 0.81, "orange", "tank", 0.02)  # gauge


def ev_charger():
    """One charging pillar on a small plinth. Parts: chargers; the screen is the page's
    own material per charger, so it lights while that charger charges."""
    t_box(1.0, 0.18, 0.8, 0, 0.09, 0, "concrete", "chargers", 0.04)
    t_box(0.7, 1.9, 0.5, 0, 1.1, 0, "white", "chargers", 0.15)
    t_box(0.72, 0.12, 0.52, 0, 1.95, 0, "orange", "chargers", 0.03)
    t_box(0.4, 0.3, 0.06, 0, 1.6, 0.27, "screen", "chargers", 0.03)
    t_box(0.16, 0.3, 0.12, 0.25, 1.05, 0.3, "ink", "chargers", 0.03)  # plug holster
    for side in (-1, 1):  # protection bollards
        t_cyl(0.1, 0.1, 0.8, side * 0.65, 0.4, 0.55, "steel", "chargers", 10)


def e_car():
    """A small electric van, 1.9 m × 4.3 m, nose towards -z (the charger)."""
    t_box(1.9, 0.75, 4.3, 0, 0.72, 1.4, "clay", bevel=0.3)
    t_box(1.7, 0.75, 2.4, 0, 1.45, 1.75, "roof", bevel=0.3)
    t_box(1.72, 0.45, 0.06, 0, 1.45, 0.5, "glassDark", bevel=0.05, rz=0)  # windscreen
    for side in (-1, 1):
        t_box(0.05, 0.4, 2.0, side * 0.86, 1.5, 1.85, "glassDark", bevel=0.03)
        t_box(0.05, 0.08, 3.6, side * 0.96, 0.75, 1.4, "orange", bevel=0.02)  # stripe
        for dz in (0.0, 2.8):
            wheel(side * 0.95, 0.36, dz)
    t_box(1.6, 0.12, 0.06, 0, 0.82, -0.75, "white", bevel=0.02)  # light bar


def e_truck():
    """An electric box truck, 2.6 m × 10 m, cab towards -z (the charger)."""
    t_box(2.5, 2.7, 2.2, 0, 1.95, -3.6, "white", bevel=0.35)  # cab
    t_box(2.3, 1.1, 0.06, 0, 2.5, -4.72, "glassDark", bevel=0.05)  # windscreen
    for side in (-1, 1):
        t_box(0.06, 0.9, 1.0, side * 1.26, 2.5, -3.9, "glassDark", bevel=0.04)
        t_box(0.12, 0.35, 0.08, side * 1.35, 2.6, -4.5, "ink", bevel=0.02)  # mirrors
    t_box(2.42, 0.3, 0.1, 0, 0.75, -4.72, "ink", bevel=0.03)  # grille
    t_box(2.0, 0.08, 0.06, 0, 1.0, -4.74, "white", bevel=0.02)  # light bar
    t_box(2.6, 3.3, 7.2, 0, 2.55, 1.3, "white", bevel=0.15)  # box body
    for side in (-1, 1):
        t_box(0.04, 0.35, 7.0, side * 1.31, 1.4, 1.3, "orange", bevel=0.02)  # stripe
        t_box(0.04, 0.12, 7.0, side * 1.31, 3.9, 1.3, "orange", bevel=0.01)
        t_box(0.15, 0.6, 4.0, side * 1.15, 0.65, 0.4, "ink", bevel=0.05)  # battery packs
        t_box(0.05, 0.35, 0.35, side * 1.27, 1.6, -2.3, "orange", bevel=0.03)  # charge port
    t_box(2.3, 0.4, 9.6, 0, 0.62, -0.2, "steel", bevel=0.05)  # chassis
    for dz, r in ((-3.6, 0.5), (2.6, 0.5), (3.9, 0.5)):
        for side in (-1, 1):
            wheel(side * 1.12, r, dz, r, 0.4)
    t_box(2.6, 0.1, 0.1, 0, 0.95, 4.95, "ink", bevel=0.02)  # rear bumper
    for side in (-1, 1):
        t_box(0.05, 3.0, 0.05, side * 0.65, 2.5, 4.92, "steel", bevel=0.01)  # door seams


def transformer():
    """The grid connection: transformer on a pad, with radiator fins, bushings and a fence.
    Matches the page's old layout around (2, 0, 3). Scenery."""
    t_box(8, 0.3, 7, 2, 0.15, 3, "concrete", bevel=0.08)
    t_box(3.6, 3.2, 2.6, 2, 1.9, 3, "clay", bevel=0.25)
    t_box(3.7, 0.2, 2.7, 2, 3.5, 3, "frame", bevel=0.04)
    for i in range(7):  # radiator fins, front and back
        for z in (4.9, 1.1):
            t_box(0.12, 2.4, 1.2, 0.4 + i * 0.55, 1.8, z if z > 3 else 1.1, "steel", bevel=0.02)
    for i in range(3):  # bushings with insulator rings
        t_cyl(0.18, 0.28, 1.4, 1 + i, 4.2, 3, "ink", seg=10)
        for k in range(3):
            t_cyl(0.3, 0.3, 0.06, 1 + i, 3.8 + k * 0.35, 3, "frame", seg=10)
    t_box(0.6, 0.6, 0.06, 2, 2.2, 4.32, "orange", bevel=0.02)  # warning sign
    for i in range(9):  # fence
        for z in (-0.6, 6.6):
            t_cyl(0.06, 0.06, 1.8, -2 + i, 0.9, z, "frame", seg=6)
    for z in (-0.6, 6.6):
        t_box(8.1, 0.05, 0.05, 2, 1.7, z, "frame", bevel=0.01)
        t_box(8.1, 0.05, 0.05, 2, 0.4, z, "frame", bevel=0.01)


MODELS = {
    "furnace_hall": furnace_hall,
    "main_hall": main_hall,
    "cold_store": cold_store,
    "battery_container": battery_container,
    "battery_hvac": battery_hvac,
    "battery_pcs": battery_pcs,
    "heat_pump_unit": heat_pump_unit,
    "heat_tank": heat_tank,
    "ev_charger": ev_charger,
    "e_car": e_car,
    "e_truck": e_truck,
    "transformer": transformer,
}

OUT_DIR.mkdir(parents=True, exist_ok=True)
for model_name, build in MODELS.items():
    reset()
    build()
    export(model_name)
