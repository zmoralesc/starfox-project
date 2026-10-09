"""The wilds' kit pieces (models/corneria2/ASSETS.md, "Trees and rocks"): the
broadleaf and pine trees of the forests, parks and gardens, the boulders and
outcrops of the hills, and the sea stacks of the coast.

    KIT_OUT=<copy.blend> KIT_PREVIEW=<dir> blender --background --python kit_nature.py
    KIT_GROVE_PREVIEW=<dir>  also renders a grove, a rock field and a stretch
                             of coast, placed as the generators place them
                             (gen_wilds.py, gen_landmarks.py) and seen from
                             the air, so the pieces are judged en masse

One function per piece, each returning [(suffix, Builder)] for
kit_tools.piece(). Every piece's origin is at the centre of its footprint on
the ground; a tree's trunk reaches TRUNK_BELOW under it, so a tree on a slope
never floats, and a rock is modelled from Z = 0 up (the generators sink it
30 % of its height, so its lower rings are wide, like a stone set in the
ground).

Everything here is a `lump()`: stacked rings of points (ring()) joined by
bands of faces and closed by a cap or a fan to a point. The rings are
jittered from a fixed seed, so a piece is lumpy or craggy but builds the same
every run. Trees are two-tone (TreeLight over Tree, or a dark second blob) in
flat-shaded facets: no ink lines are drawn on foliage, so the colour split and
the facets' light bands carry the shape. Rocks are flat-shaded Rock with Stone
strata (a band painted Stone) and TreeLight grass on their flat tops.

Trees are the kit's tightest budget (60 triangles; the map has ~80,000 of
them), so each is counted to the triangle: a lump of n points costs 2n per
band, n per fan and n - 2 per flat cap; the trunk is 12.
"""

import math
import os
import random
import sys

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit_tools as kt  # noqa: E402
from kit_tools import Builder  # noqa: E402

TRUNK_BELOW = 0.5                 # trunks reach this far under the ground
BROADLEAF_H = 14.0                # the nominal tree heights (ASSETS.md); the variants range round them
PINE_H = 16.0
STACK_H = {"A": 60.0, "B": 50.0, "C": 80.0}   # the sea stacks' heights, bed to cap
ROCK_SINK = 0.3                   # the generators sink rocks this share of their height (gen_wilds.ROCK_SINK)
TREE_SCALE = (1.3, 2.3)           # forest trees are scaled this much (gen_wilds.TREE_SCALE)


# --- Lumps ------------------------------------------------------------------------------
def ring(n, r, z, jitter=0.0, wobble=0.0, seed=0, centre=(0.0, 0.0), squash=1.0, turn=0.0):
    """n points anticlockwise (seen from above) round `centre` at height z,
    radius r (times `squash` along y): one of a lump's rings. `jitter` moves
    each point's radius and angle by up to that share; `wobble` its height by
    up to that share of r. Both come from `seed`, so a piece builds the same
    every run."""
    rng = random.Random(seed)
    pts = []
    for k in range(n):
        a = turn + 2.0 * math.pi * (k + rng.uniform(-0.35, 0.35) * jitter) / n
        rk = r * (1.0 + rng.uniform(-1.0, 1.0) * jitter)
        zk = z + rng.uniform(-1.0, 1.0) * wobble * r
        pts.append((centre[0] + rk * math.cos(a), centre[1] + rk * squash * math.sin(a), zk))
    return pts


def lump(b, rings, mat, bottom="flat", top="flat", paint=None, smooth=False, tri=False,
         bottom_mat=None, top_mat=None):
    """A closed body through `rings` (bottom to top, the same number of points
    each): a band of quads between each pair (two triangles each with `tri`,
    for more facets), closed at each end by a flat cap ("flat") or a fan to a
    point (x, y, z). paint(band, k) -> the material of a band's k-th face
    (band -1: the bottom fan; len(rings) - 1: the top fan; None: `mat`).
    Flat caps take bottom_mat / top_mat."""
    n = len(rings[0])

    def colour(band, k):
        return (paint(band, k) if paint else None) or mat

    for i in range(len(rings) - 1):
        lo, hi = rings[i], rings[i + 1]
        for k in range(n):
            k1 = (k + 1) % n
            m = colour(i, k)
            quad = [lo[k], lo[k1], hi[k1], hi[k]]
            if not tri:
                b.face(quad, m, smooth)
            elif (i + k) % 2 == 0:
                b.face(quad[:3], m, smooth)
                b.face([quad[0], quad[2], quad[3]], m, smooth)
            else:
                b.face([quad[0], quad[1], quad[3]], m, smooth)
                b.face(quad[1:], m, smooth)
    if bottom == "flat":
        b.face(rings[0][::-1], bottom_mat or mat)
    else:
        for k in range(n):
            b.face([bottom, rings[0][(k + 1) % n], rings[0][k]], colour(-1, k), smooth)
    if top == "flat":
        b.face(rings[-1], top_mat or mat)
    else:
        for k in range(n):
            b.face([rings[-1][k], rings[-1][(k + 1) % n], top], colour(len(rings) - 1, k), smooth)


def cone(b, base, apex, mat):
    """A faceted cone: a flat-capped fan from ring `base` to the point `apex`."""
    lump(b, [base], mat, bottom="flat", top=apex)


def trunk(b, r, z_top, lean=(0.0, 0.0), seed=0):
    """A four-sided trunk `r` across, from TRUNK_BELOW under the ground to
    z_top inside the crown (its top `lean` off centre), tapering: 12 triangles."""
    foot = ring(4, r, -TRUNK_BELOW, turn=math.pi / 4, seed=seed)
    head = ring(4, r * 0.7, z_top, turn=math.pi / 4, centre=lean, seed=seed)
    lump(b, [foot, head], "Trunk")


def two_tone(split, mottle=()):
    """A canopy painter: Tree below band `split`, TreeLight from it up, and
    the faces `mottle` [(band, k)] Tree too (dark patches in the light)."""
    def paint(band, k):
        if band < split or (band, k) in mottle:
            return "Tree"
        return "TreeLight"
    return paint


# --- Kit_Tree_Broadleaf: broadleaf trees (10 x 14, 60 tris) ------------------------------
# A crown is one lump of 6 points: four rings (36) and two fans (12) under a
# 12-triangle trunk come to 60 exactly. The lower two fifths (the bottom fan
# and the first band) are Tree, the rest TreeLight with a few dark patches
# along the join, so the crown reads light from the air and two-tone from
# the side.
CROWN_JITTER = 0.2
CROWN_WOBBLE = 0.18


def broadleaf_a():
    """A, round: a full crown, as wide as it is tall above the trunk."""
    b = Builder()
    trunk(b, 0.9, 5.5, seed=1)
    rings = [ring(6, 3.4, 4.8, CROWN_JITTER, CROWN_WOBBLE, seed=2),
             ring(6, 5.0, 7.6, CROWN_JITTER, CROWN_WOBBLE, seed=3, turn=0.3),
             ring(6, 4.7, 10.6, CROWN_JITTER, CROWN_WOBBLE, seed=4, turn=0.1),
             ring(6, 2.9, 12.9, CROWN_JITTER, CROWN_WOBBLE, seed=5, turn=0.5)]
    lump(b, rings, "Tree", bottom=(0.0, 0.0, 3.3), top=(0.5, 0.3, BROADLEAF_H + 0.2),
         paint=two_tone(1, mottle=[(1, 1), (1, 4), (2, 2)]))
    return [("", b)]


def broadleaf_b():
    """B, tall: an egg-shaped crown on a longer trunk, 8 x 15.5, its top
    leaning a little."""
    b = Builder()
    trunk(b, 0.8, 6.0, seed=6)
    rings = [ring(6, 2.6, 5.0, CROWN_JITTER, CROWN_WOBBLE, seed=7),
             ring(6, 3.9, 8.0, CROWN_JITTER, CROWN_WOBBLE, seed=8, turn=0.4),
             ring(6, 3.9, 11.0, CROWN_JITTER, CROWN_WOBBLE, seed=9, centre=(0.3, 0.2)),
             ring(6, 2.5, 13.6, CROWN_JITTER, CROWN_WOBBLE, seed=10, centre=(0.6, 0.3), turn=0.3)]
    lump(b, rings, "Tree", bottom=(0.0, 0.0, 3.4), top=(0.9, 0.5, 15.5),
         paint=two_tone(1, mottle=[(1, 3), (2, 0)]))
    return [("", b)]


def broadleaf_c():
    """C, lopsided: a light main blob off to one side (flat-bottomed: 28) and
    a smaller dark blob leaning out the other way (20), 11.5 x 12.5."""
    b = Builder()
    trunk(b, 0.9, 5.2, lean=(-0.6, 0.0), seed=11)
    main = [ring(5, 3.4, 4.4, CROWN_JITTER, CROWN_WOBBLE, seed=12, centre=(-1.2, 0.0)),
            ring(5, 4.6, 7.2, CROWN_JITTER, CROWN_WOBBLE, seed=13, centre=(-1.5, 0.3), turn=0.5),
            ring(5, 3.4, 10.2, CROWN_JITTER, CROWN_WOBBLE, seed=14, centre=(-1.8, 0.0), turn=0.2)]
    lump(b, main, "Tree", bottom="flat", top=(-2.2, 0.2, 12.5), paint=two_tone(1, mottle=[(1, 2)]))
    side = [ring(5, 2.6, 5.6, CROWN_JITTER, CROWN_WOBBLE, seed=15, centre=(3.2, 0.6)),
            ring(5, 2.5, 8.2, CROWN_JITTER, CROWN_WOBBLE, seed=16, centre=(3.7, 0.9), turn=0.6)]
    lump(b, side, "Tree", bottom=(2.8, 0.5, 3.9), top=(4.1, 1.0, 10.4), paint=two_tone(2))
    return [("", b)]


# --- Kit_Tree_Pine: pines (7 x 16, 60 tris) ------------------------------------------------
# Stacked cones, each its own shell (a fan and a flat base: 2n - 2) sunk into
# the one below, over a 12-triangle trunk. All Tree: the pines of the high
# ground read darker than the broadleaf forests below them.
PINE_JITTER = 0.08


def pine_tiers(b, tiers, n, mat="Tree", top_mat=None, seed=0):
    """Cones `tiers` [(base z, base radius, apex z, apex lean (x, y))] from the
    bottom up, n sides each; the top one in `top_mat` if given."""
    for i, (z0, r, z1, lean) in enumerate(tiers):
        base = ring(n, r, z0, PINE_JITTER, 0.0, seed=seed + i, turn=0.4 * i)
        cone(b, base, (lean[0], lean[1], z1), top_mat if top_mat and i == len(tiers) - 1 else mat)


def pine_a():
    """A, the classic: three stacked cones, 7 sides (36 + 12)."""
    b = Builder()
    trunk(b, 0.7, 4.5, seed=20)
    pine_tiers(b, [(2.6, 3.5, 8.6, (0.1, 0.0)), (6.4, 2.9, 12.6, (0.2, 0.1)), (10.2, 2.1, PINE_H, (0.3, 0.1))], 7, seed=21)
    return [("", b)]


def pine_b():
    """B, slender: four narrow tiers, 6 sides, 5 x 18 (40 + 12)."""
    b = Builder()
    trunk(b, 0.6, 5.0, seed=22)
    pine_tiers(b, [(3.0, 2.5, 8.6, (0.0, 0.1)), (6.6, 2.2, 11.8, (0.1, 0.1)), (9.8, 1.9, 14.8, (0.1, 0.2)),
                   (12.8, 1.5, 18.0, (0.2, 0.2))], 6, seed=23)
    return [("", b)]


def pine_c():
    """C, a broad fir: three wide tiers, 8 sides, 9 x 14 (42 + 12)."""
    b = Builder()
    trunk(b, 0.8, 4.2, seed=24)
    pine_tiers(b, [(2.2, 4.5, 7.6, (-0.1, 0.0)), (5.4, 3.6, 11.0, (-0.2, 0.1)), (8.6, 2.5, 14.0, (-0.3, 0.1))], 8, seed=25)
    return [("", b)]


# --- Kit_Rock_Boulder: boulders (about 8 x 5 x 8, 40 tris) ---------------------------------
# A lump of big facets, its widest ring low (the generator buries the bottom
# 30 %) and its bottom flat on the ground.
ROCK_JITTER = 0.16
ROCK_WOBBLE = 0.18


def boulder_a():
    """A, flat: a low slab-like stone, 9 x 4 x 7.5, 7 sides (28 + 10)."""
    b = Builder()
    rings = [ring(7, 3.9, 0.0, ROCK_JITTER, 0.0, seed=30, squash=0.85),
             ring(7, 4.5, 1.7, ROCK_JITTER, ROCK_WOBBLE, seed=31, squash=0.85, turn=0.2),
             ring(7, 2.6, 3.9, ROCK_JITTER, 0.0, seed=32, squash=0.8, centre=(0.4, -0.2), turn=0.1)]
    lump(b, rings, "Rock")
    return [("", b)]


def boulder_b():
    """B, round: a rounder stone with a peak, 8 x 5.5 x 7.5, 6 sides (24 + 10)."""
    b = Builder()
    rings = [ring(6, 3.2, 0.0, ROCK_JITTER, 0.0, seed=33, squash=0.9),
             ring(6, 4.0, 1.9, ROCK_JITTER, ROCK_WOBBLE, seed=34, squash=0.9, turn=0.3),
             ring(6, 3.0, 4.1, ROCK_JITTER, ROCK_WOBBLE, seed=35, squash=0.9, centre=(0.3, 0.2))]
    lump(b, rings, "Rock", top=(0.6, 0.3, 5.5))
    return [("", b)]


def boulder_c():
    """C, tall: a leaning standing stone, 6 x 7.5 x 6, 5 sides (30 + 6)."""
    b = Builder()
    rings = [ring(5, 3.0, 0.0, ROCK_JITTER, 0.0, seed=36),
             ring(5, 3.3, 2.5, ROCK_JITTER, ROCK_WOBBLE, seed=37, centre=(0.4, 0.0), turn=0.2),
             ring(5, 2.5, 5.2, ROCK_JITTER, ROCK_WOBBLE, seed=38, centre=(0.9, 0.2), turn=0.4),
             ring(5, 1.4, 7.5, ROCK_JITTER, 0.0, seed=39, centre=(1.3, 0.3), turn=0.1)]
    lump(b, rings, "Rock")
    return [("", b)]


# --- Kit_Rock_Outcrop: outcrops (about 30 x 18 x 30, 120 tris) -----------------------------
# Crags for the steep high ground: a cluster of slabs, a stepped crag, a tor.
# Flat tops are TreeLight grass; a band painted Stone is a stratum.
def strata(bands, grass=()):
    """A rock painter: bands in `bands` Stone, bands in `grass` TreeLight."""
    def paint(band, k):
        if band in bands:
            return "Stone"
        if band in grass:
            return "TreeLight"
        return None
    return paint


def shard(b, hw, hd, h, tilt, turn, at, seed, stone=False):
    """A slab of rock: a four-sided lump 2hw x 2hd at the foot, narrowing to
    the head `h` up, built upright then tilted `tilt` degrees, turned `turn`
    and stood with its foot at `at` (inside whatever it leans out of; the
    foot's corners stay above the ground). `stone`: a stratum across its
    middle (two more rings)."""
    r, squash, quarter = hw * math.sqrt(2.0), hd / hw, math.pi / 4
    if stone:
        rings = [ring(4, r, 0.0, ROCK_JITTER, 0.0, seed=seed, squash=squash, turn=quarter),
                 ring(4, r * 0.95, h * 0.4, ROCK_JITTER, ROCK_WOBBLE * 0.5, seed=seed + 1, squash=squash, turn=quarter),
                 ring(4, r * 0.85, h * 0.6, ROCK_JITTER, ROCK_WOBBLE * 0.5, seed=seed + 2, squash=squash, turn=quarter),
                 ring(4, r * 0.6, h, ROCK_JITTER, 0.0, seed=seed + 3, squash=squash, turn=quarter)]
    else:
        rings = [ring(4, r, 0.0, ROCK_JITTER, 0.0, seed=seed, squash=squash, turn=quarter),
                 ring(4, r * 0.9, h * 0.5, ROCK_JITTER, ROCK_WOBBLE * 0.5, seed=seed + 1, squash=squash, turn=quarter),
                 ring(4, r * 0.6, h, ROCK_JITTER, 0.0, seed=seed + 2, squash=squash, turn=quarter)]
    m = Matrix.Translation(at) @ Matrix.Rotation(math.radians(turn), 4, "Z") @ Matrix.Rotation(math.radians(tilt), 4, "X")
    with b.at(m):
        lump(b, rings, "Rock", paint=strata({1}) if stone else None)


def outcrop_a():
    """A, a slab cluster: three shards (one with a stratum) leaning out of a
    grassy mound at different tilts and turns, so no two share a plane,
    30 x 14 x 26 (38 + 28 + 20 + 20)."""
    b = Builder()
    mound = [ring(7, 14.0, 0.0, ROCK_JITTER, 0.0, seed=40, squash=0.85),
             ring(7, 14.6, 3.0, ROCK_JITTER, ROCK_WOBBLE * 0.5, seed=41, squash=0.85, turn=0.2),
             ring(7, 9.5, 6.8, ROCK_JITTER, 0.0, seed=42, squash=0.85, centre=(-1.0, 0.5))]
    lump(b, mound, "Rock", top_mat="TreeLight")
    shard(b, 5.0, 2.2, 13.0, 32.0, 20.0, (-6.0, 2.0, 2.2), seed=55)
    shard(b, 6.0, 2.0, 12.0, 24.0, -35.0, (3.0, -3.0, 2.2), seed=56, stone=True)
    shard(b, 3.6, 1.8, 9.5, 38.0, 75.0, (8.0, 5.0, 2.2), seed=57)
    return [("", b)]


def outcrop_b():
    """B, a stepped crag: a wide foot with a stratum, a grassy terrace halfway
    up, a narrower head with a grass top, 30 x 18 x 26, 8 sides (64 + 12)."""
    b = Builder()
    rings = [ring(8, 14.0, 0.0, ROCK_JITTER, 0.0, seed=43, squash=0.85),
             ring(8, 15.0, 4.5, ROCK_JITTER, ROCK_WOBBLE * 0.5, seed=44, squash=0.85, turn=0.2),
             ring(8, 13.0, 9.0, ROCK_JITTER, 0.0, seed=45, squash=0.85, centre=(1.0, 0.0), turn=0.1),
             ring(8, 8.5, 9.0, ROCK_JITTER, 0.0, seed=46, squash=0.85, centre=(2.5, 1.0), turn=0.3),
             ring(8, 4.8, 18.0, ROCK_JITTER, 0.0, seed=47, squash=0.85, centre=(3.5, 1.5), turn=0.1)]
    lump(b, rings, "Rock", paint=strata({1}, grass={2}), top_mat="TreeLight")
    return [("", b)]


def outcrop_c():
    """C, a tall tor: a leaning column of big triangular facets with a
    stratum and a grassy head, a boulder at its foot, 24 x 26 x 20, 6 sides
    (48 + 8 + 16)."""
    b = Builder()
    rings = [ring(6, 11.5, 0.0, ROCK_JITTER, 0.0, seed=48, squash=0.8),
             ring(6, 11.0, 6.0, ROCK_JITTER, ROCK_WOBBLE * 0.5, seed=49, squash=0.8, turn=0.2),
             ring(6, 8.0, 13.0, ROCK_JITTER, ROCK_WOBBLE * 0.5, seed=50, squash=0.8, centre=(1.5, 0.0), turn=0.4),
             ring(6, 6.5, 20.0, ROCK_JITTER, ROCK_WOBBLE * 0.5, seed=51, squash=0.8, centre=(3.0, 0.5), turn=0.2),
             ring(6, 3.6, 26.0, ROCK_JITTER, 0.0, seed=52, squash=0.8, centre=(3.5, 0.6), turn=0.5)]
    lump(b, rings, "Rock", paint=strata({2}), top_mat="TreeLight", tri=True)
    foot = [ring(5, 3.2, 0.0, ROCK_JITTER, 0.0, seed=53, centre=(-9.5, -4.0)),
            ring(5, 2.6, 3.4, ROCK_JITTER, ROCK_WOBBLE, seed=54, centre=(-9.0, -3.5), turn=0.3)]
    lump(b, foot, "Rock")
    return [("", b)]


# --- Kit_Rock_Stack: sea stacks (A 24 x 60, B 30 x 50, C 20 x 80; 300 tris) ----------------
# Faceted pillars standing on the sea bed (the bottom 10-35 % is underwater,
# so the strata sit in the upper half), flaring at the foot, overhanging a
# little under a grassy flat top.
def pillar(b, n, stations, seed, squash=0.9, lean=(0.0, 0.0), stone=(), tri=True):
    """A pillar through `stations` [(z, radius)], n sides, its rings leaning
    `lean` (x, y per metre of height); the bands in `stone` painted Stone, the
    top flat and grassy."""
    rings = []
    for i, (z, r) in enumerate(stations):
        rings.append(ring(n, r, z, ROCK_JITTER, 0.0 if i in (0, len(stations) - 1) else ROCK_WOBBLE * 0.6,
                          seed=seed + i, squash=squash, centre=(lean[0] * z, lean[1] * z), turn=0.25 * i))
    lump(b, rings, "Rock", paint=strata(set(stone)), top_mat="TreeLight", tri=tri)


def stack_a():
    """A, 24 x 60: a plain pillar with a flared foot, a thin stratum at 36 m,
    a wider stratum at 48 m under the overhang, 9 sides (180 + 14)."""
    b = Builder()
    pillar(b, 9, [(0.0, 12.0), (7.0, 10.5), (17.0, 9.5), (27.0, 9.0), (34.0, 8.6), (37.0, 8.6), (45.0, 9.2),
                  (49.5, 10.2), (54.5, 11.5), (58.0, 9.8), (STACK_H["A"], 7.5)], seed=60, lean=(0.02, 0.0), stone=(4, 7))
    return [("", b)]


def stack_b():
    """B, 30 x 50: stout, a two-headed one: the main pillar with its strata,
    and a lower shoulder leaning away from it, 9 and 6 sides (162 + 14 + 32)."""
    b = Builder()
    pillar(b, 9, [(0.0, 13.0), (7.0, 12.0), (15.0, 10.5), (22.0, 10.0), (25.0, 10.0), (33.0, 9.6), (40.0, 11.0),
                  (45.0, 12.0), (48.5, 10.5), (STACK_H["B"], 8.0)], seed=70, squash=0.85, lean=(-0.03, 0.01), stone=(3, 6))
    shoulder = [ring(6, 7.0, 0.0, ROCK_JITTER, 0.0, seed=80, centre=(9.0, -6.0)),
                ring(6, 6.5, 14.0, ROCK_JITTER, ROCK_WOBBLE * 0.6, seed=81, centre=(10.5, -7.0), turn=0.3),
                ring(6, 3.5, 28.0, ROCK_JITTER, 0.0, seed=82, centre=(12.0, -8.0), turn=0.1)]
    lump(b, shoulder, "Rock", top_mat="TreeLight", tri=True)
    return [("", b)]


def stack_c():
    """C, 20 x 80: a needle, narrowing all the way up to a small grassy cap,
    two strata, 8 sides (192 + 12)."""
    b = Builder()
    pillar(b, 8, [(0.0, 10.0), (8.0, 9.0), (16.0, 8.4), (24.0, 8.0), (32.0, 7.6), (36.0, 7.6), (39.0, 7.4),
                  (48.0, 7.0), (56.0, 6.8), (60.0, 7.0), (68.0, 7.8), (75.0, 6.2), (STACK_H["C"], 4.2)],
            seed=90, lean=(0.015, 0.02), stone=(4, 9))
    return [("", b)]


# --- Previews from the air ---------------------------------------------------------------
def bounds(col):
    lo = Vector((math.inf,) * 3)
    hi = Vector((-math.inf,) * 3)
    for o in col.all_objects:
        if o.type == "MESH":
            for v in o.data.vertices:
                p = o.matrix_world @ v.co - col.instance_offset
                lo = Vector(map(min, lo, p))
                hi = Vector(map(max, hi, p))
    return lo, hi


def stand(scene, name, at, turn, scale):
    """An instance of kit piece `name` in `scene` at `at`, turned `turn`
    radians about Z and scaled (x, y, z)."""
    col = bpy.data.collections[name]
    inst = bpy.data.objects.new(name, None)
    inst.instance_type = "COLLECTION"
    inst.instance_collection = col
    inst.matrix_world = (Matrix.Translation(at) @ Matrix.Rotation(turn, 4, "Z")
                         @ Matrix.Diagonal((scale[0], scale[1], scale[2], 1.0)))
    scene.collection.objects.link(inst)
    return inst


def fitted(family, size):
    """The variant of `family` (A, B, C) that `size` (w, h, d) stretches the
    least, and its scale: as settlement.Variant.fit() picks one."""
    best = None
    for letter in "ABC":
        name = "%s_%s" % (family, letter)
        lo, hi = bounds(bpy.data.collections[name])
        own = (hi.x - lo.x, hi.z - lo.z, hi.y - lo.y)
        cost = sum(abs(math.log(size[i] / own[i])) for i in range(3))
        if best is None or cost < best[0]:
            best = (cost, name, (size[0] / own[0], size[2] / own[2], size[1] / own[1]))
    return best[1], best[2]


def ground(scene, half, z, mat):
    """A square of ground (or sea) `half` out from the origin at height z."""
    b = Builder()
    b.face([(-half, -half, z), (half, -half, z), (half, half, z), (-half, half, z)], mat)
    o = b.object("Ground")
    scene.collection.objects.link(o)


def render(scene, eye, target, path, size=(1280, 720), lens=35, outlines=True):
    """Renders `scene` (Workbench, palette colours, shadows) from `eye` towards `target`."""
    cam_data = bpy.data.cameras.new("AirCam")
    cam_data.lens = lens
    cam_data.clip_end = 5000.0
    cam = bpy.data.objects.new("AirCam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    try:
        scene.render.engine = "BLENDER_WORKBENCH"
    except TypeError:
        pass
    shading = scene.display.shading
    shading.light = "STUDIO"
    shading.color_type = "MATERIAL"
    shading.show_backface_culling = True
    shading.show_object_outline = outlines
    shading.show_shadows = True
    shading.shadow_intensity = 0.6
    shading.show_cavity = False
    scene.render.resolution_x, scene.render.resolution_y = size
    world = bpy.data.worlds.new("AirWorld")
    world.color = (0.55, 0.65, 0.8)
    scene.world = world
    cam.location = Vector(eye)
    cam.rotation_euler = (Vector(target) - Vector(eye)).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True, scene=scene.name)
    bpy.data.objects.remove(cam)
    bpy.data.cameras.remove(cam_data)
    bpy.data.worlds.remove(world)


def air_previews(out):
    """A grove of trees, a rock field and a stretch of coast, placed as the
    generators place them, each seen from 150 m away and 40 m up (the player's
    usual view) and from higher."""
    os.makedirs(out, exist_ok=True)
    rng = random.Random(11)
    # The grove: a jittered 20 m grid (gen_wilds), half pines, trees at
    # 1.3-2.3x, sunk 0.3 m, random turns.
    scene = bpy.data.scenes.new("Grove")
    ground(scene, 600.0, 0.0, "FieldGreen")
    for i in range(-4, 5):
        for j in range(-3, 4):
            x = i * 20.0 + rng.uniform(-8.0, 8.0)
            y = j * 20.0 + rng.uniform(-8.0, 8.0)
            family = "Kit_Tree_Pine" if (x + 0.5 * y) > 10.0 else "Kit_Tree_Broadleaf"
            s = rng.uniform(*TREE_SCALE)
            stand(scene, "%s_%s" % (family, rng.choice("ABC")), (x, y, -0.3), rng.uniform(0, 2 * math.pi), (s, s, s))
    render(scene, (0.0, -190.0, 40.0), (0.0, 0.0, 10.0), os.path.join(out, "grove_low.png"), outlines=False)
    render(scene, (60.0, -170.0, 130.0), (0.0, 0.0, 0.0), os.path.join(out, "grove_high.png"), outlines=False)
    render(scene, (0.0, -60.0, 24.0), (0.0, 20.0, 12.0), os.path.join(out, "grove_close.png"), outlines=False)
    bpy.data.scenes.remove(scene)
    # The rock field: boulders at 4-12 m and outcrops at 20-45 m, fitted to
    # the generator's proportions and sunk 30 %.
    scene = bpy.data.scenes.new("Rocks")
    ground(scene, 600.0, 0.0, "FieldGreen")
    for _ in range(18):
        size = rng.uniform(4.0, 12.0)
        tall = size * rng.uniform(0.5, 0.8)
        name, scale = fitted("Kit_Rock_Boulder", (size, tall, size * rng.uniform(0.7, 1.0)))
        stand(scene, name, (rng.uniform(-90.0, 90.0), rng.uniform(-60.0, 60.0), -tall * ROCK_SINK),
              rng.uniform(0, 2 * math.pi), scale)
    for x, y in ((-70.0, 30.0), (-15.0, 50.0), (40.0, 20.0), (80.0, 60.0), (10.0, -40.0)):
        width, tall = rng.uniform(20.0, 45.0), rng.uniform(10.0, 30.0)
        name, scale = fitted("Kit_Rock_Outcrop", (width, tall, width * rng.uniform(0.6, 1.0)))
        stand(scene, name, (x, y, -tall * ROCK_SINK), rng.uniform(0, 2 * math.pi), scale)
    for k in range(6):
        s = rng.uniform(*TREE_SCALE)
        stand(scene, "Kit_Tree_Pine_%s" % rng.choice("ABC"), (-100.0 + 40.0 * k, 90.0, -0.3), rng.uniform(0, 6.0), (s, s, s))
    render(scene, (0.0, -190.0, 40.0), (0.0, 0.0, 8.0), os.path.join(out, "rocks_low.png"))
    render(scene, (60.0, -170.0, 130.0), (0.0, 0.0, 0.0), os.path.join(out, "rocks_high.png"))
    bpy.data.scenes.remove(scene)
    # The coast: stacks fitted to gen_landmarks' sizes, standing on a bed
    # 3-30 m under the sea.
    scene = bpy.data.scenes.new("Coast")
    ground(scene, 800.0, 0.0, "Water")
    for k, (x, y) in enumerate(((-90.0, 40.0), (-30.0, -10.0), (30.0, 60.0), (85.0, 0.0), (0.0, 120.0), (140.0, 70.0))):
        bed = rng.uniform(-30.0, -3.0)
        width = rng.uniform(18.0, 34.0)
        height = rng.uniform(30.0, 90.0) - bed
        name, scale = fitted("Kit_Rock_Stack", (width, height, width))
        stand(scene, name, (x, y, bed - 1.0), rng.uniform(0, 2 * math.pi), scale)
    render(scene, (0.0, -220.0, 40.0), (0.0, 20.0, 25.0), os.path.join(out, "coast_low.png"))
    render(scene, (80.0, -200.0, 160.0), (0.0, 20.0, 10.0), os.path.join(out, "coast_high.png"))
    bpy.data.scenes.remove(scene)
    print("air previews in " + out)


# --- The batch ------------------------------------------------------------------------
PIECES = [
    ("Kit_Tree_Broadleaf_A", broadleaf_a), ("Kit_Tree_Broadleaf_B", broadleaf_b),
    ("Kit_Tree_Broadleaf_C", broadleaf_c),
    ("Kit_Tree_Pine_A", pine_a), ("Kit_Tree_Pine_B", pine_b), ("Kit_Tree_Pine_C", pine_c),
    ("Kit_Rock_Boulder_A", boulder_a), ("Kit_Rock_Boulder_B", boulder_b), ("Kit_Rock_Boulder_C", boulder_c),
    ("Kit_Rock_Outcrop_A", outcrop_a), ("Kit_Rock_Outcrop_B", outcrop_b), ("Kit_Rock_Outcrop_C", outcrop_c),
    ("Kit_Rock_Stack_A", stack_a), ("Kit_Rock_Stack_B", stack_b), ("Kit_Rock_Stack_C", stack_c),
]


def main():
    kt.begin("kit_nature", 3)
    for name, build in PIECES:
        kt.piece(name, build())
    kt.finish()
    if os.environ.get("KIT_GROVE_PREVIEW"):
        air_previews(os.environ["KIT_GROVE_PREVIEW"])


if __name__ == "__main__":
    main()
