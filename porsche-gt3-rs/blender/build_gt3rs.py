"""Procedural Porsche 911 GT3 RS (992) in Gulf-blue livery, built with Blender's Python API.

Run inside Blender:
    blender -b -P build_gt3rs.py -- [out_dir] [--no-render]
or with the standalone `bpy` module (pip install bpy, Python 3.11):
    python build_gt3rs.py [out_dir] [--no-render]

Writes gt3rs.blend, gt3rs.glb, gt3rs.fbx and gt3rs_render.png to out_dir
(default: ./out next to this script).

Coordinates: metres, +X = front of the car, +Y = car's left, +Z = up.
Every mesh stays under 20k triangles so each part imports into Roblox Studio as a MeshPart.
"""

import math
import os
import sys

import bpy  # must come first: the standalone bpy module provides bmesh and mathutils
import bmesh
from mathutils import Euler, Matrix, Vector
from mathutils.bvhtree import BVHTree

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
RENDER = "--no-render" not in ARGS
POSITIONAL = [a for a in ARGS if not a.startswith("--")]
OUT_DIR = os.path.abspath(POSITIONAL[0] if POSITIONAL else os.path.join(os.path.dirname(os.path.abspath(__file__)), "out"))
os.makedirs(OUT_DIR, exist_ok=True)

PAINT_HEX = "#3db4dc"  # Gulf blue, matched to the reference photo

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
car_coll = bpy.data.collections.new("GT3RS")
scene.collection.children.link(car_coll)
studio_coll = bpy.data.collections.new("Studio")
scene.collection.children.link(studio_coll)

root = bpy.data.objects.new("GT3RS", None)
car_coll.objects.link(root)


# ---------------------------------------------------------------- materials

def srgb(hex_str):
    h = hex_str.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (*out, 1.0)


def material(name, hex_str, metallic=0.0, roughness=0.5, coat=0.0, emission=None, strength=0.0, transmission=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = srgb(hex_str)
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Roughness"].default_value = roughness
    if coat:
        b.inputs["Coat Weight"].default_value = coat
        b.inputs["Coat Roughness"].default_value = 0.03
    if emission:
        b.inputs["Emission Color"].default_value = srgb(emission)
        b.inputs["Emission Strength"].default_value = strength
    if transmission:
        b.inputs["Transmission Weight"].default_value = transmission
    m.diffuse_color = srgb(hex_str)
    return m


PAINT = material("Paint_GulfBlue", PAINT_HEX, 0.25, 0.3, coat=1.0)
GLOSS_BLACK = material("Gloss_Black", "#0a0b0c", 0.1, 0.18, coat=1.0)
GLASS = material("Glass_Tint", "#06080a", 0.0, 0.04, coat=1.0)
TRIM = material("Trim_Black", "#0b0c0e", 0.2, 0.45)
SATIN = material("Satin_Black", "#15171a", 0.35, 0.6)
TIRE = material("Tire", "#121314", 0.0, 0.88)
RIM = material("Rim_Black", "#1a1c1f", 0.7, 0.38)
DISC = material("Brake_Disc", "#6b6e72", 0.9, 0.45)
CHROME = material("Chrome", "#b4b8bd", 1.0, 0.16)
LAMP = material("Lamp_Housing", "#c9ced3", 1.0, 0.08)
DRL = material("Light_White", "#ffffff", 0.0, 0.3, emission="#f4f8ff", strength=8.0)
TAIL = material("Light_Red", "#3a0000", 0.0, 0.3, emission="#ff1424", strength=8.0)


# ---------------------------------------------------------------- mesh helpers

def link(name, bm_or_mesh, mats, matrix=None, smooth=False, coll=None):
    if isinstance(bm_or_mesh, bmesh.types.BMesh):
        me = bpy.data.meshes.new(name)
        bm_or_mesh.to_mesh(me)
        bm_or_mesh.free()
    else:
        me = bm_or_mesh
    for m in mats if isinstance(mats, (list, tuple)) else [mats]:
        me.materials.append(m)
    if smooth:
        me.shade_smooth()
    ob = bpy.data.objects.new(name, me)
    (coll or car_coll).objects.link(ob)
    if coll is None:
        ob.parent = root
    if matrix is not None:
        ob.matrix_world = matrix
    return ob


def trs(loc=(0, 0, 0), rot=None, scale=(1, 1, 1)):
    if rot is None:
        r = Matrix.Identity(4)
    elif isinstance(rot, Euler):
        r = rot.to_matrix().to_4x4()
    elif isinstance(rot, Matrix):
        r = rot.to_4x4()
    else:  # Quaternion
        r = rot.to_matrix().to_4x4()
    return Matrix.Translation(Vector(loc)) @ r @ Matrix.Diagonal((*scale, 1.0))


def box(name, size, mat, matrix):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    return link(name, bm, mat, matrix)


def cyl(name, r1, r2, depth, mat, matrix, seg=32, caps=True, smooth=True):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=caps, cap_tris=False, segments=seg, radius1=r1, radius2=r2, depth=depth)
    return link(name, bm, mat, matrix, smooth=smooth)


def sphere(name, r, mat, matrix, u=32, v=16):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=r)
    return link(name, bm, mat, matrix, smooth=True)


def torus(name, big_r, small_r, mat, matrix, seg=48, tseg=10):
    bm = bmesh.new()
    vs = []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        for j in range(tseg):
            b = 2 * math.pi * j / tseg
            rr = big_r + small_r * math.cos(b)
            vs.append(bm.verts.new((rr * math.cos(a), rr * math.sin(a), small_r * math.sin(b))))
    for i in range(seg):
        for j in range(tseg):
            i2, j2 = (i + 1) % seg, (j + 1) % tseg
            bm.faces.new((vs[i * tseg + j], vs[i2 * tseg + j], vs[i2 * tseg + j2], vs[i * tseg + j2]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return link(name, bm, mat, matrix, smooth=True)


def catmull(points, per_seg=12):
    pts = [Vector(p) for p in points]
    ext = [pts[0]] + pts + [pts[-1]]
    out = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        for k in range(per_seg):
            t = k / per_seg
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(pts[-1])
    return out


def tube(name, points, radius, mat, sides=10, smooth_path=True):
    pts = catmull(points) if smooth_path else [Vector(p) for p in points]
    bm = bmesh.new()
    rings = []
    normal = None
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        if normal is None:
            up = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((0, 1, 0))
            normal = up.cross(t).normalized()
        else:
            normal = (normal - t * normal.dot(t)).normalized()
        binormal = t.cross(normal).normalized()
        rings.append([bm.verts.new(p + (normal * math.cos(2 * math.pi * k / sides) + binormal * math.sin(2 * math.pi * k / sides)) * radius) for k in range(sides)])
    for a, b in zip(rings, rings[1:]):
        for k in range(sides):
            bm.faces.new((a[k], a[(k + 1) % sides], b[(k + 1) % sides], b[k]))
    bm.faces.new(rings[0])
    bm.faces.new(list(reversed(rings[-1])))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return link(name, bm, mat, smooth=True)


def look_quat(direction):
    """Rotation taking local +Z to `direction`, local +Y towards world up."""
    return Vector(direction).normalized().to_track_quat("Z", "Y")


# ---------------------------------------------------------------- body profile tables
# (x from rear -2.285 to front 2.285; values in metres)

def curve(table, x):
    n = len(table)
    if x <= table[0][0]:
        return table[0][1]
    if x >= table[-1][0]:
        return table[-1][1]
    i = 0
    while i < n - 2 and x > table[i + 1][0]:
        i += 1
    p0, p1, p2, p3 = table[max(i - 1, 0)][1], table[i][1], table[i + 1][1], table[min(i + 2, n - 1)][1]
    u = (x - table[i][0]) / (table[i + 1][0] - table[i][0])
    return 0.5 * (2 * p1 + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u + (-p0 + 3 * p1 - 3 * p2 + p3) * u ** 3)


def sgn(v):
    return -1.0 if v < 0 else 1.0


TOP = [(-2.285, 0.70), (-2.2, 0.86), (-1.9, 0.93), (-1.4, 0.95), (-0.9, 0.93), (0.0, 0.90), (0.7, 0.84), (1.3, 0.74), (1.9, 0.63), (2.2, 0.55), (2.285, 0.46)]
BOT = [(-2.285, 0.34), (-2.1, 0.24), (-1.8, 0.16), (1.9, 0.14), (2.2, 0.17), (2.285, 0.30)]
WID = [(-2.285, 0.80), (-2.1, 0.93), (-1.6, 0.975), (-1.0, 0.965), (-0.5, 0.90), (0.3, 0.88), (0.9, 0.90), (1.3, 0.93), (1.8, 0.90), (2.15, 0.82), (2.285, 0.70)]
ROOF = [(-1.95, 0.90), (-1.6, 0.98), (-1.1, 1.12), (-0.6, 1.24), (-0.2, 1.30), (0.1, 1.30), (0.35, 1.22), (0.6, 1.03), (0.82, 0.80)]
CABIN_W = [(-1.95, 0.40), (-1.5, 0.62), (-0.9, 0.70), (0.0, 0.71), (0.5, 0.69), (0.82, 0.64)]
AXLES = [(1.255, 0.335), (-1.20, 0.355)]  # (x, tyre radius)
HALF_L = 2.285


def loft(name, nx, nr, x0, x1, ring, mats):
    verts, codes = [], []
    for i in range(nx + 1):
        x = x0 + (x1 - x0) * i / nx
        for j in range(nr):
            w, h, c = ring(x, 2 * math.pi * j / nr)
            verts.append((x, w, h))
            codes.append(c)
    faces, face_mat = [], []
    for a in range(nx):
        for b in range(nr):
            p, q = a * nr + b, a * nr + (b + 1) % nr
            r, s = (a + 1) * nr + b, (a + 1) * nr + (b + 1) % nr
            faces.append((p, q, s, r))
            cs = [codes[p], codes[q], codes[r], codes[s]]
            face_mat.append(max(set(cs), key=cs.count))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    for poly, m in zip(me.polygons, face_mat):
        poly.material_index = m
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-6)
    bm.to_mesh(me)
    bm.free()
    return link(name, me, mats, smooth=True)


def body_ring(x, th):
    yt, yb, w = curve(TOP, x), curve(BOT, x), curve(WID, x)
    rr, s = 0.16, 1.0
    if x > HALF_L - rr:
        s = math.sqrt(max(0.0, 1 - ((x - (HALF_L - rr)) / rr) ** 2))
    if x < -HALF_L + rr:
        s = math.sqrt(max(0.0, 1 - (((-HALF_L + rr) - x) / rr) ** 2))
    zc, hh = (yt + yb) / 2, (yt - yb) / 2
    cs, sn = math.cos(th), math.sin(th)
    lat = w * sgn(cs) * abs(cs) ** 0.32
    lat *= (1 - 0.10 * sn * sn) if sn > 0 else (1 - 0.05 * sn * sn)
    up = zc + hh * sgn(sn) * abs(sn) ** 0.42
    if sn > 0:  # fender humps
        bump = 0.12 * math.exp(-((x - 1.4) / 0.75) ** 2) + 0.075 * math.exp(-((x + 1.25) / 0.65) ** 2)
        up += bump * math.exp(-((abs(lat) - 0.64) / 0.2) ** 2) * sn ** 0.6
    lat *= s
    up = zc + (up - zc) * s
    a = abs(lat)
    for ax, rt in AXLES:  # wheel arches
        big_r, dx = rt + 0.055, x - ax
        if abs(dx) < big_r:
            arch = rt + math.sqrt(big_r * big_r - dx * dx)
            t = min(1.0, max(0.0, (a - 0.44) / 0.14))
            if up < arch:
                up += (arch - up) * t
    black = (
        (0.95 < x < 2.1 and sn > 0.35 and a < 0.50)  # hood
        or (x > 2.0 and up < 0.44 and a < 0.72)  # front intake
        or up < 0.245  # sills
        or (x < -2.05 and up < 0.45)  # diffuser
        or (-0.95 < x < 0.75 and 0.29 < up < 0.35 and a > 0.7)  # side stripe
    )
    return lat, up, 1 if black else 0


def cabin_ring(x, th):
    roof, base = curve(ROOF, x), curve(TOP, x) - 0.03
    wb = curve(CABIN_W, x)
    wr = wb * 0.72
    cs, sn = math.cos(th), math.sin(th)
    u = sgn(cs) * abs(cs) ** 0.45
    v = sgn(sn) * abs(sn) ** 0.5
    t = (v + 1) / 2
    up = base + (roof - base) * t
    lat = u * (wb + (wr - wb) * t)
    if t > 0.86 and -0.9 < x < 0.32:
        c = 1  # black roof
    elif x > 0.3:
        c = 2  # windscreen
    elif x > -1.05 and t > 0.24 and abs(u) > 0.5:
        c = 2  # side glass
    elif -1.65 < x <= -0.9 and abs(u) < 0.62 and t > 0.3:
        c = 2  # rear glass
    else:
        c = 0
    return lat, up, c


body = loft("Body", 150, 64, -HALF_L, HALF_L, body_ring, [PAINT, GLOSS_BLACK])
cabin = loft("Greenhouse", 110, 48, -1.95, 0.82, cabin_ring, [PAINT, GLOSS_BLACK, GLASS])

# BVH over the shell, used to seat every detail part on the surface
_verts, _polys = [], []
for ob in (body, cabin):
    off = len(_verts)
    _verts += [v.co.copy() for v in ob.data.vertices]
    _polys += [[off + i for i in p.vertices] for p in ob.data.polygons]
BVH = BVHTree.FromPolygons(_verts, _polys)


def hit(origin, direction):
    loc, normal, _, _ = BVH.ray_cast(Vector(origin), Vector(direction).normalized())
    if loc is None:
        return None
    return loc, normal.normalized()


# ---------------------------------------------------------------- headlights

for side in (-1, 1):
    h = hit((1.9, 0.6 * side, 3), (0, 0, -1))
    if not h:
        continue
    p, n = h
    d = (n * 0.55 + Vector((1, 0.12 * side, 0.12))).normalized()
    m = trs(p - d * 0.02, look_quat(d), (1.45, 1.45, 1.45))
    tag = "L" if side > 0 else "R"
    sphere(f"Headlight_{tag}_Housing", 0.128, LAMP, m @ trs(scale=(1, 0.9, 0.38)), 40, 20)
    torus(f"Headlight_{tag}_Bezel", 0.128, 0.009, GLOSS_BLACK, m @ trs((0, 0, 0.004), scale=(1, 0.9, 1)))
    torus(f"Headlight_{tag}_Ring", 0.075, 0.007, DRL, m @ trs((0, 0, 0.036)), 40, 8)
    for i in range(4):
        a = i * math.pi / 2 + math.pi / 4
        box(f"Headlight_{tag}_DRL{i}", (0.034, 0.012, 0.008), DRL, m @ trs((math.cos(a) * 0.046, math.sin(a) * 0.046, 0.04), Euler((0, 0, a))))
    sphere(f"Headlight_{tag}_Lens", 0.03, CHROME, m @ trs((0, 0, 0.032), scale=(1, 1, 0.5)), 16, 10)

# ---------------------------------------------------------------- front aero

for side in (-1, 1):
    tag = "L" if side > 0 else "R"
    h = hit((3, 0.56 * side, 0.43), (-1, 0, 0))
    if h:
        box(f"Bumper_Light_{tag}", (0.02, 0.17, 0.016), DRL, trs(h[0] + Vector((0.004, 0, 0)), Euler((0, 0, 0.35 * side))))
    for k, zz in enumerate((0.30, 0.38)):
        c = hit((3, 0.8 * side, zz), (-1, 0, 0))
        if c:
            box(f"Canard_{tag}{k}", (0.2 - k * 0.04, 0.11, 0.008), TRIM,
                trs(c[0] + Vector((-0.02, 0.05 * side, 0)), Euler((0, -0.22, 0.45 * side))))
box("Front_Splitter", (0.34, 1.52, 0.022), TRIM, trs((2.06, 0, 0.115)))
for i, yy in enumerate((-0.5, 0.0, 0.5)):
    box(f"Splitter_Fin{i}", (0.38, 0.008, 0.06), TRIM, trs((2.06, yy, 0.15)))


# ---------------------------------------------------------------- vents and louvers

def slats(name, x, y, width, depth, count):
    h = hit((x, y, 3), (0, 0, -1))
    if not h:
        return
    m = trs(h[0], Vector((0, 0, 1)).rotation_difference(h[1]))
    box(f"{name}_Base", (depth, width, 0.01), SATIN, m)
    for i in range(count):
        box(f"{name}_Slat{i}", (0.012, width * 0.92, 0.022), TRIM,
            m @ trs((-depth / 2 + (i + 0.5) * depth / count, 0, 0.01), Euler((0, 0.5, 0))))


slats("Hood_Vent_L", 1.52, 0.26, 0.17, 0.34, 7)
slats("Hood_Vent_R", 1.52, -0.26, 0.17, 0.34, 7)
slats("Fender_Louver_L", 1.0, 0.64, 0.16, 0.22, 6)
slats("Fender_Louver_R", 1.0, -0.64, 0.16, 0.22, 6)
slats("Engine_Louver", -2.05, 0, 0.62, 0.26, 9)

# ---------------------------------------------------------------- sides: intakes, livery, mirrors, skirts

for side in (-1, 1):
    tag = "L" if side > 0 else "R"
    h = hit((-0.72, 3 * side, 0.62), (0, -side, 0))
    if h:
        cyl(f"Side_Intake_{tag}", 0.1, 0.1, 0.01, TRIM, trs(h[0] + h[1] * 0.002, look_quat(h[1]), (1.7, 1, 1)))
    h = hit((-0.1, 3 * side, 0.5), (0, -side, 0))
    if h:
        cu = bpy.data.curves.new(f"Decal_{tag}", "FONT")
        cu.body = "GT3 RS"
        cu.size = 0.2
        cu.shear = 0.3
        cu.extrude = 0.002
        cu.align_x = "CENTER"
        cu.align_y = "CENTER"
        tmp = bpy.data.objects.new("tmp_text", cu)
        scene.collection.objects.link(tmp)
        bpy.context.view_layer.update()
        me = bpy.data.meshes.new_from_object(tmp.evaluated_get(bpy.context.evaluated_depsgraph_get()))
        bpy.data.objects.remove(tmp)
        # text faces +Z and reads along +X; turn it to face outward, reading front-to-back on either side
        basis = Matrix(((-side, 0, 0), (0, 0, side), (0, 1, 0)))
        link(f"Decal_GT3RS_{tag}", me, GLOSS_BLACK, trs(h[0] + h[1] * 0.012, basis))
    h = hit((0.6, 0.8 * side, 3), (0, 0, -1))
    if h:
        p = h[0]
        box(f"Mirror_Stalk_{tag}", (0.05, 0.018, 0.1), TRIM, trs(p + Vector((0, 0.06 * side, 0.04)), Euler((0.6 * side, 0, 0))))
        sphere(f"Mirror_{tag}", 0.1, PAINT, trs(p + Vector((-0.01, 0.15 * side, 0.1)), scale=(0.55, 1.05, 0.52)), 24, 16)
    box(f"Side_Skirt_{tag}", (2.1, 0.06, 0.03), TRIM, trs((-0.05, 0.885 * side, 0.155)))

# ---------------------------------------------------------------- rear: light bar, exhausts, diffuser

tail_pts = []
for i in range(-8, 9):
    h = hit((-3, i * 0.1, 0.8), (1, 0, 0))
    if h:
        tail_pts.append((h[0].x - 0.006, h[0].y, 0.8))
if len(tail_pts) > 2:
    tube("Taillight_Bar", tail_pts, 0.013, TAIL, sides=8)
for side in (-1, 1):
    tag = "L" if side > 0 else "R"
    h = hit((-3, 0.1 * side, 0.36), (1, 0, 0))
    if h:
        rot = Euler((0, math.pi / 2, 0))
        cyl(f"Exhaust_{tag}", 0.048, 0.048, 0.14, CHROME, trs((h[0].x + 0.02, 0.1 * side, 0.36), rot), 28, caps=False)
        cyl(f"Exhaust_{tag}_Inner", 0.044, 0.044, 0.005, TRIM, trs((h[0].x + 0.04, 0.1 * side, 0.36), rot), 24)
box("Diffuser", (0.3, 1.4, 0.02), TRIM, trs((-2.18, 0, 0.26)))
for i, yy in enumerate((-0.45, -0.15, 0.15, 0.45)):
    box(f"Diffuser_Fin{i}", (0.3, 0.008, 0.1), TRIM, trs((-2.17, yy, 0.3)))


# ---------------------------------------------------------------- swan-neck rear wing

def bezier2(p0, p1, p2, p3, n=24):
    return [tuple((1 - t) ** 3 * a + 3 * (1 - t) ** 2 * t * b + 3 * (1 - t) * t * t * c + t ** 3 * d
                  for a, b, c, d in zip(p0, p1, p2, p3)) for t in (i / n for i in range(n))]


foil = (bezier2((0, 0), (0.08, 0.012), (0.25, 0.01), (0.40, 0.0))
        + [(0.40, -0.008)]
        + bezier2((0.40, -0.008), (0.28, -0.03), (0.10, -0.06), (0.0, -0.03))
        + bezier2((0.0, -0.03), (-0.012, -0.02), (-0.012, -0.006), (0, 0), 6)[1:])
SPAN = 1.76
bm = bmesh.new()
left = [bm.verts.new((-u, SPAN / 2, v)) for u, v in foil]
right = [bm.verts.new((-u, -SPAN / 2, v)) for u, v in foil]
for i in range(len(foil)):
    j = (i + 1) % len(foil)
    bm.faces.new((left[i], left[j], right[j], right[i]))
bm.faces.new(left)
bm.faces.new(list(reversed(right)))
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
wing_m = trs((-1.92, 0, 1.37), Euler((0, 0.12, 0)))
link("Wing_Mainplane", bm, PAINT, wing_m, smooth=True)
box("Wing_Gurney", (0.06, SPAN, 0.01), TRIM, wing_m @ trs((-0.42, 0, 0.012), Euler((0, 0.9, 0))))
for side in (-1, 1):
    tag = "L" if side > 0 else "R"
    box(f"Wing_Endplate_{tag}", (0.54, 0.012, 0.25), TRIM, wing_m @ trs((-0.2, 0.886 * side, -0.03)))
    h = hit((-1.98, 0.32 * side, 3), (0, 0, -1))
    z0 = h[0].z if h else 0.9
    tube(f"Wing_SwanNeck_{tag}", [(-1.98, 0.32 * side, z0 - 0.02), (-2.0, 0.32 * side, z0 + 0.2), (-1.98, 0.32 * side, 1.46),
                                  (-2.06, 0.32 * side, 1.47), (-2.12, 0.32 * side, 1.40)], 0.017, TRIM)


# ---------------------------------------------------------------- wheels

def wheel(tag, axle_x, rt, width, side):
    hw, rim = width / 2, rt - 0.11
    y = (curve(WID, axle_x) - 0.165) * side
    # local frame: wheel axis = local +Z pointing outboard
    m = trs((axle_x, y, rt), Euler((-math.pi / 2 * side, 0, 0)))
    prof = [(rim, -hw + 0.012), (rt - 0.03, -hw), (rt - 0.008, -hw + 0.02), (rt, -hw + 0.05),
            (rt, hw - 0.05), (rt - 0.008, hw - 0.02), (rt - 0.03, hw), (rim, hw - 0.012)]
    seg = 64
    bm = bmesh.new()
    rings = [[bm.verts.new((r * math.cos(2 * math.pi * k / seg), r * math.sin(2 * math.pi * k / seg), a)) for k in range(seg)] for r, a in prof]
    for a, b in zip(rings, rings[1:]):
        for k in range(seg):
            bm.faces.new((a[k], a[(k + 1) % seg], b[(k + 1) % seg], b[k]))
    link(f"Wheel_{tag}_Tyre", bm, TIRE, m, smooth=True)
    cyl(f"Wheel_{tag}_Barrel", rim, rim, width - 0.03, RIM, m, 48, caps=False)
    torus(f"Wheel_{tag}_Pinstripe", rim - 0.004, 0.007, PAINT, m @ trs((0, 0, hw - 0.022)), 64, 8)
    for i in range(10):
        a = 2 * math.pi * i / 10
        box(f"Wheel_{tag}_Spoke{i}", (rim - 0.05, 0.035, 0.03), RIM,
            m @ trs((math.cos(a) * (rim / 2 + 0.02), math.sin(a) * (rim / 2 + 0.02), hw - 0.06), Euler((0, 0, a))))
    cyl(f"Wheel_{tag}_Hub", 0.07, 0.065, 0.05, RIM, m @ trs((0, 0, hw - 0.055)))
    cyl(f"Wheel_{tag}_CenterLock", 0.036, 0.036, 0.04, PAINT, m @ trs((0, 0, hw - 0.03)), 6, smooth=False)
    cyl(f"Wheel_{tag}_Disc", rim - 0.04, rim - 0.04, 0.03, DISC, m @ trs((0, 0, -0.01)), 48)
    ca = 2.4
    box(f"Wheel_{tag}_Caliper", (0.16, 0.07, 0.06), PAINT,
        m @ trs((math.cos(ca) * (rim - 0.09), math.sin(ca) * (rim - 0.09), 0.035), Euler((0, 0, ca + math.pi / 2))))


for (ax, rt), width, pos in zip(AXLES, (0.29, 0.33), ("F", "R")):
    for side in (-1, 1):
        wheel(pos + ("L" if side > 0 else "R"), ax, rt, width, side)

# ---------------------------------------------------------------- exports (car only)

bpy.context.view_layer.update()
for ob in bpy.context.view_layer.objects:
    ob.select_set(ob.users_collection[0] == car_coll)
bpy.context.view_layer.objects.active = root

bpy.ops.export_scene.gltf(filepath=os.path.join(OUT_DIR, "gt3rs.glb"), export_format="GLB", use_selection=True, export_apply=True)
bpy.ops.export_scene.fbx(filepath=os.path.join(OUT_DIR, "gt3rs.fbx"), use_selection=True, object_types={"EMPTY", "MESH"},
                         apply_scale_options="FBX_SCALE_ALL", axis_forward="-Z", axis_up="Y")

# ---------------------------------------------------------------- studio: cyclorama, lights, camera

bm = bmesh.new()
prof = [(-12, 0)] + [(6 + 4 * math.sin(a), 4 - 4 * math.cos(a)) for a in (i / 12 * math.pi / 2 for i in range(13))] + [(10, 12)]
# backdrop sweeps up behind the car, away from the camera (camera sits at +X/-Y)
back, across = Vector((-0.7071, 0.7071, 0)), Vector((0.7071, 0.7071, 0))
cyc_rows = [[bm.verts.new(back * d + across * yy + Vector((0, 0, z))) for d, z in prof] for yy in (-15, 15)]
for i in range(len(prof) - 1):
    bm.faces.new((cyc_rows[0][i], cyc_rows[0][i + 1], cyc_rows[1][i + 1], cyc_rows[1][i]))
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
cyc_mat = material("Studio_Cyc", "#c9cdd1", 0.0, 0.6)
cyc = link("Studio_Cyclorama", bm, cyc_mat, coll=studio_coll, smooth=True)
for f in cyc.data.polygons:
    if f.normal.z < 0:
        f.flip()

world = bpy.data.worlds.new("Studio")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = srgb("#7d848b")
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.6
scene.world = world


def area(name, loc, target, size, power, color=(1, 1, 1)):
    li = bpy.data.lights.new(name, "AREA")
    li.shape = "RECTANGLE"
    li.size, li.size_y = size
    li.energy = power
    li.color = color
    ob = bpy.data.objects.new(name, li)
    studio_coll.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()


area("Key_Top", (0.5, 0, 6), (0, 0, 0), (7, 3), 2200)
area("Fill_Front", (7, -5, 2.5), (0, 0, 0.6), (3, 3), 900)
area("Rim_Back", (-6, 4, 3), (0, 0, 0.8), (4, 2), 700, (0.9, 0.95, 1.0))

cam_data = bpy.data.cameras.new("Camera")
cam_data.lens = 55
cam = bpy.data.objects.new("Camera", cam_data)
studio_coll.objects.link(cam)
cam.location = (6.4, -5.6, 2.3)
cam.rotation_euler = (Vector((0.1, 0, 0.55)) - cam.location).to_track_quat("-Z", "Y").to_euler()
scene.camera = cam

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT_DIR, "gt3rs.blend"))

if RENDER:
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 96
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 960
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Punchy"
    scene.render.filepath = os.path.join(OUT_DIR, "gt3rs_render.png")
    bpy.ops.render.render(write_still=True)

tris = {ob.name: sum(len(p.vertices) - 2 for p in ob.data.polygons) for ob in car_coll.objects if ob.type == "MESH"}
print(f"objects: {len(tris)}  total tris: {sum(tris.values())}  largest: {max(tris.items(), key=lambda kv: kv[1])}")
print("wrote", OUT_DIR)
