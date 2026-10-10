"""Fichina's ice, rocks and pines (models/fichina/ASSETS.md, "Batch 4: ice,
rocks and pines"): the snow-laden pines of the forests, the boulders and
outcrops of the slopes and high ground, the seracs of the glacier and the
frozen lake's shores, the ice spires, the ice arches the player flies through
and the frozen waterfall down the ice shelf's cliff.

    KIT_OUT=<copy.blend> KIT_PREVIEW=<dir> blender --background --python kit_nature.py

One function per piece, each returning [(suffix, Builder)] for
kit_tools.piece(). Every piece's origin is at the centre of its footprint on
the ground. A tree's trunk reaches TRUNK_BELOW under it, so a tree on a slope
never floats; rocks, seracs and spires are modelled from Z = 0 up (the
generators sink rocks and seracs 30 % of their height and spires 3 m), so
their lowest rings are among their widest, like stones set in the ground.

Everything but the falls is a lump(): stacked rings of points (ring())
joined by bands of triangles (two per quad, so every facet is a true plane)
and closed by a flat cap or a fan to a point. The rings are jittered from
fixed seeds, so a piece is lumpy or craggy but builds the same every run.
Faces are painted by rules that see each facet's normal: up-facing facets
are Snow, on rocks and ice alike; rocks get RockLight facets and ice gets
IceDeep ones from a seeded draw, and ice facing down is always IceDeep
(stone(), crystal()). Everything is flat-shaded: a few big planes read as cut
stone and crystal under the game's three light bands.

Pines are the kit's tightest budget (60 triangles; the map has ~40,000 of
them). A tier is a skirt: widest at its bottom rim, a Pine / PineLight band
narrowing up to a mid ring, then a PineSnow fan to the apex (the snow lying
on the tier), closed by a flat underside at the rim (4n - 2 for n points).
The tiers overlap into a stepped cone: each rim stands a little above the
mid ring of the tier below, hiding that tier's apex, so from the side the
outline is green band, white band, green band... and from the air it is
white. No ink lines are drawn on foliage, so that colour split carries the
shape. Three five-point skirts are 54; the trunk is a 4-triangle spike.

The arch and the falls are the player's: the arch's opening is checked by
casting rays through the built geometry (opening_report()), and the falls'
back is one flat plane at +Y, against the cliff.
"""

import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # models/fichina/source
import fichina_common as cc   # noqa: E402,F401  (first: makes kit_tools serve Fichina)
import kit_tools as kt  # noqa: E402
from kit_tools import Builder  # noqa: E402

from mathutils import Matrix, Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

TRUNK_BELOW = 0.5                 # trunks reach this far under the ground
ROCK_JITTER = 0.16                # rings' points move by up to this share of the radius (and of a step in angle)
ROCK_WOBBLE = 0.18                # ...and in height, by this share of the radius
ICE_JITTER = 0.12
ICE_WOBBLE = 0.1
PINE_JITTER = 0.08
SNOW_UP = 0.55                    # a facet whose normal's z is above this faces up enough to hold snow
ICE_UNDER = -0.15                 # ...and below this looks down: deep ice


# --- Rings and lumps ----------------------------------------------------------------------
def ring(n, r, z, jitter=0.0, wobble=0.0, seed=0, centre=(0.0, 0.0), squash=1.0, turn=0.0, tilt=(0.0, 0.0)):
    """n points anticlockwise (seen from above) round `centre` at height z,
    radius r (times `squash` along y): one of a lump's rings. `jitter` moves
    each point's radius and angle by up to that share; `wobble` its height by
    up to that share of r; `tilt` (per metre of x, y off the centre) leans the
    whole ring, keeping it planar. All from `seed`, so a piece builds the same
    every run."""
    rng = random.Random(seed)
    pts = []
    for k in range(n):
        a = turn + 2.0 * math.pi * (k + rng.uniform(-0.35, 0.35) * jitter) / n
        rk = r * (1.0 + rng.uniform(-1.0, 1.0) * jitter)
        dx, dy = rk * math.cos(a), rk * squash * math.sin(a)
        zk = z + rng.uniform(-1.0, 1.0) * wobble * r + tilt[0] * dx + tilt[1] * dy
        pts.append((centre[0] + dx, centre[1] + dy, zk))
    return pts


def normal(pts):
    """The unit normal of a face through `pts` (Newell's method; any winding)."""
    n = Vector((0.0, 0.0, 0.0))
    for i in range(len(pts)):
        p, q = Vector(pts[i]), Vector(pts[(i + 1) % len(pts)])
        n.x += (p.y - q.y) * (p.z + q.z)
        n.y += (p.z - q.z) * (p.x + q.x)
        n.z += (p.x - q.x) * (p.y + q.y)
    return n.normalized() if n.length > 1e-9 else Vector((0.0, 0.0, 1.0))


def put(b, pts, paint, band, k, corners=None):
    """A face through `pts` (anticlockwise seen from its front) painted by
    paint(band, k, normal, corners), the normal taken in the builder's
    current transform (the piece's space), so painting by direction works
    on parts built upright and then tilted."""
    m = b.xf[-1]
    n = normal([m @ Vector(p) for p in pts])
    if m.determinant() < 0:
        n = -n
    b.face(pts, paint(band, k, n, corners))


def lump(b, rings, paint, bottom="flat", top="flat", tri=True):
    """A closed body through `rings` (bottom to top, the same number of points
    each): a band between each pair, two triangles per quad (`tri`; their
    diagonals alternate), closed at each end by a flat cap ("flat") or a fan
    to a point (x, y, z). paint(band, k, normal, corners) -> the material of
    a face: band -1 is the bottom cap or fan, len(rings) - 1 the top one;
    `corners` says which of the quad's corners (0 lo k, 1 lo k+1, 2 hi k+1,
    3 hi k) a triangle uses, None for caps and fans."""
    n = len(rings[0])
    for i in range(len(rings) - 1):
        lo, hi = rings[i], rings[i + 1]
        for k in range(n):
            k1 = (k + 1) % n
            quad = [lo[k], lo[k1], hi[k1], hi[k]]
            if not tri:
                put(b, quad, paint, i, k, (0, 1, 2, 3))
            elif (i + k) % 2 == 0:
                put(b, quad[:3], paint, i, k, (0, 1, 2))
                put(b, [quad[0], quad[2], quad[3]], paint, i, k, (0, 2, 3))
            else:
                put(b, [quad[0], quad[1], quad[3]], paint, i, k, (0, 1, 3))
                put(b, quad[1:], paint, i, k, (1, 2, 3))
    if bottom == "flat":
        put(b, rings[0][::-1], paint, -1, None)
    else:
        for k in range(n):
            put(b, [bottom, rings[0][(k + 1) % n], rings[0][k]], paint, -1, k)
    if top == "flat":
        put(b, rings[-1], paint, len(rings) - 1, None)
    else:
        for k in range(n):
            put(b, [rings[-1][k], rings[-1][(k + 1) % n], top], paint, len(rings) - 1, k)


# --- Painters ----------------------------------------------------------------------------------
def stone(seed, light=0.35, snow=SNOW_UP):
    """A rock painter: facets looking up are Snow; of the rest, about `light`
    of the quads (both their triangles alike) are RockLight, the others Rock."""
    rng = random.Random(seed)
    drawn = {}

    def paint(band, k, n, corners):
        if n.z > snow:
            return "Snow"
        if band == -1:
            return "Rock"
        if (band, k) not in drawn:
            drawn[(band, k)] = rng.random() < light
        return "RockLight" if drawn[(band, k)] else "Rock"
    return paint


def crystal(seed, deep=0.45, snow=SNOW_UP, under=ICE_UNDER, steep=None):
    """An ice painter: facets looking up are Snow, facets looking down
    IceDeep; of the rest about `deep` of the quads are IceDeep (or `steep` of
    the near-vertical ones, if given), the others Ice: a crystal of two blues."""
    rng = random.Random(seed)
    drawn = {}

    def paint(band, k, n, corners):
        if n.z > snow:
            return "Snow"
        if n.z < under or band == -1:
            return "IceDeep"
        if (band, k) not in drawn:
            share = steep if steep is not None and abs(n.z) < 0.3 else deep
            drawn[(band, k)] = rng.random() < share
        return "IceDeep" if drawn[(band, k)] else "Ice"
    return paint


# --- Kit_Tree_SnowPine: snow-laden pines (about 7 x 16, 60 tris) ----------------------------
def trunk(b, r, z_top, lean=(0.0, 0.0), seed=0):
    """A three-sided trunk `r` across at the ground, from TRUNK_BELOW under
    it tapering to a point at z_top inside the lowest tier (`lean` off
    centre): a tetrahedron, 4 triangles."""
    foot = ring(3, r, -TRUNK_BELOW, turn=math.pi / 6, seed=seed)
    b.face(foot[::-1], "Trunk")
    for k in range(3):
        b.face([foot[k], foot[(k + 1) % 3], (lean[0], lean[1], z_top)], "Trunk")


def tier(b, rim, mid, apex):
    """One tier of a pine, a skirt: a band of quads (two triangles each)
    from the bottom rim `rim` up to the narrower ring `mid`, a PineSnow fan
    from there to the point `apex`, and a flat Pine underside at the rim:
    4n - 2. In each band quad the triangle hanging from the mid ring is
    PineSnow and the one standing on the rim Pine or PineLight, so the snow
    on a tier ends in a sawtooth over the dark foliage."""
    n = len(rim)
    for k in range(n):
        k1 = (k + 1) % n
        m = "PineLight" if k % 2 == 0 else "Pine"
        quad = [rim[k], rim[k1], mid[k1], mid[k]]
        if k % 2 == 0:
            b.face(quad[:3], m)
            b.face([quad[0], quad[2], quad[3]], "PineSnow")
        else:
            b.face([quad[0], quad[1], quad[3]], m)
            b.face(quad[1:], "PineSnow")
        b.face([mid[k], mid[k1], apex], "PineSnow")
    b.face(rim[::-1], "Pine")


def pine_tiers(b, tiers, n, seed, tilt=(0.0, 0.0), waist=0.5):
    """Tiers [(rim z, rim radius, rim centre, band height, apex z, apex (x, y))]
    from the bottom up, n points round each (jittered, turned a little per
    tier, leaning `tilt`); each mid ring is `waist` of its rim's radius, the
    band's height above it, and a third of the way from the rim's centre to
    the apex."""
    for i, (z, r, centre, band, apex_z, apex) in enumerate(tiers):
        turn = 0.6 * i
        rim = ring(n, r, z, PINE_JITTER, 0.0, seed=seed + 2 * i, centre=centre, turn=turn, tilt=tilt)
        mid_centre = (centre[0] + (apex[0] - centre[0]) / 3.0, centre[1] + (apex[1] - centre[1]) / 3.0)
        mid = ring(n, r * waist, z + band, PINE_JITTER, 0.0, seed=seed + 2 * i + 1, centre=mid_centre, turn=turn, tilt=tilt)
        tier(b, rim, mid, (apex[0], apex[1], apex_z))


# Each tier's rim stands about a band's height above the mid ring of the
# tier below, so that tier's snow shows as a white band under the dark
# skirt above it and its apex is hidden inside.
def snow_pine_a():
    """A, the classic: three skirts of five points, 7.7 x 16 (54 + 4)."""
    b = Builder()
    trunk(b, 0.6, 3.0, seed=1)
    o = (0.0, 0.0)
    pine_tiers(b, [(2.4, 3.7, o, 2.1, 7.6, (0.1, 0.0)),
                   (6.6, 3.0, o, 2.1, 11.4, (0.2, 0.1)),
                   (10.6, 2.1, (0.1, 0.0), 2.1, 16.0, (0.4, 0.2))], 5, seed=2)
    return [("", b)]


def snow_pine_b():
    """B, tall and narrow: three slim skirts of five points with long
    bands and a long tip, 5.2 x 19 (54 + 4)."""
    b = Builder()
    trunk(b, 0.5, 3.2, seed=5)
    o = (0.0, 0.0)
    pine_tiers(b, [(2.6, 2.5, o, 2.6, 9.0, (0.0, 0.1)),
                   (7.8, 2.1, o, 2.6, 13.8, (0.1, 0.1)),
                   (12.6, 1.6, (0.1, 0.1), 2.6, 19.0, (0.3, 0.3))], 5, seed=6, waist=0.55)
    return [("", b)]


def snow_pine_c():
    """C, lopsided and heavy with snow: three broad skirts of five points
    sagging to +x, short dark bands under wide snow fans, the trunk off
    centre, 8.5 x 13.5 (54 + 4)."""
    b = Builder()
    trunk(b, 0.6, 2.8, lean=(0.3, 0.1), seed=9)
    pine_tiers(b, [(2.2, 4.3, (0.5, 0.2), 1.7, 6.8, (0.9, 0.3)),
                   (6.0, 3.4, (0.9, 0.3), 1.7, 10.4, (1.3, 0.4)),
                   (9.4, 2.3, (1.2, 0.4), 1.7, 13.5, (1.6, 0.5))], 5, seed=10, tilt=(-0.12, 0.03), waist=0.45)
    return [("", b)]


# --- Kit_Rock_Boulder: boulders (about 8 x 5 x 7, 50 tris) ------------------------------------
# A lump of big facets, its widest ring low (the generator buries the bottom
# 30 %) and its bottom flat on the ground; its top cap and the facets that
# look up are Snow.
def boulder_a():
    """A, flat: a low slab-like stone with a wide snowy top, 9.5 x 3.6 x 7.5,
    7 points (28 + 5 + 5)."""
    b = Builder()
    rings = [ring(7, 4.4, 0.0, ROCK_JITTER, 0.0, seed=20, squash=0.8),
             ring(7, 4.9, 1.6, ROCK_JITTER, ROCK_WOBBLE, seed=21, squash=0.8, turn=0.2),
             ring(7, 3.0, 3.6, ROCK_JITTER, 0.0, seed=22, squash=0.8, centre=(0.4, -0.2), turn=0.1, tilt=(0.05, 0.0))]
    lump(b, rings, stone(23))
    return [("", b)]


def boulder_b():
    """B, round: a rounder stone rising to a peak, 8.5 x 5.6 x 7.5, 6 points
    (36 + 4 + 6)."""
    b = Builder()
    rings = [ring(6, 3.2, 0.0, ROCK_JITTER, 0.0, seed=24, squash=0.9),
             ring(6, 4.1, 1.5, ROCK_JITTER, ROCK_WOBBLE, seed=25, squash=0.9, turn=0.3),
             ring(6, 3.7, 3.3, ROCK_JITTER, ROCK_WOBBLE, seed=26, squash=0.9, centre=(0.3, 0.2), turn=0.1),
             ring(6, 2.2, 4.6, ROCK_JITTER, ROCK_WOBBLE * 0.5, seed=27, squash=0.9, centre=(0.5, 0.3), turn=0.4)]
    lump(b, rings, stone(28), top=(0.6, 0.3, 5.6))
    return [("", b)]


def boulder_c():
    """C, tall: a leaning standing stone with a small snowy head,
    6.5 x 7.8 x 6, 5 points (30 + 3 + 3)."""
    b = Builder()
    rings = [ring(5, 2.9, 0.0, ROCK_JITTER, 0.0, seed=29),
             ring(5, 3.2, 2.6, ROCK_JITTER, ROCK_WOBBLE, seed=30, centre=(0.4, 0.0), turn=0.2),
             ring(5, 2.4, 5.2, ROCK_JITTER, ROCK_WOBBLE, seed=31, centre=(0.9, 0.2), turn=0.4),
             ring(5, 1.3, 7.8, ROCK_JITTER, 0.0, seed=32, centre=(1.3, 0.3), turn=0.1, tilt=(0.1, 0.05))]
    lump(b, rings, stone(33))
    return [("", b)]


# --- Kit_Rock_Outcrop: outcrops (about 30 x 18 x 26, 150 tris) --------------------------------
# Crags for the steep high ground: a cluster of slabs, a stepped crag, a tall
# tor. Terraces and tops come out Snow by themselves (they look up).
def shard(b, hw, hd, h, tilt, turn, at, seed, paint):
    """A slab of rock: a four-sided lump 2hw x 2hd at the foot, narrowing to
    the head `h` up, built upright then tilted `tilt` degrees, turned `turn`
    and stood with its foot at `at` (inside whatever it leans out of; the
    foot's corners stay above the ground): 16 + 2 + 2."""
    r, squash, quarter = hw * math.sqrt(2.0), hd / hw, math.pi / 4
    rings = [ring(4, r, 0.0, ROCK_JITTER, 0.0, seed=seed, squash=squash, turn=quarter),
             ring(4, r * 0.9, h * 0.5, ROCK_JITTER, ROCK_WOBBLE * 0.5, seed=seed + 1, squash=squash, turn=quarter),
             ring(4, r * 0.6, h, ROCK_JITTER, 0.0, seed=seed + 2, squash=squash, turn=quarter)]
    m = Matrix.Translation(at) @ Matrix.Rotation(math.radians(turn), 4, "Z") @ Matrix.Rotation(math.radians(tilt), 4, "X")
    with b.at(m):
        lump(b, rings, paint)


def outcrop_a():
    """A, a slab cluster: three shards leaning out of a snowy mound at
    different tilts and turns, so no two share a plane, and a boulder at its
    foot, 31 x 14 x 27 (38 + 3 x 20 + 16)."""
    b = Builder()
    paint = stone(40, light=0.3)
    mound = [ring(7, 14.0, 0.0, ROCK_JITTER, 0.0, seed=41, squash=0.85),
             ring(7, 14.6, 3.0, ROCK_JITTER, ROCK_WOBBLE * 0.5, seed=42, squash=0.85, turn=0.2),
             ring(7, 9.5, 6.6, ROCK_JITTER, 0.0, seed=43, squash=0.85, centre=(-1.0, 0.5), tilt=(0.03, 0.02))]
    lump(b, mound, paint)
    shard(b, 5.0, 2.2, 13.0, 32.0, 20.0, (-6.0, 2.0, 2.2), 44, paint)
    shard(b, 6.0, 2.0, 12.0, 24.0, -35.0, (3.0, -3.0, 2.2), 47, paint)
    shard(b, 3.6, 1.8, 9.5, 38.0, 75.0, (8.0, 5.0, 2.2), 50, paint)
    foot = [ring(5, 3.4, 0.0, ROCK_JITTER, 0.0, seed=53, centre=(-11.0, -7.0)),
            ring(5, 2.6, 3.2, ROCK_JITTER, ROCK_WOBBLE, seed=54, centre=(-10.5, -6.5), turn=0.3)]
    lump(b, foot, paint)
    return [("", b)]


def outcrop_b():
    """B, a stepped crag: a wide foot, a snowy terrace halfway up (a ring
    stepped in at the same height), a narrower head with a snow top,
    31 x 18 x 27, 8 points (64 + 6 + 6)."""
    b = Builder()
    rings = [ring(8, 14.0, 0.0, ROCK_JITTER, 0.0, seed=60, squash=0.85),
             ring(8, 15.0, 4.5, ROCK_JITTER, ROCK_WOBBLE * 0.5, seed=61, squash=0.85, turn=0.2),
             ring(8, 13.0, 9.0, ROCK_JITTER, 0.0, seed=62, squash=0.85, centre=(1.0, 0.0), turn=0.1),
             ring(8, 8.5, 9.2, ROCK_JITTER, 0.0, seed=63, squash=0.85, centre=(2.5, 1.0), turn=0.3),
             ring(8, 4.8, 18.0, ROCK_JITTER, 0.0, seed=64, squash=0.85, centre=(3.5, 1.5), turn=0.1, tilt=(0.08, 0.0))]
    lump(b, rings, stone(65, light=0.3))
    return [("", b)]


def outcrop_c():
    """C, a tall tor: a leaning column of big triangular facets with a snowy
    head, a slab leaning on its flank and a boulder at its foot, 25 x 26 x 21,
    6 points (48 + 4 + 4, 20, 16)."""
    b = Builder()
    paint = stone(70, light=0.3)
    rings = [ring(6, 11.5, 0.0, ROCK_JITTER, 0.0, seed=71, squash=0.8),
             ring(6, 11.0, 6.0, ROCK_JITTER, ROCK_WOBBLE * 0.5, seed=72, squash=0.8, turn=0.2),
             ring(6, 8.0, 13.0, ROCK_JITTER, ROCK_WOBBLE * 0.5, seed=73, squash=0.8, centre=(1.5, 0.0), turn=0.4),
             ring(6, 6.5, 20.0, ROCK_JITTER, ROCK_WOBBLE * 0.5, seed=74, squash=0.8, centre=(3.0, 0.5), turn=0.2),
             ring(6, 3.6, 26.0, ROCK_JITTER, 0.0, seed=75, squash=0.8, centre=(3.5, 0.6), turn=0.5, tilt=(0.1, 0.0))]
    lump(b, rings, paint)
    shard(b, 4.0, 2.0, 13.0, 32.0, 111.0, (-9.0, -4.5, 1.5), 76, paint)   # its head leans into the tor's flank
    foot = [ring(5, 3.2, 0.0, ROCK_JITTER, 0.0, seed=79, centre=(-9.5, 5.0)),
            ring(5, 2.6, 3.4, ROCK_JITTER, ROCK_WOBBLE, seed=80, centre=(-9.0, 5.5), turn=0.3)]
    lump(b, foot, paint)
    return [("", b)]


# --- Kit_Ice_Serac: seracs (6-30 x 5-25, 60 tris) ---------------------------------------------
# Blocks of glacier ice: four- and five-sided lumps, built from Z = 0 up (the
# generator sinks them 30 %), tilted by shearing their rings so their bottoms
# stay flat on the ground; their steep faces lean to IceDeep.
def serac_a():
    """A, a tilted block: a four-sided block 15 x 11 x 12 sheared to +x,
    its top ring tilted so the snow cap slopes (24 + 2 + 2)."""
    b = Builder()
    q = math.pi / 4
    rings = [ring(4, 9.2, 0.0, ICE_JITTER, 0.0, seed=90, squash=0.8, turn=q + 0.15),
             ring(4, 9.6, 5.0, ICE_JITTER, ICE_WOBBLE, seed=91, squash=0.8, turn=q + 0.1, centre=(1.2, 0.4)),
             ring(4, 8.4, 10.5, ICE_JITTER, 0.0, seed=92, squash=0.8, turn=q + 0.2, centre=(2.6, 0.8), tilt=(0.12, -0.06)),
             ring(4, 6.0, 12.0, ICE_JITTER, 0.0, seed=93, squash=0.8, turn=q + 0.2, centre=(3.4, 1.0), tilt=(0.1, -0.05))]
    lump(b, rings, crystal(94, deep=0.2, steep=0.45))
    return [("", b)]


def serac_b():
    """B, a leaning shard: a five-sided blade 10 x 20 x 8 leaning to +x,
    narrowing to a small snowy top (30 + 3 + 3)."""
    b = Builder()
    rings = [ring(5, 4.6, 0.0, ICE_JITTER, 0.0, seed=95, squash=0.8),
             ring(5, 4.9, 6.0, ICE_JITTER, ICE_WOBBLE, seed=96, squash=0.8, centre=(1.0, 0.3), turn=0.2),
             ring(5, 3.7, 13.0, ICE_JITTER, ICE_WOBBLE, seed=97, squash=0.75, centre=(2.3, 0.6), turn=0.1),
             ring(5, 1.7, 20.0, ICE_JITTER, 0.0, seed=98, squash=0.8, centre=(3.3, 1.0), turn=0.3, tilt=(0.15, 0.05))]
    lump(b, rings, crystal(99, deep=0.2, steep=0.45))
    return [("", b)]


def serac_c():
    """C, a cluster: two four-sided blocks of different heights and turns
    leaning together, 24 x 10 x 16 (2 x (16 + 2 + 2))."""
    b = Builder()
    paint = crystal(100, deep=0.2, steep=0.45)
    q = math.pi / 4
    big = [ring(4, 8.6, 0.0, ICE_JITTER, 0.0, seed=101, squash=0.85, turn=q + 0.3, centre=(-5.5, 1.0)),
           ring(4, 8.8, 5.0, ICE_JITTER, ICE_WOBBLE, seed=102, squash=0.85, turn=q + 0.25, centre=(-5.0, 1.4)),
           ring(4, 7.2, 10.0, ICE_JITTER, 0.0, seed=103, squash=0.85, turn=q + 0.35, centre=(-4.2, 1.8), tilt=(-0.1, 0.08))]
    lump(b, big, paint)
    small = [ring(4, 6.6, 0.0, ICE_JITTER, 0.0, seed=104, squash=0.9, turn=q - 0.35, centre=(6.5, -2.0)),
             ring(4, 6.8, 3.5, ICE_JITTER, ICE_WOBBLE, seed=105, squash=0.9, turn=q - 0.3, centre=(7.0, -2.3)),
             ring(4, 5.2, 7.0, ICE_JITTER, 0.0, seed=106, squash=0.9, turn=q - 0.4, centre=(7.8, -2.8), tilt=(0.12, -0.1))]
    lump(b, small, paint)
    return [("", b)]


# --- Kit_Ice_Spire: ice pinnacles (20-50 x 40-150, 200 tris) ------------------------------------
# Towering faceted crystals, six points round, flaring at the foot (the
# generator sinks them 3 m into the ice); a ring stepped in just above a
# wider one makes a ledge, which comes out Snow.
def spike(b, stations, seed, paint, apex, squash=0.85, lean=(0.0, 0.0), n=6, jitter=ICE_JITTER):
    """A pinnacle through `stations` [(z, radius)] or [(z, radius, (x, y))]
    (an explicit centre), n points round, its rings leaning `lean` (x, y per
    metre of height) where no centre is given, fanning to `apex`."""
    rings = []
    for i, st in enumerate(stations):
        z, r = st[0], st[1]
        centre = st[2] if len(st) > 2 else (lean[0] * z, lean[1] * z)
        ends = i in (0, len(stations) - 1)
        rings.append(ring(n, r, z, jitter, 0.0 if ends else ICE_WOBBLE * 0.6, seed=seed + i,
                          squash=squash, centre=centre, turn=0.23 * i))
    lump(b, rings, paint, top=apex)


def ice_spire_a():
    """A, a single spike: 30 x 110, a flared foot, a snowy ledge at 40 m and
    a small shard leaning at its foot (120 + 4 + 6, 20 + 3 + 5)."""
    b = Builder()
    paint = crystal(110)
    spike(b, [(0.0, 14.5), (10.0, 13.5), (24.0, 12.0), (40.0, 10.0), (43.0, 7.6), (58.0, 7.2), (74.0, 6.0),
              (88.0, 4.8), (100.0, 3.2)], 111, paint, (1.8, 0.6, 110.0), lean=(0.015, 0.004))
    rings = [ring(5, 5.0, 0.0, ICE_JITTER, 0.0, seed=120, centre=(11.0, -6.0)),
             ring(5, 4.4, 9.0, ICE_JITTER, ICE_WOBBLE, seed=121, centre=(13.0, -7.5), turn=0.3),
             ring(5, 2.4, 20.0, ICE_JITTER, 0.0, seed=122, centre=(15.0, -9.0), turn=0.1)]
    lump(b, rings, paint, top=(16.0, -9.5, 26.0))
    return [("", b)]


def ice_spire_b():
    """B, a twin spike: a 90 m spike and a 62 m one leaning away from it
    out of one foot, 42 x 90 x 30 (84 + 4 + 6, 60 + 4 + 6)."""
    b = Builder()
    paint = crystal(130)
    spike(b, [(0.0, 13.0, (-8.0, 0.0)), (12.0, 12.0, (-8.5, 0.2)), (28.0, 10.0, (-9.0, 0.4)), (31.0, 8.0, (-9.0, 0.5)),
              (48.0, 7.0, (-9.5, 0.8)), (64.0, 5.4, (-10.0, 1.0)), (78.0, 3.6, (-10.5, 1.2))],
          131, paint, (-11.0, 1.4, 90.0))
    spike(b, [(0.0, 10.0, (10.0, 1.5)), (10.0, 9.4, (11.0, 1.7)), (24.0, 7.6, (12.5, 2.0)), (40.0, 5.6, (14.5, 2.3)),
              (52.0, 3.4, (16.0, 2.6))], 140, paint, (17.5, 2.9, 62.0), squash=0.8)
    return [("", b)]


def ice_spire_c():
    """C, a crooked spire: 130 m, its rings drifting to +x as it rises,
    narrowing to a waist at 75 m, then swelling again and overhanging its
    foot a little before the point, 29 x 130 x 24 (108 + 4 + 6)."""
    b = Builder()
    paint = crystal(150)
    spike(b, [(0.0, 13.5, (0.0, 0.0)), (15.0, 12.2, (1.0, 0.0)), (35.0, 10.2, (3.0, 0.5)), (55.0, 8.2, (5.0, 1.0)),
              (58.0, 6.8, (5.3, 1.0)), (75.0, 6.4, (6.5, 1.3)), (92.0, 7.0, (8.5, 1.7)), (108.0, 7.0, (11.5, 2.2)),
              (120.0, 4.6, (13.5, 2.7)), (126.0, 2.8, (14.5, 3.0))], 151, paint, (15.8, 3.4, 130.0), squash=0.82)
    return [("", b)]


# --- Kit_Ice_Arch: the ice arches (160 x 100 x 30, 2,000 tris) --------------------------------
# A faceted tube bent along a spine of stations: up the left leg, over a
# flattened elliptical arc, down the right leg. Each ring lies across the
# spine's tangent, so the tube's bands are collars round the arch; the
# jitter only ever moves the inside of the bend inwards into the ice, so the
# opening is as the stations say. The icicle teeth are paint: on the lowest
# quad of each side over the span, the triangle hanging from the side's
# upper edge is IceDeep, so across the bands (their diagonals alternate) a
# sawtooth of deep teeth points down into the opening.
ARCH_W, ARCH_H = 160.0, 100.0     # nominal size (ASSETS.md); the opening must be 0.70 w x 0.72 h
ARCH_SIDES = 10                   # points round each ring: big planes, seen from the approach
ARCH_FOOT_X = 68.0                # the feet's spine: inner faces at 68 - 11 = 57, clear 114 m
ARCH_SPRING_Z = 34.0              # the legs end, the arc begins
ARCH_SPAN = (64.0, 56.5)          # the arc's half width and rise (an ellipse about the springing centre)
ARCH_ARC_STEPS = 14               # stations round the arc (bands about 14 m along it)
ARCH_TEETH_K = (5, 9)             # the quads carrying teeth: the bottom of the front (points 5-6) and back (9-0) sides
ARCH_UNDER_K = (6, 7, 8)          # the quads of the underside: IceDeep


def arch_spine():
    """The spine, [(x, z, radius across the spine, radius along y)]."""
    legs_up = [(-68.0, 0.0, 11.0, 15.0), (-68.0, 10.0, 11.6, 15.0), (-67.0, 22.0, 10.8, 14.0), (-65.0, 34.0, 10.2, 13.5)]
    arc = []
    a, rise = ARCH_SPAN
    rng = random.Random(160)
    for i in range(1, ARCH_ARC_STEPS):
        th = math.pi * (1.0 - i / ARCH_ARC_STEPS)
        bulge = 1.0 + 0.12 * math.sin(3.0 * th + 0.8) + rng.uniform(-0.05, 0.05)
        arc.append((a * math.cos(th), ARCH_SPRING_Z + rise * math.sin(th), 9.4 * bulge, 12.0 * bulge))
    legs_down = [(65.0, 34.0, 10.2, 13.5), (67.0, 22.0, 10.8, 14.0), (68.0, 10.0, 11.6, 15.0), (68.0, 0.0, 11.0, 15.0)]
    return legs_up + arc + legs_down


def tube_ring(p, t, rv, ry, n, seed, jitter, wobble):
    """n points round spine point `p` in the plane across the tangent `t`:
    `ry` along y, `rv` across it in the x-z plane (its + side is t x y: the
    outside of a bend, up over the crown). Jittered like ring(), except that
    points on the inside of the bend only ever move inwards (the opening is
    gameplay); `wobble` slides each point along the tangent by up to that
    share of rv."""
    rng = random.Random(seed)
    u = Vector((0.0, 1.0, 0.0))
    v = t.cross(u).normalized()
    pts = []
    for k in range(n):
        a = 2.0 * math.pi * (k + rng.uniform(-0.3, 0.3) * jitter) / n
        s = 1.0 + rng.uniform(-1.0, 1.0) * jitter
        if math.sin(a) < 0.0:
            s = min(s, 1.0)
        q = p + u * (ry * s * math.cos(a)) + v * (rv * s * math.sin(a)) + t * (rng.uniform(-1.0, 1.0) * wobble * rv)
        pts.append(tuple(q))
    return pts


def ice_arch():
    """The arch: one tube along arch_spine() (rings across the spine's
    tangent by central differences; the feet vertical, so their caps lie flat
    on the ground), teeth under the span, Snow over it."""
    b = Builder()
    spine = arch_spine()
    pts = [Vector((x, 0.0, z)) for x, z, _, _ in spine]
    rings = []
    for i, (x, z, rv, ry) in enumerate(spine):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        foot = i in (0, len(pts) - 1)
        rings.append(tube_ring(pts[i], t, rv, ry, ARCH_SIDES, seed=170 + i, jitter=0.14,
                               wobble=0.0 if foot else 0.1))
    span = range(3, len(spine) - 4)       # the bands between the springings
    side = crystal(200, deep=0.25)

    def paint(band, k, n, corners):
        if band in span:
            if k in ARCH_UNDER_K:
                return "IceDeep"
            if k == ARCH_TEETH_K[0] and corners is not None and 0 in corners and 3 in corners:
                return "IceDeep"
            if k == ARCH_TEETH_K[1] and corners is not None and 1 in corners and 2 in corners:
                return "IceDeep"
            if n.z > SNOW_UP:
                return "Snow"
            return "Ice"
        return side(band, k, n, corners)
    lump(b, rings, paint)
    return [("", b)]


def arch_profile(x, z):
    """The gateway the game needs: 0.70 w wide and 0.72 h high with a round
    top (a semicircle of 0.35 w), as Corneria's gen_landmarks.py checks it."""
    r = 0.35 * ARCH_W
    zs = 0.72 * ARCH_H - r
    return abs(x) <= r and (z <= zs or x * x + (z - zs) ** 2 <= r * r)


def opening_report(name, builders, profile, flight_hd):
    """Casts rays through the piece's geometry: the clear width at the base
    (1 m up, from the centre out to each side), the clear height at the
    centre (up from the ground), and a flight along y through every point of
    a 2 m grid inside `profile`(x, z) -> bool, the opening the game needs.
    Prints them as fractions of the piece's width and height."""
    verts, tris = [], []
    for _, b in builders:
        base = len(verts)
        verts += [tuple(v) for v in b.verts]
        for idx, _, _ in b.faces:                 # every face here is convex enough: a fan triangulates it
            for i in range(1, len(idx) - 1):
                tris.append((base + idx[0], base + idx[i], base + idx[i + 1]))
    bvh = BVHTree.FromPolygons(verts, tris, all_triangles=True)
    width = max(v[0] for v in verts) - min(v[0] for v in verts)
    height = max(v[2] for v in verts) - min(v[2] for v in verts)

    def reach(origin, direction):
        hit = bvh.ray_cast(Vector(origin), Vector(direction), 1000.0)
        return hit[3] if hit[0] is not None else math.inf
    clear_w = reach((0.0, 0.0, 1.0), (1.0, 0.0, 0.0)) + reach((0.0, 0.0, 1.0), (-1.0, 0.0, 0.0))
    clear_h = reach((0.0, 0.0, 0.0), (0.0, 0.0, 1.0))
    samples, blocked = 0, []
    for ix in range(-int(width / 4), int(width / 4) + 1):
        for iz in range(0, int(height / 2) + 1):
            x, z = ix * 2.0, iz * 2.0 + 0.5
            if not profile(x, z):
                continue
            samples += 1
            if reach((x, -flight_hd - 50.0, z), (0.0, 1.0, 0.0)) < 2 * flight_hd + 100.0:
                blocked.append((x, z))
    print("  %s opening: clear width at the base %.1f m (%.3f x width), clear height at the centre %.1f m "
          "(%.3f x height), %d of %d flight samples blocked%s" % (
              name, clear_w, clear_w / width, clear_h, clear_h / height, len(blocked), samples,
              " at " + ", ".join("(%.0f, %.0f)" % p for p in blocked[:8]) if blocked else ""))


# --- Kit_Ice_Falls: the frozen waterfall (140 x 260 x 50, 3,000 tris) ---------------------------
# One closed shell: a faceted front sheet over rows of points (a row per
# height station, each with its own half width and depth), a flat back in
# the plane y = FALLS_BACK against the cliff, flat sides, a flat bottom and
# a snowy top strip at the lip. Across each row the points run trough,
# shoulder, crest, shoulder: FALLS_COLUMNS bulging ice columns of uneven
# widths and relief (a couple nearly flat sheets), their crests wandering
# a little as they fall and the curtain thickest in the middle; the folds
# between them (the triangles along each trough) are IceDeep, the columns
# Ice, and every facet that looks up (the mound's shoulder, the ledges where
# the depth steps back, the lip) is Snow. Above each ledge the pattern shifts
# half a column, so the columns above don't line up with the ones below: a
# cascade in steps.
FALLS_W, FALLS_H, FALLS_D = 140.0, 260.0, 50.0
FALLS_BACK = FALLS_D / 2
FALLS_COLUMNS = 9
FALLS_SHAPE = (0.0, 0.6, 1.0, 0.6)   # relief across a column: trough, shoulder, crest, shoulder
FALLS_STEPS = (0.0, 0.28, 0.5, 0.72)  # ...and where across the column those points sit
FALLS_FOLD = 0.3                      # a triangle whose mean relief is under this lies in a fold: IceDeep
FALLS_MIDDLE = 3.0                    # the curtain is this much thicker at its middle than at its edges
# (z, depth of the troughs in front of the origin, half width, column relief, pattern offset)
FALLS_ROWS = [
    (0.0, 22.5, 70.0, 1.0, 0), (4.0, 23.6, 70.5, 1.2, 0), (9.0, 23.0, 69.0, 1.6, 0), (14.0, 21.0, 67.0, 2.0, 0),
    (17.0, 17.4, 65.0, 2.2, 0),                                        # the mound's snowy shoulder
    (26.0, 14.4, 62.0, 2.8, 0), (40.0, 12.6, 59.0, 3.8, 0), (58.0, 13.2, 56.5, 4.6, 0),
    (78.0, 14.4, 55.0, 5.0, 0), (98.0, 15.6, 54.0, 5.0, 0),
    (103.0, 9.6, 53.0, 3.8, 2),                                        # ledge 1
    (124.0, 11.2, 52.5, 4.6, 2), (146.0, 13.0, 52.0, 5.2, 2), (168.0, 14.6, 51.5, 5.4, 2),
    (173.0, 9.2, 51.0, 3.8, 0),                                        # ledge 2
    (196.0, 10.8, 50.5, 4.6, 0), (220.0, 12.4, 50.0, 5.0, 0), (240.0, 13.2, 49.5, 4.6, 0),
    (252.0, 11.0, 49.0, 3.2, 0), (258.0, 8.4, 48.5, 2.0, 0), (260.0, 6.4, 48.0, 1.0, 0),   # the lip
]


def face_out(b, pts, mat, out):
    """A face through `pts`, wound so its front faces along `out`."""
    n = normal(pts)
    b.face(pts if n.dot(Vector(out)) >= 0.0 else pts[::-1], mat)


def ice_falls():
    """The frozen waterfall, as described above."""
    b = Builder()
    rng = random.Random(300)
    count = 4 * FALLS_COLUMNS + 1
    # The columns' edges across the width (-1..1), of uneven widths, with
    # the four relief points of each column between them.
    widths = [rng.uniform(0.55, 1.6) for _ in range(FALLS_COLUMNS)]
    edges = [-1.0]
    for w in widths:
        edges.append(edges[-1] + 2.0 * w / sum(widths))
    base_u = [edges[c] + (edges[c + 1] - edges[c]) * s for c in range(FALLS_COLUMNS) for s in FALLS_STEPS] + [1.0]
    col_scale = [rng.uniform(0.6, 1.5) for _ in range(FALLS_COLUMNS + 2)]                    # the columns differ in relief
    for c in rng.sample(range(FALLS_COLUMNS), 2):
        col_scale[c] = 0.2                                                                   # ...two are near-flat sheets
    wander = [(rng.uniform(0.02, 0.05), rng.uniform(40.0, 90.0), rng.uniform(0.0, 6.3)) for _ in range(count)]
    rows, folds = [], []
    for z, depth, half, amp, offset in FALLS_ROWS:
        pts, fold = [], []
        for k in range(count):
            u = base_u[k]
            if 0 < k < count - 1:
                a, period, phase = wander[k]
                u += a * math.sin(z / period + phase) + rng.uniform(-0.1, 0.1) * (base_u[k + 1] - base_u[k - 1]) / 2
            f = FALLS_SHAPE[(k + offset) % 4]
            relief = amp * f * col_scale[(k + offset) // 4] + rng.uniform(-0.12, 0.12) * amp
            thick = FALLS_MIDDLE * (1.0 - u * u) * min(1.0, z / 40.0)
            pts.append((u * half, max(-FALLS_BACK + 0.5, -(depth + relief + thick)), z + rng.uniform(-0.1, 0.1) * amp))
            fold.append(f)
        rows.append(pts)
        folds.append(fold)
    rows[0] = [(x, y, 0.0) for x, y, _ in rows[0]]
    rows[-1] = [(x, y, FALLS_H) for x, y, _ in rows[-1]]

    def sheet(tri, fold):
        n = normal(tri)
        if n.z > SNOW_UP:
            return "Snow"
        return "IceDeep" if sum(fold) / 3.0 < FALLS_FOLD else "Ice"
    # The front: two triangles per quad, their diagonals alternating.
    for j in range(len(rows) - 1):
        lo, hi, flo, fhi = rows[j], rows[j + 1], folds[j], folds[j + 1]
        for k in range(count - 1):
            quad = [lo[k], lo[k + 1], hi[k + 1], hi[k]]
            fq = [flo[k], flo[k + 1], fhi[k + 1], fhi[k]]
            tris = ((0, 1, 2), (0, 2, 3)) if (j + k) % 2 == 0 else ((0, 1, 3), (1, 2, 3))
            for t in tris:
                tri = [quad[i] for i in t]
                b.face(tri, sheet(tri, [fq[i] for i in t]))
    # The sides, the back, the bottom and the top.
    back = lambda p: (p[0], FALLS_BACK, p[2])
    for j in range(len(rows) - 1):
        for k, out in ((0, (-1.0, 0.0, 0.0)), (count - 1, (1.0, 0.0, 0.0))):
            p0, p1 = rows[j][k], rows[j + 1][k]
            face_out(b, [p0, p1, back(p1)], "Ice", out)
            face_out(b, [p0, back(p1), back(p0)], "Ice", out)
        face_out(b, [back(rows[j][0]), back(rows[j][-1]), back(rows[j + 1][-1]), back(rows[j + 1][0])],
                 "IceDeep", (0.0, 1.0, 0.0))
    face_out(b, rows[0] + [back(rows[0][-1]), back(rows[0][0])], "Ice", (0.0, 0.0, -1.0))
    face_out(b, rows[-1] + [back(rows[-1][-1]), back(rows[-1][0])], "Snow", (0.0, 0.0, 1.0))
    return [("", b)]


# --- The batch ---------------------------------------------------------------------------------
PIECES = [
    ("Kit_Tree_SnowPine_A", snow_pine_a), ("Kit_Tree_SnowPine_B", snow_pine_b), ("Kit_Tree_SnowPine_C", snow_pine_c),
    ("Kit_Rock_Boulder_A", boulder_a), ("Kit_Rock_Boulder_B", boulder_b), ("Kit_Rock_Boulder_C", boulder_c),
    ("Kit_Rock_Outcrop_A", outcrop_a), ("Kit_Rock_Outcrop_B", outcrop_b), ("Kit_Rock_Outcrop_C", outcrop_c),
    ("Kit_Ice_Serac_A", serac_a), ("Kit_Ice_Serac_B", serac_b), ("Kit_Ice_Serac_C", serac_c),
    ("Kit_Ice_Spire_A", ice_spire_a), ("Kit_Ice_Spire_B", ice_spire_b), ("Kit_Ice_Spire_C", ice_spire_c),
    ("Kit_Ice_Arch", ice_arch),
    ("Kit_Ice_Falls", ice_falls),
]


def main():
    kt.begin("kit_nature", 3)
    for name, build in PIECES:
        builders = build()
        if kt.piece(name, builders) is not None and name == "Kit_Ice_Arch":
            opening_report(name, builders, arch_profile, 15.0)
    kt.finish()


if __name__ == "__main__":
    main()
