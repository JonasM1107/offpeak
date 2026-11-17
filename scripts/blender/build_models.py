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
from mathutils import Vector

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
    "tree": (0.89, 0.87, 0.84),
    "panel": (0.1, 0.12, 0.16),  # the page puts its solar cell texture on this one
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
def t_box(w, h, d, x, y, z, material, part=None, bevel=0.04, rz=0.0, ry=0.0, rx=0.0):
    """A box w (x) × h (up) × d (z) centred on (x, y, z) in page coordinates; rx, ry and rz
    turn it about the page's axes, like mesh.rotation.x / .y / .z on the page (use one)."""
    return b_box(w, d, h, x, -z, y, material, part, bevel, rot=(rx, -rz, ry))


def t_cyl(r_bottom, r_top, h, x, y, z, material, part=None, seg=20, axis="y"):
    """A cylinder in page coordinates; axis 'y' stands up, 'x' and 'z' lie down."""
    return b_cyl(
        r_bottom, r_top, h, x, -z, y, material, part, seg, {"y": "z", "x": "x", "z": "y"}[axis]
    )


def t_seg(p0, p1, r, material, part=None, seg=6):
    """A round bar from point p0 to p1 (page coordinates), for lattices and cables."""
    a, b = Vector((p0[0], -p0[2], p0[1])), Vector((p1[0], -p1[2], p1[1]))
    d = b - a
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=seg, radius=r, depth=d.length, location=(a + b) / 2
    )
    obj = bpy.context.active_object
    obj.rotation_euler = Vector((0, 0, 1)).rotation_difference(d).to_euler()
    bpy.ops.object.transform_apply(rotation=True)
    return finish(obj, material, part, 0)


def t_sphere(r, x, y, z, material, part=None, seg=16):
    """A smooth sphere in page coordinates."""
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=seg, ring_count=seg // 2 + 2, radius=r, location=(x, -z, y)
    )
    obj = bpy.context.active_object
    for f in obj.data.polygons:
        f.use_smooth = True
    return finish(obj, material, part, 0)


def wheel(x, y, z, r=0.36, width=0.26):
    """A tyre with a hub cap, axle along x."""
    t_cyl(r, r, width, x, y, z, "ink", None, 16, axis="x")
    t_cyl(r * 0.55, r * 0.55, width + 0.02, x, y, z, "steel", None, 12, axis="x")


def export(name, texcoords=False):
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
        # only models with a texture (the solar module) need texture coordinates
        export_texcoords=texcoords,
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


def wind_base():
    """The turbine's foundation, tower door and converter cabinet (the page draws the
    tower, whose height depends on the turbine). Parts: foundation, tower, converter."""
    t_cyl(2.6, 2.4, 0.6, 0, 0.3, 0, "concrete", "foundation", 32)
    t_cyl(1.05, 1.05, 0.12, 0, 0.66, 0, "steel", "foundation", 24)  # flange
    t_box(0.6, 1.8, 0.12, 0, 1.6, 0.84, "frame", "tower", 0.05)  # door
    t_box(0.5, 1.6, 0.06, 0, 1.6, 0.9, "clay", "tower", 0.04)
    t_box(1.2, 0.3, 0.6, 0, 0.6, 1.2, "concrete", "tower", 0.04)  # step
    t_box(1.4, 1.8, 1.0, 2.4, 0.9, 1.4, "clay", "converter", 0.15)
    t_box(1.42, 0.12, 1.02, 2.4, 1.45, 1.4, "orange", "converter", 0.03)
    for i in range(5):
        t_box(0.9, 0.04, 0.04, 2.4, 0.4 + i * 0.12, 1.92, "ink", "converter", 0.01)
    t_cyl(0.07, 0.07, 1.6, 1.4, 0.12, 1.0, "ink", "converter", 8, axis="x")  # cable


def wind_nacelle():
    """The nacelle, centred on its middle, rotor side towards +z. Part: nacelle."""
    t_box(1.5, 1.5, 3.8, 0, 0, 0, "white", "nacelle", 0.55)
    t_box(1.52, 0.1, 3.0, 0, -0.35, -0.2, "clay", "nacelle", 0.03)  # seam band
    t_cyl(0.55, 0.55, 0.35, 0, -0.9, -0.2, "steel", "nacelle", 20)  # yaw bearing
    for i in range(4):  # cooler on top at the back
        t_box(1.2, 0.06, 0.06, 0, 0.82, -1.2 + i * 0.3, "steel", "nacelle", 0.01)
    t_box(1.25, 0.08, 1.1, 0, 0.78, -0.75, "frame", "nacelle", 0.02)
    t_cyl(0.03, 0.03, 0.8, 0, 1.15, -1.6, "ink", "nacelle", 6)  # anemometer mast
    t_box(0.5, 0.05, 0.05, 0, 1.55, -1.6, "ink", "nacelle", 0.01)


def wind_hub():
    """The spinner (nose cone) in the rotor's centre, pointing to +z. Part: nacelle."""
    t_cyl(0.65, 0.65, 0.4, 0, 0, 0, "white", "nacelle", 24, axis="z")
    t_cyl(0.66, 0.08, 1.0, 0, 0, 0.7, "orange", "nacelle", 24, axis="z")


def wind_blade():
    """One rotor blade, 5 m from the rotor centre's hub ring outwards along +y: tapered
    and twisted like a real blade. The page turns it and scales it to the turbine.
    Part: blades."""
    import bmesh  # noqa: PLC0415 (only inside Blender)

    t_cyl(0.2, 0.18, 0.5, 0, 0.6, 0, "white", "blades", 16)  # root
    mesh = bpy.data.meshes.new("blade")
    bm = bmesh.new()
    rings, pts = [], 12
    for i in range(11):
        t = i / 10
        length = 0.8 + t * 4.2  # page y of this section
        chord = 0.78 * (1 - 0.7 * t) * (0.75 + 0.25 * min(1, t * 5))
        thick = chord * (0.28 - 0.16 * t)
        twist = 0.45 * (1 - t)
        ring = []
        for k in range(pts):
            a = 2 * math.pi * k / pts
            cx, cz = math.cos(a) * chord / 2, math.sin(a) * thick / 2
            x = cx * math.cos(twist) - cz * math.sin(twist)
            z = cx * math.sin(twist) + cz * math.cos(twist)
            ring.append(bm.verts.new((x, -z, length)))  # page (x, y, z) -> Blender (x, -z, y)
        rings.append(ring)
    for r0, r1 in zip(rings, rings[1:], strict=False):
        for k in range(pts):
            bm.faces.new((r0[k], r0[(k + 1) % pts], r1[(k + 1) % pts], r1[k]))
    bm.faces.new(list(reversed(rings[-1])))
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new("blade", mesh)
    bpy.context.collection.objects.link(obj)
    for f in mesh.polygons:
        f.use_smooth = True
    finish(obj, "white", "blades", 0)


def pv_module():
    """One solar module, 1.75 m × 1.04 m, lying flat (the page tilts it): glass with the
    cell texture, in an aluminium frame. Part: modules."""
    t_box(1.71, 0.04, 1.0, 0, 0, 0, "panel", "modules", 0)
    for z in (-0.51, 0.51):
        t_box(1.75, 0.06, 0.03, 0, 0, z, "steel", "modules", 0.01)
    for x in (-0.865, 0.865):
        t_box(0.03, 0.06, 1.04, x, 0, 0, "steel", "modules", 0.01)


def pv_rack():
    """One rack row of the solar field, 22.4 m long, tilted 0.5 rad towards +z (south),
    centred on the row (the page places one per row). Part: mounting."""
    up_y, up_z = math.sin(0.5), -math.cos(0.5)
    for k in range(5):
        x = -10.5 + k * 5.3
        t_cyl(0.07, 0.07, 1.19, x, 0.6, 0.85, "steel", "mounting", 8)  # front leg
        t_cyl(0.07, 0.07, 2.52, x, 1.25, -0.85, "steel", "mounting", 8)  # back leg
        for z in (0.85, -0.85):
            t_box(0.3, 0.12, 0.3, x, 0.06, z, "concrete", "mounting", 0.03)  # footings
        t_box(0.08, 0.1, 2.3, x, 1.62, 0, "steel", "mounting", 0.01, rx=0.5)  # purlin
        t_box(0.05, 0.05, 1.9, x, 0.95, 0, "steel", "mounting", 0.01, rx=-0.75)  # brace
    for d in (-0.6, 0.6):
        t_box(22.4, 0.08, 0.1, 0, 1.65 + up_y * d, up_z * d, "steel", "mounting", 0.01, rx=0.5)
    t_box(22.0, 0.08, 0.16, 0, 0.5, -0.95, "ink", "mounting", 0.02)  # cable tray


def pv_inverter():
    """A string inverter on its post. Part: inverter."""
    t_cyl(0.08, 0.08, 1.2, 0, 0.6, 0, "steel", "inverter", 8)
    t_box(0.9, 0.7, 0.35, 0, 1.4, 0.05, "white", "inverter", 0.08)
    t_box(0.92, 0.08, 0.37, 0, 1.62, 0.05, "orange", "inverter", 0.02)
    t_box(0.25, 0.15, 0.04, 0.2, 1.35, 0.24, "ink", "inverter", 0.01)
    for i in range(4):
        t_box(0.04, 0.4, 0.04, -0.3 + i * 0.12, 1.35, 0.24, "frame", "inverter", 0.01)


def pylon():
    """The grid pylon: an 18 m lattice tower with two cross-arms, insulator strings and
    three cables down to the transformer's bushings. Its origin is the tower's foot; the
    page puts it 7 m behind and 6 m left of the transformer. Scenery."""
    height, base, top, levels = 18.0, 1.84, 0.3, 6

    def half(y):
        return base - (base - top) * y / height

    ys = [i * height / levels for i in range(levels + 1)]
    corners = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
    for y0, y1 in zip(ys, ys[1:], strict=False):
        h0, h1 = half(y0), half(y1)
        for k, (cx, cz) in enumerate(corners):
            t_seg((cx * h0, y0, cz * h0), (cx * h1, y1, cz * h1), 0.09, "frame")  # legs
            nx, nz = corners[(k + 1) % 4]
            t_seg((cx * h1, y1, cz * h1), (nx * h1, y1, nz * h1), 0.05, "frame")  # ring
            t_seg((cx * h0, y0, cz * h0), (nx * h1, y1, nz * h1), 0.035, "frame", seg=4)  # X
            t_seg((nx * h0, y0, nz * h0), (cx * h1, y1, cz * h1), 0.035, "frame", seg=4)
    for y, reach in ((16.5, 4.5), (13.5, 3.6)):  # cross-arms, as trusses
        for side in (-1, 1):
            t_seg((0, y, -0.3), (side * reach, y, -0.15), 0.06, "frame")
            t_seg((0, y, 0.3), (side * reach, y, 0.15), 0.06, "frame")
            t_seg((side * half(y), y - 1.2, 0), (side * reach, y, 0), 0.04, "frame", seg=4)
    t_seg((0, height, 0), (0, height + 1.6, 0), 0.06, "frame")  # earth-wire peak
    for x in (-4.5, 4.5):  # earth-wire clamps on the top arm
        t_cyl(0.12, 0.12, 0.2, x, 16.35, 0, "ink", seg=8)
    ends = []
    for x in (1.4, 2.6, 3.5):  # insulator strings on the lower arm
        for k in range(6):
            t_cyl(0.16, 0.16, 0.08, x, 13.3 - k * 0.2, 0, "ink", seg=10)
        t_seg((x, 13.45, 0), (x, 12.2, 0), 0.03, "steel", seg=4)
        ends.append((x, 12.2, 0))
    for i, (ex, ey, ez) in enumerate(ends):  # cables sagging down to the bushings
        tx, ty, tz = 6 + i, 4.9, 7
        pts = []
        for k in range(9):
            t = k / 8
            pts.append(
                (
                    ex + (tx - ex) * t,
                    ey + (ty - ey) * t - 1.2 * math.sin(math.pi * t),
                    ez + (tz - ez) * t,
                )
            )
        for a, b in zip(pts, pts[1:], strict=False):
            t_seg(a, b, 0.03, "ink", seg=4)
    for cx, cz in corners:  # footings
        t_box(0.8, 0.4, 0.8, cx * base, 0.2, cz * base, "concrete", bevel=0.05)


def site_meter():
    """The site meter in the middle of the island, where every flow meets. The page adds
    the pulsing ring around it. Scenery."""
    t_cyl(3.0, 3.0, 0.4, 0, 0.2, 0, "white", seg=48)
    t_cyl(3.05, 3.05, 0.08, 0, 0.42, 0, "frame", seg=48)
    t_cyl(1.2, 1.2, 1.6, 0, 1.0, 0, "ink", seg=32)
    t_cyl(1.3, 1.3, 0.16, 0, 1.86, 0, "white", seg=32)  # cap
    t_cyl(0.7, 0.4, 0.3, 0, 2.05, 0, "white", seg=24)
    t_box(0.7, 0.4, 0.06, 0, 1.25, 1.2, "orange", bevel=0.02)  # display
    for k in range(8):  # cable glands where the paths come in
        a = k * math.pi / 4
        t_box(0.5, 0.3, 0.5, math.cos(a) * 2.6, 0.5, math.sin(a) * 2.6, "clay", bevel=0.06, ry=-a)


def tree_round():
    """A round tree, about 6 m tall at scale 1 (the page scales each tree). Scenery; the
    crown takes the page's tree material."""
    t_cyl(0.3, 0.22, 2.4, 0, 1.2, 0, "frame", seg=10)
    t_seg((0, 2.0, 0), (0.7, 2.9, 0.2), 0.1, "frame")
    t_sphere(2.0, 0, 4.0, 0, "tree", seg=20)
    t_sphere(1.4, 0.9, 4.9, 0.4, "tree", seg=16)
    t_sphere(1.3, -0.8, 4.6, -0.5, "tree", seg=16)


def tree_tall():
    """A tall, narrow tree (a conifer) in three tiers. Scenery."""
    t_cyl(0.25, 0.2, 1.6, 0, 0.8, 0, "frame", seg=10)
    for i, (r, h) in enumerate(((2.0, 2.8), (1.6, 2.4), (1.1, 2.0))):
        bpy.ops.mesh.primitive_cone_add(
            vertices=20, radius1=r, radius2=0.05, depth=h, location=(0, 0, 2.3 + i * 1.5)
        )
        obj = bpy.context.active_object
        for f in obj.data.polygons:
            f.use_smooth = True
        finish(obj, "tree", None, 0)


def fence_segment():
    """One post of the island's fence and the rails to the next post, 2.625 m along +x
    (the page puts 140 of them in a circle). Scenery."""
    t_cyl(0.08, 0.08, 1.6, 0, 0.8, 0, "frame", seg=8)
    t_cyl(0.11, 0.11, 0.06, 0, 1.62, 0, "frame", seg=8)
    for y in (0.35, 0.9, 1.5):
        t_seg((0, y, 0), (2.625, y, 0), 0.035, "frame", seg=5)
    for k in range(1, 7):  # light vertical wires
        x = k * 2.625 / 7
        t_seg((x, 0.2, 0), (x, 1.5, 0), 0.012, "frame", seg=3)


# ── The home (homeowner profile) ────────────────────────────────────────────
ROOF_DEG = 34.0  # the house's roof pitch (NRW solar cadastre); the page tilts its modules to match


def t_gable(w, d, rise, y0, x, z, material, part=None, overhang=0.4):
    """A pitched roof in page coordinates: the ridge runs along x, the slopes face +z (the
    street side) and -z. w × d is the footprint under it, y0 the eave height."""
    hw, hd = w / 2 + overhang, d / 2 + overhang
    rise = rise + overhang * math.tan(math.radians(ROOF_DEG))
    pts = [
        (-hw, y0, hd),
        (hw, y0, hd),
        (hw, y0 + rise, 0),
        (-hw, y0 + rise, 0),
        (-hw, y0, -hd),
        (hw, y0, -hd),
    ]
    verts = [(px + x, -(pz + z), py) for px, py, pz in pts]  # page -> Blender
    faces = [(0, 1, 2, 3), (3, 2, 5, 4), (0, 3, 4), (1, 5, 2), (0, 4, 5, 1)]
    mesh = bpy.data.meshes.new("gable")
    mesh.from_pydata(verts, [], faces)
    obj = bpy.data.objects.new("gable", mesh)
    bpy.context.collection.objects.link(obj)
    return finish(obj, material, part, 0.05)


def semi_detached():
    """A pair of semi-detached houses, 2 × 7 m wide and 10 m deep, two storeys and a pitched
    roof whose street side faces +z. The right half (x 0..7) is ours: the page puts the
    solar modules on its street-side roof and calls the whole half "House". The left half
    is the neighbours'. Origin: middle of the party wall, at the street-side wall line minus
    5 m (so the houses span z -5..5). Part of our half: house."""
    W, D, EAVE = 7.0, 10.0, 5.8
    rise = D / 2 * math.tan(math.radians(ROOF_DEG))
    for side, part, wall in ((1, "house", "white"), (-1, None, "clay")):
        cx = side * W / 2
        t_box(W + 0.1, 0.5, D + 0.2, cx, 0.25, 0, "concrete", part, 0.05)  # plinth
        t_box(W, EAVE - 0.5, D, cx, 0.25 + EAVE / 2, 0, wall, part, 0.08)
        t_gable(W, D, rise, EAVE, cx, 0, "roof", part)
        for z in (D / 2 + 0.38, -D / 2 - 0.38):  # gutters
            t_cyl(0.09, 0.09, W + 0.8, cx, EAVE - 0.05, z, "steel", part, 10, axis="x")
        t_cyl(0.07, 0.07, EAVE, cx + side * (W / 2 - 0.3), EAVE / 2, D / 2 + 0.4, "steel", part, 8)
        for fz, face in ((D / 2 + 0.03, 1), (-D / 2 - 0.03, -1)):  # windows, two floors
            for wx in (-1.6, 1.6):
                for wy in (1.9, 4.4):
                    if face == 1 and wy == 1.9 and wx == -side * 1.6:
                        continue  # the front door goes here
                    t_box(1.3, 1.25, 0.08, cx + wx, wy, fz, "windows", part, 0.03)
                    t_box(1.5, 0.1, 0.25, cx + wx, wy - 0.7, fz + face * 0.1, "frame", part, 0.02)
        dx = cx - side * 1.6  # front door with canopy and steps
        t_box(1.1, 2.2, 0.12, dx, 1.6, D / 2 + 0.05, "ink" if part else "frame", part, 0.03)
        t_box(1.8, 0.12, 1.0, dx, 2.95, D / 2 + 0.5, "frame", part, 0.03)
        t_box(1.6, 0.25, 1.0, dx, 0.12, D / 2 + 0.55, "concrete", part, 0.03)
    t_box(0.12, EAVE, D + 0.3, 0, EAVE / 2 + 0.25, 0, "frame", None, 0.02)  # party wall line
    t_box(0.7, 1.8, 0.7, -4.8, EAVE + rise - 0.2, -1.6, "clay", None, 0.06)  # neighbours' chimney
    t_box(0.8, 0.12, 0.8, -4.8, EAVE + rise + 0.75, -1.6, "frame", None, 0.02)
    t_box(
        0.5, 0.06, 0.18, W - 0.9, 3.0, D / 2 + 0.06, "orange", "house", 0.02
    )  # house number plate


def carport():
    """A carport, 3.6 m × 6 m, flat roof sloping to the back, open on the street side (+z).
    Scenery; the page adds the wallbox and the car."""
    for x in (-1.7, 1.7):
        for z in (-2.8, 2.8):
            t_box(0.14, 2.6, 0.14, x, 1.3, z, "white", None, 0.03)
    t_box(3.9, 0.18, 6.3, 0, 2.7, 0, "white", None, 0.06, rx=-0.04)
    t_box(3.92, 0.1, 6.32, 0, 2.6, 0, "orange", None, 0.02, rx=-0.04)  # fascia stripe
    t_box(3.5, 0.06, 5.8, 0, 0.03, 0, "concrete", None, 0.03)
    t_box(3.6, 1.8, 0.08, 0, 1.0, -2.85, "clay", None, 0.03)  # back panel


def wallbox():
    """A wall-mounted car charger with a status window (the page's "screen" material) and
    a coiled cable. Part: chargers."""
    t_box(0.42, 0.55, 0.16, 0, 0.0, 0, "white", "chargers", 0.06)
    t_box(0.3, 0.06, 0.02, 0, 0.12, 0.085, "screen", "chargers", 0.01)
    t_box(0.44, 0.06, 0.18, 0, -0.25, 0, "orange", "chargers", 0.02)
    t_cyl(0.16, 0.16, 0.05, 0, -0.55, 0.12, "ink", "chargers", 16, axis="z")  # cable coil
    t_cyl(0.11, 0.11, 0.06, 0, -0.55, 0.12, "white", "chargers", 16, axis="z")


def ev_car():
    """A compact electric car, 1.85 m × 4.3 m, nose towards -z. Scenery."""
    t_box(1.85, 0.7, 4.3, 0, 0.65, 0, "white", bevel=0.3)
    t_box(1.6, 0.62, 2.3, 0, 1.25, 0.25, "glassDark", bevel=0.28)
    t_box(1.62, 0.08, 2.32, 0, 1.58, 0.25, "white", bevel=0.05)  # roof
    for side in (-1, 1):
        t_box(0.04, 0.08, 3.4, side * 0.93, 0.62, 0, "orange", bevel=0.01)  # stripe
        for dz in (-1.35, 1.35):
            wheel(side * 0.86, 0.34, dz, 0.34, 0.24)
    t_box(1.5, 0.08, 0.05, 0, 0.8, -2.16, "white", bevel=0.02)  # light bar
    t_box(0.15, 0.15, 0.04, 0.75, 0.85, -1.4, "ink", bevel=0.02)  # charge port flap


def home_battery():
    """A wall-mounted home battery (stacked modules) with its inverter above. Parts:
    battery, inverter."""
    t_box(0.65, 0.16, 0.42, 0, 0.08, 0, "ink", "battery", 0.03)  # base
    for k in range(4):
        t_box(0.6, 0.3, 0.36, 0, 0.32 + k * 0.31, 0, "white", "battery", 0.04)
        t_box(0.61, 0.03, 0.37, 0, 0.47 + k * 0.31, 0, "frame", "battery", 0.01)
    t_box(0.62, 0.08, 0.38, 0, 1.47, 0, "orange", "battery", 0.02)
    t_box(0.62, 0.7, 0.24, 0, 2.05, -0.06, "white", "inverter", 0.06)
    t_box(0.2, 0.08, 0.02, 0.12, 2.2, 0.07, "ink", "inverter", 0.01)


def home_meter():
    """The house's meter pillar at the front garden, where every flow meets. Scenery."""
    t_box(0.9, 1.4, 0.45, 0, 0.7, 0, "white", None, 0.08)
    t_box(0.92, 0.1, 0.47, 0, 1.35, 0, "orange", None, 0.02)
    t_box(0.3, 0.2, 0.03, 0, 1.0, 0.24, "ink", None, 0.01)
    t_box(1.2, 0.12, 0.7, 0, 0.06, 0, "concrete", None, 0.03)


def grid_cabinet():
    """The grid operator's street cabinet, where the house's cable comes from, and a street
    lamp. Scenery."""
    t_box(1.1, 1.25, 0.45, 0, 0.62, 0, "clay", None, 0.08)
    for i in range(5):
        t_box(0.6, 0.03, 0.03, 0, 0.35 + i * 0.12, 0.24, "frame", None, 0.01)
    t_box(0.25, 0.25, 0.03, 0.3, 0.95, 0.24, "orange", None, 0.01)
    t_cyl(0.07, 0.05, 5.0, 1.6, 2.5, 0, "frame", None, 8)
    t_box(0.9, 0.12, 0.25, 1.95, 5.0, 0, "frame", None, 0.03)
    t_box(0.5, 0.05, 0.2, 2.2, 4.93, 0, "screen", None, 0.01)


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
    "wind_base": wind_base,
    "wind_nacelle": wind_nacelle,
    "wind_hub": wind_hub,
    "wind_blade": wind_blade,
    "pv_module": pv_module,
    "pv_rack": pv_rack,
    "pv_inverter": pv_inverter,
    "pylon": pylon,
    "site_meter": site_meter,
    "tree_round": tree_round,
    "tree_tall": tree_tall,
    "fence_segment": fence_segment,
    "semi_detached": semi_detached,
    "carport": carport,
    "wallbox": wallbox,
    "ev_car": ev_car,
    "home_battery": home_battery,
    "home_meter": home_meter,
    "grid_cabinet": grid_cabinet,
}

OUT_DIR.mkdir(parents=True, exist_ok=True)
for model_name, build in MODELS.items():
    reset()
    build()
    export(model_name, texcoords=model_name == "pv_module")
