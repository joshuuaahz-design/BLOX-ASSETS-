"""Roblox-style Porsche 911 GT3 RS (992), built with Blender's Python API.

Chunky bevelled blocks, wedges and flat-shaded smooth-plastic materials, so the car
reads like a Roblox build. Livery follows reference/gt3rs_reference.jpg: the paint
colour is sampled from that photo, and the photo is packed into the .blend as a
reference image (it is not exported or rendered).

Run:
    blender -b -P build_gt3rs_roblox.py -- [out_dir] [--no-render]

Writes gt3rs_roblox.blend, gt3rs_roblox.fbx, gt3rs_roblox.glb and
gt3rs_roblox_render.png to out_dir (default: ./out next to this script).

Coordinates: metres, +X = front of the car, +Y = car's left, +Z = up.
Export layout for Roblox Studio: one mesh per material group (Body, Glass, Trim,
Lamps, Aero, Livery) plus four separate wheels, so wheels can be constrained
to a chassis.
"""

import math
import os
import sys

import bpy
import bmesh
from mathutils import Euler, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
RENDER = "--no-render" not in ARGS
POSITIONAL = [a for a in ARGS if not a.startswith("--")]
OUT_DIR = os.path.abspath(POSITIONAL[0] if POSITIONAL else os.path.join(HERE, "out"))
REF_PATH = os.path.join(HERE, "reference", "gt3rs_reference.jpg")
os.makedirs(OUT_DIR, exist_ok=True)

FALLBACK_PAINT = "#5cc3e3"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene


def new_coll(name, parent=None):
    c = bpy.data.collections.new(name)
    (parent or scene.collection).children.link(c)
    return c


CAR = new_coll("GT3RS_Roblox")
GROUPS = {n: new_coll(n, CAR) for n in ("Body", "Glass", "Trim", "Lamps", "Aero", "Livery", "Wheels")}
STUDIO = new_coll("Studio")
REF = new_coll("Reference")


# ---------------------------------------------------------------- reference photo

def sample_paint():
    """Average the photo's blue paint at a few body spots; brightest blue wins."""
    if not os.path.exists(REF_PATH):
        return FALLBACK_PAINT, None
    img = bpy.data.images.load(REF_PATH)
    img.pack()
    w, h = img.size
    px = list(img.pixels)
    spots = [(150, 530), (230, 535), (560, 500), (600, 430), (200, 470), (440, 380), (520, 420)]
    best = None
    for (x, y) in spots:
        acc = [0.0, 0.0, 0.0]
        n = 0
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                xx, yy = x + dx, (h - 1) - (y + dy)
                if 0 <= xx < w and 0 <= yy < h:
                    i = (yy * w + xx) * 4
                    for k in range(3):
                        acc[k] += px[i + k]
                    n += 1
        r, g, b = (c / n for c in acc)
        score = (b - r) + 0.5 * (r + g + b) / 3
        if b > r + 0.15 and (best is None or score > best[0]):
            best = (score, (r, g, b))
    if best is None:
        return FALLBACK_PAINT, img
    r, g, b = best[1]
    return "#%02x%02x%02x" % tuple(int(max(0, min(1, c)) * 255) for c in (r, g, b)), img


PAINT_HEX, REF_IMG = sample_paint()
if REF_IMG is not None:
    ref = bpy.data.objects.new("Reference_Photo", None)
    ref.empty_display_type = 'IMAGE'
    ref.data = REF_IMG
    ref.empty_display_size = 4.0
    ref.location = (0, 6, 1.5)
    ref.rotation_euler = Euler((math.pi / 2, 0, math.pi))
    ref.hide_render = True
    REF.objects.link(ref)


# ---------------------------------------------------------------- materials (SmoothPlastic look)

def lin(hex_str):
    h = hex_str.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (*out, 1.0)


def material(name, hex_str, rough=0.45, metal=0.0, emit=None, strength=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = lin(hex_str)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit:
        b.inputs["Emission Color"].default_value = lin(emit)
        b.inputs["Emission Strength"].default_value = strength
    m.diffuse_color = lin(hex_str)
    return m


M_PAINT = material("Paint_GulfBlue", PAINT_HEX, 0.38)
M_BLACK = material("Plastic_Black", "#1c1d21", 0.55)
M_CARBON = material("Carbon_Satin", "#121316", 0.6, 0.0)
M_GLASS = material("Glass_Tint", "#0d1116", 0.08, 0.3)
M_TIRE = material("Rubber_Tire", "#18181a", 0.85)
M_RIM = material("Rim_Gunmetal", "#26282c", 0.35, 0.5)
M_LAMP = material("Lamp_White", "#f4f8ff", 0.2, 0.0, "#ffffff", 4.0)
M_LENS = material("Lamp_Lens", "#2a2e33", 0.05, 0.8)
M_TAIL = material("Lamp_Red", "#ff1a2a", 0.3, 0.0, "#ff1424", 6.0)
M_STEEL = material("Brake_Steel", "#7a7d82", 0.4, 0.8)
M_BASE = material("Baseplate_Grey", "#a3a2a5", 0.6)


# ---------------------------------------------------------------- part helpers

def finish(name, bm, mat, group, loc, rot, bevel):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=bm.edges[:], offset=bevel, offset_type='OFFSET',
                        segments=1, profile=0.5, affect='EDGES', clamp_overlap=True)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = False
    me.materials.append(mat)
    o = bpy.data.objects.new(name, me)
    o.location = loc
    o.rotation_euler = rot if isinstance(rot, Euler) else Euler(rot)
    GROUPS[group].objects.link(o)
    return o


def part(name, size, loc, mat, group="Body", rot=(0, 0, 0), bevel=0.035):
    """Roblox Part: a bevelled block."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= size[0]
        v.co.y *= size[1]
        v.co.z *= size[2]
    return finish(name, bm, mat, group, loc, rot, min(bevel, min(size) * 0.3))


def wedge(name, size, loc, mat, group="Body", rot=(0, 0, 0), bevel=0.03):
    """Roblox WedgePart: full height at -X, sloping down to the bottom edge at +X."""
    hx, hy, hz = size[0] / 2, size[1] / 2, size[2] / 2
    bm = bmesh.new()
    v = [bm.verts.new(p) for p in [(-hx, -hy, -hz), (hx, -hy, -hz), (hx, hy, -hz),
                                   (-hx, hy, -hz), (-hx, -hy, hz), (-hx, hy, hz)]]
    for f in [(0, 1, 2, 3), (0, 3, 5, 4), (1, 2, 5, 4), (0, 1, 4), (3, 5, 2)]:
        bm.faces.new([v[i] for i in f])
    return finish(name, bm, mat, group, loc, rot, min(bevel, min(size) * 0.25))


def cyl(name, r, depth, loc, mat, group, rot=(math.pi / 2, 0, 0), seg=20, bevel=0.02):
    """Roblox Cylinder: axis along Y by default (wheels)."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg,
                          radius1=r, radius2=r, depth=depth)
    return finish(name, bm, mat, group, loc, rot, min(bevel, depth * 0.3))


def text(name, body, size, loc, rot, mat, group="Livery"):
    cu = bpy.data.curves.new(name, 'FONT')
    cu.body = body
    cu.size = size
    cu.extrude = 0.008
    cu.shear = 0.25
    cu.align_x = 'CENTER'
    cu.align_y = 'CENTER'
    tmp = bpy.data.objects.new(name + "_tmp", cu)
    scene.collection.objects.link(tmp)
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    bpy.data.objects.remove(tmp)
    bpy.data.curves.remove(cu)
    me.materials.clear()
    me.materials.append(mat)
    o = bpy.data.objects.new(name, me)
    o.location = loc
    o.rotation_euler = rot
    GROUPS[group].objects.link(o)
    return o


FLIP = (0, 0, math.pi)  # wedge sloping down toward -X
SIDES = ((-1, "R"), (1, "L"))  # +Y is the car's left


def on_slope(x0, z_top, x_len, z_drop, x):
    """Height of a wedge's sloped face at x (wedge tall end at x0)."""
    return z_top - (x - x0) * z_drop / x_len


# ---------------------------------------------------------------- lower body

part("Chassis_Floor", (4.30, 1.80, 0.14), (0.0, 0, 0.30), M_BLACK, "Trim")
part("Body_Tub_Rear", (2.95, 1.62, 0.46), (-0.62, 0, 0.58), M_PAINT)
part("Body_Tub_Front", (1.40, 1.62, 0.30), (1.50, 0, 0.51), M_PAINT)
part("Body_Doors", (1.55, 1.92, 0.42), (-0.05, 0, 0.58), M_PAINT)
part("Door_Stripe_Black", (1.57, 1.94, 0.07), (-0.05, 0, 0.42), M_BLACK, "Livery")
for s, side in SIDES:
    part(f"Side_Skirt_{side}", (1.60, 0.10, 0.08), (-0.05, 0.98 * s, 0.30), M_CARBON, "Aero")
    part(f"Door_Shutline_{side}", (0.02, 0.012, 0.36), (0.55, 0.962 * s, 0.60), M_BLACK, "Trim")
    part(f"Door_Handle_{side}", (0.14, 0.02, 0.03), (0.05, 0.965 * s, 0.74), M_BLACK, "Trim")

# ---------------------------------------------------------------- front end

HOOD_X0, HOOD_LEN, HOOD_TOP, HOOD_DROP = 0.845, 1.25, 0.90, 0.24
wedge("Hood_Black", (HOOD_LEN, 0.92, HOOD_DROP), (HOOD_X0 + HOOD_LEN / 2, 0, HOOD_TOP - HOOD_DROP / 2), M_CARBON)
hood_tilt = math.atan2(HOOD_DROP, HOOD_LEN)
for nm, x, y, sz in (("Hood_Vent_R", 1.38, -0.22, (0.32, 0.20, 0.04)),
                     ("Hood_Vent_L", 1.38, 0.22, (0.32, 0.20, 0.04)),
                     ("Hood_Nostril", 1.82, 0.0, (0.22, 0.34, 0.04))):
    part(nm, sz, (x, y, on_slope(HOOD_X0, HOOD_TOP, HOOD_LEN, HOOD_DROP, x) + 0.012), M_BLACK, "Trim", rot=(0, hood_tilt, 0))
    for i in range(4):
        sx = x - sz[0] / 2 + (i + 0.5) * sz[0] / 4
        part(f"{nm}_Slat_{i}", (0.025, sz[1] * 0.9, 0.03), (sx, y, on_slope(HOOD_X0, HOOD_TOP, HOOD_LEN, HOOD_DROP, sx) + 0.04),
             M_CARBON, "Trim", rot=(0, hood_tilt + 0.5, 0), bevel=0.005)

NOSE_X0, NOSE_LEN, FENDER_TOP, NOSE_DROP = 1.925, 0.42, 0.99, 0.22
nose_tilt = math.atan2(NOSE_DROP, NOSE_LEN)
for s, side in SIDES:
    part(f"Front_Fender_{side}", (1.15, 0.54, 0.22), (1.35, 0.72 * s, 0.88), M_PAINT)
    wedge(f"Front_Fender_Nose_{side}", (NOSE_LEN, 0.54, NOSE_DROP), (NOSE_X0 + NOSE_LEN / 2, 0.72 * s, FENDER_TOP - NOSE_DROP / 2), M_PAINT)
    for i in range(4):
        part(f"Fender_Louver_{side}_{i}", (0.05, 0.28, 0.03), (0.90 + i * 0.08, 0.74 * s, 1.00), M_BLACK, "Trim", bevel=0.008)

    # round headlight sitting on the sloped fender nose, facing forward-up
    n = Vector((math.sin(nose_tilt), 0, math.cos(nose_tilt)))
    t = Vector((math.cos(nose_tilt), 0, -math.sin(nose_tilt)))
    c = Vector((NOSE_X0 + NOSE_LEN / 2, 0.72 * s, on_slope(NOSE_X0, FENDER_TOP, NOSE_LEN, NOSE_DROP, NOSE_X0 + NOSE_LEN / 2)))
    tilt = (0, nose_tilt, 0)
    cyl(f"Headlight_Housing_{side}", 0.16, 0.06, c + n * 0.02, M_LENS, "Lamps", rot=tilt, seg=20)
    cyl(f"Headlight_Ring_{side}", 0.12, 0.02, c + n * 0.055, M_LAMP, "Lamps", rot=tilt, seg=20, bevel=0.0)
    cyl(f"Headlight_Core_{side}", 0.09, 0.024, c + n * 0.058, M_LENS, "Lamps", rot=tilt, seg=20, bevel=0.0)
    for k, (dy, dt) in enumerate(((0.045, 0.045), (-0.045, 0.045), (0.045, -0.045), (-0.045, -0.045))):
        part(f"Headlight_DRL_{side}_{k}", (0.03, 0.03, 0.02), c + n * 0.075 + t * dt + Vector((0, dy, 0)),
             M_LAMP, "Lamps", rot=tilt, bevel=0.004)

part("Front_Bumper", (0.42, 1.90, 0.32), (2.14, 0, 0.53), M_PAINT)
part("Front_Intake", (0.06, 1.30, 0.18), (2.35, 0, 0.47), M_BLACK, "Trim")
part("Front_Intake_Bar", (0.07, 1.30, 0.03), (2.37, 0, 0.47), M_CARBON, "Trim")
part("Front_Splitter", (0.55, 1.96, 0.05), (2.15, 0, 0.27), M_CARBON, "Aero")
part("Splitter_Lip", (0.04, 1.96, 0.03), (2.43, 0, 0.30), M_PAINT, "Aero")
for s, side in SIDES:
    part(f"Splitter_Strut_{side}", (0.03, 0.03, 0.20), (2.30, 0.40 * s, 0.37), M_CARBON, "Aero", rot=(0, math.radians(-25), 0))
    part(f"Diveplane_Upper_{side}", (0.26, 0.14, 0.025), (2.30, 0.92 * s, 0.58), M_CARBON, "Aero", rot=(0, math.radians(-12), 0))
    part(f"Diveplane_Lower_{side}", (0.30, 0.16, 0.025), (2.30, 0.92 * s, 0.44), M_CARBON, "Aero", rot=(0, math.radians(-12), 0))
    part(f"Bumper_DRL_{side}", (0.03, 0.30, 0.04), (2.36, 0.62 * s, 0.62), M_LAMP, "Lamps")
    part(f"Front_Arch_Vent_{side}", (0.30, 0.04, 0.16), (1.88, 0.965 * s, 0.56), M_BLACK, "Trim")

# ---------------------------------------------------------------- cabin

WS_X0, WS_LEN, WS_TOP, WS_DROP = 0.16, 0.72, 1.26, 0.46
ws_tilt = math.atan2(WS_DROP, WS_LEN)
wedge("Windshield", (WS_LEN, 1.40, WS_DROP), (WS_X0 + WS_LEN / 2, 0, WS_TOP - WS_DROP / 2), M_GLASS, "Glass")
bx = WS_X0 + 0.10
part("Windshield_Banner", (0.14, 1.30, 0.02), (bx, 0, on_slope(WS_X0, WS_TOP, WS_LEN, WS_DROP, bx) + 0.005), M_BLACK, "Livery", rot=(0, ws_tilt, 0), bevel=0.004)
text("Windshield_Banner_Text", "GT3 RS", 0.09, (bx + 0.006, 0, on_slope(WS_X0, WS_TOP, WS_LEN, WS_DROP, bx) + 0.018),
     Euler((0, ws_tilt, math.pi / 2), 'ZYX'), M_PAINT)
part("Cabin_Glass", (1.16, 1.42, 0.46), (-0.42, 0, 1.03), M_GLASS, "Glass")
part("Roof_Black", (1.30, 1.36, 0.08), (-0.36, 0, 1.30), M_CARBON)
for s, side in SIDES:
    part(f"A_Pillar_{side}", (0.06, 0.06, 0.56), (0.52, 0.69 * s, 1.03), M_PAINT, rot=(0, -(math.pi / 2 - ws_tilt), 0))
    part(f"B_Pillar_{side}", (0.10, 0.06, 0.46), (-0.55, 0.70 * s, 1.03), M_PAINT)
    part(f"Mirror_Stalk_{side}", (0.06, 0.18, 0.05), (0.46, 0.92 * s, 0.86), M_BLACK, "Trim")
    part(f"Mirror_{side}", (0.14, 0.20, 0.12), (0.44, 1.05 * s, 0.92), M_PAINT)

FB_LEN, FB_DROP = 1.05, 0.46
wedge("Fastback", (FB_LEN, 1.42, FB_DROP), (-1.525, 0, 1.03), M_PAINT, rot=FLIP)
wedge("Rear_Window", (0.62, 1.10, 0.27), (-1.26, 0, 1.12), M_GLASS, "Glass", rot=FLIP)
for i in range(7):
    part(f"Engine_Louver_{i}", (0.05, 0.86, 0.025), (-1.82 - i * 0.07, 0, 0.93), M_BLACK, "Trim", bevel=0.006)

# ---------------------------------------------------------------- rear

for s, side in SIDES:
    part(f"Rear_Hip_{side}", (1.30, 0.46, 0.26), (-1.30, 0.80 * s, 0.93), M_PAINT)
    part(f"Side_Intake_{side}", (0.40, 0.04, 0.22), (-0.70, 0.965 * s, 0.66), M_BLACK, "Trim")
    part(f"Side_Intake_Slat_{side}", (0.38, 0.05, 0.03), (-0.70, 0.97 * s, 0.66), M_CARBON, "Trim", bevel=0.006)
part("Rear_Deck", (0.62, 1.92, 0.40), (-2.00, 0, 0.72), M_PAINT)
part("Rear_Ducktail", (0.20, 1.80, 0.06), (-2.28, 0, 0.94), M_CARBON, "Aero", rot=(0, math.radians(-15), 0))
part("Tail_Light_Bar", (0.05, 1.76, 0.06), (-2.32, 0, 0.84), M_TAIL, "Lamps")
part("Rear_Bumper_Black", (0.30, 1.90, 0.26), (-2.15, 0, 0.42), M_BLACK, "Trim")
for i, y in enumerate((-0.45, -0.15, 0.15, 0.45)):
    part(f"Diffuser_Fin_{i}", (0.30, 0.03, 0.14), (-2.20, y, 0.30), M_CARBON, "Aero")
for s, side in SIDES:
    cyl(f"Exhaust_{side}", 0.06, 0.16, (-2.30, 0.12 * s, 0.40), M_STEEL, "Trim", rot=(0, math.pi / 2, 0), seg=16)

# swan-neck wing
for s, side in SIDES:
    part(f"Wing_Upright_{side}", (0.10, 0.05, 0.56), (-2.02, 0.36 * s, 1.20), M_CARBON, "Aero", rot=(0, math.radians(-10), 0))
    part(f"Wing_Neck_{side}", (0.22, 0.05, 0.06), (-2.10, 0.36 * s, 1.50), M_CARBON, "Aero")
    part(f"Wing_Endplate_{side}", (0.58, 0.05, 0.32), (-2.18, 1.02 * s, 1.43), M_CARBON, "Aero")
part("Wing_Main", (0.48, 2.00, 0.06), (-2.16, 0, 1.44), M_PAINT, "Aero", rot=(0, math.radians(-8), 0))
part("Wing_Gurney", (0.06, 2.00, 0.05), (-2.42, 0, 1.49), M_CARBON, "Aero")

# door decals: "GT3 RS" reads front-to-back on both sides
text("Decal_GT3RS_R", "GT3 RS", 0.30, (-0.05, -0.968, 0.62), Euler((math.pi / 2, 0, 0)), M_BLACK)
text("Decal_GT3RS_L", "GT3 RS", 0.30, (-0.05, 0.968, 0.62), Euler((math.pi / 2, 0, math.pi)), M_BLACK)


# ---------------------------------------------------------------- wheels

def wheel(name, x, y, r, w):
    s = 1 if y > 0 else -1
    out = s * (w / 2)
    pieces = [
        cyl(name, r, w, (0, 0, 0), M_TIRE, "Wheels", seg=24, bevel=0.05),
        cyl(name + "_Rim", r * 0.66, w + 0.02, (0, 0, 0), M_RIM, "Wheels", seg=20, bevel=0.015),
        cyl(name + "_RimStripe", r * 0.69, 0.012, (0, out + s * 0.006, 0), M_PAINT, "Wheels", seg=20, bevel=0.0),
        cyl(name + "_RimFace", r * 0.62, 0.012, (0, out + s * 0.012, 0), M_RIM, "Wheels", seg=20, bevel=0.0),
        cyl(name + "_CenterLock", 0.06, 0.06, (0, out + s * 0.05, 0), M_PAINT, "Wheels", seg=6, bevel=0.01),
        cyl(name + "_BrakeDisc", r * 0.55, 0.03, (0, -s * 0.02, 0), M_STEEL, "Wheels", seg=20, bevel=0.0),
        part(name + "_Caliper", (0.18, 0.08, 0.10), (-0.10, s * 0.03, r * 0.40), M_PAINT, "Wheels", bevel=0.015),
    ]
    for k in range(10):
        a = k / 10 * math.pi * 2
        pieces.append(part(f"{name}_Spoke_{k}", (0.035, 0.03, r * 0.55),
                           (math.sin(a) * r * 0.33, out + s * 0.03, math.cos(a) * r * 0.33),
                           M_CARBON, "Wheels", rot=(0, a, 0), bevel=0.008))
    for p in pieces:
        p.location = Vector(p.location) + Vector((x, y, r))
    return pieces


WHEELS = {
    "Wheel_FL": wheel("Wheel_FL", 1.35, 0.86, 0.37, 0.32),
    "Wheel_FR": wheel("Wheel_FR", 1.35, -0.86, 0.37, 0.32),
    "Wheel_RL": wheel("Wheel_RL", -1.30, 0.86, 0.39, 0.36),
    "Wheel_RR": wheel("Wheel_RR", -1.30, -0.86, 0.39, 0.36),
}


# ---------------------------------------------------------------- merge into Roblox-friendly meshes

def join(objs, name):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    o = bpy.context.view_layer.objects.active
    o.name = name
    o.data.name = name
    return o


root = bpy.data.objects.new("GT3RS_Roblox", None)
root.empty_display_size = 0.5
CAR.objects.link(root)
merged = []
for gname, coll in GROUPS.items():
    if gname == "Wheels":
        continue
    merged.append(join(list(coll.objects), gname))
for wname, pieces in WHEELS.items():
    # the tire is joined into, so the wheel's origin stays at the hub and it spins about its own axle
    merged.append(join(pieces, wname))
for o in merged:
    o.parent = root

tri_counts = {}
for o in merged:
    o.data.calc_loop_triangles()
    tri_counts[o.name] = len(o.data.loop_triangles)


# ---------------------------------------------------------------- studio: baseplate, lights, camera

part("Baseplate", (40, 40, 0.4), (0, 0, -0.2), M_BASE, "Body", bevel=0.0)
base = bpy.data.objects["Baseplate"]
GROUPS["Body"].objects.unlink(base)
STUDIO.objects.link(base)

sun = bpy.data.objects.new("Key_Sun", bpy.data.lights.new("Key_Sun", 'SUN'))
sun.data.energy = 3.5
sun.data.angle = math.radians(10)
sun.rotation_euler = Euler((math.radians(48), math.radians(12), math.radians(40)))
fill = bpy.data.objects.new("Fill", bpy.data.lights.new("Fill", 'AREA'))
fill.data.energy = 900
fill.data.size = 6
fill.location = (6, -7, 5)
fill.rotation_euler = (Vector((0, 0, 0.6)) - fill.location).to_track_quat('-Z', 'Y').to_euler()
rim = bpy.data.objects.new("Rim", bpy.data.lights.new("Rim", 'AREA'))
rim.data.energy = 700
rim.data.size = 5
rim.location = (-6, 6, 4)
rim.rotation_euler = (Vector((0, 0, 0.6)) - rim.location).to_track_quat('-Z', 'Y').to_euler()
for o in (sun, fill, rim):
    STUDIO.objects.link(o)

world = bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.62, 0.66, 0.72, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.7

cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
cam.data.lens = 50
cam.location = (7.0, -6.2, 2.8)
cam.rotation_euler = (Vector((0.1, 0, 0.6)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
STUDIO.objects.link(cam)
scene.camera = cam


# ---------------------------------------------------------------- save, export, render

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT_DIR, "gt3rs_roblox.blend"), compress=True)

bpy.ops.object.select_all(action='DESELECT')
for o in [root] + merged:
    o.select_set(True)
bpy.ops.export_scene.gltf(filepath=os.path.join(OUT_DIR, "gt3rs_roblox.glb"), export_format='GLB',
                          use_selection=True, export_apply=True, export_yup=True)
bpy.ops.export_scene.fbx(filepath=os.path.join(OUT_DIR, "gt3rs_roblox.fbx"), use_selection=True,
                         apply_scale_options='FBX_SCALE_UNITS', axis_forward='-Z', axis_up='Y',
                         mesh_smooth_type='FACE', path_mode='COPY', embed_textures=False)

if RENDER:
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 96
    scene.cycles.use_denoising = False
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 800
    scene.view_settings.view_transform = 'AgX'
    scene.render.filepath = os.path.join(OUT_DIR, "gt3rs_roblox_render.png")
    bpy.ops.render.render(write_still=True)

print("PAINT_HEX", PAINT_HEX)
print("TRIANGLES", tri_counts)
