"""The city's low kit pieces (models/corneria2/ASSETS.md, "City"): the
suburban houses, the old town's shops, the mid-rise apartments, the port's
warehouses, tanks and gantry crane, and the road bridge deck and its piers.
The offices, towers, round towers and spire are another batch's.

    KIT_OUT=<copy.blend> KIT_PREVIEW=<dir> blender --background --python kit_city_low.py

One function per piece or family, each returning [(suffix, Builder)] for
kit_tools.piece(). Every piece stands on Z = 0 with its origin at the centre
of its footprint and its front (door, loading doors, shopfront) on -Y.

Shells: a roof or an annex is its own closed shell sunk SINK into the part it
stands on, and a roof block's ends stand PROUD of the wall faces below, so no
two faces of different shells share a plane (coplanar faces flicker) and no
two shells share an edge (the merged vertices would make it non-manifold).
Windows, doors, bands and stripes are painted: cells of the walls' own faces
in another material, so they draw no ink line.
"""

import math
import os
import sys

from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit_tools as kt  # noqa: E402
from kit_tools import Builder  # noqa: E402

SINK = 0.1       # how far a part sinks into the one it stands on
PROUD = 0.02     # how far a roof block's ends stand out from the wall faces under it

FRONT, RIGHT, BACK, LEFT = 0, 1, 2, 3   # a box's sides, as prism() numbers them


# --- Helpers -------------------------------------------------------------------------
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


def hip_roof(b, x0, y0, x1, y1, z0, z1, mat, inset=None, top_mat=None):
    """A hipped roof over the rectangle, its eaves at z0 and its ridge at z1:
    the top rectangle is `inset` on every side (default: half the short
    side, so the top is a ridge line, or a point on a square)."""
    w, d = x1 - x0, y1 - y0
    i = min(w, d) / 2.0 if inset is None else inset
    xa, xb = (x0 + i, x1 - i) if i < w / 2.0 - 1e-6 else ((x0 + x1) / 2.0,) * 2
    ya, yb = (y0 + i, y1 - i) if i < d / 2.0 - 1e-6 else ((y0 + y1) / 2.0,) * 2
    lo = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)]
    hi = [(xa, ya, z1), (xb, ya, z1), (xb, yb, z1), (xa, yb, z1)]
    b.face(lo[::-1], mat)
    for k in range(4):
        k1 = (k + 1) % 4
        b.face([lo[k], lo[k1], hi[k1], hi[k]], mat)
    b.face(hi, top_mat or mat)       # dropped by face() when the ridge is a line


def gable_roof(b, hw, hl, z_wall, pitch, overhang, thick, wall_mat, roof_mat):
    """A gabled roof over walls spanning x +-hw, y +-hl up to z_wall; the
    ridge runs along y, so the gable ends face the front and back. The gable
    ends are a wedge in the wall's colour (sunk into the walls, a hair proud
    of their faces); the roof slab overhangs them all round, its underside
    just under the wedge's slopes so the two never share a plane."""
    zr = z_wall + hw * pitch - 0.06      # the slab's underside at the ridge: the wall tops sit inside it
    xe = hw + PROUD
    b.extrude([(-xe, z_wall - SINK), (xe, z_wall - SINK), (xe, zr + 0.05 - xe * pitch),
               (0.0, zr + 0.05), (-xe, zr + 0.05 - xe * pitch)], -hl - PROUD, hl + PROUD, wall_mat)
    e = hw + overhang
    zu = zr - e * pitch
    b.extrude([(-e, zu), (0.0, zr), (e, zu), (e, zu + thick), (0.0, zr + thick), (-e, zu + thick)],
              -hl - overhang, hl + overhang, roof_mat)


def roof_block(b, outline, hl, mat, cell=None, smooth=False, cap_mat=None):
    """A roof shape (an outline in x, z over the walls) pushed from -hl to
    +hl, its ends a hair proud of the wall faces there."""
    b.extrude(outline, -hl - PROUD, hl + PROUD, mat, cell=cell, smooth=smooth, cap_mat=cap_mat)


def bar(b, p0, p1, size, mat):
    """A square beam `size` across from point p0 to p1 (a brace, a stay)."""
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    m = Matrix.Translation(p0) @ d.to_track_quat("Z", "Y").to_matrix().to_4x4()
    h = size / 2.0
    with b.at(m):
        b.box(-h, -h, 0.0, h, h, d.length, mat)


def arc(hw, rise, z0, segments, inner=0.0):
    """Points of a half-ellipse from (-hw, z0) over (0, z0 + rise) to (hw, z0),
    left to right, `inner` metres inside it."""
    pts = []
    for k in range(segments + 1):
        t = math.pi - math.pi * k / segments
        pts.append(((hw - inner) * math.cos(t), z0 + (rise - inner) * math.sin(t)))
    return pts


def bays_of(n, pillar, opening):
    """Widths of an arcade: n openings between n + 1 pillars."""
    return [pillar] + [opening, pillar] * n


def odd(col):
    return col % 2 == 1


# --- Kit_City_House: suburban houses (14 x 7.5 x 12, 150 tris) ------------------------
HOUSE_W, HOUSE_D, HOUSE_H = 14.0, 12.0, 7.5
EAVE = 0.6                       # roof overhang


def house_a():
    """An L: a two-storey wing under a hipped terracotta roof, with a
    one-storey wing (door, big window) in the crook."""
    b = Builder()
    hw, hd = HOUSE_W / 2 - EAVE, HOUSE_D / 2 - EAVE
    # The tall wing: ribbon windows all round, under its roof.
    top = block(b, -hw, -hd, 0.4, hd, 0.0,
                [(1.0, "Wall"), (1.4, "Glass"), (1.5, "Wall"), (1.4, "Glass"), (0.6, "Wall")])
    hip_roof(b, -hw - EAVE, -hd - EAVE, 1.0, hd + EAVE, top - SINK, HOUSE_H, "Roof")
    # The low wing: the door and a tall window on the front.
    low = block(b, 0.4 - SINK, -hd - PROUD, hw, 1.2, 0.0, [(2.4, "Wall"), (0.8, "Wall")],
                bays={FRONT: [1.2, 1.6, 0.8, 2.0, 0.6]},
                paint=cells({(FRONT, 1, 0): "Orange", (FRONT, 3, 0): "Glass"}))
    hip_roof(b, -0.4, -hd - EAVE, hw + EAVE, 1.8, low - SINK, low + 1.2, "Roof")
    return [("", b)]


def house_b():
    """A two-storey gabled house under a teal roof, the gable to the street,
    with a flat-roofed garage beside it."""
    b = Builder()
    hd = HOUSE_D / 2 - EAVE
    cx, hw = -1.8, 4.6                       # the house, left of centre; the garage fills the right
    z_wall = block(b, cx - hw, -hd, cx + hw, hd, 0.0,
                   [(2.0, "Wall"), (1.1, "Glass"), (0.8, "Wall"), (1.1, "Glass")],
                   bays={FRONT: [1.0, 1.4, 1.0, 3.6, 2.2]},
                   paint=cells({(FRONT, 1, 0): "Teal", (FRONT, 3, 0): "Glass"}))
    with b.at(Matrix.Translation((cx, 0.0, 0.0))):
        gable_roof(b, hw, hd, z_wall, 0.5, EAVE, 0.35, "Wall", "Teal")
    block(b, cx + hw - SINK, -hd - PROUD, HOUSE_W / 2, 1.4, 0.0, [(2.6, "Wall"), (0.5, "Wall")],
          bays={FRONT: [0.6, 2.7, 0.6]}, paint=cells({(FRONT, 1, 0): "RoofDark"}), top_mat="RoofDark")
    return [("", b)]


def house_c():
    """A single vaulted volume: a teal barrel shell over white walls with a
    glass band, the shell's ends filled with wall."""
    b = Builder()
    hw, hd = HOUSE_W / 2 - EAVE, HOUSE_D / 2 - EAVE
    z_wall = block(b, -hw, -hd, hw, hd, 0.0, [(1.0, "Wall"), (1.6, "Glass"), (1.8, "Wall")],
                   bays={FRONT: [2.0, 1.4, 1.2, 5.0, 3.2]},
                   paint=cells({(FRONT, 1, 0): "Orange", (FRONT, 3, 0): "Glass", (FRONT, 3, 2): "Glass"}))
    z0, rise, thick, segs = z_wall - 0.2, HOUSE_H - z_wall + 0.2, 0.4, 6
    outer = arc(hw + EAVE, rise, z0, segs)
    inner = arc(hw + EAVE, rise, z0, segs, thick)
    # The shell: a thick arc, open below, its soffit showing past the walls...
    b.extrude(inner + outer[::-1], -hd - EAVE, hd + EAVE, "Teal", smooth=True)
    # ...and the loft inside it filled with wall, proud of the walls' ends and
    # a hair into the shell, so no gap shows between the two.
    loft = arc(hw + EAVE, rise, z0, segs, thick - 0.05)
    roof_block(b, [(loft[0][0], z0 - SINK)] + loft + [(loft[-1][0], z0 - SINK)], hd, "Wall")
    return [("", b)]


def house_d():
    """Split-level, flat-roofed: a two-storey block with an orange parapet
    stripe beside a one-storey wing with a roof deck and a teal door canopy."""
    b = Builder()
    hw, hd = HOUSE_W / 2, HOUSE_D / 2 - 0.3
    block(b, -hw, -hd + 0.4, -0.5, hd + PROUD, 0.0,
          [(2.4, "Wall"), (1.2, "Glass"), (1.4, "Wall"), (1.4, "Glass"), (0.4, "Wall"), (0.4, "Orange")],
          bays={FRONT: [1.0, 4.5, 1.0]}, paint=cells({(FRONT, 1, 0): "Glass"}), top_mat="RoofDark")
    block(b, -0.7, -hd, hw, hd, 0.0, [(1.0, "Wall"), (1.6, "Glass"), (0.8, "Wall")],
          bays={FRONT: [1.4, 1.6, 4.7]},
          paint=cells({(FRONT, 1, 0): "RoofDark", (FRONT, 1, 1): "RoofDark"}), top_mat="Concrete")
    b.box(0.3, -hd - 0.9, 2.7, 2.7, -hd + SINK, 3.0, "Teal")          # the door canopy
    b.box(-6.0, 2.0, 7.1, -4.0, 4.0, HOUSE_H + 0.3, "Teal")           # a stair head on the roof
    return [("", b)]


# --- Kit_City_Shop: old-town buildings (250 tris) -------------------------------------
TRIM = 0.4                                 # a stone string course


def shop_front(windows, door=None, sides=(FRONT,)):
    """A painter for a shop's `sides`: dark arcade openings in the odd bays of
    the ground row, windows above them on the `windows` rows, and on the
    front a door at bay `door`."""
    def paint(side, col, row):
        if side not in sides:
            return None
        if row == 0:
            return "Orange" if (side, col) == (FRONT, door) else ("GlassDark" if odd(col) else None)
        return "Glass" if row in windows and odd(col) else None
    return paint


def shop_a():
    """12 x 11 x 8: a cream townhouse with a painted stone arcade and an
    orange awning band, tall windows above (on the sides too), under a
    hipped terracotta roof."""
    b = Builder()
    hw, hd = 5.5, 3.5
    side_bays = [1.5, 1.6, 0.8, 1.6, 1.5]
    top = block(b, -hw, -hd, hw, hd, 0.0,
                [(3.6, "Cream"), (0.8, "Orange"), (TRIM, "Stone"), (3.6, "Cream"), (TRIM, "Stone")],
                bays={FRONT: bays_of(4, 1.0, 1.5), RIGHT: side_bays, LEFT: side_bays},
                paint=shop_front(windows=(3,), sides=(FRONT, RIGHT, LEFT)))
    hip_roof(b, -hw - 0.5, -hd - 0.5, hw + 0.5, hd + 0.5, top - SINK, 11.0, "Roof")
    return [("", b)]


def shop_b():
    """9 x 17 x 8: narrow and tall, a shopfront under a blue awning, three
    floors of tall windows and a teal gable to the street."""
    b = Builder()
    hw, hd = 4.1, 3.6
    floors = [(3.8, "Cream"), (0.7, "AwningBlue"), (0.3, "Stone"), (3.4, "Cream"), (0.3, "Stone"),
              (3.4, "Cream"), (0.3, "Stone"), (2.3, "Cream")]

    def paint(side, col, row):
        if side != FRONT:
            return None
        if row == 0:
            return {1: "Glass", 3: "Orange"}.get(col)
        if row in (3, 5) and col in (1, 3, 5):
            return "Glass"
        return "Glass" if (row, col) == (7, 3) else None
    z_wall = block(b, -hw, -hd, hw, hd, 0.0, floors, bays={FRONT: [0.8, 3.4, 0.8, 1.4, 0.8, 1.0, 0.8]},
                   paint=paint)
    gable_roof(b, hw, hd, z_wall, 0.5, 0.4, 0.35, "Cream", "Teal")
    return [("", b)]


def shop_c():
    """17 x 12 x 10: a wide, low shop with a long arcade and orange awning,
    a flat roof and a small teal-roofed roof pavilion at the back."""
    b = Builder()
    hw, hd = 8.5, 5.0
    top = block(b, -hw, -hd, hw, hd, 0.0,
                [(3.6, "Cream"), (0.8, "Orange"), (TRIM, "Stone"), (3.4, "Cream"), (TRIM, "Stone"), (1.0, "Cream")],
                bays={FRONT: bays_of(5, 1.2, 2.0)}, paint=shop_front(windows=(3,)), top_mat="RoofDark")
    pav = block(b, -7.0, -1.0, -1.0, 4.0, top - SINK, [(1.9, "Cream")])
    hip_roof(b, -7.4, -1.4, -0.6, 4.4, pav - SINK, 12.4, "Teal")
    return [("", b)]


def shop_d():
    """16 x 19 x 11: the old town's tallest, three floors over the arcade,
    a terracotta hip and a round corner turret under a teal dome."""
    b = Builder()
    hw, hd = 7.6, 5.0
    top = block(b, -hw, -hd, hw, hd, 0.0,
                [(4.0, "Cream"), (0.8, "AwningBlue"), (3.8, "Cream"), (TRIM, "Stone"), (3.8, "Cream"),
                 (3.6, "Cream")],
                bays={FRONT: bays_of(4, 1.2, 2.3)}, paint=shop_front(windows=(2, 4, 5)))
    hip_roof(b, -hw - 0.5, -hd - 0.45, hw + 0.5, hd + 0.45, top - SINK, 18.4, "Roof")
    # The turret at the front-left corner: a cream drum with a glass slot
    # facing the street corner, under a teal dome.
    r, segs = 2.6, 10
    with b.at(Matrix.Translation((-5.8, -3.4, 0.0))):
        b.lathe([(r, 0.0), (r, 16.6), (r * 0.92, 17.4), (r * 0.62, 18.1), (0.0, 18.6)], "Cream", segments=segs,
                cell=lambda k, row: "Teal" if row > 0 else ("Glass" if k in (5, 6, 7) else None),
                turn=math.pi / segs)
    return [("", b)]


# --- Kit_City_Apartment: mid-rise housing (400 tris) -----------------------------------
def balconies(n, slab=1.6, shade=0.6, glass=1.4, wall="Cream"):
    """n storeys of balcony bands: a wall slab, the dark recess under it, glass."""
    return [(slab, wall), (shade, "GlassDark"), (glass, "Glass")] * n


def apartment_a():
    """32 x 22 x 12: a slab. Four balcony storeys over a dark glass lobby,
    a set-back white top storey, a teal stair tower proud of the left end
    and an orange entrance canopy."""
    b = Builder()
    hw, y0, y1 = 16.0, -5.2, 6.0
    top = block(b, -hw, y0, hw, y1, 0.0, [(4.0, "GlassDark")] + balconies(4) + [(0.4, "Cream")],
                bays={FRONT: [12.0, 8.0, 12.0]},
                paint=lambda s, c, r: ("Orange" if r == 0 else "GlassDark") if (s, c) == (FRONT, 1) else None,
                top_mat="RoofDark")
    block(b, -13.0, y0 + 1.4, 13.0, y1 - 1.0, top - SINK, [(1.0, "Tower"), (2.2, "Glass"), (0.5, "Tower")],
          top_mat="RoofDark")
    b.box(-hw - 0.4, -3.0, 0.0, -hw + 3.6, 4.0, 22.8, "Teal", top_mat="RoofDark")   # the stair tower
    b.box(-4.0, y0 - 1.0, 3.6, 4.0, y0 + SINK, 4.1, "Orange")                       # the canopy
    return [("", b)]


def apartment_b():
    """22 x 26 x 20: a white block with a rounded, fully glazed end, five
    glass bands, an orange roof edge and a lift house on the roof."""
    b = Builder()
    hd, r, segs = 10.0, 10.0, 8
    outline = [(-11.0, -hd), (1.0, -hd)]
    for k in range(1, segs):
        a = -math.pi / 2 + math.pi * k / segs
        outline.append((1.0 + r * math.cos(a), r * math.sin(a)))
    outline += [(1.0, hd), (-11.0, hd)]
    storeys = [(4.5, "GlassDark")] + [(1.8, "Tower"), (2.0, "Glass")] * 5 + [(0.5, "Orange")]
    levels, z = [], 0.0
    for h, _ in storeys[:-1]:
        z += h
        levels.append(z)
    cuts = [4.0 / 12.0, 6.0 / 12.0]          # the front's bays: wall, door, wall
    b.prism(outline, 0.0, z + storeys[-1][0], "Tower", levels=levels, smooth=True,
            columns=lambda s, _l: cuts if s == FRONT else [],
            cell=lambda s, c, r, _u, _z: "Orange" if (s, c, r) == (FRONT, 1, 0) else storeys[r][1],
            top_mat="RoofDark")
    b.box(-7.8, 1.0, 24.0 - SINK, -3.0, 7.0, 26.0, "Tower", top_mat="RoofDark")    # the lift house
    b.box(-11.3, -4.0, 0.0, -8.0, 4.0, 25.0, "Tower", top_mat="RoofDark")          # a stair tower, proud of the end
    return [("", b)]


def apartment_c():
    """16 x 18 x 10: small. Three balcony storeys, a white top storey set
    back on the left, a teal stair tower at the back-right corner."""
    b = Builder()
    hw, hd = 8.0, 5.0
    top = block(b, -hw, -hd, hw, hd, 0.0, [(3.6, "Cream")] + balconies(3) + [(0.4, "Cream")],
                bays={FRONT: [5.0, 1.8, 9.2]},
                paint=lambda s, c, r: ("Orange" if r == 0 else "GlassDark") if (s, c) == (FRONT, 1) else None,
                top_mat="RoofDark")
    block(b, -4.0, -3.5, hw - 0.2, hd - 0.2, top - SINK, [(0.9, "Tower"), (2.0, "Glass"), (0.4, "Tower")],
          top_mat="RoofDark")
    b.box(4.0, 1.0, 0.0, hw + 0.3, hd + 0.3, 18.6, "Teal", top_mat="RoofDark")
    return [("", b)]


# --- Kit_City_Warehouse: port warehouses (200 tris) ------------------------------------
DOOR_H = 8.0          # the loading doors
FRAME = 1.0           # ...and their hazard-painted frames


def shed_front(doors):
    """Bays for a warehouse front: walls between `doors` [(wall before, door
    width)] and a wall after; and the painter: a dark door in a yellow frame,
    a yellow-and-black lintel stripe above."""
    bays = []
    for wall, door in doors:
        bays += [wall, FRAME, door, FRAME]
    bays.append(bays[0])

    def paint(side, col, row):
        if side != FRONT or col % 4 == 0 or row > 1:
            return None
        if col % 4 == 2:
            return "RoofDark" if row == 0 else "TaxiYellow"
        return "TaxiYellow" if row == 0 else "HazardBlack"
    return bays, paint


def warehouse_a():
    """50 x 14 x 36: a steel shed with three loading doors under a sawtooth
    roof, its steep faces glazed."""
    b = Builder()
    hw, hd, teeth = 25.0, 18.0, 5
    bays, paint = shed_front([(4.5, 8.0), (4.5, 8.0), (4.5, 8.0)])
    top = block(b, -hw, -hd, hw, hd, 0.0, [(DOOR_H, "Steel"), (1.0, "Steel"), (1.0, "Steel")],
                bays={FRONT: bays}, paint=paint)
    xe, low, high = hw + PROUD, top + 0.2, 14.0
    pitch = 2 * xe / teeth
    outline = [(-xe, top - SINK), (xe, top - SINK)]
    for i in reversed(range(teeth)):
        outline += [(-xe + (i + 1) * pitch, high), (-xe + i * pitch, low)]
    roof_block(b, outline, hd, "RoofDark", cell=lambda s: "Glass" if s % 2 == 1 and s > 0 else None,
               cap_mat="Steel")
    return [("", b)]


def warehouse_b():
    """72 x 16 x 50: the big one, concrete walls under a smooth barrel vault,
    two wide doors."""
    b = Builder()
    hw, hd = 36.0, 25.0
    bays, paint = shed_front([(10.0, 20.0), (7.2, 20.0)])
    top = block(b, -hw, -hd, hw, hd, 0.0, [(DOOR_H, "Concrete"), (1.0, "Concrete"), (1.0, "Steel")],
                bays={FRONT: bays}, paint=paint)
    xe = hw + PROUD
    vault = arc(xe, 16.0 - top, top, 12)
    roof_block(b, [(-xe, top - SINK)] + vault + [(xe, top - SINK)], hd, "RoofDark", smooth=True,
               cap_mat="Concrete")
    return [("", b)]


def warehouse_c():
    """40 x 12 x 50: a flat-roofed steel shed with a concrete eave band, two
    doors and three long roof vents."""
    b = Builder()
    hw, hd = 20.0, 25.0
    bays, paint = shed_front([(5.0, 10.0), (6.0, 10.0)])
    top = block(b, -hw, -hd, hw, hd, 0.0, [(DOOR_H, "Steel"), (1.0, "Steel"), (1.5, "Concrete")],
                bays={FRONT: bays}, paint=paint, top_mat="RoofDark")
    for x in (-13.0, -1.5, 10.0):
        b.box(x, -hd + 5.0, top - SINK, x + 3.0, hd - 5.0, 12.0, "Steel", top_mat="RoofDark")
    return [("", b)]


# --- Kit_City_Tank: storage tanks (120 tris) -------------------------------------------
def tank_a():
    """24 x 16: a steel drum with an orange band under a shallow cone."""
    b = Builder()
    b.lathe([(12.0, 0.0), (12.0, 12.2), (12.0, 14.0), (0.0, 16.0)], "Steel", segments=16,
            cell=lambda k, row: "Orange" if row == 1 else None)
    return [("", b)]


def tank_b():
    """20 x 12: squat and white, a domed top with a teal rim."""
    b = Builder()
    b.lathe([(10.0, 0.0), (10.0, 9.8), (7.5, 11.3), (0.0, 12.0)], "Wall", segments=16,
            cell=lambda k, row: "Teal" if row == 1 else None)
    return [("", b)]


# --- Kit_City_Crane: harbour gantry cranes (10 x 50 x 30, 600 tris) ----------------------
LEG = 1.4             # the legs' thickness
BEAM = 2.5            # the portal beams' depth


def crane():
    """A container gantry: four yellow legs on black bogies, hazard-striped at
    the foot and braced; portal beams at the top carry a boom along y with a
    machinery house, a trolley and a cab under it, and an A-frame mast with
    stays to the boom's ends."""
    b = Builder()
    xl, yl, z_top = 5.0 - LEG / 2, 6.0, 30.0
    bogie = 1.5
    stripes = [(2.0, "TaxiYellow"), (1.5, "HazardBlack"), (1.5, "TaxiYellow"), (1.5, "HazardBlack"),
               (z_top - bogie - 6.5, "TaxiYellow")]
    for x in (-xl, xl):
        for y in (-yl, yl):
            b.box(x - 0.8, y - 2.0, 0.0, x + 0.8, y + 2.0, bogie, "HazardBlack")
            block(b, x - LEG / 2, y - LEG / 2, x + LEG / 2, y + LEG / 2, bogie - SINK, stripes)
        # A diagonal brace on each side, and the beam joining the legs along y
        # (a little wider than the legs, and not as deep as the portal beams,
        # so no faces are shared).
        bar(b, (x, -yl + 0.4, bogie + 2.0), (x, yl - 0.4, z_top - BEAM - 0.5), 1.2, "TaxiYellow")
        b.box(x - LEG / 2 - 0.1, -yl - 1.0, z_top - BEAM + 0.3, x + LEG / 2 + 0.1, yl + 1.0, z_top - 0.05,
              "TaxiYellow")
    for y in (-yl, yl):          # the portal beams across x, carrying the boom
        b.box(-5.0, y - LEG / 2 - 0.1, z_top - BEAM, 5.0, y + LEG / 2 + 0.1, z_top + SINK, "TaxiYellow")
    # The boom: a yellow girder with hazard stripes at both ends.
    ends = [1.0, 1.0, 1.0, 24.0, 1.0, 1.0, 1.0]
    block(b, -3.0, -15.0, 3.0, 15.0, z_top, [(3.5, "TaxiYellow")],
          bays={RIGHT: ends, LEFT: ends},
          paint=lambda s, c, r: "HazardBlack" if s in (RIGHT, LEFT) and c in (0, 2, 4, 6) else None)
    # On it, the machinery house; under it, the trolley and the driver's cab.
    block(b, -3.5, 2.0, 3.5, 9.0, z_top + 3.5 - SINK, [(2.5, "Steel"), (1.2, "GlassDark"), (0.8, "Steel")],
          top_mat="RoofDark")
    b.box(-3.3, -9.0, z_top - 1.5, 3.3, -6.0, z_top + SINK, "Steel")
    block(b, -1.4, -12.5, 1.4, -10.0, z_top - 2.5, [(1.6, "GlassDark"), (1.0, "Steel")],
          top_mat="RoofDark")
    # The A-frame mast (a tapering frustum sunk into the house's roof) and
    # its stays to the boom's ends.
    z_house = z_top + 3.5 - SINK + 4.5
    lo = [(-2.0, 4.0, z_house - SINK), (2.0, 4.0, z_house - SINK), (2.0, 7.0, z_house - SINK),
          (-2.0, 7.0, z_house - SINK)]
    hi = [(-0.6, 5.0, 50.0), (0.6, 5.0, 50.0), (0.6, 6.0, 50.0), (-0.6, 6.0, 50.0)]
    b.face(lo[::-1], "TaxiYellow")
    for k in range(4):
        k1 = (k + 1) % 4
        b.face([lo[k], lo[k1], hi[k1], hi[k]], "TaxiYellow")
    b.face(hi, "TaxiYellow")
    bar(b, (0.0, 5.5, 49.4), (0.0, -14.5, z_top + 3.6), 0.5, "Steel")
    bar(b, (0.0, 5.5, 49.4), (0.0, 14.5, z_top + 3.6), 0.5, "Steel")
    return [("", b)]


# --- Kit_City_Bridge: road bridge deck (24 x 4 x 100, 200 tris) --------------------------
def bridge():
    """A concrete box-girder deck with an orange stripe along each side and
    solid steel parapets. Uniform along y (it is stretched); its top is the
    parapets' top, so the deck surface sits a metre below the piece's top."""
    b = Builder()
    hw, hl = 12.0, 50.0
    deck, top = 3.0, 4.0
    right = [(10.0, 0.0), (hw, 1.0), (hw, 1.6), (hw, 2.4), (hw, deck), (hw, top), (hw - 0.8, top), (hw - 0.8, deck)]
    left = [(-x, z) for x, z in reversed(right)]
    outline = right + left
    mats = ["Concrete", "Concrete", "Orange", "Concrete", "Steel", "Steel", "Steel", "Concrete"]
    side_mats = mats + mats[::-1][1:] + ["Concrete"]

    def cell(s):
        return side_mats[s]
    b.extrude(outline, -hl, hl, "Concrete", cell=cell)
    return [("", b)]


# --- Kit_City_Pier: bridge piers (17 x 20 x 8, 100 tris) ----------------------------------
def pier():
    """A concrete wall pier with rounded ends under a cap beam. Built 17 m
    wide (across the road), the width the generator fits it to."""
    b = Builder()
    hw, r, segs, h = 8.5, 4.0, 6, 20.0
    outline = []
    for k in range(segs + 1):
        a = -math.pi / 2 + math.pi * k / segs
        outline.append((hw - r + r * math.cos(a), r * math.sin(a)))
    for k in range(segs + 1):
        a = math.pi / 2 + math.pi * k / segs
        outline.append((-hw + r + r * math.cos(a), r * math.sin(a)))
    b.prism(outline, 0.0, h - 1.6, "Concrete", smooth=True)
    b.box(-hw - 0.3, -r - 0.3, h - 1.8, hw + 0.3, r + 0.3, h, "Concrete")
    return [("", b)]


# --- The batch -----------------------------------------------------------------------
PIECES = [
    ("Kit_City_House_A", house_a), ("Kit_City_House_B", house_b),
    ("Kit_City_House_C", house_c), ("Kit_City_House_D", house_d),
    ("Kit_City_Shop_A", shop_a), ("Kit_City_Shop_B", shop_b),
    ("Kit_City_Shop_C", shop_c), ("Kit_City_Shop_D", shop_d),
    ("Kit_City_Apartment_A", apartment_a), ("Kit_City_Apartment_B", apartment_b),
    ("Kit_City_Apartment_C", apartment_c),
    ("Kit_City_Warehouse_A", warehouse_a), ("Kit_City_Warehouse_B", warehouse_b),
    ("Kit_City_Warehouse_C", warehouse_c),
    ("Kit_City_Tank_A", tank_a), ("Kit_City_Tank_B", tank_b),
    ("Kit_City_Crane", crane), ("Kit_City_Bridge", bridge), ("Kit_City_Pier", pier),
]


def main():
    kt.begin("kit_city_low", 1)
    for name, build in PIECES:
        kt.piece(name, build())
    kt.finish()


if __name__ == "__main__":
    main()
