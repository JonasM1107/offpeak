"""Build the furnace hall of the 3D site view in Blender and export it as a GLB file.

Run (Blender without its window):

    /Applications/Blender.app/Contents/MacOS/Blender --background \
        --python scripts/blender/furnace_hall.py -- app/ui/models/furnace_hall.glb

The model replaces the simple boxes of the electric furnace in app/ui/site_scene.html.
The page reads two things from it:
- each object's custom property "part" (exported as glTF extras), the same part names
  the fact sheet uses (shell, lining, chimney, busbars, elements), so clicking a part
  still lights it up;
- each material's name (white, clay, roof, ...), which the page swaps for its own
  material of that name, so the hall matches the rest of the scene. "door" glows when
  the furnace runs, "windows" when it is night.

Units are metres. Blender's Z points up; the exporter turns it into three.js's Y-up,
and Blender's -Y (where the door is) becomes three.js's +Z (the side facing the camera).
The footprint is 8 m × 9 m, as before.
"""

import math
import sys
from collections import defaultdict

import bpy

OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "furnace_hall.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)

# Colours only matter for previews in Blender; the page uses its own materials by name.
COLOURS = {
    "white": (0.96, 0.96, 0.95),
    "clay": (0.9, 0.87, 0.83),
    "roof": (0.78, 0.74, 0.69),
    "frame": (0.62, 0.58, 0.52),
    "concrete": (0.75, 0.72, 0.68),
    "steel": (0.58, 0.55, 0.5),
    "ink": (0.05, 0.05, 0.045),
    "orange": (1.0, 0.11, 0.0),
    "glassDark": (0.03, 0.03, 0.03),
    "door": (0.05, 0.05, 0.045),
    "windows": (0.03, 0.03, 0.03),
}
MATS = {}
for name, rgb in COLOURS.items():
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, 1)
    MATS[name] = m


def finish(obj, material, part, bevel):
    """Give an object its material and part, and soften its edges a little."""
    if bevel > 0:
        mod = obj.modifiers.new("bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 2 if bevel >= 0.05 else 1  # small parts: one bevel step is enough
        mod.limit_method = "ANGLE"
    obj.data.materials.append(MATS[material])
    obj["part"] = part
    return obj


def box(sx, sy, sz, x, y, z, material, part, bevel=0.04):
    """A box sx × sy × sz (x across, y deep, z up) centred on (x, y, z)."""
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, z))
    obj = bpy.context.active_object
    obj.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(scale=True)
    return finish(obj, material, part, min(bevel, sx / 2.2, sy / 2.2, sz / 2.2))


def cyl(r_bottom, r_top, h, x, y, z, material, part, seg=24, axis="z"):
    """A cylinder (or cone) of height h centred on (x, y, z), standing along `axis`."""
    rot = {"z": (0, 0, 0), "x": (0, math.pi / 2, 0), "y": (math.pi / 2, 0, 0)}[axis]
    bpy.ops.mesh.primitive_cone_add(
        vertices=seg, radius1=r_bottom, radius2=r_top, depth=h, location=(x, y, z), rotation=rot
    )
    obj = bpy.context.active_object
    bpy.ops.object.transform_apply(rotation=True)
    return finish(obj, material, part, 0)


def gable_roof(width, depth, rise, z0, material, part):
    """A pitched roof: the ridge runs front to back (along y), at height z0 + rise."""
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
    mesh = bpy.data.meshes.new("roof")
    mesh.from_pydata(verts, [], faces)
    obj = bpy.data.objects.new("roof", mesh)
    bpy.context.collection.objects.link(obj)
    return finish(obj, material, part, 0.06)


# ── The building ────────────────────────────────────────────────────────────
W, D = 8.0, 9.0  # footprint
PLINTH, WALL = 0.5, 5.6  # concrete base, wall height above it
TOP = PLINTH + WALL  # 6.1, where the roof starts

box(W + 0.3, D + 0.3, PLINTH, 0, 0, PLINTH / 2, "concrete", "shell", 0.06)
box(W, D, WALL, 0, 0, PLINTH + WALL / 2, "white", "shell", 0.12)

# trapezoid sheet cladding: vertical ribs on both long sides
for side in (-1, 1):
    for i in range(12):
        y = -D / 2 + 0.55 + i * (D - 1.1) / 11
        box(
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
    # a band of high windows under the eaves, lit at night
    box(0.08, D - 1.6, 0.7, side * (W / 2 + 0.06), 0, TOP - 0.9, "windows", "shell", 0.03)

# eave band, gutter and roof with a raised ridge vent along the top
box(W + 0.25, D + 0.25, 0.25, 0, 0, TOP + 0.12, "frame", "shell", 0.04)
for side in (-1, 1):
    cyl(0.1, 0.1, D + 0.4, side * (W / 2 + 0.35), 0, TOP + 0.1, "steel", "shell", 10, axis="y")
gable_roof(W + 0.7, D + 0.6, 1.4, TOP + 0.24, "roof", "shell")
RIDGE = TOP + 0.24 + 1.4
box(1.3, D - 2.0, 0.55, 0, 0, RIDGE + 0.15, "roof", "shell", 0.06)
for i in range(9):  # louvre slats on both sides of the vent
    y = -D / 2 + 1.6 + i * 0.72
    for side in (-1, 1):
        box(0.06, 0.5, 0.3, side * 0.68, y, RIDGE + 0.15, "glassDark", "shell", 0.01)

# ── Front: the furnace door ─────────────────────────────────────────────────
FRONT = -D / 2
box(4.2, 0.18, 4.5, 0, FRONT - 0.05, PLINTH + 2.25, "roof", "lining", 0.06)  # door surround
box(3.3, 0.12, 3.6, 0, FRONT - 0.15, PLINTH + 1.8, "door", "lining", 0.03)  # glows when running
for i in range(10):  # roller-door slats
    box(3.2, 0.06, 0.05, 0, FRONT - 0.23, PLINTH + 0.25 + i * 0.36, "ink", "lining", 0.01)
box(5.0, 1.5, 0.16, 0, FRONT - 0.75, PLINTH + 4.7, "frame", "shell", 0.04)  # canopy
for side in (-1, 1):
    box(0.1, 1.3, 0.1, side * 2.3, FRONT - 0.65, PLINTH + 4.45, "steel", "shell", 0.02)  # brackets
    cyl(0.18, 0.18, 0.9, side * 2.7, FRONT - 1.4, 0.45, "white", "shell", 16)  # bollards
    cyl(0.19, 0.19, 0.15, side * 2.7, FRONT - 1.4, 0.82, "orange", "shell", 16)

# ── Busbar cabinet and the cable up to the roof ────────────────────────────
box(1.6, 0.8, 2.2, -3.2, FRONT - 0.35, 1.1, "clay", "busbars", 0.1)
box(1.62, 0.82, 0.14, -3.2, FRONT - 0.35, 1.75, "orange", "busbars", 0.03)
box(0.5, 0.05, 0.6, -3.2, FRONT - 0.77, 1.2, "ink", "busbars", 0.02)  # display
cyl(0.09, 0.09, TOP - 2.2, -3.6, FRONT - 0.12, 2.2 + (TOP - 2.2) / 2, "steel", "busbars", 10)

# ── Heating elements: vents along the ridge, orange like everything electric ──
for i in range(5):
    y = -3.0 + i * 1.5
    cyl(0.22, 0.18, 0.6, 0, y, RIDGE + 0.72, "orange", "elements", 16)
    cyl(0.26, 0.26, 0.08, 0, y, RIDGE + 1.04, "ink", "elements", 16)

# ── Chimney at the back right, with a platform and a ladder ────────────────
CX, CY, CB, CT = 2.0, 2.0, TOP, 17.0  # position, bottom, top
cyl(0.9, 0.72, CT - CB, CX, CY, (CB + CT) / 2, "white", "chimney", 28)
for z in (10.0, 13.5):
    r = 0.9 - (z - CB) / (CT - CB) * 0.18
    cyl(r + 0.04, r + 0.04, 0.35, CX, CY, z, "clay", "chimney", 28)  # bands
cyl(0.8, 0.8, 0.35, CX, CY, CT + 0.1, "ink", "chimney", 28)  # cap
PZ = 14.8
cyl(1.35, 1.35, 0.1, CX, CY, PZ, "steel", "chimney", 28)  # platform
for k in range(8):  # railing posts
    a = k * math.pi / 4
    cyl(
        0.04,
        0.04,
        0.9,
        CX + math.cos(a) * 1.3,
        CY + math.sin(a) * 1.3,
        PZ + 0.45,
        "steel",
        "chimney",
        6,
    )
for side in (-1, 1):  # ladder rails
    cyl(0.035, 0.035, PZ - CB, CX + 0.92, CY + side * 0.22, (CB + PZ) / 2, "steel", "chimney", 6)
for i in range(int((PZ - CB) / 0.45)):  # rungs
    cyl(0.025, 0.025, 0.44, CX + 0.92, CY, CB + 0.3 + i * 0.45, "steel", "chimney", 6, axis="y")

# ── Side door with steps (east) ─────────────────────────────────────────────
box(0.12, 1.2, 2.2, W / 2 + 0.06, 2.6, PLINTH + 1.1, "clay", "shell", 0.04)
box(0.8, 1.6, 0.25, W / 2 + 0.45, 2.6, 0.12, "concrete", "shell", 0.03)
box(0.5, 1.6, 0.25, W / 2 + 0.3, 2.6, 0.37, "concrete", "shell", 0.03)

# ── Join objects with the same part and material: fewer nodes in the file ──
groups = defaultdict(list)
for obj in bpy.context.scene.objects:
    groups[(obj["part"], obj.data.materials[0].name)].append(obj)
for (part, material), objs in groups.items():
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objs:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    for obj in objs:  # apply the bevels before joining
        bpy.context.view_layer.objects.active = obj
        for mod in list(obj.modifiers):
            bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1:
        bpy.ops.object.join()
    joined = bpy.context.view_layer.objects.active
    joined.name = f"{part}_{material}"
    joined["part"] = part

bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format="GLB",
    export_apply=True,
    export_extras=True,
    export_yup=True,
    export_texcoords=False,  # no textures, so no texture coordinates: a smaller file
)
print("exported", OUT)
