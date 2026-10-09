"""The military base's kit pieces (models/corneria2/ASSETS.md, "The military
base"): the Cornerian Army airfield's hangars, control tower, headquarters,
barracks, motor-pool sheds, radar domes and bunkers. gen_base.py places every
one at its own size (no variants, no stretching), so each keeps the footprint
the brief gives, with the hangar's doors on the -Y front, towards the apron.

    KIT_OUT=<copy.blend> KIT_PREVIEW=<dir> blender --background --python kit_base.py
    KIT_BASE_PREVIEW=<dir>  also renders the pieces laid out as gen_base.py
                            lays them out (the hangar row, the tower, the
                            compound) from the air at ~200 m and ~60 m

One function per piece, each returning [(suffix, Builder)] for
kit_tools.piece(). Every piece stands on Z = 0 with its origin at the centre
of its footprint.

Shells: a roof, a mast or an annex is its own closed shell sunk SINK into the
part it stands on, and a roof's ends stand PROUD of the wall faces below, so
no two faces of different shells share a plane (coplanar faces flicker) and
no two shells share an edge. Doors, windows, stripes, number panels and the
helipad's marks are painted: cells of the surface's own faces in another
material, so they draw no ink line. The base's look: olive Military walls
with MilitaryDark roofs and doors, Concrete for the tower and HQ, Steel for
the hangar vaults and the radome's drum, TaxiYellow / HazardBlack door
frames and lintels, Orange bands as markers, and a few LightStrip lines
(hangar ridges, floodlights, the tower's and HQ's roof edges) for the
sci-fi look.
"""

import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit_tools as kt  # noqa: E402
from kit_tools import Builder  # noqa: E402

SINK = 0.1       # how far a part sinks into the one it stands on
PROUD = 0.02     # how far a roof's ends stand out from the wall faces under it
LIGHT = 0.6      # a painted LightStrip edge band is this wide
TIP = 1.6        # the WarningLight at a mast's tip is this tall

FRONT, RIGHT, BACK, LEFT = 0, 1, 2, 3   # a box's sides, as prism() numbers them


# --- Helpers (block, cells, gable_roof, arc: as kit_city_low.py) -------------------------
def block(b, x0, y0, x1, y1, z0, storeys, bays=None, paint=None, top_mat=None, bottom=True):
    """A walled box from z0: `storeys` [(height, material)] stack up its sides
    and paint them all round. `bays` {side: [widths]} cuts a side into bays
    (metres from its start, scaled to fit), and paint(side, bay, row) -> a
    material (None: the storey's) paints single cells: windows, doors,
    stripes. The top is `top_mat` or the top storey's. Returns the top z."""
    levels, z = [], z0
    for h, _ in storeys[:-1]:
        z += h
        levels.append(z)
    z1 = z0 + sum(h for h, _ in storeys)
    bays = bays or {}

    def columns(side, _length):
        widths = bays.get(side)
        if not widths:
            return []
        total, acc, cuts = sum(widths), 0.0, []
        for w in widths[:-1]:
            acc += w
            cuts.append(acc / total)
        return cuts

    def cell(side, col, row, _u, _z):
        return (paint(side, col, row) if paint else None) or storeys[row][1]

    b.box(x0, y0, z0, x1, y1, z1, storeys[-1][1], levels=levels, columns=columns, cell=cell,
          top_mat=top_mat or storeys[-1][1], bottom=bottom)
    return z1


def cells(painted):
    """A paint function from {(side, bay, row): material}."""
    return lambda side, col, row: painted.get((side, col, row))


def gable_roof(b, hw, hl, z_wall, pitch, overhang, thick, wall_mat, roof_mat):
    """A gabled roof over walls spanning x +-hw, y +-hl up to z_wall; the
    ridge runs along y. The gable ends are a wedge in the wall's colour (sunk
    into the walls, a hair proud of their faces); the roof slab overhangs
    them all round, its underside just under the wedge's slopes so the two
    never share a plane. Returns the ridge's top z."""
    zr = z_wall + hw * pitch - 0.06      # the slab's underside at the ridge: the wall tops sit inside it
    xe = hw + PROUD
    b.extrude([(-xe, z_wall - SINK), (xe, z_wall - SINK), (xe, zr + 0.05 - xe * pitch),
               (0.0, zr + 0.05), (-xe, zr + 0.05 - xe * pitch)], -hl - PROUD, hl + PROUD, wall_mat)
    e = hw + overhang
    zu = zr - e * pitch
    b.extrude([(-e, zu), (0.0, zr), (e, zu), (e, zu + thick), (0.0, zr + thick), (-e, zu + thick)],
              -hl - overhang, hl + overhang, roof_mat)
    return zr + thick


def long_roof(b, hw, hl, z_wall, pitch, overhang, thick, wall_mat, roof_mat):
    """gable_roof() turned a quarter: the ridge runs along x over walls
    spanning x +-hw, y +-hl (the base's long low buildings)."""
    with b.at(Matrix.Rotation(math.pi / 2, 4, "Z")):
        return gable_roof(b, hl, hw, z_wall, pitch, overhang, thick, wall_mat, roof_mat)


def circle_arc(hw, rise, z0, segments, apex=0.0):
    """Points of a circular arc from (-hw, z0) over (0, z0 + rise) to (hw, z0),
    left to right, turning the same angle at every step (so none creases).
    `apex` > 0 splits the top point into a flat strip that wide (a ridge
    light), kept at the arc's height."""
    radius = (hw * hw + rise * rise) / (2.0 * rise)
    zc = z0 + rise - radius
    half = math.asin(hw / radius)
    pts = []
    for k in range(segments + 1):
        a = -half + 2.0 * half * k / segments
        if apex > 0.0 and k == segments // 2:
            pts += [(-apex / 2, z0 + rise), (apex / 2, z0 + rise)]
        else:
            pts.append((radius * math.sin(a), zc + radius * math.cos(a)))
    return pts


def vault(b, profile, y0, y1, mat, strips=(), cell=None, smooth=True, cap_mat=None):
    """extrude() with its sides also cut along y at the fractions `strips`:
    `profile` [(x, z)] pushed from y0 to y1; cell(side, strip) -> material.
    Bands across a vault (a stripe over the doors) and along it (a ridge
    light) are cells of the same shell."""
    ys = [y0] + [y0 + (y1 - y0) * f for f in sorted(strips)] + [y1]
    n = len(profile)
    for s in range(n):
        (ax, az), (bx, bz) = profile[s], profile[(s + 1) % n]
        for j in range(len(ys) - 1):
            m = (cell(s, j) if cell else None) or mat
            b.face([(ax, ys[j], az), (ax, ys[j + 1], az), (bx, ys[j + 1], bz), (bx, ys[j], bz)], m, smooth)
    b.face([(x, y0, z) for x, z in profile], cap_mat or mat)
    b.face([(x, y1, z) for x, z in profile[::-1]], cap_mat or mat)


def cut(outline, cuts):
    """`outline` [(x, y)] with each side s cut at the fractions cuts.get(s):
    (points, tags): one (side, column) tag per edge from point i to i + 1."""
    pts, tags = [], []
    n = len(outline)
    for s in range(n):
        a, c = Vector(outline[s]), Vector(outline[(s + 1) % n])
        for k, u in enumerate([0.0] + sorted(cuts.get(s, []))):
            pts.append(tuple(a.lerp(c, u)))
            tags.append((s, k))
    return pts, tags


def loft(b, pts, tags, rows, cell=None, smooth=False, bottom=True, top=True, bottom_mat=None, top_mat=None):
    """A shape whose horizontal sections are `pts` (from cut()) scaled about
    the origin: `rows` [(scale, z, material of the band above)]; sloping
    walls, a canted cab, a bunker. cell(side, column, row) -> material
    paints single cells of the sides."""
    rings = [[(x * s, y * s, z) for x, y in pts] for s, z, _ in rows]
    n = len(pts)
    for r in range(len(rings) - 1):
        for i in range(n):
            i1 = (i + 1) % n
            side, col = tags[i]
            m = (cell(side, col, r) if cell else None) or rows[r][2]
            b.face([rings[r][i], rings[r][i1], rings[r + 1][i1], rings[r + 1][i]], m, smooth)
    if bottom:
        b.face(rings[0][::-1], bottom_mat or rows[0][2])
    if top:
        b.face(rings[-1], top_mat or rows[-2][2])


def mast(b, x, y, z0, height, r=0.6, segments=8, mat="Steel"):
    """A round mast standing on z0 (sunk SINK) with a WarningLight tip."""
    with b.at(Matrix.Translation((x, y, 0.0))):
        b.lathe([(r, z0 - SINK), (r, z0 + height - TIP), (r, z0 + height - 0.3), (0.0, z0 + height)], mat,
                segments=segments, cell=lambda k, row: "WarningLight" if row > 0 else None)


def dish(b, x, y, z, tilt, r=2.4, depth=0.7, segments=8):
    """A dish antenna on a Steel post: the dish is a shallow closed bowl
    about its back pole at (x, y, z), tilted `tilt` radians from straight up
    towards the front; the post stands on z - 2.4 and holds the pole."""
    b.box(x - 0.45, y - 0.45, z - 2.4, x + 0.45, y + 0.45, z + 0.3, "Steel")
    with b.at(Matrix.Translation((x, y, z)) @ Matrix.Rotation(tilt, 4, "X")):
        b.lathe([(0.0, 0.0), (r, depth), (0.0, depth * 0.55)], "Steel", segments=segments)


def hazard(height, band=1.4, first="TaxiYellow"):
    """Storeys of alternating TaxiYellow / HazardBlack bands up to `height`."""
    mats = [first, "HazardBlack" if first == "TaxiYellow" else "TaxiYellow"]
    n = max(1, round(height / band))
    return [(height / n, mats[i % 2]) for i in range(n)]


def helipad(b, cx, cy, r, z0, z1, mat="RoofDark", mark="Marking", segments=16):
    """A round landing pad: a drum with a painted ring and an H on top. The
    disc inside the ring holds a square (its corners on the ring's polygon
    at 45 degrees, so `segments` must be a multiple of 8) painted as a 7 x 7
    grid for the H; four fans fill between the square and the ring."""
    def p(rr, z, k):
        a = 2 * math.pi * k / segments
        return (cx + rr * math.cos(a), cy + rr * math.sin(a), z)
    ri = r * 0.8
    for k in range(segments):
        k1 = (k + 1) % segments
        b.face([p(r, z0, k), p(r, z0, k1), p(r, z1, k1), p(r, z1, k)], mat, True)
        b.face([p(r, z1, k), p(r, z1, k1), p(ri, z1, k1), p(ri, z1, k)], mark)
    b.face([p(r, z0, k) for k in range(segments)][::-1], mat)
    q, n = segments // 8, 7
    for c in range(4):                      # the fans: the arc from one corner to the next, back along the
        k0 = q + 2 * q * c                  # chord through the grid's edge points (no T-junctions)
        a, d = Vector(p(ri, z1, k0)), Vector(p(ri, z1, (k0 + 2 * q) % segments))
        b.face([p(ri, z1, (k0 + i) % segments) for i in range(2 * q + 1)]
               + [tuple(d.lerp(a, i / n)) for i in range(1, n)], mat)
    h = ri * math.cos(math.pi / 4)

    def letter(i, j):
        if 1 <= j <= 5 and (i in (1, 5) or (j == 3 and 2 <= i <= 4)):
            return mark
        return None
    b.grid((cx - h, cy - h, z1), (2 * h, 0.0, 0.0), (0.0, 2 * h, 0.0), n, n, letter, mat)


# --- Kit_Base_Hangar: 60 x 22 x 50, 1,200 tris ---------------------------------------------
HANGAR_W, HANGAR_H, HANGAR_D = 60.0, 22.0, 50.0
HANGAR_WALL = 13.0           # the walls' top; the vault rises from there to HANGAR_H
DOOR_LEAVES = 8              # columns per door leaf: the lintel's hazard blocks


def hangar():
    """A fighter hangar: olive walls under a smooth Steel barrel vault with a
    glowing ridge line and a yellow band over the door end. The front is two
    huge painted MilitaryDark door leaves in a TaxiYellow frame under a
    yellow-and-black lintel, with a white number panel (a black "1") above
    the seam; the sides carry dark buttress piers and a clerestory band, the
    back a small door. Two floodlight masts stand at the front corners."""
    b = Builder()
    hw, hd = HANGAR_W / 2, HANGAR_D / 2
    rows = [(9.6, "Military"), (1.2, "Military"), (HANGAR_WALL - 10.8, "Military")]  # doors, lintel, upper band
    leaf = 25.0 / DOOR_LEAVES
    front = [3.5, 1.0] + [leaf] * DOOR_LEAVES + [1.0] + [leaf] * DOOR_LEAVES + [1.0, 3.5]
    seam, last = DOOR_LEAVES + 2, len(front) - 1
    side = [2.0, 10.0, 2.0, 10.0, 2.0, 10.0, 2.0, 10.0, 2.0]
    back = [22.0, 1.0, 14.0, 1.0, 22.0]

    def paint(s, c, r):
        if s == FRONT:
            if c in (0, last):
                return None
            if c in (1, last - 1):                                   # the frame
                return "TaxiYellow" if r < 2 else None
            if c == seam:                                            # the leaves' seam, the panel's digit
                return ["TaxiYellow", "TaxiYellow", "HazardBlack"][r]
            if r == 0:
                return "MilitaryDark"
            if r == 1:
                return "TaxiYellow" if c % 2 == 0 else "HazardBlack"
            return "Marking" if c in (seam - 1, seam + 1) else None
        if r == 2:
            return "GlassDark"                                       # the clerestory, round the other sides
        if s == BACK:
            return {1: "TaxiYellow", 2: "MilitaryDark", 3: "TaxiYellow"}.get(c) if r == 0 else None
        return "MilitaryDark" if c % 2 == 0 else None                # the piers
    top = block(b, -hw, -hd, hw, hd, 0.0, rows, bays={FRONT: front, RIGHT: side, LEFT: side, BACK: back},
                paint=paint)
    # The vault: a circular arc (the same turn at every step, so only its
    # eaves crease) with a flat ridge strip, from the wall tops to HANGAR_H.
    xe, segs = hw + PROUD, 10
    arc = circle_arc(xe, HANGAR_H - top, top, segs, apex=1.6)
    profile = [(-xe, top - SINK), (xe, top - SINK)] + arc[::-1]
    ridge = 2 + segs // 2                 # the side index of the ridge strip in the profile
    band = 2.5 / (HANGAR_D + 2 * PROUD)   # the yellow band over the door end
    panel = (0.3, 0.46)                   # a white roof panel either side of the ridge, read from the air

    def roof(s, strip):
        if s < 2 or s == len(profile) - 1:
            return "Military"                                        # the sunk bottom and the eave slivers
        if s == ridge:
            return "LightStrip"
        if strip == 0:
            return "TaxiYellow"
        return "Marking" if strip == 2 and abs(s - ridge) == 1 else None
    vault(b, profile, -hd - PROUD, hd + PROUD, "Steel", strips=[band, *panel], cell=roof, cap_mat="Military")
    # The floodlight masts: a Steel pole with a lit head, at each front corner.
    for x in (-hw + 1.5, hw - 1.5):
        y = -hd + 1.5
        with b.at(Matrix.Translation((x, y, 0.0))):
            b.lathe([(0.6, 0.0), (0.6, 21.0)], "Steel", segments=8)
            b.box(-1.3, -0.8, 20.7, 1.3, 0.8, 22.1, "Steel",
                  cell=lambda s, c, r, u, z: "LightStrip" if s == FRONT else None, bottom_mat="LightStrip")
    return [("", b)]


# --- Kit_Base_ControlTower: 14 x 40 x 14, 1,500 tris -----------------------------------------
def control_tower():
    """A Concrete shaft on a one-storey annex, an orange band near its top
    and a dark stair slit up the front; a flared collar carries a gallery
    deck and the cab: dark glass panes between concrete mullions, canted
    outward, under a roof slab edged with a light strip, a mast with a
    warning light and a dish on the annex."""
    b = Builder()
    hw = 7.0
    # The annex: a concrete block with a window band and an orange door.
    top = block(b, -hw, -hw, hw, hw, 0.0, [(3.0, "Concrete"), (1.5, "GlassDark")],
                bays={FRONT: [4.2, 2.4, 7.4]}, paint=cells({(FRONT, 1, 0): "Orange"}), top_mat="RoofDark")
    dish(b, -4.0, 3.0, top + 2.4, math.radians(50))
    # The shaft: 7 x 7, the slit on the front, the orange band.
    s = 3.5
    z_shaft = block(b, -s, -s, s, s, top - SINK, [(18.0, "Concrete"), (1.2, "Orange"), (2.4, "Concrete")],
                    bays={FRONT: [2.4, 2.2, 2.4]},
                    paint=lambda side, c, r: "GlassDark" if (side, c) == (FRONT, 1) and r != 1 else None)
    # The collar flaring out under the deck slab (its bottom ring inside the
    # shaft, a little smaller so no side shares the shaft's plane).
    square = [(-s, -s), (s, -s), (s, s), (-s, s)]
    pts, tags = cut(square, {})
    loft(b, pts, tags, [(6.8 / 7.0, z_shaft - 0.3, "Concrete"), (9.6 / 7.0, z_shaft + 2.0, "Concrete")])
    z_deck = z_shaft + 2.0
    b.box(-5.5, -5.5, z_deck - SINK, 5.5, 5.5, z_deck + 1.1, "Concrete", top_mat="RoofDark")
    # The cab: a sill ring inside the deck slab, the canted glass storey
    # with a mullion at each corner and two between, a concrete top band.
    cab_w = 13.2
    pane = (cab_w - 4.0) / 3.0
    widths = [1.0, pane, 1.0, pane, 1.0, pane, 1.0]
    fr = [sum(widths[:i + 1]) / cab_w for i in range(len(widths) - 1)]
    outline = [(-cab_w / 2, -cab_w / 2), (cab_w / 2, -cab_w / 2), (cab_w / 2, cab_w / 2), (-cab_w / 2, cab_w / 2)]
    pts, tags = cut(outline, {FRONT: fr, RIGHT: fr, BACK: fr, LEFT: fr})
    z_cab = z_deck + 1.0
    loft(b, pts, tags, [(9.0 / cab_w, z_cab, "Concrete"), (9.4 / cab_w, z_cab + 0.8, "GlassDark"),
                        (1.0, z_cab + 5.5, "Concrete"), (1.0, z_cab + 6.5, "Concrete")],
         cell=lambda side, c, r: "Concrete" if r == 1 and c % 2 == 0 else None, top_mat="RoofDark")
    z_roof = z_cab + 6.5
    # The roof slab with its light strip edge, the mast and a short aerial.
    block(b, -hw, -hw, hw, hw, z_roof - SINK, [(0.9, "RoofDark"), (LIGHT, "LightStrip")], top_mat="RoofDark")
    z_top = z_roof - SINK + 0.9 + LIGHT
    mast(b, 5.3, 5.3, z_top, 40.0 - z_top, r=0.5)
    b.box(-5.8, -5.8, z_top - SINK, -4.6, -4.6, z_top + 2.0, "Steel")
    return [("", b)]


# --- Kit_Base_HQ: 70 x 24 x 40, 1,500 tris ----------------------------------------------------
def hq():
    """Command headquarters: a long concrete block with three dark glass
    bands all round and a glass lobby between orange piers on the front,
    under an entrance canopy (a yellow-edged slab on hazard-striped columns);
    a set-back upper storey with a light-strip edge, a helipad on the lower
    roof beside it, a mast and a dish."""
    b = Builder()
    hw, y0, y1 = 35.0, -17.0, 20.0          # the body; the canopy fills the depth to -20
    storeys = [(4.0, "Concrete"), (2.6, "GlassDark"), (1.6, "Concrete"), (2.6, "GlassDark"), (1.6, "Concrete"),
               (2.6, "GlassDark"), (2.0, "Concrete")]
    top = block(b, -hw, y0, hw, y1, 0.0, storeys, bays={FRONT: [24.0, 1.5, 19.0, 1.5, 24.0]},
                paint=cells({(FRONT, 1, 0): "Orange", (FRONT, 2, 0): "GlassDark", (FRONT, 3, 0): "Orange"}),
                top_mat="RoofDark")
    # The canopy and its two columns.
    b.box(-9.0, -20.0, 4.0, 9.0, y0 + SINK, 5.2, "Concrete",
          cell=lambda s, c, r, u, z: "TaxiYellow" if s == FRONT else None, bottom_mat="RoofDark")
    for x in (-6.5, 6.5):
        block(b, x - 0.6, -19.4, x + 0.6, -18.2, 0.0, hazard(4.1), top_mat="TaxiYellow")
    # The upper storey, set back, with its lit edge; the helipad beside it.
    up = block(b, -33.0, -15.0, 5.0, 17.0, top - SINK,
               [(1.0, "Concrete"), (2.0, "GlassDark"), (0.5, "Concrete"), (LIGHT, "LightStrip")], top_mat="RoofDark")
    helipad(b, 21.0, 2.0, 11.0, top - SINK, top + 0.9)
    mast(b, -29.0, 13.0, up, 24.5 - up, r=0.7)
    dish(b, -20.0, 12.0, up + 1.2, math.radians(40))
    for x in (-10.0, -4.0):                  # roof plant
        b.box(x, -8.0, up - SINK, x + 4.0, 4.0, up + 1.6, "RoofDark")
    return [("", b)]


# --- Kit_Base_Barracks: 40 x 10 x 14, 300 tris -------------------------------------------------
def barracks():
    """A long low olive block under a low-pitched MilitaryDark roof: five
    wide painted windows on each long side (the middle one on the front a
    dark double door), one on each end, a vent stack on the roof."""
    b = Builder()
    hw, hd, overhang = 19.6, 6.6, 0.4
    long = [2.7, 4.6] * 5 + [2.7]
    end = [4.5, 4.2, 4.5]

    def paint(s, c, r):
        if s in (FRONT, BACK) and c % 2 == 1:
            if s == FRONT and c == 5 and r < 2:
                return "MilitaryDark"
            return "GlassDark" if r == 1 else None
        return "GlassDark" if s in (RIGHT, LEFT) and c == 1 and r == 1 else None
    z_wall = block(b, -hw, -hd, hw, hd, 0.0, [(1.2, "Military"), (1.8, "Military"), (3.5, "Military")],
                   bays={FRONT: long, BACK: long, RIGHT: end, LEFT: end}, paint=paint)
    ridge = long_roof(b, hw, hd, z_wall, 0.47, overhang, 0.35, "Military", "MilitaryDark")
    b.box(12.0, 1.5, ridge - 1.8, 13.5, 3.0, ridge + 0.5, "Steel")
    return [("", b)]


# --- Kit_Base_Shed: 30 x 8 x 20, 200 tris ----------------------------------------------------
def shed():
    """A motor-pool shed: olive walls, a big dark vehicle door in a yellow
    frame under a black lintel on the front, a tall window beside it and a
    row along the back, a shallow MilitaryDark roof with a vent."""
    b = Builder()
    hw, hd, overhang = 14.8, 9.8, 0.2
    front = [5.0, 1.2, 14.0, 1.2, 4.0, 2.4, 1.8]
    back = [4.8, 4.0, 2.0, 4.0, 2.0, 4.0, 2.0, 4.0, 2.8]

    def paint(s, c, r):
        if s == FRONT:
            if c == 2:
                return "MilitaryDark" if r < 2 else "HazardBlack"
            if c in (1, 3):
                return "TaxiYellow"
            return "GlassDark" if (c, r) == (5, 1) else None
        return "GlassDark" if s == BACK and c % 2 == 1 and r == 1 else None
    z_wall = block(b, -hw, -hd, hw, hd, 0.0, [(1.0, "Military"), (3.8, "Military"), (1.2, "Military")],
                   bays={FRONT: front, BACK: back}, paint=paint)
    ridge = long_roof(b, hw, hd, z_wall, 0.18, overhang, 0.35, "Military", "MilitaryDark")
    b.box(-10.0, -1.0, ridge - 0.8, -7.0, 1.0, ridge + 0.3, "Steel")
    return [("", b)]


# --- Kit_Base_Radar: 18 x 22 x 18, 1,000 tris ----------------------------------------------
def radar():
    """A radome: a white smooth sphere on a Steel drum (a dark window band,
    an orange band) over a square concrete plinth with a yellow top stripe
    and a dark door; a red light at the dome's pole, a lit equipment box."""
    b = Builder()
    hw, r_drum, r_dome, zc = 9.0, 6.5, 8.5, 13.5
    top = block(b, -hw, -hw, hw, hw, 0.0, [(2.4, "Concrete"), (1.0, "TaxiYellow")],
                bays={FRONT: [7.0, 2.4, 8.6]}, paint=cells({(FRONT, 1, 0): "MilitaryDark"}), top_mat="RoofDark")
    # The drum, then the sphere from where its radius equals the drum's, one lathe.
    z_meet = zc - math.sqrt(r_dome ** 2 - r_drum ** 2)
    profile = [(r_drum, top - SINK), (r_drum, top + 1.6), (r_drum, top + 3.4), (r_drum, z_meet)]
    a0, rings = math.asin((z_meet - zc) / r_dome), 11
    for k in range(1, rings + 1):
        a = a0 + (math.pi / 2 - a0) * k / rings
        profile.append((r_dome * math.cos(a) if k < rings else 0.0, zc + r_dome * math.sin(a)))
    drum_mats = ["Steel", "GlassDark", "Orange"]
    b.lathe(profile, "Wall", segments=16,
            cell=lambda k, row: drum_mats[row] if row < 3 else ("WarningLight" if row == len(profile) - 2 else None),
            cap_mat="Steel")
    b.box(3.0, -8.0, top - SINK, 7.5, -5.0, top + 2.0, "Steel",
          cell=lambda s, c, r, u, z: "LightStrip" if s == FRONT else None)
    return [("", b)]


# --- Kit_Base_Bunker: 10 x 4 x 10, 150 tris --------------------------------------------------
def bunker():
    """A low armoured bunker: a sloped concrete block with a dark slit across
    the front slope, a periscope box on top and a dark door at the back."""
    b = Builder()
    hw, h = 5.0, 3.6
    pts, tags = cut([(-hw, -hw), (hw, -hw), (hw, hw), (-hw, hw)], {FRONT: [0.2, 0.8]})
    slope = lambda z: 1.0 - 0.4 * z / h       # the top is 6 x 6
    loft(b, pts, tags, [(1.0, 0.0, "Concrete"), (slope(1.4), 1.4, "Concrete"), (slope(2.6), 2.6, "Concrete"),
                        (slope(h), h, "Concrete")],
         cell=lambda side, c, r: "HazardBlack" if (side, c, r) == (FRONT, 1, 1) else None)
    b.box(1.6, 1.6, h - SINK, 2.8, 2.8, 4.2, "Steel")
    b.box(-1.5, 1.5, 0.0, 1.5, 4.8, 2.6, "Concrete",
          cell=lambda s, c, r, u, z: "MilitaryDark" if s == BACK else None, top_mat="RoofDark")
    return [("", b)]


# --- The airfield preview --------------------------------------------------------------------
def render_view(scene, eye, target, path, size=(1600, 900), lens=35):
    """Renders `scene` as kit_tools.preview() does (Workbench, flat palette
    colours, outlines, backface culling) from `eye` looking at `target`."""
    cam_data = bpy.data.cameras.new("BaseCam")
    cam_data.lens = lens
    cam = bpy.data.objects.new("BaseCam", cam_data)
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
    world = bpy.data.worlds.new("BaseWorld")
    world.color = (0.55, 0.65, 0.8)
    scene.world = world
    eye, target = Vector(eye), Vector(target)
    cam.location = eye
    cam.rotation_euler = (target - eye).to_track_quat("-Z", "Y").to_euler()
    cam_data.clip_end = 6000.0
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True, scene=scene.name)
    bpy.data.objects.remove(cam)
    bpy.data.cameras.remove(cam_data)
    bpy.data.worlds.remove(world)


def ground_plane(scene, name, x0, y0, x1, y1, z, mat):
    me = bpy.data.meshes.new(name)
    me.from_pydata([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], [], [(0, 1, 2, 3)])
    me.materials.append(kt.cc.material(mat))
    o = bpy.data.objects.new(name, me)
    scene.collection.objects.link(o)


def airfield_preview(out):
    """Stands the pieces as gen_base.py does (Blender axes: the apron south
    of the hangar row, the compound north of it) and renders the row from
    the south-east at about 200 m and 60 m up, and the compound."""
    os.makedirs(out, exist_ok=True)
    scene = bpy.data.scenes.new("Airfield")

    def stand(name, x, y, turn=0.0):
        inst = bpy.data.objects.new(name, None)
        inst.instance_type = "COLLECTION"
        inst.instance_collection = bpy.data.collections[name]
        inst.location = (x, y, 0.0)
        inst.rotation_euler = (0.0, 0.0, turn)
        scene.collection.objects.link(inst)
    ground_plane(scene, "Ground", -1500.0, -400.0, 1500.0, 900.0, -0.3, "FieldGreen")
    ground_plane(scene, "Apron", -700.0, -122.0, 700.0, 265.0, -0.1, "Concrete")
    ground_plane(scene, "Taxiway", -1300.0, -148.0, 1000.0, -122.0, -0.1, "Road")
    ground_plane(scene, "Compound", -820.0, 290.0, 820.0, 660.0, -0.1, "Pavement")
    for k in range(10):
        stand("Kit_Base_Hangar", -540.0 + 120.0 * k, 225.0)
    stand("Kit_Base_ControlTower", 790.0, 150.0)
    stand("Kit_Base_HQ", 75.0, 466.0)
    for a0 in (164.0, 328.0, -492.0):                       # barracks blocks (150 x 120, rows at 20 m from the edges)
        for i in range(3):
            for y in (506.0, 546.0):
                stand("Kit_Base_Barracks", a0 + (i + 0.5) * 50.0, y)
    for i in range(3):                                       # a shed block
        for j in range(3):
            stand("Kit_Base_Shed", -328.0 + (i + 0.5) * 50.0, 290.0 + (j + 0.5) * 40.0)
    for x, y in ((-1100.0, 450.0), (-1250.0, 250.0)):
        stand("Kit_Base_Radar", x, y)
    for x, y in ((-1060.0, 160.0), (1120.0, -170.0)):
        stand("Kit_Base_Bunker", x, y)
    render_view(scene, (1050.0, -280.0, 200.0), (200.0, 250.0, 10.0), os.path.join(out, "airfield_200m.png"))
    render_view(scene, (1000.0, -20.0, 60.0), (560.0, 230.0, 14.0), os.path.join(out, "airfield_60m.png"))
    render_view(scene, (900.0, -100.0, 220.0), (0.0, 480.0, 10.0), os.path.join(out, "compound_200m.png"))
    render_view(scene, (300.0, 330.0, 60.0), (80.0, 470.0, 10.0), os.path.join(out, "compound_60m.png"))
    bpy.data.scenes.remove(scene)
    print("airfield previews in " + out)


# --- The batch -------------------------------------------------------------------------------
PIECES = [
    ("Kit_Base_Hangar", hangar), ("Kit_Base_ControlTower", control_tower), ("Kit_Base_HQ", hq),
    ("Kit_Base_Barracks", barracks), ("Kit_Base_Shed", shed), ("Kit_Base_Radar", radar),
    ("Kit_Base_Bunker", bunker),
]


def main():
    kt.begin("kit_base", 5)
    for name, build in PIECES:
        kt.piece(name, build())
    kt.finish()
    if os.environ.get("KIT_BASE_PREVIEW"):
        airfield_preview(os.environ["KIT_BASE_PREVIEW"])


if __name__ == "__main__":
    main()
