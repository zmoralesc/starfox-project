"""Corneria City's skyline (ASSETS.md, "City"): the office stacks
Kit_City_Office_A..D, the skyscraper stacks Kit_City_Tower_A..D, the drum
tower stacks Kit_City_RoundTower_A..B and the central Kit_City_Spire.

    KIT_OUT=<copy.blend> KIT_PREVIEW=<dir> blender --background --python kit_city_high.py
    KIT_STACK_PREVIEW=<dir>  also renders each stack assembled (base, shafts,
                             crown) and the whole batch standing as a skyline

A stack is three collections, <name>_Base, _Shaft and _Crown, each with its
origin at the centre of its own bottom. settlement.py stands the base on the
ground, as many shafts as reach the height asked for on it, then the crown,
scaling all three by the same width and depth and the shafts a little in
height. So every shaft here keeps one outline top and bottom and paints its
bands in whole storeys (STOREY) from z = 0; a base ends in the shaft's outline
with the storey rhythm running into it, and a crown starts with the shaft's
outline (or sits set back on the shaft's RoofDark top). The base can't
overlap the shaft (the shaft stands on the base's measured top), so the joints
rely on matching outlines; masts and roof fittings are sunk SINK into what
they stand on, never flush.

Colour: the city is white. Most of each facade is Tower or Cream (piers,
spandrels, corner masses, podiums) and the glass is the accent: strips, a
curtain wall on one face, a glass corner. Only RoundTower_B and the spire
stay glass-forward. Painted shapes are big: a strip or band under 1.5 m is
lost at the distances the city is seen from.

Side cells are kept few: prism() caps take every cut on their edge, so each
vertex round a shaft's perimeter costs two cap triangles, which is most of a
striped shaft's budget.

Open joints: a cap ending exactly on a continuing wall ties with it in
depth along the joint line, and the screen-space ink pass dots the line
with the cap's normal. So stack parts are left open where they join flush:
shafts have no caps at all, crowns no bottom cap, bases no top cap (a wider
podium's roof is a ring, `skirt()`, sharing the flush section's vertices).
Every crown starts with a full-outline section that has its own roof, so
nothing looks into an open shaft. kit_tools.check() ignores open edges at
those heights for parts named _Base / _Shaft / _Crown.

Joint plugs: float rounding still leaves hairline cracks at the joints in
the game, so every shaft and crown gets a second object, "<name>_Plug": a
closed sleeve in the wall's main colour, the part's bottom outline inset
PLUG_INSET, from PLUG_BELOW below the joint to PLUG_ABOVE into the part.
Seen through a crack it reads as wall (same facing, 5 cm behind).
settlement.measure() skips *_Plug objects, so the stacking heights are
unchanged; check() reports those parts' base z as -PLUG_BELOW, which is
expected. Bases need none.
"""

import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit_tools as kt  # noqa: E402
from kit_tools import Builder  # noqa: E402

STOREY = 4.0                       # one floor
OFFICE_SHAFT = 3 * STOREY          # office shafts: 3 storeys
TOWER_SHAFT = 4 * STOREY           # tower and drum shafts: 4 storeys
SINK = 0.2                         # fittings sink this far into what they stand on (no coplanar faces, nothing floats)
LIGHT = 0.6                        # painted LightStrip bands are this wide
TIP = 2.0                          # the WarningLight at an antenna's tip is this tall
STACK_SHAFTS = 4                   # shafts per assembled preview
PLUG_INSET = 0.05                  # a joint plug sits this far inside the wall...
PLUG_BELOW, PLUG_ABOVE = 0.4, 0.1  # ...from this far into the part below to this far into its own part


# --- Outlines and painting -----------------------------------------------------------------
def rect(hw, hd):
    """A 2hw x 2hd rectangle anticlockwise from above: (outline, side tags
    R, B, L, F: right, back, left, front)."""
    return [(hw, -hd), (hw, hd), (-hw, hd), (-hw, -hd)], ["R", "B", "L", "F"]


def rounded(hw, hd, r, segs=4, corners="FR BR BL FL"):
    """The rectangle with the named corners rounded off by `r` in `segs` arcs
    (1: a chamfer): (outline, side tags: the flats R/B/L/F, the arcs "arc")."""
    out, tags = [], []
    for name, (cx, cy), a0, after in (("FR", (hw - r, -hd + r), -90.0, "R"), ("BR", (hw - r, hd - r), 0.0, "B"),
                                        ("BL", (-hw + r, hd - r), 90.0, "L"), ("FL", (-hw + r, -hd + r), 180.0, "F")):
        if name in corners.split():
            for i in range(segs + 1):
                a = math.radians(a0 + 90.0 * i / segs)
                out.append((cx + r * math.cos(a), cy + r * math.sin(a)))
                tags.append("arc" if i < segs else after)
        else:
            out.append((cx + (r if "R" in name else -r), cy + (r if "B" in name else -r)))
            tags.append(after)
    return out, tags


def cuts(widths, length):
    """Column cut fractions for cells `widths` wide along a side `length`
    long, the run centred (any remainder widens the end cells)."""
    acc = (length - sum(widths)) / 2
    out = []
    for w in widths[:-1]:
        acc += w
        if 0.0 < acc < length:
            out.append(acc / length)
    return out


def fins(fin, bay):
    """Column cuts for fin|bay|fin|...|fin: as many bays as fit the side."""
    def columns(_s, length):
        n = max(1, int((length - fin) // (fin + bay)))
        return cuts([fin] + [bay, fin] * n, length)
    return columns


def piers(pier, n):
    """Column cuts for `n` piers (two at the corners) with equal bays between."""
    def columns(_s, length):
        bay = (length - n * pier) / (n - 1)
        return cuts([pier, bay] * (n - 1) + [pier], length)
    return columns


def inset(outline, d):
    """`outline` (anticlockwise from above) moved `d` inwards, corners mitred."""
    n = len(outline)
    out = []
    for i in range(n):
        p = Vector(outline[i])
        a, b = Vector(outline[i - 1]), Vector(outline[(i + 1) % n])
        n1 = Vector(((p - a).y, -(p - a).x)).normalized()     # outward normals of the edges meeting at p
        n2 = Vector(((b - p).y, -(b - p).x)).normalized()
        m = (n1 + n2) / (1.0 + n1.dot(n2))
        out.append(tuple(p - m * d))
    return out


def plug(outline, mat):
    """A joint plug factory for a part whose bottom is `outline` (see the
    module docstring): each call makes the sleeve as a new Builder."""
    def make():
        b = Builder()
        b.prism(inset(outline, PLUG_INSET), -PLUG_BELOW, PLUG_ABOVE, mat)
        return b
    return make


def round_plug(r, segments, mat="Tower"):
    """The joint plug factory for a drum of radius `r`, lathed like it."""
    def make():
        b = Builder()
        b.lathe([(r - PLUG_INSET, -PLUG_BELOW), (r - PLUG_INSET, PLUG_ABOVE)], mat, segments=segments)
        return b
    return make


def storeys(pattern, height):
    """Band cut heights for a storey `pattern` [(material, metres)] repeated
    to `height`, and the painter of its rows."""
    levels, z = [], 0.0
    mats = []
    while z < height - 1e-6:
        for m, h in pattern:
            z += h
            levels.append(z)
            mats.append(m)
    return levels[:-1], lambda r: mats[r]


# --- Round parts --------------------------------------------------------------------------
def lathe_rows(b, rows, segments=16, cap_mat=None, bottom=True, top=True):
    """A lathe from `rows` [(radius, z, material of the band above the ring)]:
    the material may be a function of the segment (fins painted round).
    Unlike Builder.lathe() it can leave an end open (`bottom`, `top`: a
    stack part's joint), so it builds its own faces."""
    rings = []
    for r, z, _ in rows:
        if r <= 0.0:
            rings.append([(0.0, 0.0, z)] * segments)
        else:
            rings.append([(r * math.cos(2 * math.pi * k / segments), r * math.sin(2 * math.pi * k / segments), z)
                          for k in range(segments)])
    for i in range(len(rings) - 1):
        m = rows[i][2]
        for k in range(segments):
            k1 = (k + 1) % segments
            b.face([rings[i][k], rings[i][k1], rings[i + 1][k1], rings[i + 1][k]], (m(k) if callable(m) else m) or "Tower",
                   True)
    if bottom and rows[0][0] > 0.0:
        b.face(rings[0][::-1], cap_mat or "Tower")
    if top and rows[-1][0] > 0.0:
        b.face(rings[-1], cap_mat or "Tower")


def skirt(b, outer, inner, z, columns, mat):
    """A flat ring roof at `z` between two outlines with the same number of
    sides (a podium's top round a flush section), each side cut at the
    fractions `columns`(side, inner side length) so it shares every vertex
    with the prisms on both sides."""
    n = len(inner)
    for s in range(n):
        ai, bi = Vector(inner[s]), Vector(inner[(s + 1) % n])
        ao, bo = Vector(outer[s]), Vector(outer[(s + 1) % n])
        us = [0.0] + sorted(columns(s, (bi - ai).length)) + [1.0]
        for u0, u1 in zip(us, us[1:]):
            p = lambda a, c, u: (a.lerp(c, u).x, a.lerp(c, u).y, z)
            b.face([p(ai, bi, u0), p(ai, bi, u1), p(ao, bo, u1), p(ao, bo, u0)], mat)


def mast(b, z0, height, r=1.0, segments=8):
    """An antenna standing on z0 (sunk SINK): a drum `r` thick that steps
    thinner halfway, a LightStrip band on each section and a WarningLight tip."""
    top, mid, r2 = z0 + height, z0 + height * 0.45, r * 0.55
    lathe_rows(b, [(r, z0 - SINK, "Tower"), (r, mid - 1.2, "LightStrip"), (r, mid, "Tower"),
                   (r2, mid, "Tower"), (r2, (mid + top) / 2 - 0.5, "LightStrip"), (r2, (mid + top) / 2 + 0.5, "Tower"),
                   (r2, top - TIP, "WarningLight"), (0.0, top, None)], segments)


def ring(b, r_in, r_out, z0, z1, mat, segments=16, rim_mat=None, top_mat=None):
    """A flat ring (a hollow drum) from r_in to r_out, z0 to z1, its rims smooth."""
    def p(r, z, k):
        a = 2 * math.pi * k / segments
        return (r * math.cos(a), r * math.sin(a), z)
    for k in range(segments):
        k1 = (k + 1) % segments
        b.face([p(r_out, z0, k), p(r_out, z0, k1), p(r_out, z1, k1), p(r_out, z1, k)], rim_mat or mat, True)
        b.face([p(r_in, z0, k1), p(r_in, z0, k), p(r_in, z1, k), p(r_in, z1, k1)], mat, True)
        b.face([p(r_out, z1, k), p(r_out, z1, k1), p(r_in, z1, k1), p(r_in, z1, k)], top_mat or mat)
        b.face([p(r_in, z0, k), p(r_in, z0, k1), p(r_out, z0, k1), p(r_out, z0, k)], mat)


def pad(b, cx, cy, r, z0, z1, mat="RoofDark", mark="Marking", segments=16):
    """A round landing pad at (cx, cy) with a painted `mark` ring on top."""
    def p(rr, z, k):
        a = 2 * math.pi * k / segments
        return (cx + rr * math.cos(a), cy + rr * math.sin(a), z)
    radii = [r, r * 0.82, r * 0.62, 0.0]       # rim, ring, disc
    ring_mats = [mat, mark, mat]
    for k in range(segments):
        k1 = (k + 1) % segments
        b.face([p(r, z0, k), p(r, z0, k1), p(r, z1, k1), p(r, z1, k)], mat, True)
        for i in range(3):
            ro, ri = radii[i], radii[i + 1]
            b.face([p(ro, z1, k), p(ro, z1, k1), p(ri, z1, k1), p(ri, z1, k)], ring_mats[i])
    b.face([p(r, z0, k) for k in range(segments)][::-1], mat)


# --- Hand-built shapes -------------------------------------------------------------------
def canted_box(b, hw, hd, z0, z_front, z_back, mat, top_strips, side_mat=None):
    """A 2hw x 2hd block from z0 whose top slopes from z_front (at -Y) to
    z_back: a canted glass top. `top_strips` [(fraction of the depth, material)]
    paint the slope front to back; the sides are cut at the same lines so the
    shell stays closed."""
    ys, acc = [-hd], 0.0
    for f, _ in top_strips:
        acc += f
        ys.append(-hd + 2 * hd * acc)
    ys[-1] = hd
    z_at = lambda y: z_front + (z_back - z_front) * (y + hd) / (2 * hd)
    for (y0, y1), (_, m) in zip(zip(ys, ys[1:]), top_strips):
        b.face([(-hw, y0, z_at(y0)), (hw, y0, z_at(y0)), (hw, y1, z_at(y1)), (-hw, y1, z_at(y1))], m)
        b.face([(hw, y0, z0), (hw, y1, z0), (hw, y1, z_at(y1)), (hw, y0, z_at(y0))], side_mat or mat)
        b.face([(-hw, y1, z0), (-hw, y0, z0), (-hw, y0, z_at(y0)), (-hw, y1, z_at(y1))], side_mat or mat)
    b.face([(-hw, -hd, z0), (hw, -hd, z0), (hw, -hd, z_front), (-hw, -hd, z_front)], mat)
    b.face([(hw, hd, z0), (-hw, hd, z0), (-hw, hd, z_back), (hw, hd, z_back)], mat)
    b.face([(hw, y, z0) for y in ys] + [(-hw, y, z0) for y in ys[::-1]], mat)


def rib(b, stations, angle, half_width, mat):
    """A rib running up a round body at `angle` round Z: a closed flat-sided
    strip through `stations` [(inner radius, outer radius, z)], the inner edge
    sunk inside the body and the outer proud of it."""
    u = Vector((math.cos(angle), math.sin(angle), 0.0))
    t = Vector((-math.sin(angle), math.cos(angle), 0.0))
    rings = []
    for ri, ro, z in stations:
        up = Vector((0.0, 0.0, z))
        rings.append([tuple(u * ri - t * half_width + up), tuple(u * ro - t * half_width + up),
                      tuple(u * ro + t * half_width + up), tuple(u * ri + t * half_width + up)])
    for a, c in zip(rings, rings[1:]):
        for j in range(4):
            j1 = (j + 1) % 4
            b.face([a[j], a[j1], c[j1], c[j]], mat)
    b.face(rings[0][::-1], mat)
    b.face(rings[-1], mat)


# --- Offices: 12-85 m, stone and glass -------------------------------------------------------
def office_a():
    """A, a 36 x 16 slab: cream storeys with a horizontal glass strip each,
    the lobby set back under the slab's overhang, a teal sign fin on the roof."""
    hw, hd = 18.0, 8.0
    outline, _ = rect(hw, hd)
    pattern = [("Glass", 1.6), ("Cream", 2.4)]
    # Base (8 m): a concrete step, the lobby 2 m back from the front under the
    # overhang, then the slab's first Cream edge over it.
    base = Builder()
    base.box(-hw, -hd, 0.0, hw, hd, 0.3, "Concrete")
    # The lobby, the overhang's underside (a skirt out to the slab) and the
    # slab's edge are one open shell, cut at the lobby's fractions throughout.
    lobby = [(hw - 0.5, -hd + 2.0), (hw - 0.5, hd - 0.5), (-hw + 0.5, hd - 0.5), (-hw + 0.5, -hd + 2.0)]
    cols = fins(2.0, 4.0)
    same_cuts = lambda s, length: cols(s, (Vector(lobby[(s + 1) % 4]) - Vector(lobby[s])).length)
    base.prism(lobby, 0.3, 7.0, "GlassDark", columns=cols, top=False,
               cell=lambda s, c, r, u, z: "Tower" if c % 2 == 0 else None)
    skirt(base, outline, lobby, 7.0, cols, "Tower")
    base.prism(outline, 7.0, 8.0, "Cream", columns=same_cuts, top=False, bottom=False)
    # Shaft (12 m): three storeys of bands.
    shaft = Builder()
    levels, row = storeys(pattern, OFFICE_SHAFT)
    shaft.prism(outline, 0.0, OFFICE_SHAFT, "Cream", levels=levels, cell=lambda s, c, r, u, z: row(r),
                top=False, bottom=False)
    # Crown (6.5 m): a parapet with an orange stripe on the front, a roof
    # plant box and a teal fin along the back edge with a light strip on top.
    crown = Builder()
    crown.prism(outline, 0.0, 1.2, "Cream", levels=[0.5], top_mat="RoofDark", bottom=False,
                cell=lambda s, c, r, u, z: "Orange" if r == 0 and s == 3 else None)
    crown.box(-8.0, -5.0, 1.2 - SINK, 8.0, 2.0, 3.6, "RoofDark")
    crown.box(-13.0, hd - 1.6, 1.2 - SINK, 13.0, hd - 0.4, 6.5, "Teal", top_mat="LightStrip")
    return base, shaft, crown, plug(outline, "Cream")


def office_b():
    """B, 24 x 22 with curved glass front corners: wide white piers with a
    glass strip between each pair, a set-back top storey and a mast."""
    hw, hd = 12.0, 11.0
    outline, tags = rounded(hw, hd, 6.0, corners="FR FL")
    columns = fins(4.0, 2.5)

    def paint(s, c, r, u, z):
        if tags[s] == "arc":
            return "Glass"
        return "Tower" if c % 2 == 0 else "Glass"
    # Base (8 m): the piers start on a concrete step (one prism: a second on
    # the same outline would share its uncut edges); the glass is darker and
    # the front strips carry a teal canopy band.
    base = Builder()
    base.prism(outline, 0.0, 8.0, "GlassDark", levels=[0.5, 6.8], columns=columns, top=False,
               bottom_mat="RoofDark", smooth=True,
               cell=lambda s, c, r, u, z: "Concrete" if r == 0 else (
                   "Teal" if r == 2 and tags[s] == "F" and c % 2 == 1 else (
                       "GlassDark" if paint(s, c, r, u, z) == "Glass" else "Tower")))
    # Shaft (12 m): the piers and strips, full height.
    shaft = Builder()
    shaft.prism(outline, 0.0, OFFICE_SHAFT, "Tower", columns=columns, cell=paint, top=False,
                bottom=False, smooth=True)
    # Crown (12 m): a parapet band, a set-back white top storey with a light
    # strip at its edge, and an antenna at the back.
    crown = Builder()
    crown.prism(outline, 0.0, 1.0, "Tower", top_mat="RoofDark", bottom=False, smooth=True)
    inner, itags = rounded(hw - 2.5, hd - 2.5, 3.5, corners="FR FL")
    crown.prism(inner, 1.0 - SINK, 5.5, "Tower", levels=[4.6], top_mat="RoofDark", smooth=True,
                cell=lambda s, c, r, u, z: "LightStrip" if r == 1 else ("Glass" if itags[s] == "arc" else None))
    mast(crown, 5.5, 6.5, 0.7)
    return base, shaft, crown, plug(outline, "Tower")


def office_c():
    """C, 16 x 12, thin: a white block with one glass field on the front and
    back between wide piers, blank white sides, a canted glass top."""
    hw, hd = 8.0, 6.0
    outline, tags = rect(hw, hd)
    pattern = [("Glass", 2.6), ("Tower", 1.4)]
    columns = lambda s, length: cuts([3.0, length - 6.0, 3.0], length) if tags[s] in "FB" else []
    paint = lambda s, c, r, u, z: "Tower" if tags[s] not in "FB" or c != 1 else None
    # Base (8 m): a step, the lobby with an orange painted door, a Tower band.
    base = Builder()
    base.prism(outline, 0.0, 8.0, "Glass", levels=[0.4, 3.6, 6.8], top=False, bottom_mat="RoofDark",
               columns=lambda s, length: cuts([3.0, 2.5, 5.0, 2.5, 3.0], length) if tags[s] in "FB" else [],
               cell=lambda s, c, r, u, z: "Concrete" if r == 0 else (
                   "Tower" if r == 3 or tags[s] not in "FB" or c in (0, 4) else (
                       "Orange" if r == 1 and tags[s] == "F" and c == 2 else None)))
    # Shaft (12 m).
    shaft = Builder()
    levels, row = storeys(pattern, OFFICE_SHAFT)
    shaft.prism(outline, 0.0, OFFICE_SHAFT, "Glass", levels=levels, columns=columns, top=False,
                bottom=False, cell=lambda s, c, r, u, z: paint(s, c, r, u, z) or row(r))
    # Crown (8 m + mast): a Tower parapet band, then the canted top sloping up
    # towards the back, glass in a white frame, a light strip at the high edge.
    crown = Builder()
    crown.prism(outline, 0.0, 1.0, "Tower", top_mat="RoofDark", bottom=False)
    canted_box(crown, hw, hd, 1.0 - SINK, 2.5, 8.0, "Tower",
               [(0.1, "Tower"), (0.78, "Glass"), (0.06, "Tower"), (0.06, "LightStrip")])
    with crown.at(Matrix.Translation((hw - 1.5, hd - 1.5, 0.0))):   # on the slope near the back corner
        mast(crown, 7.0, 6.0, 0.5)
    return base, shaft, crown, plug(outline, "Tower")


def office_d():
    """D, 30 x 28, deep, with chamfered corners as cream piers: cream storeys
    with a strip window each, a stepped parapet, a roof helipad and plant."""
    hw, hd = 15.0, 14.0
    outline, tags = rounded(hw, hd, 4.5, segs=1)
    pattern = [("Glass", 1.8), ("Cream", 2.2)]
    # Base (8 m): a concrete podium band, a dark glass lobby, the cream edge.
    base = Builder()
    base.prism(outline, 0.0, 8.0, "Cream", levels=[1.5, 6.6], top=False, bottom_mat="RoofDark",
               cell=lambda s, c, r, u, z: "Concrete" if r == 0 else (
                   None if tags[s] == "arc" else ("GlassDark" if r == 1 else None)))
    # Shaft (12 m): the bands, the chamfers cream the whole way up.
    shaft = Builder()
    levels, row = storeys(pattern, OFFICE_SHAFT)
    shaft.prism(outline, 0.0, OFFICE_SHAFT, "Cream", levels=levels, top=False, bottom=False,
                cell=lambda s, c, r, u, z: None if tags[s] == "arc" else row(r))
    # Crown (6 m): a parapet with an orange stripe, a set-back roof storey
    # with a light strip, a helipad and a plant box.
    crown = Builder()
    crown.prism(outline, 0.0, 1.2, "Cream", levels=[0.5], top_mat="RoofDark", bottom=False,
                cell=lambda s, c, r, u, z: "Orange" if r == 0 and tags[s] != "arc" else None)
    inner, itags = rounded(hw - 4.0, hd - 4.0, 3.0, segs=1)
    crown.prism(inner, 1.2 - SINK, 5.5, "Cream", levels=[4.3, 4.9], top_mat="RoofDark",
                cell=lambda s, c, r, u, z: ["GlassDark", "LightStrip", "Cream"][r] if itags[s] != "arc" else (
                    "LightStrip" if r == 1 else None))
    pad(crown, 0.0, 0.0, 6.5, 5.5 - SINK, 6.0)
    return base, shaft, crown, plug(outline, "Cream")


# --- Towers: 87-205 m, white and glass ---------------------------------------------------------
def tower_a():
    """A, 28 x 28: wide white piers with glass strips between, the lobby set
    back under the overhanging block; the crown four white corner pylons
    round a glass penthouse, light strips at their tops, and a mast."""
    hw = 14.0
    outline, _ = rect(hw, hw)
    fin = fins(4.0, 2.5)
    paint = lambda s, c, r, u, z: "Tower" if c % 2 == 0 else None
    # Base (20 m): a step, the lobby 2 m in on every side, the block above.
    base = Builder()
    base.box(-hw, -hw, 0.0, hw, hw, 0.4, "Concrete")
    lobby, _ = rect(hw - 2.0, hw - 2.0)
    base.prism(lobby, 0.4, 8.0, "GlassDark", columns=fin, cell=paint, top_mat="RoofDark")
    base.prism(outline, 8.0, 20.0, "Glass", columns=fin, cell=paint, top=False, bottom_mat="Tower")
    # Shaft (16 m): the piers and strips, one cell high (the caps take every cut).
    shaft = Builder()
    shaft.prism(outline, 0.0, TOWER_SHAFT, "Glass", columns=fin, cell=paint, top=False, bottom=False)
    # Crown (32 m): a white cap storey under a light strip, the glass
    # penthouse set back, the pylons on the cap's corners, the mast.
    crown = Builder()
    crown.prism(outline, 0.0, 4.0, "Tower", levels=[3.4], top_mat="RoofDark", bottom=False,
                cell=lambda s, c, r, u, z: "LightStrip" if r == 1 else None)
    pent, _ = rect(10.5, 10.5)
    crown.prism(pent, 4.0 - SINK, 16.0, "Glass", levels=[7.6, 8.8, 12.4, 13.6], top_mat="RoofDark", bottom_mat="RoofDark",
                cell=lambda s, c, r, u, z: "Tower" if r % 2 == 1 else None)
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            x0, y0 = sorted((sx * 10.0, sx * hw)), sorted((sy * 10.0, sy * hw))
            crown.box(x0[0], y0[0], 4.0 - SINK, x0[1], y0[1], 22.0, "Tower", levels=[20.8], top_mat="RoofDark",
                      cell=lambda s, c, r, u, z: "LightStrip" if r == 1 else None)
    mast(crown, 16.0, 16.0, 1.2)
    return base, shaft, crown, plug(outline, "Tower")


def tower_b():
    """B, 36 x 36: a glass curtain wall between wide white corner piers,
    white spandrels; on a wider podium; the crown a cap storey framed in
    light strips, a glass drum, a sensor ring on spokes and an antenna."""
    hw, pw = 18.0, 20.0
    outline, _ = rect(hw, hw)
    pier = piers(5.0, 2)
    storey = [("Glass", 2.4), ("Tower", 1.6)]
    levels, row = storeys(storey, TOWER_SHAFT)
    paint = lambda s, c, r, u, z: "Tower" if c != 1 else row(r)
    # Base (20 m): the podium (concrete, a glass band, a Tower edge), a tall
    # lobby storey, a Tower band, two storeys of the pattern.
    # One open shell: the podium's walls, its roof as a ring, the block's
    # walls (cut at the block's fractions all the way, so every vertex is shared).
    base = Builder()
    podium, _ = rect(pw, pw)
    same_cuts = lambda s, length: pier(s, 2 * hw)
    base.prism(podium, 0.0, 6.0, "Tower", levels=[1.0, 4.0], columns=same_cuts, top=False, bottom_mat="RoofDark",
               cell=lambda s, c, r, u, z: ["Concrete", "Glass", "Tower"][r])
    skirt(base, podium, outline, 6.0, same_cuts, "RoofDark")
    base.prism(outline, 6.0, 20.0, "Glass", levels=[11.0, 12.0, 14.4, 16.0, 18.4], columns=pier, top=False, bottom=False,
               cell=lambda s, c, r, u, z: "Tower" if c != 1 else ["GlassDark", "Tower", "Glass", "Tower", "Glass", "Tower"][r])
    # Shaft (16 m).
    shaft = Builder()
    shaft.prism(outline, 0.0, TOWER_SHAFT, "Glass", levels=levels, columns=pier, cell=paint, top=False, bottom=False)
    # Crown (34 m): the white cap storey framed in light strips, a glass
    # drum, the ring on four spokes, the mast.
    crown = Builder()
    crown.prism(outline, 0.0, 6.0, "Tower", levels=[5.4], bottom=False, top_mat="RoofDark",
                columns=lambda s, length: cuts([LIGHT, length - 2 * LIGHT, LIGHT], length),
                cell=lambda s, c, r, u, z: "LightStrip" if r == 1 or c != 1 else "Tower")
    lathe_rows(crown, [(11.0, 6.0 - SINK, "Tower"), (11.0, 7.0, "Glass"), (11.0, 13.0, "Tower"), (11.0, 14.0, None)],
               16, cap_mat="RoofDark")
    ring(crown, 14.0, 17.0, 10.4, 12.0, "Tower", 16, rim_mat="LightStrip")
    for k in range(4):
        with crown.at(Matrix.Rotation(math.pi / 2 * k + math.pi / 4, 4, "Z")):
            crown.box(10.0, -0.5, 10.8, 15.0, 0.5, 11.6, "Tower")
    mast(crown, 14.0, 20.0, 1.2)
    return base, shaft, crown, plug(outline, "Tower")


def tower_c():
    """C, 44 x 44, the big one: three wide white piers a side with glass
    fields between under white floor bands, a concrete plinth and
    double-height lobby, and a canted glass top."""
    hw = 22.0
    outline, _ = rect(hw, hw)
    pier = piers(7.0, 3)
    storey = [("Tower", 2.0), ("Glass", 6.0)]
    levels, row = storeys(storey, TOWER_SHAFT)
    paint = lambda s, c, r, u, z: "Tower" if c % 2 == 0 else row(r)
    # Base (24 m): the plinth, the lobby, the podium edge, then the pattern
    # so it ends in a full glass band under the shaft's white one.
    base = Builder()
    base.prism(outline, 0.0, 24.0, "Glass", levels=[2.0, 8.0, 10.0, 16.0, 18.0], columns=pier, top=False,
               bottom_mat="RoofDark",
               cell=lambda s, c, r, u, z: "Concrete" if r == 0 else (
                   "Tower" if c % 2 == 0 else ["Concrete", "GlassDark", "Tower", "Glass", "Tower", "Glass"][r]))
    # Shaft (16 m).
    shaft = Builder()
    shaft.prism(outline, 0.0, TOWER_SHAFT, "Glass", levels=levels, columns=pier, cell=paint, top=False, bottom=False)
    # Crown (38 m): a white cap storey with a glass band under a light strip,
    # the canted glass top rising towards the back with a light strip on its
    # high edge, a mast.
    crown = Builder()
    crown.prism(outline, 0.0, 6.0, "Tower", levels=[1.5, 4.5, 5.1], top_mat="RoofDark", bottom=False,
                cell=lambda s, c, r, u, z: ["Tower", "Glass", "LightStrip", "Tower"][r])
    canted_box(crown, 18.0, 18.0, 6.0 - SINK, 12.0, 30.0, "Tower",
               [(0.08, "Tower"), (0.82, "Glass"), (0.05, "Tower"), (0.05, "LightStrip")])
    with crown.at(Matrix.Translation((-14.0, 14.0, 0.0))):
        mast(crown, 28.0 - 0.5, 10.0, 0.8)
    return base, shaft, crown, plug(outline, "Tower")


def tower_d():
    """D, 32 x 32: a white tower with a glass curtain wall on the front only
    (two dark strips on each other face), a twin-blade crown: two white
    blades with lit sloping tops over a glass box."""
    hw = 16.0
    outline, tags = rect(hw, hw)
    columns = lambda s, length: cuts([4.0, length - 8.0, 4.0] if tags[s] == "F" else [10.0, 3.0, 6.0, 3.0, 10.0], length)
    storey = [("Glass", 6.5), ("Tower", 1.5)]      # the front, in two-storey bands
    levels, row = storeys(storey, TOWER_SHAFT)

    def paint(s, c, r, u, z):
        if tags[s] == "F":
            return "Tower" if c != 1 else row(r)
        return "GlassDark" if c % 2 == 1 else "Tower"
    # Base (20 m): a concrete plinth, the lobby (the front glazed, the strips
    # running down the other faces), a Tower band, then the front's pattern.
    base = Builder()
    base.prism(outline, 0.0, 20.0, "Tower", levels=[1.5, 8.0, 12.0, 18.5], columns=columns, top=False,
               bottom_mat="RoofDark",
               cell=lambda s, c, r, u, z: "Concrete" if r == 0 else (
                   "Tower" if r in (2, 4) else (
                       ("Tower" if c != 1 else "Glass") if tags[s] == "F" else ("GlassDark" if c % 2 == 1 else "Tower"))))
    # Shaft (16 m).
    shaft = Builder()
    shaft.prism(outline, 0.0, TOWER_SHAFT, "Tower", levels=levels, columns=columns, cell=paint, top=False, bottom=False)
    # Crown (33.5 m): a parapet under a light strip, the two blades (their
    # sloping tops lit), the glass box between them, a mast on the high end.
    crown = Builder()
    crown.prism(outline, 0.0, 3.0, "Tower", levels=[2.4], top_mat="RoofDark", bottom=False,
                cell=lambda s, c, r, u, z: "LightStrip" if r == 1 else None)
    blade = [(-hw, 3.0 - SINK), (hw, 3.0 - SINK), (hw, 26.0), (-hw, 19.0)]
    for y0, y1 in ((8.0, 11.0), (-11.0, -8.0)):
        crown.extrude(blade, y0, y1, "Tower", cell=lambda s: "LightStrip" if s == 2 else None)
    crown.box(-13.0, -8.5, 3.0 - SINK, 13.0, 8.5, 17.0, "Glass", levels=[7.0, 8.5, 13.0, 14.5], top_mat="RoofDark",
              cell=lambda s, c, r, u, z: "Tower" if r % 2 == 1 else None)
    with crown.at(Matrix.Translation((13.0, 9.5, 0.0))):
        mast(crown, 25.0, 8.0, 0.8)
    return base, shaft, crown, plug(outline, "Tower")


# --- Drum towers: 90-190 m, round glass -------------------------------------------------------
def round_a():
    """A, 30 across: white storeys with a glass strip each, a ring podium, a
    domed crown with a ring deck and a mast."""
    r, seg = 15.0, 16
    band = [("Tower", 5.2), ("Glass", 2.8)]       # per two storeys: wide bands read from afar
    # Base (20 m): the ring podium, then the drum: a tall dark lobby, the bands.
    # One open shell: podium, its roof ring, the drum; open at the top.
    base = Builder()
    lathe_rows(base, [(18.0, 0.0, "Concrete"), (18.0, 1.0, "Glass"), (18.0, 4.0, "Tower"), (18.0, 6.0, "RoofDark"),
                      (r, 6.0, "GlassDark"), (r, 12.0, "Tower"), (r, 17.2, "Glass"), (r, 20.0, None)], seg,
               cap_mat="RoofDark", top=False)
    # Shaft (16 m): walls only.
    shaft = Builder()
    rows, z = [], 0.0
    for _ in range(2):
        for m, h in band:
            rows.append((r, z, m))
            z += h
    rows.append((r, z, None))
    lathe_rows(shaft, rows, seg, bottom=False, top=False)
    # Crown (14.5 m + mast): a light strip at the top of the drum, the ring
    # deck, a dark glass storey, the dome.
    crown = Builder()
    lathe_rows(crown, [(r, 0.0, "Tower"), (r, 2.4, "LightStrip"), (r, 3.0, "Tower"), (17.5, 3.0, "Tower"),
                       (17.5, 4.5, "RoofDark"), (14.0, 4.5, "GlassDark"), (14.0, 7.5, "Tower"), (13.5, 8.0, "Tower"),
                       (12.5, 9.5, "Tower"), (10.5, 11.5, "Tower"), (7.5, 13.0, "Tower"), (4.0, 14.0, "Tower"),
                       (0.0, 14.5, None)], seg, bottom=False)
    mast(crown, 14.3, 14.0, 1.0)
    return base, shaft, crown, round_plug(r, seg)


def round_b():
    """B, 42 across, the glass-forward one: white fins round the glass, a
    dark band every four storeys, a ring podium, a saucer crown with a deck
    and a mast."""
    r, seg = 21.0, 20
    fin = lambda k: "Tower" if k % 2 == 0 else "Glass"
    # Base (20 m): the ring podium, a dark lobby, a Tower band, then the fins.
    # One open shell: podium, its roof ring, the drum; open at the top.
    base = Builder()
    lathe_rows(base, [(23.0, 0.0, "Concrete"), (23.0, 1.0, "Glass"), (23.0, 4.0, "Tower"), (23.0, 5.0, "RoofDark"),
                      (r, 5.0, "GlassDark"), (r, 11.0, "Tower"), (r, 12.0, fin), (r, 20.0, None)], seg,
               cap_mat="RoofDark", top=False)
    # Shaft (16 m): the dark band, then the fins; walls only.
    shaft = Builder()
    lathe_rows(shaft, [(r, 0.0, "GlassDark"), (r, 1.2, fin), (r, 16.0, None)], seg, bottom=False, top=False)
    # Crown (17 m + mast): the light strip, the saucer flaring out (no wider
    # than the podium) in dark glass with a lit rim, a deck, a glass drum and
    # a shallow dome.
    crown = Builder()
    lathe_rows(crown, [(r, 0.0, "Tower"), (r, 2.4, "LightStrip"), (r, 3.0, "Tower"), (23.0, 5.0, "GlassDark"),
                       (23.0, 7.0, "LightStrip"), (23.0, 7.6, "Tower"), (20.0, 9.5, "RoofDark"), (15.0, 10.0, "GlassDark"),
                       (15.0, 13.0, "Tower"), (13.0, 14.5, "Tower"), (7.5, 16.0, "Tower"), (0.0, 17.0, None)], seg,
               bottom=False)
    mast(crown, 16.8, 15.0, 1.2)
    return base, shaft, crown, round_plug(r, seg)


# --- The spire: 340 m ------------------------------------------------------------------------
SPIRE_SEG = 24
SPIRE_TIERS = [(24.0, 100.0, 23.0, 20.0), (106.0, 176.0, 20.0, 17.0),      # (z bottom, z top, r bottom, r top)
               (182.0, 242.0, 17.0, 14.0), (248.0, 288.0, 14.0, 10.0)]
SPIRE_RIBS = 3                     # white ribs up the tiers, the first facing the front
RIB_WIDTH = 5.0
RIB_SINK = 1.5                     # a rib's inner edge inside the body
RIB_FOOT = 9.0                     # the ribs stand on the plinth's top step...
RIB_PROUD = (27.5, 15.5)           # ...their outer edge a line from this radius there to this at the last tier's top


def spire():
    """The central spire: a stepped plinth with a glass lobby ring, four
    tapering tiers of mullioned glass (a white mullion every fourth segment)
    in white collars with light strips, three white ribs, an observation
    ring and the antenna."""
    b = Builder()
    mullions = lambda k: ("Tower", "Glass", "GlassDark", "Glass")[k % 4]
    # The plinth: two square steps, the upper (wide enough for the ribs'
    # feet) with a dark glass band.
    b.box(-30.0, -30.0, 0.0, 30.0, 30.0, 3.0, "Concrete")
    b.box(-28.0, -28.0, 3.0 - SINK, 28.0, 28.0, RIB_FOOT, "Tower", levels=[4.5, 7.5],
          cell=lambda s, c, r, u, z: "GlassDark" if r == 1 else None, top_mat="RoofDark")
    # The lobby ring, then collar / tier / collar... up to the observation ring and antenna base.
    rows = [(23.5, RIB_FOOT - SINK, "Tower"), (23.5, 10.0, mullions), (23.5, 19.0, "Tower")]
    rows += [(25.5, 19.0, "Tower"), (25.5, 24.0 - LIGHT, "LightStrip"), (25.5, 24.0, "Tower")]
    for i, (z0, z1, r0, r1) in enumerate(SPIRE_TIERS):
        rows += [(r0, z0, mullions), (r1, z1, "Tower")]
        if i + 1 < len(SPIRE_TIERS):
            rc, zc = SPIRE_TIERS[i + 1][2] + 2.0, SPIRE_TIERS[i + 1][0]
            rows += [(rc, z1, "Tower"), (rc, zc - LIGHT, "LightStrip"), (rc, zc, "Tower")]
    z_top = SPIRE_TIERS[-1][1]
    rows += [(17.0, z_top + 2.0, "GlassDark"), (17.0, z_top + 5.5, "LightStrip"), (17.0, z_top + 6.2, "Tower"),
             (14.0, z_top + 8.5, "Tower"), (7.0, z_top + 10.0, "Tower"), (5.0, z_top + 12.0, "Tower"),
             (3.0, z_top + 16.0, None)]
    lathe_rows(b, rows, SPIRE_SEG, cap_mat="RoofDark")
    mast(b, z_top + 16.0, 340.0 - (z_top + 16.0), 2.2, 12)
    # The ribs: the inner edge follows the lobby ring and the tiers inside the
    # body (each tier starts at the radius the one below ends), the outer
    # edge is a straight line from the plinth to the last tier's top, kept a
    # little proud of each collar; the top ends inside the observation ring.
    proud = lambda z: RIB_PROUD[0] + (RIB_PROUD[1] - RIB_PROUD[0]) * (z - RIB_FOOT) / (z_top - RIB_FOOT)
    stations = [(23.5 - RIB_SINK, proud(RIB_FOOT), RIB_FOOT - SINK)]
    for i, (z0, z1, r0, r1) in enumerate(SPIRE_TIERS):
        if i == 0:
            stations.append((r0 - RIB_SINK, proud(z0), z0))
        clear = SPIRE_TIERS[i + 1][2] + 2.0 + 0.8 if i + 1 < len(SPIRE_TIERS) else 0.0
        stations.append((r1 - RIB_SINK, max(proud(z1), clear), z1))
        if i + 1 < len(SPIRE_TIERS):
            stations.append((r1 - RIB_SINK, max(proud(SPIRE_TIERS[i + 1][0]), clear), SPIRE_TIERS[i + 1][0]))
    stations.append((SPIRE_TIERS[-1][3] - RIB_SINK, RIB_PROUD[1], z_top + 2.5))
    for k in range(SPIRE_RIBS):
        rib(b, stations, -math.pi / 2 + 2 * math.pi * k / SPIRE_RIBS, RIB_WIDTH / 2, "Tower")
    return b


# --- Assembled previews ------------------------------------------------------------------------
def bounds(col):
    """A part's bounds about its origin, without its joint plug (as settlement.measure())."""
    lo = Vector((math.inf,) * 3)
    hi = Vector((-math.inf,) * 3)
    for o in col.all_objects:
        if o.type == "MESH" and not o.name.endswith("_Plug"):
            for v in o.data.vertices:
                p = o.matrix_world @ v.co - col.instance_offset
                lo = Vector(map(min, lo, p))
                hi = Vector(map(max, hi, p))
    return lo, hi


def render(scene, lo, hi, path, direction, size=(640, 640), lens=50):
    """Renders `scene` as kit_tools.preview() does, looking at the box lo..hi from `direction`."""
    centre = (lo + hi) / 2
    radius = (hi - lo).length / 2
    cam_data = bpy.data.cameras.new("StackCam")
    cam_data.lens = lens
    cam = bpy.data.objects.new("StackCam", cam_data)
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
    shading.show_object_outline = True
    shading.show_cavity = False
    scene.render.resolution_x, scene.render.resolution_y = size
    world = bpy.data.worlds.new("StackWorld")
    world.color = (0.55, 0.65, 0.8)
    scene.world = world
    d = Vector(direction).normalized()
    distance = radius / math.tan(math.radians(18)) * 1.05
    cam.location = centre + d * distance
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    cam_data.clip_end = distance * 4
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True, scene=scene.name)
    bpy.data.objects.remove(cam)
    bpy.data.cameras.remove(cam_data)
    bpy.data.worlds.remove(world)


def stand(scene, name, x, shafts):
    """Stands stack `name` in `scene` at x with `shafts` shafts (as
    settlement.py would, by measured heights); returns its bounds."""
    lo = Vector((math.inf,) * 3)
    hi = Vector((-math.inf,) * 3)
    z = 0.0
    for part, n in (("Base", 1), ("Shaft", shafts), ("Crown", 1)):
        col = bpy.data.collections[name + "_" + part]
        plo, phi = bounds(col)
        for _ in range(n):
            inst = bpy.data.objects.new(col.name, None)
            inst.instance_type = "COLLECTION"
            inst.instance_collection = col
            inst.location = (x, 0.0, z)
            scene.collection.objects.link(inst)
            lo = Vector(map(min, lo, plo + Vector((x, 0.0, z))))
            hi = Vector(map(max, hi, phi + Vector((x, 0.0, z))))
            z += phi.z - plo.z
    return lo, hi


def stack_previews(stacks, out):
    """Renders each stack assembled (front three-quarter, and low from the
    street) and all of them with the spire as a skyline."""
    os.makedirs(out, exist_ok=True)
    for name in stacks:
        scene = bpy.data.scenes.new("Stack")
        lo, hi = stand(scene, name, 0.0, STACK_SHAFTS)
        render(scene, lo, hi, os.path.join(out, name + "_stack.png"), (0.75, -1.0, 0.45), (480, 960))
        render(scene, lo, hi, os.path.join(out, name + "_street.png"), (0.5, -1.0, 0.08), (480, 960))
        bpy.data.scenes.remove(scene)
    scene = bpy.data.scenes.new("Skyline")
    lo = Vector((math.inf,) * 3)
    hi = Vector((-math.inf,) * 3)
    x, street = 0.0, 25.0
    for name in stacks:
        width = max(bounds(bpy.data.collections[name + "_" + p])[1].x for p in ("Base", "Shaft", "Crown"))
        slo, shi = stand(scene, name, x + width, 3 if "Office" in name else 5)
        lo = Vector(map(min, lo, slo))
        hi = Vector(map(max, hi, shi))
        x = shi.x + street
    col = bpy.data.collections["Kit_City_Spire"]
    slo, shi = bounds(col)
    inst = bpy.data.objects.new(col.name, None)
    inst.instance_type = "COLLECTION"
    inst.instance_collection = col
    inst.location = (x - slo.x, 0.0, 0.0)
    scene.collection.objects.link(inst)
    lo = Vector(map(min, lo, slo + inst.location))
    hi = Vector(map(max, hi, shi + inst.location))
    render(scene, lo, hi, os.path.join(out, "skyline_front.png"), (0.15, -1.0, 0.3), (1600, 800), lens=40)
    render(scene, lo, hi, os.path.join(out, "skyline_low.png"), (0.6, -1.0, 0.08), (1600, 800), lens=40)
    bpy.data.scenes.remove(scene)
    print("stack previews in " + out)


# --- Build -------------------------------------------------------------------------------------
STACKS = {"Kit_City_Office_A": office_a, "Kit_City_Office_B": office_b, "Kit_City_Office_C": office_c,
          "Kit_City_Office_D": office_d, "Kit_City_Tower_A": tower_a, "Kit_City_Tower_B": tower_b,
          "Kit_City_Tower_C": tower_c, "Kit_City_Tower_D": tower_d, "Kit_City_RoundTower_A": round_a,
          "Kit_City_RoundTower_B": round_b}

if __name__ == "__main__":
    kt.begin("kit_city_high", 2)
    for name, build in STACKS.items():
        base, shaft, crown, plug_of = build()
        kt.piece(name + "_Base", [("", base)])
        kt.piece(name + "_Shaft", [("", shaft), ("Plug", plug_of())])
        kt.piece(name + "_Crown", [("", crown), ("Plug", plug_of())])
    kt.piece("Kit_City_Spire", [("", spire())])
    kt.finish()
    if os.environ.get("KIT_STACK_PREVIEW"):
        stack_previews(list(STACKS), os.environ["KIT_STACK_PREVIEW"])
