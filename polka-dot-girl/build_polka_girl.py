"""Roblox-style "Polka Dot Girl" avatar, built with Blender's Python API.

Follows reference/polka_girl_reference.jpg: very long glossy dark-brown hair with a
center part and side-swept bangs over one eye, a white polka-dot headband with a black
bow, heart charms and a dangling chain, a little white bow hair clip, closed happy eyes
with blush and a tongue-out smile, a white polka-dot top with frills and a black ribbon,
a heart necklace, a pearl heart bracelet, grey polka-dot baggy pants, fluffy white leg
warmers and chunky white shoes.

Run:
    blender -b -P build_polka_girl.py -- [out_dir] [--no-render]
    # or, with the bpy module:  python3.11 build_polka_girl.py [out_dir] [--no-render]

Writes polka_girl.blend, polka_girl.fbx, polka_girl.glb, polka_girl_render.png and the
textures (tex_*.png) to out_dir (default: ./out next to this script).

Units: built in studs, written out in metres at Roblox's 1 stud = 0.28 m, so the
3D Importer brings her in at normal character height (about 5.6 studs).
Coordinates: +Z up, she faces -Y. One mesh per material (Skin, Head, Hair, Top, Pants,
Fur, Shoes, Headband, Ribbon, Silver, Pearl), so every MeshPart has a single texture.
"""

import math
import os
import random
import sys

import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ARGV = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
RENDER = "--no-render" not in ARGV
POSITIONAL = [a for a in ARGV if not a.startswith("--")]
OUT_DIR = os.path.abspath(POSITIONAL[0] if POSITIONAL else os.path.join(HERE, "out"))
os.makedirs(OUT_DIR, exist_ok=True)

S = 0.28  # metres per stud
random.seed(7)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# ---------------------------------------------------------------- palette

SKIN = "#f3d8c8"
HAIR = "#22140f"
TOP_BG, TOP_DOT = "#f5f3f1", "#141414"
PANTS_BG, PANTS_DOT = "#3f3b3b", "#121111"
BAND_BG, BAND_DOT = "#f7f6f4", "#161616"
FUR = "#f4f2f0"
SHOE = "#dcdce0"
RIBBON = "#121212"
SILVER = "#d8dbe0"
PEARL = "#f6f1ea"
BLUSH = "#f2a3a6"
LASH = "#2a1714"
TONGUE = "#e8707c"


def srgb(hex_str):
    h = hex_str.lstrip("#")
    return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]


def lin(hex_str):
    return (*[c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb(hex_str)], 1.0)


# ---------------------------------------------------------------- textures (numpy, saved as PNG)

def save_image(name, rgba):
    """rgba: HxWx4 float array in sRGB, row 0 = top."""
    h, w, _ = rgba.shape
    img = bpy.data.images.new(name, w, h, alpha=True)
    img.pixels.foreach_set(np.flipud(rgba).astype(np.float32).ravel())
    img.filepath_raw = os.path.join(OUT_DIR, name + ".png")
    img.file_format = 'PNG'
    img.save()
    return img


def polka(name, bg, dot, size=256, per_tile=2, radius=0.16):
    """Offset-row polka dots, `per_tile` dots per row, tiles seamlessly."""
    yy, xx = np.mgrid[0:size, 0:size] / size
    pitch = 1 / per_tile
    mask = np.zeros((size, size), bool)
    for row in range(per_tile * 2 + 1):
        cy = row * pitch / 2
        off = (pitch / 2) if row % 2 else 0
        for col in range(-1, per_tile + 1):
            cx = col * pitch + off
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    mask |= (xx - cx - dx) ** 2 + (yy - cy - dy) ** 2 < (radius * pitch) ** 2
    img = np.ones((size, size, 4))
    img[..., :3] = srgb(bg)
    img[mask, :3] = srgb(dot)
    return save_image(name, img)


def face_texture(size=512):
    """Front of the head: skin, closed happy eyes with lashes, blush, tongue-out smile."""
    img = np.ones((size, size, 4))
    img[..., :3] = srgb(SKIN)
    yy, xx = np.mgrid[0:size, 0:size].astype(float)

    def blend(mask_alpha, hex_str):
        a = np.clip(mask_alpha, 0, 1)[..., None]
        img[..., :3] = img[..., :3] * (1 - a) + np.array(srgb(hex_str)) * a

    # blush: soft ellipses under the eyes
    for cx in (150, 362):
        d = ((xx - cx) / 62) ** 2 + ((yy - 330) / 30) ** 2
        blend(0.75 * np.exp(-d * 1.6), BLUSH)
    # closed eyes: downward-curving arcs (a "u") with three lashes each
    for cx, outward in ((160, -1), (352, 1)):
        u = (xx - cx) / 58
        curve = 268 + 22 * (1 - u ** 2)
        on = (np.abs(u) <= 1) & (np.abs(yy - curve) < 6.5)
        blend(on.astype(float), LASH)
        for k in (0.35, 0.7, 1.0):  # lashes on the outer half, flicking down and out
            lx = cx + outward * k * 58
            ly = 268 + 22 * (1 - k ** 2)
            tx, ty = lx + outward * (10 + 14 * k), ly + 14 - 10 * k
            px, py = xx - lx, yy - ly
            vx, vy = tx - lx, ty - ly
            t = np.clip((px * vx + py * vy) / (vx * vx + vy * vy), 0, 1)
            dist = np.hypot(px - t * vx, py - t * vy)
            blend((dist < 4.5).astype(float), LASH)
    # mouth: small cat-like "w" smile
    u = (xx - 256) / 26
    w_curve = 372 + 8 * np.abs(np.sin(u * math.pi))
    blend(((np.abs(u) <= 1) & (np.abs(yy - w_curve) < 3.5)).astype(float), LASH)
    # tongue poking out under the centre
    d = ((xx - 262) / 15) ** 2 + ((yy - 386) / 14) ** 2
    blend(((d < 1) & (yy > 377)).astype(float), TONGUE)
    return save_image("tex_face", img)


TEX_TOP = polka("tex_top_polka", TOP_BG, TOP_DOT, per_tile=3, radius=0.12)
TEX_PANTS = polka("tex_pants_polka", PANTS_BG, PANTS_DOT, per_tile=2, radius=0.13)
TEX_BAND = polka("tex_headband_polka", BAND_BG, BAND_DOT, per_tile=2, radius=0.16)
TEX_FACE = face_texture()


# ---------------------------------------------------------------- materials

def material(name, hex_str, rough=0.45, metal=0.0, tex=None, sheen=0.0, coat=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = lin(hex_str)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if sheen:
        b.inputs["Sheen Weight"].default_value = sheen
    if coat:
        b.inputs["Coat Weight"].default_value = coat
        b.inputs["Coat Roughness"].default_value = 0.12
    if tex:
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = tex
        t.interpolation = 'Linear'
        nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
    m.diffuse_color = lin(hex_str)
    return m


MATS = {
    "Skin": material("Skin", SKIN, 0.55),
    "Head": material("Head_Face", SKIN, 0.55, tex=TEX_FACE),
    "Hair": material("Hair_DarkBrown", HAIR, 0.42, coat=0.25),
    "Top": material("Top_Polka", TOP_BG, 0.5, tex=TEX_TOP),
    "Pants": material("Pants_Polka", PANTS_BG, 0.32, tex=TEX_PANTS, coat=0.3),
    "Fur": material("Fur_White", FUR, 0.95, sheen=1.0),
    "Shoes": material("Shoes_White", SHOE, 0.4),
    "Headband": material("Headband_Polka", BAND_BG, 0.45, tex=TEX_BAND),
    "Ribbon": material("Ribbon_Black", RIBBON, 0.45, coat=0.15),
    "Silver": material("Charm_Silver", SILVER, 0.18, metal=1.0),
    "Pearl": material("Pearl", PEARL, 0.2, coat=1.0),
}
# Which groups get world-space box UVs (polka textures), and the stud size of one texture tile
TILE = {"Top": 1.1, "Pants": 1.0, "Headband": 0.55}

GIRL = bpy.data.collections.new("PolkaDotGirl")
scene.collection.children.link(GIRL)
GROUPS = {}
for g in MATS:
    c = bpy.data.collections.new(g)
    GIRL.children.link(c)
    GROUPS[g] = c
STUDIO = bpy.data.collections.new("Studio")
scene.collection.children.link(STUDIO)


# ---------------------------------------------------------------- part helpers (inputs in studs)

def finish(name, bm, group, loc, rot=(0, 0, 0), bevel=0.0, segs=1, smooth=False):
    """Bevel, then bake rotation + location + stud scale into the vertices (object at origin)."""
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=bm.edges[:], offset=bevel, offset_type='OFFSET',
                        segments=segs, profile=0.5, affect='EDGES', clamp_overlap=True)
    mat = Matrix.Scale(S, 4) @ Matrix.Translation(Vector(loc)) @ \
        Matrix.Rotation(rot[2], 4, 'Z') @ Matrix.Rotation(rot[1], 4, 'Y') @ Matrix.Rotation(rot[0], 4, 'X')
    bm.transform(mat)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = smooth
    me.materials.append(MATS[group])
    o = bpy.data.objects.new(name, me)
    GROUPS[group].objects.link(o)
    return o


def box(name, size, loc, group, rot=(0, 0, 0), bevel=0.04, segs=1, smooth=False):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= size[0]
        v.co.y *= size[1]
        v.co.z *= size[2]
    return finish(name, bm, group, loc, rot, min(bevel, min(size) * 0.45), segs, smooth)


def cyl(name, r1, r2, depth, loc, group, rot=(0, 0, 0), seg=24, bevel=0.0, smooth=True):
    """Upright frustum (axis Z), r1 at the bottom."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg,
                          radius1=r1, radius2=r2, depth=depth)
    return finish(name, bm, group, loc, rot, bevel, 2, smooth)


def ball(name, r, loc, group, scale=(1, 1, 1), seg=12, rings=8):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=r)
    for v in bm.verts:
        v.co.x *= scale[0]
        v.co.y *= scale[1]
        v.co.z *= scale[2]
    return finish(name, bm, group, loc, smooth=True)


def heart(name, size, loc, group, depth=0.06, rot=(0, 0, 0)):
    """Flat heart facing -Y, `size` studs tall."""
    bm = bmesh.new()
    pts = []
    for i in range(28):
        t = 2 * math.pi * i / 28
        x = 16 * math.sin(t) ** 3
        z = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((x / 34 * size, z / 34 * size + size * 0.08))
    front = [bm.verts.new((x, -depth / 2, z)) for x, z in pts]
    back = [bm.verts.new((x, depth / 2, z)) for x, z in pts]
    bm.faces.new(front[::-1])
    bm.faces.new(back)
    for i in range(len(pts)):
        j = (i + 1) % len(pts)
        bm.faces.new((front[i], front[j], back[j], back[i]))
    return finish(name, bm, group, loc, rot, 0.0, smooth=False)


def bow(name, loc, group, width=0.5, rot=(0, 0, 0)):
    """Two tilted loops and a knot, facing -Y."""
    w = width
    out = [
        box(name + "_L", (w * 0.5, w * 0.16, w * 0.42), (loc[0] - w * 0.27, loc[1], loc[2] + w * 0.03), group,
            rot=(rot[0], rot[1] + 0.35, rot[2]), bevel=w * 0.12, segs=2, smooth=True),
        box(name + "_R", (w * 0.5, w * 0.16, w * 0.42), (loc[0] + w * 0.27, loc[1], loc[2] + w * 0.03), group,
            rot=(rot[0], rot[1] - 0.35, rot[2]), bevel=w * 0.12, segs=2, smooth=True),
        box(name + "_Knot", (w * 0.2, w * 0.2, w * 0.24), (loc[0], loc[1] - w * 0.03, loc[2]), group,
            bevel=w * 0.06, segs=2, smooth=True),
    ]
    for side in (-1, 1):  # tails
        out.append(box(name + f"_Tail{side}", (w * 0.13, w * 0.08, w * 0.45),
                       (loc[0] + side * w * 0.1, loc[1] + 0.01, loc[2] - w * 0.28), group,
                       rot=(0, side * 0.35, 0), bevel=w * 0.03))
    return out


def chain(name, p0, p1, links, group, r=0.035):
    for i in range(links + 1):
        t = i / links
        ball(f"{name}_{i}", r, tuple(a + (b - a) * t for a, b in zip(p0, p1)), group, seg=6, rings=4)


# ---------------------------------------------------------------- legs, shoes, fur warmers

LEG_X = 0.43
for side, sx in (("L", -1), ("R", 1)):
    x = sx * LEG_X
    box(f"Shoe_{side}", (0.86, 1.02, 0.34), (x, -0.06, 0.17), "Shoes", bevel=0.09, segs=2)
    box(f"Sole_{side}", (0.9, 1.06, 0.08), (x, -0.06, 0.04), "Shoes", bevel=0.03)
    # baggy pants leg: slightly wider at the bottom
    cyl(f"PantsLeg_{side}", 0.47, 0.42, 1.55, (x, 0.0, 1.38), "Pants", seg=4, rot=(0, 0, math.pi / 4),
        bevel=0.08, smooth=False)
    # fluffy warmer: a lumpy puff plus a ring of soft tufts
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=40, v_segments=20, radius=1.0)
    for v in bm.verts:
        n = v.co.normalized()
        lump = 1.0 + 0.09 * math.sin(7 * math.atan2(n.y, n.x) + 3 * n.z) + random.uniform(-0.05, 0.05)
        v.co.x *= 0.72 * lump
        v.co.y *= 0.72 * lump
        v.co.z *= 0.48 * lump
    finish(f"Fur_{side}", bm, "Fur", (x, -0.02, 0.62), smooth=True)
    for k in range(34):
        a = 2 * math.pi * k / 34 + random.uniform(-0.08, 0.08)
        z = 0.62 + random.uniform(-0.32, 0.32)
        r = 0.66 * math.sqrt(max(0.15, 1 - ((z - 0.62) / 0.5) ** 2))
        tilt = random.uniform(1.1, 1.5)  # point the tuft outward from the leg
        cyl(f"Tuft_{side}_{k}", 0.09, 0.0, 0.22, (x + r * math.cos(a), -0.02 + r * math.sin(a), z), "Fur",
            rot=(-math.sin(a) * tilt, math.cos(a) * tilt, 0), seg=6)

# hips / pants top
box("Hips", (1.72, 0.92, 0.5), (0, 0, 2.38), "Pants", bevel=0.08, segs=2)

# ---------------------------------------------------------------- torso, top, ribbon, necklace

box("Torso", (1.56, 0.82, 1.5), (0, 0, 3.25), "Skin", bevel=0.12, segs=2)
box("TopBody", (1.62, 0.88, 1.12), (0, 0, 3.08), "Top", bevel=0.1, segs=2)
cyl("TopPeplum", 1.0, 0.84, 0.38, (0, 0, 2.62), "Top", seg=4, rot=(0, 0, math.pi / 4), bevel=0.06,
    smooth=False)
for i in range(13):  # frill along the neckline, front and back
    x = -0.66 + i * 0.11
    for y in (-0.45, 0.45):
        ball(f"Frill_{i}_{y}", 0.07, (x, y, 3.66), "Top", scale=(1, 0.6, 0.8), seg=8, rings=5)
for sx in (-1, 1):  # straps
    box(f"Strap_{sx}", (0.26, 0.9, 0.36), (sx * 0.56, 0, 3.8), "Top", bevel=0.05)
# black piping across the bust and a little ribbon bow with tails
box("Piping", (1.6, 0.04, 0.05), (0, -0.452, 3.38), "Ribbon", bevel=0.01)
bow("NeckBow", (0, -0.47, 3.6), "Ribbon", width=0.28)
for sx in (-1, 1):
    box(f"RibbonTail_{sx}", (0.04, 0.03, 0.42), (sx * 0.05, -0.465, 3.3), "Ribbon", rot=(0, sx * 0.18, 0),
        bevel=0.0)
# neck + necklace with a heart pendant
cyl("Neck", 0.24, 0.22, 0.3, (0, 0, 4.07), "Skin", seg=16)
for i in range(15):
    a = math.pi * (1.1 + 0.8 * i / 14)  # front half of the neck
    ball(f"Necklace_{i}", 0.025, (0.29 * math.cos(a), 0.29 * math.sin(a) - 0.06, 3.95 - 0.12 * math.sin(math.pi * i / 14)),
         "Silver", seg=6, rings=4)
heart("NecklaceHeart", 0.13, (0, -0.42, 3.78), "Silver", depth=0.04)

# ---------------------------------------------------------------- arms, pearl heart bracelet

for side, sx in (("L", -1), ("R", 1)):
    box(f"Arm_{side}", (0.6, 0.62, 1.78), (sx * 1.12, 0, 3.0), "Skin", rot=(0, sx * 0.06, 0), bevel=0.14, segs=2)
bx, bz = -1.1, 2.4  # bracelet on her right wrist
for i in range(18):
    a = 2 * math.pi * i / 18
    ball(f"Pearl_{i}", 0.055, (bx + 0.37 * math.cos(a), 0.38 * math.sin(a), bz), "Pearl", seg=8, rings=6)
heart("BraceletHeart", 0.2, (bx, -0.44, bz - 0.12), "Silver", depth=0.05)

# ---------------------------------------------------------------- head (face texture on the front)

HEAD_Z = 4.86
head = box("Head", (1.34, 1.22, 1.3), (0, 0, HEAD_Z), "Head", bevel=0.34, segs=4, smooth=True)

# ---------------------------------------------------------------- hair

def strands(name, x0, x1, y, z_top, z_bot, count, depth=0.22, jitter=0.35, tilt=0.0):
    """A sheet of long strands: thin bevelled slabs with ragged, tapered ends."""
    width = (x1 - x0) / count
    for i in range(count):
        x = x0 + width * (i + 0.5)
        zb = z_bot - random.uniform(0, jitter)
        h = z_top - zb
        o = box(f"{name}_{i}", (width * 1.25, depth * random.uniform(0.85, 1.15), h),
                (x, y + random.uniform(-0.03, 0.03), zb + h / 2), "Hair",
                rot=(0, tilt + random.uniform(-0.02, 0.02), 0), bevel=width * 0.45, segs=2, smooth=True)
        bm = bmesh.new()
        bm.from_mesh(o.data)
        zmin = min(v.co.z for v in bm.verts)
        for v in bm.verts:  # taper the bottom 25% to a soft point
            f = (v.co.z - zmin) / (h * S)
            if f < 0.25:
                k = 0.45 + 0.55 * f / 0.25
                v.co.x = x * S + (v.co.x - x * S) * k
        bm.to_mesh(o.data)
        bm.free()


# scalp cap and crown
box("HairCap", (1.48, 1.34, 0.62), (0, 0.06, HEAD_Z + 0.5), "Hair", bevel=0.3, segs=4, smooth=True)
box("HairBackOfHead", (1.46, 0.7, 1.1), (0, 0.32, HEAD_Z + 0.1), "Hair", bevel=0.3, segs=4, smooth=True)
box("HairCrownPart", (0.04, 1.0, 0.05), (0, -0.05, HEAD_Z + 0.78), "Skin", bevel=0.01)  # center part
# back curtain down to the thighs
strands("HairBack", -0.82, 0.82, 0.58, HEAD_Z + 0.5, 1.75, 14, depth=0.34)
# side curtains framing the face
for sx in (-1, 1):
    strands(f"HairSide{sx}", sx * 0.72 - 0.1, sx * 0.72 + 0.1, 0.18, HEAD_Z + 0.55, 2.6, 2, depth=0.8)
# front locks falling over the shoulders, past the hips
strands("HairFrontL", -0.98, -0.6, -0.3, HEAD_Z + 0.2, 1.95, 4, depth=0.26, tilt=0.05)
strands("HairFrontR", 0.6, 0.98, -0.3, HEAD_Z + 0.2, 2.15, 4, depth=0.26, tilt=-0.05)
# bangs: from the centre part, a soft fringe to the brows and a long swoop over her right eye
def bang(name, x, z_top, length, width, angle):
    """One fringe strand hanging from (x, z_top), rotated `angle` about Y (+ swings its tip to -X)."""
    loc = (x - math.sin(angle) * length / 2, -0.66, z_top - math.cos(angle) * length / 2)
    box(name, (width, 0.13, length), loc, "Hair", rot=(0, angle, 0), bevel=width * 0.45, segs=3, smooth=True)


for i, x in enumerate((0.12, 0.3, 0.46)):  # short side, to the brows
    bang(f"Fringe_{i}", x, HEAD_Z + 0.68, 0.5, 0.24, -0.12 - 0.08 * i)
for i, (x, length, ang) in enumerate([(0.04, 0.78, 0.42), (-0.12, 1.0, 0.36), (-0.28, 1.05, 0.24),
                                      (-0.44, 1.0, 0.14), (-0.58, 0.9, 0.05)]):  # swoop over the eye
    bang(f"Swoop_{i}", x, HEAD_Z + 0.68, length, 0.26, ang)

# ---------------------------------------------------------------- headband, bow, charms, hair clip

band_r = 0.86
for i in range(19):
    a = math.radians(8 + i * (164 / 18))
    box(f"Band_{i}", (0.22, 0.26, 0.15), (band_r * math.cos(a), -0.12, HEAD_Z + 0.44 + band_r * math.sin(a) * 0.62),
        "Headband", rot=(0, -(a - math.pi / 2), 0), bevel=0.04)
bow("HeadBow", (0.62, -0.42, HEAD_Z + 0.78), "Ribbon", width=0.62, rot=(0, -0.45, 0))
heart("BandHeart_A", 0.14, (0.36, -0.36, HEAD_Z + 0.84), "Silver", depth=0.05, rot=(0, -0.3, 0))
heart("BandHeart_B", 0.12, (0.82, -0.34, HEAD_Z + 0.56), "Silver", depth=0.05, rot=(0, -0.8, 0))
chain("Chain", (0.84, -0.4, HEAD_Z + 0.5), (0.9, -0.45, HEAD_Z - 0.15), 12, "Silver")
heart("ChainHeart", 0.16, (0.9, -0.46, HEAD_Z - 0.28), "Silver", depth=0.05)
bow("HairClip", (-0.62, -0.7, HEAD_Z + 0.12), "Silver", width=0.3, rot=(0, 0.3, 0))


# ---------------------------------------------------------------- UVs

def box_uv(obj, tile):
    """World-space box projection so polka dots stay the same size on every part."""
    me = obj.data
    uv = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        n = poly.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co / S
            u, v = [(co.y, co.z), (co.x, co.z), (co.x, co.y)][ax]
            uv.data[li].uv = (u / tile, v / tile)


def head_uv(obj):
    """Front of the head shows the face texture; everything else samples plain skin."""
    me = obj.data
    uv = me.uv_layers.new(name="UVMap")
    xs = [v.co.x for v in me.vertices]
    zs = [v.co.z for v in me.vertices]
    x0, x1, z0, z1 = min(xs), max(xs), min(zs), max(zs)
    for poly in me.polygons:
        front = poly.normal.y < -0.35
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = ((co.x - x0) / (x1 - x0), (co.z - z0) / (z1 - z0)) if front else (0.02, 0.98)


def join(objs, name):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1:
        bpy.ops.object.join()
    o = bpy.context.view_layer.objects.active
    o.name = name
    o.data.name = name
    return o


root = bpy.data.objects.new("PolkaDotGirl", None)
root.empty_display_size = 0.5
GIRL.objects.link(root)
merged = []
for gname, coll in GROUPS.items():
    o = join(list(coll.objects), gname)
    if gname == "Head":
        head_uv(o)
    elif gname in TILE:
        box_uv(o, TILE[gname])
    else:
        o.data.uv_layers.new(name="UVMap")
    o.parent = root
    merged.append(o)

tri_counts = {}
for o in merged:
    o.data.calc_loop_triangles()
    tri_counts[o.name] = len(o.data.loop_triangles)

# ---------------------------------------------------------------- studio

floor = bpy.data.objects.new("Floor", bpy.data.meshes.new("Floor"))
bm = bmesh.new()
bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=6)
bm.to_mesh(floor.data)
bm.free()
floor.data.materials.append(material("Floor_White", "#f4f4f6", 0.7))
STUDIO.objects.link(floor)


def area(name, energy, size, loc, target=(0, 0, 0.8)):
    l = bpy.data.objects.new(name, bpy.data.lights.new(name, 'AREA'))
    l.data.energy = energy
    l.data.size = size
    l.location = loc
    l.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    STUDIO.objects.link(l)


area("Key", 200, 2.0, (-1.6, -2.4, 2.6))
area("Fill", 110, 3.0, (2.4, -2.0, 1.4))
area("Rim", 220, 1.5, (1.0, 2.2, 2.6))

world = bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (1, 1, 1, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.3

cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
cam.data.lens = 70
cam.location = (1.6, -4.3, 1.35)
cam.rotation_euler = (Vector((0.0, 0, 0.8)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
STUDIO.objects.link(cam)
scene.camera = cam

# ---------------------------------------------------------------- save, export, render

bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT_DIR, "polka_girl.blend"), compress=True)

bpy.ops.object.select_all(action='DESELECT')
for o in [root] + merged:
    o.select_set(True)
bpy.ops.export_scene.gltf(filepath=os.path.join(OUT_DIR, "polka_girl.glb"), export_format='GLB',
                          use_selection=True, export_apply=True, export_yup=True)
bpy.ops.export_scene.fbx(filepath=os.path.join(OUT_DIR, "polka_girl.fbx"), use_selection=True,
                         apply_scale_options='FBX_SCALE_UNITS', axis_forward='-Z', axis_up='Y',
                         mesh_smooth_type='FACE', path_mode='COPY', embed_textures=True)

if RENDER:
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 64
    scene.cycles.use_denoising = False
    scene.render.resolution_x = 900
    scene.render.resolution_y = 1300
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'AgX - Punchy'
    scene.render.filepath = os.path.join(OUT_DIR, "polka_girl_render.png")
    bpy.ops.render.render(write_still=True)

print("TRIANGLES", tri_counts, "TOTAL", sum(tri_counts.values()))
