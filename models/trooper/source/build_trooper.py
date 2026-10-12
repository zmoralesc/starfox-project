"""Builds the Shogun Trooper (the armoured humanoid enemy) in Blender, rigs
and animates it, checks it and exports it.

Run from the command line (a factory-empty scene; writes trooper.glb and
the preview renders):
    cd models/trooper/source
    blender --background --python build_trooper.py -- --export
Without --export it builds, checks and renders only.

Like build_enemy_fighter.py, every size is in GAME coordinates (Godot: +X
right, +Y up, -Z forward), in metres, converted to Blender's Z-up frame by
G(). The origin is the hips (the root bone's head): soles at y = -3.5, top
of the helmet dome at +3.5 (the rangefinder reaches 4.0). The exported
model faces -Z in Godot.

Materials (the game swaps them for toon materials and recolours some per
enemy type; keep the names):
    Trooper_Body     main armour, a dark warm gunmetal
    Trooper_Accent   painted plates: shoulder plate edges, skirt, shield
                     emblem, helmet cheeks (deep crimson)
    Trooper_Lights   visor T, cannon ring, backpack vents, heel nozzles,
                     rangefinder lens (orange-yellow glow)
    Trooper_Joint    dark undersuit between the plates

Rig: one armature ("Rig"), rigid skinning (each piece is weighted 100% to
one bone). Rest pose = standing, feet flat, elbows bent 90 so the cannon
and the left forearm point forward. Every bone has roll 0, so with the
bones laid out along the world axes their local frames come out clean:
    bones pointing up (root, hips, spine, chest, head, rangefinder,
    backpack): local X = +X, Y = +Y (up), Z = +Z (back) -> identity in Godot
    bones pointing down (upper arms, thighs, shins, skirts): X = +X,
    Y = -Y (down), Z = -Z (forward); +X rotation swings the tail forward
    forearms (pointing forward): X = +X, Y = -Z (forward), Z = +Y (up);
    +X rotation raises the tail
    shoulders (pointing out): Y = +-X, Z = up

Markers (empties parented to bones; Godot puts them under BoneAttachment3D
nodes): MuzzleTipL / MuzzleTipR (forearm.R, -Z out of the barrels),
BackpackPoint and SmokePoint (backpack), VisorPoint (head), HeelL / HeelR
(foot.L / foot.R, -Z pointing down out of the nozzle).

Animations are Blender actions, one NLA track each, exported by track name
(sampled at FPS): hover_idle, dash, brake, fire_windup, fire_recoil, land,
landed_idle, take_off, death.
"""

import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

EXPORT = "--export" in sys.argv or globals().get("FORCE_EXPORT", False)
HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else \
    r"C:\dev\spaceship-project\models\trooper\source"
OUT = os.path.dirname(HERE)
PREVIEW_DIR = os.path.join(HERE, "preview")
FPS = 60

# (sRGB colour as the game shows it, emission strength).
COLORS = {
    "Body": ((0.24, 0.22, 0.20), 0.0),
    "Accent": ((0.46, 0.07, 0.08), 0.0),
    "Lights": ((1.0, 0.62, 0.12), 10.0),
    "Joint": ((0.09, 0.09, 0.10), 0.0),
}

# --- Key positions (game coordinates), shared by the mesh and the rig.
HIP_X = 0.7            # leg spacing
SHOULDER = Vector((1.35, 2.05, 0.0))
ELBOW_Y = 0.55
KNEE_Y = -1.6
ANKLE_Y = -3.0
SOLE_Y = -3.5
HEEL_Z = 0.38          # heel nozzle centre
CANNON_Y = 0.45        # barrel height
BARREL_X = 0.19        # barrel spacing from the forearm line
MUZZLE_Z = -2.32
RANGEFINDER_PIVOT = Vector((-0.76, 2.95, -0.1))
BACKPACK_C = Vector((0.0, 1.5, 1.05))
SHIELD_C = Vector((-2.3, 0.45, -1.15))
SHIELD_YAW = 220.0     # degrees about Y: the shield's face points front-left

# Bone: (head, tail, parent). Children of the same joint share its head.
BONES = {
    "root": ((0, 0, 0), (0, 0.6, 0), None),
    "hips": ((0, 0, 0), (0, 0.45, 0), "root"),
    "spine": ((0, 0.45, 0), (0, 1.05, 0), "hips"),
    "chest": ((0, 1.05, 0), (0, 2.3, 0), "spine"),
    "head": ((0, 2.4, 0), (0, 3.4, 0), "chest"),
    "rangefinder": (tuple(RANGEFINDER_PIVOT), (RANGEFINDER_PIVOT.x, 3.9, RANGEFINDER_PIVOT.z), "head"),
    "backpack": ((0, 1.1, BACKPACK_C.z), (0, 1.9, BACKPACK_C.z), "chest"),
    "shoulder.R": ((0.95, SHOULDER.y, 0), tuple(SHOULDER), "chest"),
    "shoulder.L": ((-0.95, SHOULDER.y, 0), (-SHOULDER.x, SHOULDER.y, 0), "chest"),
    "upper_arm.R": (tuple(SHOULDER), (SHOULDER.x, ELBOW_Y, 0), "shoulder.R"),
    "upper_arm.L": ((-SHOULDER.x, SHOULDER.y, 0), (-SHOULDER.x, ELBOW_Y, 0), "shoulder.L"),
    "forearm.R": ((SHOULDER.x, ELBOW_Y, 0), (SHOULDER.x, ELBOW_Y, -1.4), "upper_arm.R"),
    "forearm.L": ((-SHOULDER.x, ELBOW_Y, 0), (-SHOULDER.x, ELBOW_Y, -1.4), "upper_arm.L"),
    "thigh.R": ((HIP_X, -0.2, 0), (HIP_X, KNEE_Y, 0), "hips"),
    "thigh.L": ((-HIP_X, -0.2, 0), (-HIP_X, KNEE_Y, 0), "hips"),
    "shin.R": ((HIP_X, KNEE_Y, 0), (HIP_X, ANKLE_Y, 0), "thigh.R"),
    "shin.L": ((-HIP_X, KNEE_Y, 0), (-HIP_X, ANKLE_Y, 0), "thigh.L"),
    "foot.R": ((HIP_X, ANKLE_Y, 0), (HIP_X, -3.3, -0.5), "shin.R"),
    "foot.L": ((-HIP_X, ANKLE_Y, 0), (-HIP_X, -3.3, -0.5), "shin.L"),
    "toe.R": ((HIP_X, -3.3, -0.5), (HIP_X, -3.4, -1.05), "foot.R"),
    "toe.L": ((-HIP_X, -3.3, -0.5), (-HIP_X, -3.4, -1.05), "foot.L"),
    "skirt.F": ((0, -0.2, -0.55), (0, -1.4, -0.55), "hips"),
    "skirt.B": ((0, -0.2, 0.55), (0, -1.4, 0.55), "hips"),
    "skirt.L": ((-1.22, -0.2, 0), (-1.22, -1.3, 0), "hips"),
    "skirt.R": ((1.22, -0.2, 0), (1.22, -1.3, 0), "hips"),
}
THIGH_LEN = -0.2 - KNEE_Y
SHIN_LEN = KNEE_Y - ANKLE_Y

# (name, bone, game position, orientation): "forward" = the marker's -Z is
# the model's -Z; "down" = its -Z points at -Y.
MARKERS = [
    ("MuzzleTipL", "forearm.R", (SHOULDER.x - BARREL_X, CANNON_Y, MUZZLE_Z), "forward"),
    ("MuzzleTipR", "forearm.R", (SHOULDER.x + BARREL_X, CANNON_Y, MUZZLE_Z), "forward"),
    ("BackpackPoint", "backpack", tuple(BACKPACK_C), "forward"),
    ("SmokePoint", "backpack", (0.0, 0.3, BACKPACK_C.z), "forward"),
    ("VisorPoint", "head", (0.0, 2.95, -0.82), "forward"),
    ("HeelL", "foot.L", (-HIP_X, SOLE_Y, HEEL_Z), "down"),
    ("HeelR", "foot.R", (HIP_X, SOLE_Y, HEEL_Z), "down"),
]

X, Y, Z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))
# For each extrusion axis: the two outline axes (u, v) and the axis itself.
AX = {"x": (Y, Z, X), "y": (X, Z, Y), "z": (X, Y, Z)}


def G(x, y, z):
    """Game (Y up, -Z forward) to Blender (Z up, +Y forward)."""
    return Vector((x, -z, y))


def to_game(v):
    return Vector((v.x, v.z, -v.y))


def material(name):
    full = "Trooper_" + name
    m = bpy.data.materials.get(full) or bpy.data.materials.new(full)
    srgb, emit = COLORS[name]
    rgb = tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb)
    m.use_nodes = True
    bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.6
    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["Emission Strength"].default_value = emit
    if emit > 0:
        bsdf.inputs["Emission Color"].default_value = (*rgb, 1.0)
    # Workbench previews show diffuse_color: lift the glow so it reads.
    m.diffuse_color = (*rgb, 1.0) if emit == 0 else (1.0, 0.75, 0.2, 1.0)
    return m


# ---------------------------------------------------------------- geometry
COL = None
PIECES = []


def piece(name, verts, faces, mat, bone, smooth=False):
    """One closed mesh object (game-space verts), tagged with its bone."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([G(*v) for v in verts], [], faces)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(material(mat))
    for p in me.polygons:
        p.use_smooth = smooth and len(p.vertices) <= 4
    o = bpy.data.objects.new(name, me)
    COL.objects.link(o)
    o["bone"] = bone
    PIECES.append(o)
    return o


def ring(outline, axis, a):
    u, v, n = AX[axis]
    return [u * p[0] + v * p[1] + n * a for p in outline]


def loft(name, rings, mat, bone, smooth=False, xform=None):
    """Closed solid through rings of game points (same count), with end caps."""
    if xform is not None:
        rings = [[xform @ p for p in r] for r in rings]
    n = len(rings[0])
    verts = [tuple(p) for r in rings for p in r]
    faces = []
    for k in range(len(rings) - 1):
        b = k * n
        faces += [(b + i, b + (i + 1) % n, b + n + (i + 1) % n, b + n + i) for i in range(n)]
    faces.append(tuple(range(n)))
    faces.append(tuple(range((len(rings) - 1) * n, len(rings) * n)))
    return piece(name, verts, faces, mat, bone, smooth)


def prism(name, outline, axis, a0, a1, mat, bone, scale1=1.0, shift1=(0.0, 0.0), xform=None, smooth=False):
    """A 2D outline (in the plane across `axis`) extruded from a0 to a1; the
    far ring may be scaled about the outline's centre and shifted."""
    cx = sum(p[0] for p in outline) / len(outline)
    cy = sum(p[1] for p in outline) / len(outline)
    far = [(cx + (p[0] - cx) * scale1 + shift1[0], cy + (p[1] - cy) * scale1 + shift1[1]) for p in outline]
    return loft(name, [ring(outline, axis, a0), ring(far, axis, a1)], mat, bone, smooth, xform)


def chamfered(hu, hv, c):
    """A rectangle outline with its corners cut by c (an octagon)."""
    if c <= 0:
        return [(-hu, -hv), (hu, -hv), (hu, hv), (-hu, hv)]
    return [(-hu + c, -hv), (hu - c, -hv), (hu, -hv + c), (hu, hv - c),
            (hu - c, hv), (-hu + c, hv), (-hu, hv - c), (-hu, -hv + c)]


def box(name, center, size, mat, bone, chamfer=0.0, axis="z", xform=None):
    """A box; chamfer cuts the edges parallel to `axis`. With xform the
    centre is in its frame (the box is rotated about its own centre)."""
    k = "xyz".index(axis)
    uv = [i for i in range(3) if i != k]
    outline = chamfered(size[uv[0]] / 2, size[uv[1]] / 2, chamfer)
    M = (xform if xform is not None else Matrix.Identity(4)) @ Matrix.Translation(Vector(center))
    return prism(name, outline, axis, -size[k] / 2, size[k] / 2, mat, bone, xform=M)


def lathe(name, profile, segments, mat, bone, axis="y", origin=(0, 0, 0), scale=(1.0, 1.0),
          offset_deg=-90.0, smooth=True, xform=None):
    """A solid of revolution. `profile` is a closed polygon of (radius,
    height) points; edges along the axis (both radii 0) are skipped, so a
    profile touching the axis makes a closed shape and one clear of it makes
    a ring with a hole. The first vertex column sits at the front (-Z)."""
    u, v, n = AX[axis]
    verts, index = [], {}
    for i, (r, h) in enumerate(profile):
        if r == 0:
            index[(i, 0)] = len(verts)
            verts.append(n * h)
        else:
            for j in range(segments):
                t = math.radians(offset_deg) + 2 * math.pi * j / segments
                index[(i, j)] = len(verts)
                verts.append(u * (r * math.cos(t) * scale[0]) + v * (r * math.sin(t) * scale[1]) + n * h)
    faces = []
    m = len(profile)
    for i in range(m):
        i1 = (i + 1) % m
        r0, r1 = profile[i][0], profile[i1][0]
        if r0 == 0 and r1 == 0:
            continue
        for j in range(segments):
            j1 = (j + 1) % segments
            if r0 == 0:
                faces.append((index[(i, 0)], index[(i1, j)], index[(i1, j1)]))
            elif r1 == 0:
                faces.append((index[(i, j)], index[(i1, 0)], index[(i, j1)]))
            else:
                faces.append((index[(i, j)], index[(i, j1)], index[(i1, j1)], index[(i1, j)]))
    o = Vector(origin)
    verts = [tuple(o + (xform @ p if xform is not None else p)) for p in verts]
    return piece(name, verts, faces, mat, bone, smooth)


def sphere(name, center, r, mat, bone, segments=12, rings=4):
    profile = [(0.0, r)]
    for k in range(1, rings):
        a = math.pi * k / rings
        profile.append((r * math.sin(a), r * math.cos(a)))
    profile.append((0.0, -r))
    return lathe(name, profile, segments, mat, bone, origin=center)


def tube(name, p0, p1, r0, r1, mat, bone, segments=12, smooth=True):
    """A cylinder/cone from p0 (radius r0) to p1 (radius r1)."""
    d = Vector(p1) - Vector(p0)
    R = Y.rotation_difference(d.normalized()).to_matrix().to_4x4()
    return lathe(name, [(0.0, 0.0), (r0, 0.0), (r1, d.length), (0.0, d.length)], segments, mat, bone,
                 origin=p0, smooth=smooth, xform=R, offset_deg=-90.0 + 180.0 / segments)


def slab(name, path, thickness, z0, z1, mat, bone, away):
    """A curved plate: `path` is a polyline in (x, y) (its inner surface),
    thickened away from the point `away`, extruded along z."""
    pts = [Vector(p) for p in path]
    normals = []
    for i in range(len(pts) - 1):
        d = pts[i + 1] - pts[i]
        n = Vector((-d.y, d.x)).normalized()
        mid = (pts[i] + pts[i + 1]) / 2
        if n.dot(mid - Vector(away)) < 0:
            n = -n
        normals.append(n)
    outer = []
    for i, p in enumerate(pts):
        n = normals[min(i, len(normals) - 1)] if i in (0, len(pts) - 1) else (normals[i - 1] + normals[i]).normalized()
        outer.append(p + n * thickness)
    outline = [tuple(p) for p in pts] + [tuple(p) for p in reversed(outer)]
    return prism(name, outline, "z", z0, z1, mat, bone)


# ---------------------------------------------------------------- the trooper
def sym(fn):
    """Build a right-side piece, then its mirror (x negated), by calling
    fn(side_name, sign) for sign +1 (right, ".R") and -1 (left, ".L")."""
    fn("R", 1.0)
    fn("L", -1.0)


def build_torso():
    # Hips: the pelvis block, widening upward.
    loft("Pelvis", [ring(chamfered(1.15, 0.5, 0.25), "y", -0.55), ring(chamfered(1.3, 0.55, 0.3), "y", 0.4)],
         "Body", "hips")
    box("Belt", (0, 0.15, -0.58), (2.4, 0.26, 0.14), "Body", "hips")
    box("Buckle", (0, 0.15, -0.67), (0.4, 0.34, 0.06), "Body", "hips")
    # Abdomen: dark undersuit with a front band.
    loft("Abdomen", [ring(chamfered(0.8, 0.45, 0.2), "y", 0.3), ring(chamfered(0.9, 0.5, 0.22), "y", 1.05)],
         "Joint", "spine")
    prism("AbdomenBand", [(-0.78, 0.5), (0.78, 0.5), (0.82, 0.75), (0.82, 0.95), (-0.82, 0.95), (-0.82, 0.75)],
          "z", -0.3, -0.66, "Body", "spine")
    # Chest: a tapered block with two layered front plates.
    loft("Torso", [ring(chamfered(0.95, 0.5, 0.22), "y", 0.95), ring(chamfered(1.25, 0.62, 0.3), "y", 2.3)],
         "Body", "chest")
    upper = [(-1.15, 1.65), (1.15, 1.65), (1.2, 2.0), (1.05, 2.28), (-1.05, 2.28), (-1.2, 2.0)]
    loft("ChestPlateUpper", [ring(upper, "z", -0.45), [Vector((x, y, -0.84 + (2.28 - y) * 0.1)) for x, y in upper]],
         "Body", "chest")
    lower = [(-1.0, 1.2), (1.0, 1.2), (1.08, 1.55), (1.08, 1.72), (-1.08, 1.72), (-1.08, 1.55)]
    loft("ChestPlateLower", [ring(lower, "z", -0.4), [Vector((x, y, -0.75 + (1.72 - y) * 0.1)) for x, y in lower]],
         "Body", "chest")
    # Neck and collar.
    tube("Neck", (0, 2.2, 0), (0, 2.75, 0), 0.27, 0.27, "Joint", "chest")
    lathe("Collar", [(0.33, 2.28), (0.62, 2.28), (0.56, 2.44), (0.33, 2.44)], 12, "Body", "chest")


def build_backpack():
    c = BACKPACK_C
    box("Backpack", (c.x, c.y, c.z), (2.0, 1.8, 0.95), "Body", "backpack", chamfer=0.15)
    box("BackpackLid", (c.x, 2.45, c.z - 0.05), (1.4, 0.2, 0.7), "Body", "backpack", chamfer=0.05)
    for s in (1.0, -1.0):
        box("BackpackIntake%s" % ("R" if s > 0 else "L"), (s * 1.08, 1.65, c.z - 0.05), (0.2, 1.0, 0.6), "Body",
            "backpack")
    for i, y in enumerate((1.95, 1.7, 1.45)):
        box("BackpackVent%d" % i, (c.x, y, c.z + 0.5), (1.3, 0.14, 0.1), "Lights", "backpack")
    for s in (1.0, -1.0):
        side = "R" if s > 0 else "L"
        lathe("BackpackNozzle" + side, [(0.18, 0.75), (0.26, 0.3), (0.4, -0.05), (0.3, -0.05), (0.2, 0.25), (0.1, 0.55)],
              12, "Body", "backpack", origin=(s * 0.5, 0, c.z))
        lathe("BackpackGlow" + side, [(0.0, 0.5), (0.3, 0.05), (0.0, 0.05)], 12, "Lights", "backpack",
              origin=(s * 0.5, 0, c.z))


def build_head():
    dome = [(0, 3.5), (0.22, 3.48), (0.42, 3.4), (0.56, 3.26), (0.64, 3.1), (0.68, 2.88), (0.67, 2.72), (0.63, 2.6),
            (0.56, 2.55), (0, 2.55)]
    lathe("Dome", dome, 20, "Body", "head", scale=(1.0, 1.1))
    face = [(-0.55, 2.5), (0.55, 2.5), (0.62, 2.7), (0.62, 3.1), (0.5, 3.18), (-0.5, 3.18), (-0.62, 3.1), (-0.62, 2.7)]
    loft("Faceplate", [ring(face, "z", -0.2), [Vector((x * (0.86 + (y - 2.5) * 0.2), y, -0.8 + (3.18 - y) * 0.15)) for x, y in face]],
         "Body", "head")
    visor = [(-0.44, 3.08), (0.44, 3.08), (0.44, 2.92), (0.1, 2.9), (0.1, 2.58), (-0.1, 2.58), (-0.1, 2.9), (-0.44, 2.92)]
    loft("Visor", [ring(visor, "z", -0.6), [Vector((x, y, -0.84 + (3.18 - y) * 0.15)) for x, y in visor]],
         "Lights", "head")
    for s in (1.0, -1.0):
        cheek = [(s * 0.14, 2.88), (s * 0.52, 2.88), (s * 0.46, 2.6), (s * 0.17, 2.54)]
        loft("Cheek%s" % ("R" if s > 0 else "L"),
             [ring(cheek, "z", -0.5), [Vector((x, y, -0.86 + (3.18 - y) * 0.15 + (abs(x) - 0.14) * 0.1)) for x, y in cheek]],
             "Accent", "head")
    # A ridge down the brow: a strip over the dome's front meridian to the visor.
    outer = [(3.52, 0.0), (3.49, -0.33), (3.33, -0.59), (3.22, -0.7), (3.21, -0.84), (3.08, -0.86)]
    inner = [(3.4, 0.0), (3.38, -0.3), (3.22, -0.5), (3.1, -0.6), (3.1, -0.7), (3.0, -0.72)]
    prism("BrowRidge", outer + inner[::-1], "x", -0.05, 0.05, "Body", "head")
    # Left ear piece with the rangefinder stalk on it.
    box("Ear", (-0.74, 2.9, -0.08), (0.16, 0.34, 0.3), "Body", "head")
    p = RANGEFINDER_PIVOT
    box("RangefinderStalk", (p.x, 3.4, p.z), (0.08, 0.95, 0.1), "Body", "rangefinder")
    box("RangefinderBox", (p.x, 3.92, p.z), (0.3, 0.2, 0.36), "Body", "rangefinder")
    box("RangefinderLens", (p.x, 3.92, p.z - 0.18), (0.12, 0.1, 0.04), "Lights", "rangefinder")


def build_shoulders():
    def one(side, s):
        bone = "shoulder." + side
        joint = (s * SHOULDER.x, SHOULDER.y)
        lathe("ShoulderCap" + side, [(0, 2.6), (0.3, 2.58), (0.5, 2.38), (0.52, 2.2), (0, 2.2)], 12, "Body", bone,
              origin=(s * 1.25, 0, 0), offset_deg=-75.0)
        plates = [([(1.1, 2.55), (1.42, 2.32), (1.65, 2.0)], 0.7),
                  ([(1.38, 2.25), (1.62, 1.92), (1.8, 1.55)], 0.66),
                  ([(1.58, 1.8), (1.78, 1.45), (1.9, 1.05)], 0.62)]
        for i, (path, d) in enumerate(plates):
            path = [(s * x, y) for x, y in path]
            slab("Sode%s%d" % (side, i), path, 0.16, -d, d, "Body", bone, joint)
            # The painted lower edge, proud of the plate's outer face.
            a, b = Vector(path[1]), Vector(path[2])
            n = Vector((-(b - a).y, (b - a).x)).normalized()
            if n.dot((a + b) / 2 - Vector(joint)) < 0:
                n = -n
            edge = [tuple(a + n * 0.13 + (b - a).normalized() * 0.04), tuple(b + n * 0.13 - (b - a).normalized() * 0.02)]
            slab("SodeEdge%s%d" % (side, i), edge, 0.06, -(d - 0.05), d - 0.05, "Accent", bone, joint)
    sym(one)


def build_arms():
    def one(side, s):
        x = s * SHOULDER.x
        upper = "upper_arm." + side
        sphere("ShoulderJoint" + side, (x, SHOULDER.y, 0), 0.3, "Joint", upper)
        tube("UpperArm" + side, (x, SHOULDER.y, 0), (x, ELBOW_Y, 0), 0.27, 0.27, "Joint", upper)
        lathe("UpperArmPlate" + side, [(0, 1.78), (0.37, 1.78), (0.35, 0.85), (0, 0.85)], 12, "Body", upper,
              origin=(x, 0, 0), offset_deg=-75.0)
        sphere("Elbow" + side, (x, ELBOW_Y, 0), 0.33, "Joint", "forearm." + side)
        box("ElbowGuard" + side, (x + s * 0.34, ELBOW_Y, 0.08), (0.2, 0.44, 0.44), "Body", "forearm." + side,
            chamfer=0.08, axis="x")
    sym(one)
    # Right forearm: the cannon.
    x = SHOULDER.x
    box("CannonHousing", (x, 0.5, -0.55), (0.78, 0.72, 1.8), "Body", "forearm.R", chamfer=0.14)
    box("CannonReceiver", (x, 0.95, -0.45), (0.46, 0.32, 0.9), "Body", "forearm.R", chamfer=0.06)
    for s, side in ((-1.0, "L"), (1.0, "R")):
        bx = x + s * BARREL_X
        lathe("Barrel" + side, [(0, -1.2), (0.13, -1.2), (0.13, MUZZLE_Z + 0.04), (0, MUZZLE_Z + 0.04)], 8, "Joint",
              "forearm.R", axis="z", origin=(bx, CANNON_Y, 0))
        lathe("MuzzleRing" + side, [(0, MUZZLE_Z + 0.2), (0.17, MUZZLE_Z + 0.2), (0.17, MUZZLE_Z), (0, MUZZLE_Z)], 8,
              "Body", "forearm.R", axis="z", origin=(bx, CANNON_Y, 0))
    box("CannonRing", (x, CANNON_Y, -1.72), (0.86, 0.66, 0.16), "Lights", "forearm.R", chamfer=0.12)
    box("CannonSidePlate", (x + 0.42, 0.5, -0.6), (0.12, 0.5, 1.2), "Body", "forearm.R", chamfer=0.03, axis="x")
    # Left forearm: a gauntlet with the tower shield on a bracket.
    x = -SHOULDER.x
    tube("Forearm", (x, ELBOW_Y, 0), (x, ELBOW_Y, -1.3), 0.3, 0.3, "Body", "forearm.L")
    box("Fist", (x, ELBOW_Y, -1.45), (0.5, 0.5, 0.45), "Body", "forearm.L", chamfer=0.08)
    box("Vambrace", (x, 0.8, -0.65), (0.5, 0.2, 0.9), "Body", "forearm.L", chamfer=0.04, axis="z")
    M = Matrix.Translation(SHIELD_C) @ Matrix.Rotation(math.radians(SHIELD_YAW), 4, "Y")
    box("ShieldBracket", (0, 0.05, -0.45), (0.5, 0.4, 0.95), "Joint", "forearm.L", xform=M)
    shield = [(-0.6, -1.65), (0.6, -1.65), (0.6, 1.25), (0.3, 1.55), (-0.3, 1.55), (-0.6, 1.25)]
    prism("Shield", shield, "z", -0.06, 0.06, "Body", "forearm.L", xform=M)
    prism("ShieldRim", [(-0.5, -1.55), (0.5, -1.55), (0.5, 1.2), (0.26, 1.44), (-0.26, 1.44), (-0.5, 1.2)],
          "z", 0.0, 0.09, "Body", "forearm.L", xform=M)
    prism("ShieldEmblem", [(0, -0.3), (0.28, 0.2), (0, 0.7), (-0.28, 0.2)], "z", 0.05, 0.14, "Accent", "forearm.L",
          xform=M)


def build_skirt():
    """Four hanging kusazuri, three lames each, stepping outward."""
    def plate(bone, pivot, outward, across, half_width):
        # outward: the horizontal unit vector the plate leans toward; across:
        # the horizontal unit vector along its width. Each lame is a
        # parallelogram in the (outward, y) plane extruded across.
        lean = 0.25 / 1.2
        for i in range(3):
            y0 = -0.25 - 0.38 * i
            y1 = y0 - 0.46
            w = half_width - 0.04 * i

            def d(y):
                return 0.035 * i + lean * (-0.2 - y)

            local = [(d(y0) - 0.06, y0), (d(y0) + 0.05, y0), (d(y1) + 0.05, y1), (d(y1) - 0.06, y1)]
            rings = [[pivot + outward * a + Y * y + across * t for a, y in local] for t in (-w, w)]
            loft("Skirt%s%d" % (bone[-1], i), rings, "Accent" if i > 0 else "Body", bone)
    plate("skirt.F", Vector((0, 0, -0.55)), -Z, X, 0.8)
    plate("skirt.B", Vector((0, 0, 0.55)), Z, X, 0.8)
    plate("skirt.L", Vector((-1.22, 0, 0)), -X, Z, 0.45)
    plate("skirt.R", Vector((1.22, 0, 0)), X, Z, 0.45)


def build_legs():
    def one(side, s):
        x = s * HIP_X
        thigh, shin, foot, toe = ("%s.%s" % (b, side) for b in ("thigh", "shin", "foot", "toe"))
        sphere("Hip" + side, (x, -0.2, 0), 0.4, "Joint", thigh)
        tube("Thigh" + side, (x, -0.1, 0), (x, KNEE_Y - 0.02, 0), 0.32, 0.3, "Joint", thigh)
        lathe("ThighPlate" + side, [(0, -0.45), (0.43, -0.45), (0.4, -1.3), (0, -1.3)], 12, "Body", thigh,
              origin=(x + s * 0.03, 0, -0.03), offset_deg=-75.0)
        sphere("Knee" + side, (x, KNEE_Y, 0), 0.34, "Joint", shin)
        box("Tasset" + side, (x, -0.9, -0.46), (0.5, 0.6, 0.16), "Body", thigh, chamfer=0.04, axis="z")
        box("KneeCap" + side, (x, KNEE_Y - 0.02, -0.36), (0.42, 0.44, 0.2), "Body", shin, chamfer=0.06, axis="z")
        tube("Shin" + side, (x, KNEE_Y, 0), (x, ANKLE_Y, 0), 0.27, 0.27, "Joint", shin)
        lathe("Greave" + side, [(0, -1.85), (0.4, -1.85), (0.35, -2.85), (0, -2.85)], 12, "Body", shin,
              origin=(x, 0, -0.02), offset_deg=-75.0)
        box("GreavePlate" + side, (x, -2.35, -0.4), (0.42, 0.7, 0.14), "Body", shin, chamfer=0.04, axis="z")
        sphere("Ankle" + side, (x, ANKLE_Y, 0), 0.28, "Joint", foot)
        box("AnkleGuard" + side, (x + s * 0.24, ANKLE_Y + 0.02, 0.0), (0.16, 0.42, 0.42), "Body", foot, chamfer=0.06,
            axis="x")
        # The foot: sole from the toe joint back to the heel step; the heel
        # block sits higher so the nozzle can hang below it.
        profile = [(-0.5, SOLE_Y), (-0.52, -3.2), (-0.4, -3.0), (0.45, -2.95), (0.66, -3.1), (0.64, -3.38),
                   (0.1, -3.4), (0.06, SOLE_Y)]
        prism("Foot" + side, [(y, z) for z, y in profile], "x", x - 0.42, x + 0.42, "Body", foot)
        toe_profile = [(-0.42, -3.1), (-0.42, -3.45), (-1.05, SOLE_Y), (-1.1, -3.3), (-0.9, -3.12)]
        prism("Toe" + side, [(y, z) for z, y in toe_profile], "x", x - 0.38, x + 0.38, "Body", toe)
        lathe("HeelNozzle" + side, [(0.16, -3.05), (0.26, SOLE_Y), (0.18, SOLE_Y), (0.1, -3.3)], 12, "Body", foot,
              origin=(x, 0, HEEL_Z))
        lathe("HeelGlow" + side, [(0.0, -3.2), (0.15, -3.44), (0.0, -3.44)], 12, "Lights", foot, origin=(x, 0, HEEL_Z))
    sym(one)


def build_mesh():
    build_torso()
    build_backpack()
    build_head()
    build_shoulders()
    build_arms()
    build_skirt()
    build_legs()


# ---------------------------------------------------------------- rig
def build_armature():
    data = bpy.data.armatures.new("Rig")
    arm = bpy.data.objects.new("Rig", data)
    COL.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    for name, (head, tail, parent) in BONES.items():
        eb = data.edit_bones.new(name)
        eb.head = G(*head)
        eb.tail = G(*tail)
        eb.roll = 0.0
        if parent:
            eb.parent = data.edit_bones[parent]
    bpy.ops.object.mode_set(mode="OBJECT")
    for pb in arm.pose.bones:
        pb.rotation_mode = "XYZ"
    return arm


def join_pieces(arm):
    """One mesh from every piece, each vertex in the vertex group of its
    piece's bone (rigid skinning), deformed by the armature."""
    me = bpy.data.meshes.new("Trooper")
    verts, faces, mats, smooth, bones = [], [], [], [], []
    mat_index = {}
    for o in PIECES:
        pm = o.data
        base = len(verts)
        verts += [v.co.copy() for v in pm.vertices]
        for p in pm.polygons:
            m = pm.materials[p.material_index]
            if m.name not in mat_index:
                mat_index[m.name] = len(mat_index)
                me.materials.append(m)
            faces.append(tuple(base + i for i in p.vertices))
            mats.append(mat_index[m.name])
            smooth.append(p.use_smooth)
        bones += [o["bone"]] * len(pm.vertices)
    me.from_pydata(verts, [], faces)
    for i, p in enumerate(me.polygons):
        p.material_index = mats[i]
        p.use_smooth = smooth[i]
    obj = bpy.data.objects.new("Trooper", me)
    COL.objects.link(obj)
    groups = {}
    for i, b in enumerate(bones):
        groups.setdefault(b, []).append(i)
    for b in BONES:
        obj.vertex_groups.new(name=b).add(groups.get(b, []), 1.0, "REPLACE")
    mod = obj.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    obj.parent = arm
    for o in PIECES:
        bpy.data.objects.remove(o)
    return obj


def build_markers(arm):
    """Empties parented to bones, placed in the rest pose."""
    bpy.context.view_layer.update()
    out = []
    for name, bone, pos, kind in MARKERS:
        e = bpy.data.objects.new(name, None)
        e.empty_display_type = "ARROWS"
        e.empty_display_size = 0.3
        COL.objects.link(e)
        e.parent = arm
        e.parent_type = "BONE"
        e.parent_bone = bone
        # -Z of the marker: along the model's -Z ("forward") or straight down.
        # The glTF exporter turns a bone-parented object +90 degrees about X
        # on top of the axis conversion (measured in Godot 4.7), so the empties
        # are placed a quarter turn back from where they should end up: an
        # identity empty comes out facing -Z in Godot, one turned -90 about X
        # comes out facing down.
        rot = Matrix.Identity(4) if kind == "forward" else Matrix.Rotation(math.radians(-90), 4, "X")
        world = Matrix.Translation(G(*pos)) @ rot
        # Bone parenting hangs the child off the bone's tail.
        pb = arm.pose.bones[bone]
        tail_mat = pb.matrix.copy()
        tail_mat.translation = pb.tail
        e.matrix_parent_inverse = Matrix.Identity(4)
        e.matrix_basis = (arm.matrix_world @ tail_mat).inverted() @ world
        out.append(e)
    bpy.context.view_layer.update()
    for e, (name, bone, pos, kind) in zip(out, MARKERS):
        got = to_game(e.matrix_world.translation)
        err = (got - Vector(pos)).length
        # What the exporter will make of it (see above): Blender -Z here reads as game -Z.
        fwd = to_game(e.matrix_world.to_3x3() @ Vector((0, 0, -1)))
        fwd = Vector((fwd.x, -fwd.z, fwd.y))
        print("MARKER %-14s on %-10s at %s  -Z=%s%s" % (name, bone, tuple(round(c, 2) for c in got),
                                                        tuple(round(c, 2) for c in fwd), "" if err < 1e-3 else "  MISPLACED"))
    return out


# ---------------------------------------------------------------- animation
UPPER_BODY = ["chest", "head", "rangefinder", "shoulder.R", "shoulder.L", "upper_arm.R", "upper_arm.L",
              "forearm.R", "forearm.L"]


def squat(theta_deg):
    """Leg angles that keep the feet flat on the ground with the knees bent
    by 2*theta, and the hips drop that goes with them."""
    t = math.radians(theta_deg)
    drop = (THIGH_LEN + SHIN_LEN) * (1.0 - math.cos(t))
    rot = {"thigh.R": (theta_deg, 0, 0), "thigh.L": (theta_deg, 0, 0),
           "shin.R": (-2 * theta_deg, 0, 0), "shin.L": (-2 * theta_deg, 0, 0),
           "foot.R": (theta_deg, 0, 0), "foot.L": (theta_deg, 0, 0)}
    return rot, drop


def squat_for_drop(drop):
    """The squat angle whose hips drop is `drop` (m)."""
    return math.degrees(math.acos(max(-1.0, min(1.0, 1.0 - drop / (THIGH_LEN + SHIN_LEN)))))


def hover_pose(arm_out=8.0):
    return {"thigh.R": (-12, 0, 0), "thigh.L": (-12, 0, 0), "shin.R": (-28, 0, 0), "shin.L": (-28, 0, 0),
            "foot.R": (-10, 0, 0), "foot.L": (-10, 0, 0), "toe.R": (-12, 0, 0), "toe.L": (-12, 0, 0),
            "upper_arm.R": (0, 0, -arm_out), "upper_arm.L": (0, 0, arm_out)}


def landed_pose(theta=8.0, roll=0.0, head_yaw=0.0):
    """Standing: knees bent, weight rolled onto one hip (roll, degrees: + = right hip up)."""
    rot, drop = squat(theta)
    loc = {"hips": (0, -drop, 0)}
    if roll:
        # The rolled hips raise one hip joint and lower the other; each leg
        # takes its own bend so both feet stay planted, and the thighs
        # cancel the roll so the legs stay vertical.
        dy = HIP_X * math.sin(math.radians(roll))
        for side, sgn in (("R", 1.0), ("L", -1.0)):
            t = squat_for_drop(max(0.0, drop - sgn * dy))
            rot["thigh." + side] = (t, 0, -roll)
            rot["shin." + side] = (-2 * t, 0, 0)
            rot["foot." + side] = (t, 0, 0)
        rot["hips"] = (0, 0, roll)
    rot["upper_arm.R"] = (0, 0, -5)
    rot["upper_arm.L"] = (0, 0, 5)
    rot["head"] = (0, head_yaw, 0)
    rot["chest"] = (0, head_yaw * 0.3, 0)
    return rot, loc


WINDUP_END = {"upper_arm.R": (35, 0, -20), "forearm.R": (-20, 0, 0), "shoulder.R": (8, 0, 0),
              "upper_arm.L": (40, 0, 12), "forearm.L": (0, 0, -25), "shoulder.L": (6, 0, 0),
              "chest": (-5, 0, 0), "head": (-3, 0, 0), "rangefinder": (-100, -20, 0)}


def action_fcurves(act):
    """The action's F-curves (Blender 5 keeps them in slotted channel bags)."""
    if hasattr(act, "fcurves"):
        return list(act.fcurves)
    return [fc for layer in act.layers for strip in layer.strips for bag in strip.channelbags for fc in bag.fcurves]


def merged(*poses):
    out = {}
    for p in poses:
        out.update(p)
    return out


class Clip:
    """Keyframes for one action: key(frame, rotations, locations, snap)."""

    def __init__(self, name, seconds, bones=None):
        self.name = name
        self.frames = int(round(seconds * FPS))
        self.bones = bones or list(BONES)
        self.keys = []

    def key(self, frame, rot, loc=None, snap=False):
        self.keys.append((frame, rot, loc or {}, snap))

    def bake(self, arm):
        act = bpy.data.actions.new(self.name)
        act.use_frame_range = True
        act.frame_start = 0
        act.frame_end = self.frames
        ad = arm.animation_data or arm.animation_data_create()
        ad.action = act
        if hasattr(ad, "action_slot") and ad.action_slot is None and hasattr(act, "slots"):
            ad.action_slot = act.slots.new("OBJECT", arm.name) if len(act.slots) == 0 else act.slots[0]
        snaps = set()
        for frame, rot, loc, snap in self.keys:
            for b in self.bones:
                pb = arm.pose.bones[b]
                pb.rotation_euler = [math.radians(a) for a in rot.get(b, (0, 0, 0))]
                pb.keyframe_insert("rotation_euler", frame=frame)
                pb.location = loc.get(b, (0, 0, 0))
                pb.keyframe_insert("location", frame=frame)
            if snap:
                snaps.add(frame)
        for fc in action_fcurves(act):
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT" if int(round(kp.co.x)) in snaps else "BEZIER"
                kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"
        for pb in arm.pose.bones:
            pb.rotation_euler = (0, 0, 0)
            pb.location = (0, 0, 0)
        ad.action = None
        track = ad.nla_tracks.new()
        track.name = self.name
        strip = track.strips.new(self.name, 0, act)
        if hasattr(strip, "action_slot") and hasattr(act, "slots") and len(act.slots):
            strip.action_slot = act.slots[0]
        strip.action_frame_start = 0
        strip.action_frame_end = self.frames
        return act


def build_animations(arm):
    hover = hover_pose()
    landed, landed_loc = landed_pose()
    clips = []

    c = Clip("hover_idle", 2.0)
    bob = 0.15
    for i, (y, swing) in enumerate(((0, 0), (bob, 4), (0, 0), (-bob, -4), (0, 0))):
        sway = {"skirt.F": (swing, 0, 0), "skirt.B": (swing, 0, 0), "skirt.L": (0, 0, swing * 0.7),
                "skirt.R": (0, 0, -swing * 0.7), "upper_arm.R": (0, 0, -8 - swing * 0.5),
                "upper_arm.L": (0, 0, 8 + swing * 0.5), "head": (swing * 0.5, 0, 0)}
        c.key(i * c.frames // 4, merged(hover, sway), {"root": (0, y, 0)})
    clips.append(c)

    c = Clip("dash", 0.5)
    crouch = merged(hover, {"spine": (-12, 0, 0), "chest": (-10, 0, 0), "head": (6, 0, 0),
                            "thigh.R": (-40, 0, 0), "thigh.L": (-40, 0, 0), "shin.R": (-40, 0, 0), "shin.L": (-40, 0, 0),
                            "foot.R": (-15, 0, 0), "foot.L": (-15, 0, 0),
                            "upper_arm.R": (-20, 0, -2), "upper_arm.L": (-20, 0, 2),
                            "forearm.R": (10, 0, 0), "forearm.L": (10, 0, 0),
                            "skirt.F": (-8, 0, 0), "skirt.B": (-20, 0, 0), "skirt.L": (-15, 0, 0), "skirt.R": (-15, 0, 0)})
    upright = merged(hover, {"chest": (3, 0, 0), "upper_arm.R": (0, 0, -20), "upper_arm.L": (0, 0, 20),
                             "skirt.F": (6, 0, 0), "skirt.B": (-6, 0, 0)})
    c.key(0, hover)
    c.key(10, crouch, {"hips": (0, -0.3, 0)})
    c.key(14, crouch, {"hips": (0, -0.3, 0)}, snap=True)
    c.key(15, upright)
    c.key(c.frames, hover)
    clips.append(c)

    c = Clip("brake", 0.3)
    stop = merged(hover, {"thigh.R": (30, 0, 0), "thigh.L": (30, 0, 0), "shin.R": (-15, 0, 0), "shin.L": (-15, 0, 0),
                          "foot.R": (15, 0, 0), "foot.L": (15, 0, 0), "toe.R": (0, 0, 0), "toe.L": (0, 0, 0),
                          "upper_arm.R": (15, 0, -40), "upper_arm.L": (15, 0, 40), "chest": (12, 0, 0),
                          "spine": (6, 0, 0), "head": (5, 0, 0), "skirt.F": (25, 0, 0), "skirt.B": (8, 0, 0),
                          "skirt.L": (15, 0, 0), "skirt.R": (15, 0, 0)})
    c.key(0, hover)
    c.key(9, stop, {"hips": (0, 0.05, 0)})
    c.key(c.frames, hover)
    clips.append(c)

    c = Clip("fire_windup", 0.4, UPPER_BODY)
    c.key(0, hover)
    c.key(c.frames, WINDUP_END)
    clips.append(c)

    c = Clip("fire_recoil", 0.15, UPPER_BODY)
    kick = merged(WINDUP_END, {"upper_arm.R": (25, 0, -20), "forearm.R": (-16, 0, 0), "shoulder.R": (12, 0, 0),
                               "chest": (-2, 0, 0)})
    c.key(0, WINDUP_END)
    c.key(2, kick)
    c.key(c.frames, WINDUP_END)
    clips.append(c)

    c = Clip("land", 0.6)
    under = merged(hover, {"thigh.R": (0, 0, 0), "thigh.L": (0, 0, 0), "shin.R": (0, 0, 0), "shin.L": (0, 0, 0),
                           "foot.R": (0, 0, 0), "foot.L": (0, 0, 0), "toe.R": (0, 0, 0), "toe.L": (0, 0, 0),
                           "upper_arm.R": (0, 0, -15), "upper_arm.L": (0, 0, 15), "chest": (3, 0, 0),
                           "skirt.F": (10, 0, 0)})
    deep_rot, deep_drop = squat(33.0)
    absorb = merged(hover, deep_rot, {"toe.R": (0, 0, 0), "toe.L": (0, 0, 0),
                                      "upper_arm.R": (-10, 0, -25), "upper_arm.L": (-10, 0, 25), "chest": (-8, 0, 0),
                                      "head": (-5, 0, 0), "skirt.F": (18, 0, 0), "skirt.B": (-12, 0, 0),
                                      "skirt.L": (0, 0, 15), "skirt.R": (0, 0, -15)})
    c.key(0, hover)
    c.key(12, under)
    c.key(22, absorb, {"hips": (0, -deep_drop, 0)})
    c.key(c.frames, landed, landed_loc)
    clips.append(c)

    c = Clip("landed_idle", 2.0)
    right, right_loc = landed_pose(roll=2.0, head_yaw=12.0)
    left, left_loc = landed_pose(roll=-2.0, head_yaw=-10.0)
    for i, (p, l) in enumerate(((landed, landed_loc), (right, right_loc), (landed, landed_loc), (left, left_loc),
                                (landed, landed_loc))):
        c.key(i * c.frames // 4, p, l)
    clips.append(c)

    c = Clip("take_off", 0.5)
    crouch_rot, crouch_drop = squat(30.0)
    crouch = merged(landed, crouch_rot, {"upper_arm.R": (-15, 0, -5), "upper_arm.L": (-15, 0, 5), "chest": (-6, 0, 0),
                                         "head": (-4, 0, 0)})
    push = merged(landed, {"thigh.R": (0, 0, 0), "thigh.L": (0, 0, 0), "shin.R": (0, 0, 0), "shin.L": (0, 0, 0),
                           "foot.R": (0, 0, 0), "foot.L": (0, 0, 0), "upper_arm.R": (10, 0, -20),
                           "upper_arm.L": (10, 0, 20), "chest": (4, 0, 0), "skirt.F": (12, 0, 0), "skirt.B": (-12, 0, 0),
                           "skirt.L": (0, 0, 12), "skirt.R": (0, 0, -12)})
    c.key(0, landed, landed_loc)
    c.key(9, crouch, {"hips": (0, -crouch_drop, 0)})
    c.key(16, push, {"hips": (0, 0.1, 0)})
    c.key(c.frames, hover)
    clips.append(c)

    c = Clip("death", 1.2)
    blown = merged(hover, {"backpack": (30, 0, 0), "chest": (-6, 0, 0)})
    fold = merged(hover, {"spine": (-30, 0, 0), "chest": (-30, 0, 0), "head": (-35, 0, 0),
                          "upper_arm.R": (0, 0, -15), "upper_arm.L": (0, 0, 15), "forearm.R": (-50, 0, 0),
                          "forearm.L": (-45, 0, 0), "thigh.R": (25, 0, 0), "thigh.L": (20, 0, 0),
                          "shin.R": (-70, 0, 0), "shin.L": (-60, 0, 0), "foot.R": (-35, 0, 0), "foot.L": (-30, 0, 0),
                          "toe.R": (-10, 0, 0), "toe.L": (-10, 0, 0), "root": (-25, 0, 0), "backpack": (80, 0, 0),
                          "skirt.F": (20, 0, 0), "skirt.B": (-20, 0, 0)})
    tumble = merged(fold, {"root": (-60, 0, 20), "spine": (-40, 0, 5), "chest": (-35, 0, 8), "head": (-40, 10, 0),
                           "upper_arm.R": (-20, 0, -30), "upper_arm.L": (-20, 0, 25), "skirt.L": (0, 0, 20),
                           "skirt.R": (0, 0, -20)})
    limp = merged(tumble, {"root": (-75, 0, 35), "head": (-45, 20, 10), "forearm.R": (-70, 0, 0),
                           "forearm.L": (-60, 0, 0)})
    c.key(0, hover)
    c.key(5, blown, {"backpack": (0, 0, 0.5)})
    c.key(20, fold, {"backpack": (0, 0, 0.8), "hips": (0, -0.6, 0)})
    c.key(45, tumble, {"backpack": (0, 0, 0.8), "hips": (0, -0.6, 0), "root": (0, -0.9, 0)})
    c.key(c.frames, limp, {"backpack": (0, 0, 0.8), "hips": (0, -0.6, 0), "root": (0, -1.2, 0)})
    clips.append(c)

    for c in clips:
        c.bake(arm)
    return clips


# ---------------------------------------------------------------- checks
def islands(obj):
    """The object's connected shells (game coordinates); pieces are built
    one shell each, so this is one entry per piece."""
    me = obj.data
    me.calc_loop_triangles()
    parent = list(range(len(me.vertices)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for poly in me.polygons:
        vs = poly.vertices
        for k in range(1, len(vs)):
            a, b = find(vs[0]), find(vs[k])
            if a != b:
                parent[a] = b
    groups = {}
    for poly in me.polygons:
        groups.setdefault(find(poly.vertices[0]), []).append(poly.index)
    verts = [to_game(v.co) for v in me.vertices]
    tris_by_poly = {}
    for t in me.loop_triangles:
        tris_by_poly.setdefault(t.polygon_index, []).append(tuple(t.vertices))
    out = []
    for polys in groups.values():
        tris = [tv for pi in polys for tv in tris_by_poly[pi]]
        used = sorted({i for tv in tris for i in tv})
        lo = Vector((min(verts[i].x for i in used), min(verts[i].y for i in used), min(verts[i].z for i in used)))
        hi = Vector((max(verts[i].x for i in used), max(verts[i].y for i in used), max(verts[i].z for i in used)))
        out.append({"obj": obj.name, "polys": polys, "tris": tris, "verts": verts, "lo": lo, "hi": hi, "mesh": me})
    return out


def check_outward(all_islands):
    """Every closed shell's signed volume is positive (front faces out)."""
    bad = []
    for isl in all_islands:
        verts = isl["verts"]
        volume = sum(verts[a].dot(verts[b].cross(verts[c])) for a, b, c in isl["tris"]) / 6.0
        if volume <= 0.0:
            bad.append((isl["obj"], volume))
    print("CHECK outward normals: %d of %d shells inside out" % (len(bad), len(all_islands)))
    for name, volume in bad[:10]:
        print("   INSIDE OUT %s (volume %.3f)" % (name, volume))
    return not bad


def check_closed(objects):
    ok = True
    for o in objects:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bad = [e for e in bm.edges if len(e.link_faces) != 2]
        if bad:
            ok = False
            print("   OPEN %s: %d non-manifold edges" % (o.name, len(bad)))
        bm.free()
    print("CHECK closed meshes:", "all closed" if ok else "FAILED")
    return ok


def boxes_touch(a, b, pad=0.02):
    return all(a["lo"][k] - pad <= b["hi"][k] and b["lo"][k] - pad <= a["hi"][k] for k in range(3))


def check_attached(all_islands, root_name="Pelvis"):
    """Nothing floats: every piece overlaps another and all are reachable
    from the pelvis through overlaps (in the rest pose)."""
    bvhs = [BVHTree.FromPolygons(isl["verts"], isl["tris"]) for isl in all_islands]
    n = len(all_islands)
    adj = [set() for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if boxes_touch(all_islands[i], all_islands[j]) and bvhs[i].overlap(bvhs[j]):
                adj[i].add(j)
                adj[j].add(i)
    root = next(i for i in range(n) if all_islands[i]["obj"] == root_name)
    seen, stack = {root}, [root]
    while stack:
        i = stack.pop()
        for j in adj[i]:
            if j not in seen:
                seen.add(j)
                stack.append(j)
    loose = [i for i in range(n) if i not in seen]
    print("CHECK attached: %d pieces, %d not reachable from the pelvis" % (n, len(loose)))
    for i in loose[:30]:
        isl = all_islands[i]
        print("   FLOATING %s at %s..%s" % (isl["obj"], tuple(round(c, 2) for c in isl["lo"]),
                                            tuple(round(c, 2) for c in isl["hi"])))
    return not loose


def poly_overlap_2d(a, b, eps=0.01):
    """True if two simple 2D polygons share interior area."""
    def cross(o, p, q):
        return (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])

    def crosses(p0, p1, q0, q1):
        d1, d2 = cross(q0, q1, p0), cross(q0, q1, p1)
        d3, d4 = cross(p0, p1, q0), cross(p0, p1, q1)
        if abs(d1) < 1e-9 or abs(d2) < 1e-9 or abs(d3) < 1e-9 or abs(d4) < 1e-9:
            return False
        return (d1 > 0) != (d2 > 0) and (d3 > 0) != (d4 > 0)

    def inside(pt, poly):
        x, y = pt
        hit = False
        n = len(poly)
        for i in range(n):
            (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % n]
            dx, dy = x1 - x0, y1 - y0
            ln = math.hypot(dx, dy)
            if ln > 1e-9:
                t = max(0.0, min(1.0, ((x - x0) * dx + (y - y0) * dy) / (ln * ln)))
                if math.hypot(x - (x0 + t * dx), y - (y0 + t * dy)) < eps:
                    return False
            if (y0 > y) != (y1 > y):
                xi = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
                if xi > x:
                    hit = not hit
        return hit

    na, nb = len(a), len(b)
    for i in range(na):
        for j in range(nb):
            if crosses(a[i], a[(i + 1) % na], b[j], b[(j + 1) % nb]):
                return True
    return any(inside(p, b) for p in a) or any(inside(p, a) for p in b)


def check_shared_planes(all_islands, tol=0.012):
    """No two faces of different pieces lie in one plane where they overlap."""
    buckets = {}
    for idx, isl in enumerate(all_islands):
        me, verts = isl["mesh"], isl["verts"]
        for pi in isl["polys"]:
            poly = me.polygons[pi]
            n = to_game(poly.normal)
            if n.length < 0.5:
                continue
            c = sum((verts[i] for i in poly.vertices), Vector()) / len(poly.vertices)
            key = (round(n.x, 1), round(n.y, 1), round(n.z, 1), round(n.dot(c) / 0.1))
            for dk in (-1, 0, 1):
                buckets.setdefault(key[:3] + (key[3] + dk,), []).append((idx, pi))
    bad = set()
    for key, faces in buckets.items():
        if len({f[0] for f in faces}) < 2:
            continue
        polys = []
        for idx, pi in faces:
            isl = all_islands[idx]
            poly = isl["mesh"].polygons[pi]
            n = to_game(poly.normal)
            u = (X if abs(n.x) < 0.9 else Y).cross(n).normalized()
            v = n.cross(u)
            pts = [isl["verts"][i] for i in poly.vertices]
            polys.append((idx, pi, n, [(p.dot(u), p.dot(v)) for p in pts], pts[0].dot(n), u, v))
        for a in range(len(polys)):
            for b in range(a + 1, len(polys)):
                ia, pa, na, qa, oa, ua, va = polys[a]
                ib, pb, nb, qb, ob, ub, vb = polys[b]
                if ia == ib or na.dot(nb) < 0.999 or abs(oa - ob) > tol:
                    continue
                # Project b's points into a's frame so both share one 2D basis.
                ptsb = [all_islands[ib]["verts"][i] for i in all_islands[ib]["mesh"].polygons[pb].vertices]
                qb2 = [(p.dot(ua), p.dot(va)) for p in ptsb]
                if poly_overlap_2d(qa, qb2):
                    bad.add((all_islands[ia]["obj"], all_islands[ib]["obj"], tuple(round(c, 1) for c in na)))
    print("CHECK shared planes: %d overlapping coplanar face pairs" % len(bad))
    for oa, ob, n in sorted(bad)[:30]:
        print("   SHARED %s / %s, normal %s" % (oa, ob, n))
    return not bad


def run_checks(objects):
    tris = 0
    for o in objects:
        o.data.calc_loop_triangles()
        tris += len(o.data.loop_triangles)
    print("TRIANGLES %d in %d pieces" % (tris, len(objects)))
    all_islands = [isl for o in objects for isl in islands(o)]
    results = [check_closed(objects), check_outward(all_islands), check_attached(all_islands),
               check_shared_planes(all_islands)]
    print("CHECKS", "ALL PASSED" if all(results) else "FAILED")
    return all(results)


# ---------------------------------------------------------------- previews
def solo_track(arm, name):
    """Evaluate only the named NLA track (none for the rest pose)."""
    for t in arm.animation_data.nla_tracks:
        t.is_solo = False
        t.mute = (t.name != name)


def render_views(arm):
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    scene = bpy.context.scene
    try:
        scene.render.engine = "BLENDER_WORKBENCH"
    except TypeError:
        scene.render.engine = "BLENDER_EEVEE"
    shading = scene.display.shading
    shading.light = "STUDIO"
    shading.color_type = "MATERIAL"
    shading.show_object_outline = True
    shading.object_outline_color = (0.0, 0.0, 0.0)
    shading.show_backface_culling = True
    shading.show_cavity = False
    shading.show_shadows = False
    shading.show_specular_highlight = False
    scene.display.render_aa = "8"
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.exposure = 1.3
    scene.view_settings.gamma = 1.15
    scene.render.film_transparent = False
    world = bpy.data.worlds.get("PreviewWorld") or bpy.data.worlds.new("PreviewWorld")
    world.color = (0.5, 0.54, 0.6)
    scene.world = world
    scene.render.resolution_x = 1200
    scene.render.resolution_y = 1200
    scene.render.resolution_percentage = 100
    cam_data = bpy.data.cameras.new("PreviewCamera")
    cam = bpy.data.objects.new("PreviewCamera", cam_data)
    COL.objects.link(cam)
    scene.camera = cam
    cam_data.clip_end = 500.0

    def shoot(name, loc, target, lens=50.0, ortho=None):
        cam.location = G(*loc)
        direction = (G(*target) - cam.location).normalized()
        cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
        if ortho:
            cam_data.type = "ORTHO"
            cam_data.ortho_scale = ortho
        else:
            cam_data.type = "PERSP"
            cam_data.lens = lens
        scene.render.filepath = os.path.join(PREVIEW_DIR, name + ".png")
        bpy.ops.render.render(write_still=True)
        print("rendered", name)

    def views(prefix, centre_y):
        c = (0.0, centre_y, 0.0)
        shoot(prefix + "_front", (0.0, centre_y, -40.0), c, ortho=9.0)
        shoot(prefix + "_side", (40.0, centre_y, 0.0), c, ortho=9.0)
        shoot(prefix + "_back", (0.0, centre_y, 40.0), c, ortho=9.0)
        shoot(prefix + "_quarter", (-13.0, centre_y + 5.0, -15.0), c, lens=50.0)
        shoot(prefix + "_quarter_right", (14.0, centre_y + 4.0, -13.0), c, lens=50.0)

    solo_track(arm, "")
    scene.frame_set(0)
    views("rest", 0.0)
    shoot("helmet", (-2.6, 3.7, -3.4), (0.0, 3.0, 0.0), lens=70.0)
    solo_track(arm, "hover_idle")
    scene.frame_set(30)
    views("hover", 0.0)
    solo_track(arm, "landed_idle")
    scene.frame_set(0)
    views("landed", 0.0)
    solo_track(arm, "fire_windup")
    scene.frame_set(24)
    shoot("windup", (-12.0, 5.0, -15.0), (0.0, 0.5, 0.0), lens=50.0)
    shoot("windup_helmet", (-2.8, 3.6, -3.4), (0.0, 2.95, 0.0), lens=70.0)
    solo_track(arm, "death")
    scene.frame_set(72)
    shoot("death", (-12.0, 5.0, -15.0), (0.0, -0.5, 0.0), lens=50.0)
    solo_track(arm, "land")
    scene.frame_set(22)
    shoot("land_absorb", (14.0, 3.0, -13.0), (0.0, -0.5, 0.0), lens=50.0)
    solo_track(arm, "")
    scene.frame_set(0)
    bpy.data.objects.remove(cam)


# ---------------------------------------------------------------- export
def export(objects):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objects:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "trooper.glb"), export_format="GLB",
                              use_selection=True, use_active_scene=True, export_apply=True, export_yup=True,
                              export_materials="EXPORT", export_cameras=False, export_lights=False,
                              export_skins=True, export_def_bones=False, export_rest_position_armature=True,
                              export_animations=True, export_animation_mode="NLA_TRACKS", export_frame_range=False,
                              export_force_sampling=True, export_optimize_animation_size=True,
                              export_optimize_animation_keep_anim_armature=True, export_reset_pose_bones=True)
    print("exported trooper.glb")


def main():
    global COL
    if bpy.app.background:
        for o in list(bpy.data.objects):
            bpy.data.objects.remove(o)
    scene = bpy.context.scene
    scene.name = "Trooper"
    scene.render.fps = FPS
    scene.frame_start = 0
    COL = bpy.data.collections.get("Trooper")
    if COL is None:
        COL = bpy.data.collections.new("Trooper")
        scene.collection.children.link(COL)
    build_mesh()
    ok = run_checks(PIECES)
    arm = build_armature()
    mesh = join_pieces(arm)
    markers = build_markers(arm)
    clips = build_animations(arm)
    for c in clips:
        print("CLIP %-12s %5.2f s (%d frames)%s" % (c.name, c.frames / FPS, c.frames,
                                                   "" if len(c.bones) == len(BONES) else "  upper body"))
    render_views(arm)
    if EXPORT:
        export([arm, mesh] + markers)
    print("trooper built; checks", "passed" if ok else "FAILED")


main()
