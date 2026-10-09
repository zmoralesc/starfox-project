"""The harbour town's, villages' and farms' kit pieces (models/corneria/ASSETS.md,
"The harbour town, villages and farms"): the coastal houses Kit_Town_House_A..D,
the town hall, the harbour sheds, the lighthouse, the jetty deck and its posts,
the moored boats, and the farmsteads' barn and silo.

    KIT_OUT=<copy.blend> KIT_PREVIEW=<dir> blender --background --python kit_town.py
    KIT_TOWN_PREVIEW=<dir>  also renders a street of houses fitted to lots as
                            gen_town.py fits them, and the harbour (the jetty
                            stretched on its posts, boats beside it, the sheds,
                            the lighthouse), seen from the air

One function per piece or family, each returning [(suffix, Builder)] for
kit_tools.piece(). Every piece stands on Z = 0 with its origin at the centre
of its footprint and its front (door, doors, bow) on -Y; the jetty's origin
is at its underside (gen_town stands it with its deck `above` the ground and
its posts reach up to that underside), the boats' at the keel (they float
sunk BOAT_SUNK, so the water is at that height on the hull).

The look: a cheerful Mediterranean seaside town beside the city's suburbs
(kit_city_low.py), with its own colours: whitewash (Wall) under terracotta
(Roof) with Teal or AwningBlue shutters, doors and roofs, cream civic stone,
and a red-and-white lighthouse. Shells follow kit_city_low's rules: a roof or
an annex is its own closed shell sunk SINK into what it stands on, with its
ends PROUD of the wall faces under it (no coplanar faces, no shared edges).
Windows, doors, shutters, stripes and the barn's cross-braced door are
painted: cells of the walls' own faces in another material.
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

SINK = 0.1       # how far a part sinks into the one it stands on
PROUD = 0.02     # how far a roof block's ends stand out from the wall faces under it
EAVE = 0.4       # the houses' roof overhang
BOAT_SUNK = 0.8  # gen_town floats the boats this far under the water (BOATS["sunk"])

FRONT, RIGHT, BACK, LEFT = 0, 1, 2, 3   # a box's sides, as prism() numbers them


# --- Helpers (block, cells, hip_roof, gable_roof, roof_block, bar: as kit_city_low.py) ---
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


def gable_roof(b, hw, hl, z_wall, pitch, overhang, thick, wall_mat, roof_mat, along="y"):
    """A gabled roof over walls spanning x +-hw, y +-hl up to z_wall; the
    ridge runs along y (`along` "y": the gable ends face front and back) or,
    turned a quarter, along x (`along` "x": then hw is the half DEPTH the
    slopes span and hl the half width the ridge runs). The gable ends are a
    wedge in the wall's colour (sunk into the walls, a hair proud of their
    faces); the roof slab overhangs them all round, its underside just under
    the wedge's slopes so the two never share a plane. Returns the ridge's top."""
    if along == "x":
        with b.at(Matrix.Rotation(math.pi / 2, 4, "Z")):
            return gable_roof(b, hw, hl, z_wall, pitch, overhang, thick, wall_mat, roof_mat)
    zr = z_wall + hw * pitch - 0.06      # the slab's underside at the ridge: the wall tops sit inside it
    xe = hw + PROUD
    b.extrude([(-xe, z_wall - SINK), (xe, z_wall - SINK), (xe, zr + 0.05 - xe * pitch),
               (0.0, zr + 0.05), (-xe, zr + 0.05 - xe * pitch)], -hl - PROUD, hl + PROUD, wall_mat)
    e = hw + overhang
    zu = zr - e * pitch
    b.extrude([(-e, zu), (0.0, zr), (e, zu), (e, zu + thick), (0.0, zr + thick), (-e, zu + thick)],
              -hl - overhang, hl + overhang, roof_mat)
    return zr + thick


def gambrel_roof(b, hw, hl, z_wall, xb, zb, zr, overhang, thick, wall_mat, roof_mat):
    """A gambrel roof (the barn's): each side breaks at (+-xb, zb) between a
    steep lower slope from the eave and a flatter upper one to the ridge at
    zr. The ridge runs along y; a wall-coloured wedge fills the gable ends
    under a slab, as gable_roof()."""
    lower = (zb - z_wall) / (hw - xb)        # the lower slope's pitch (it carries on past the eave)
    xe, e = hw + PROUD, hw + overhang
    line = [(-e, z_wall - lower * overhang), (-xb, zb), (0.0, zr), (xb, zb), (e, z_wall - lower * overhang)]
    b.extrude([(-xe, z_wall - SINK), (xe, z_wall - SINK), (xe, z_wall - lower * PROUD + 0.05),
               (xb, zb + 0.05), (0.0, zr + 0.05), (-xb, zb + 0.05), (-xe, z_wall - lower * PROUD + 0.05)],
              -hl - PROUD, hl + PROUD, wall_mat)
    b.extrude(line + [(x, z + thick) for x, z in line[::-1]], -hl - overhang, hl + overhang, roof_mat)


def chimney(b, x, y, z_roof, size=1.2, height=1.6, mat="Wall", cap="RoofDark"):
    """A square chimney through the roof at (x, y): from well inside the roof
    (z_roof is the roof surface there) to `height` above it."""
    h = size / 2.0
    b.box(x - h, y - h, z_roof - 0.8, x + h, y + h, z_roof + height, mat, top_mat=cap)


def bar(b, p0, p1, size, mat):
    """A square beam `size` across from point p0 to p1 (a brace, a stay)."""
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    m = Matrix.Translation(p0) @ d.to_track_quat("Z", "Y").to_matrix().to_4x4()
    h = size / 2.0
    with b.at(m):
        b.box(-h, -h, 0.0, h, h, d.length, mat)


def bays_of(n, pillar, opening):
    """Widths of an arcade: n openings between n + 1 pillars."""
    return [pillar] + [opening, pillar] * n


def odd(col):
    return col % 2 == 1


def lathe_rows(b, rows, segments=16, cap_mat=None, bottom=True, top=True, turn=0.0):
    """A lathe from `rows` [(radius, z, material of the band above the ring)]
    (as kit_city_high's): the material may be a function of the segment, so
    a door or the lantern's panes can be painted round it. Two rings at one
    height make a flat annulus: a deck, a cornice."""
    rings = []
    for r, z, _ in rows:
        if r <= 0.0:
            rings.append([(0.0, 0.0, z)] * segments)
        else:
            rings.append([(r * math.cos(turn + 2 * math.pi * k / segments),
                           r * math.sin(turn + 2 * math.pi * k / segments), z) for k in range(segments)])
    for i in range(len(rings) - 1):
        m = rows[i][2]
        for k in range(segments):
            k1 = (k + 1) % segments
            b.face([rings[i][k], rings[i][k1], rings[i + 1][k1], rings[i + 1][k]],
                   (m(k) if callable(m) else m) or "Wall", True)
    if bottom and rows[0][0] > 0.0:
        b.face(rings[0][::-1], cap_mat or "Wall")
    if top and rows[-1][0] > 0.0:
        b.face(rings[-1], cap_mat or "Wall")


# --- Kit_Town_House: coastal houses (200 tris) ------------------------------------------------
# Whitewashed walls, painted shutters (a whole window cell in Teal or
# AwningBlue: at the distances the town is seen from, a window and its
# shutters are one coloured patch), a painted door, a terracotta or teal
# roof, a chimney. Four silhouettes: a cottage, a house with a terrace
# annex, a terrace row, a two-storey villa with a corner tower.
def house_a():
    """A, 10 x 9 x 10, the cottage (also the lighthouse keeper's): one storey
    under a steep terracotta gable, ridge along the street, teal shutters, a
    blue door, a chimney at one end."""
    b = Builder()
    hw, hd = 5.0 - EAVE, 5.0 - EAVE
    top = block(b, -hw, -hd, hw, hd, 0.0, [(1.0, "Wall"), (1.8, "Wall"), (2.0, "Wall")],
                bays={FRONT: [1.0, 2.0, 1.4, 1.6, 1.4, 2.0, 1.0], RIGHT: [3.0, 2.2, 4.0], LEFT: [4.0, 2.2, 3.0]},
                paint=cells({(FRONT, 1, 1): "Teal", (FRONT, 5, 1): "Teal", (FRONT, 3, 0): "AwningBlue",
                             (FRONT, 3, 1): "AwningBlue", (RIGHT, 1, 1): "Teal", (LEFT, 1, 1): "Teal"}))
    ridge = gable_roof(b, hd, hw, top, 0.8, EAVE, 0.35, "Wall", "Roof", along="x")
    chimney(b, 3.4, 0.0, ridge - 0.35, height=0.9)
    return [("", b)]


def house_b():
    """B, 14 x 10 x 10: a two-storey house under a terracotta hip, a teal
    railing under a shaded loggia across the upper floor, and a one-storey
    annex with a blue awning and a roof terrace beside it."""
    b = Builder()
    hd = 5.0 - EAVE
    x0, x1 = -7.0 + EAVE, 2.0                    # the house, left; the annex fills the right
    top = block(b, x0, -hd, x1, hd, 0.0, [(2.8, "Wall"), (1.0, "Wall"), (1.8, "Wall"), (1.4, "Wall")],
                bays={FRONT: [1.0, 2.0, 1.0, 1.6, 3.0], LEFT: [3.0, 2.2, 4.0]},
                paint=cells({(FRONT, 1, 0): "Teal", (FRONT, 3, 0): "Orange",
                             (FRONT, 1, 1): "Teal", (FRONT, 2, 1): "Teal", (FRONT, 3, 1): "Teal",
                             (FRONT, 1, 2): "GlassDark", (FRONT, 2, 2): "GlassDark", (FRONT, 3, 2): "GlassDark",
                             (LEFT, 1, 0): "Teal", (LEFT, 1, 2): "Teal"}))
    hip_roof(b, x0 - EAVE, -hd - EAVE, x1 + EAVE, hd + EAVE, top - SINK, 10.0, "Roof")
    chimney(b, -4.0, 2.6, 8.9, height=1.0)
    block(b, x1 - SINK, -hd - PROUD, 7.0, 3.4, 0.0, [(2.4, "Wall"), (0.8, "Wall"), (0.4, "Wall")],
          bays={FRONT: [0.8, 3.4, 0.8]}, paint=cells({(FRONT, 1, 0): "Glass", (FRONT, 1, 1): "AwningBlue"}),
          top_mat="Concrete")
    return [("", b)]


def house_c():
    """C, 20 x 12 x 10, a terrace row: three attached houses under one steep
    terracotta roof (ridge along the street), each with its own door and
    shutter colour, a chimney at each end."""
    b = Builder()
    hw, hd = 10.0 - EAVE, 5.0 - EAVE
    shutters = ["Teal", "AwningBlue", "Teal"]
    doors = ["Orange", "RoofDark", "AwningBlue"]

    def paint(side, col, row):
        if side != FRONT or row > 1 or col == 12:
            return None
        house, slot = divmod(col, 4)
        if slot == 1:
            return shutters[house]
        if slot == 3:
            return doors[house] if row == 0 else shutters[house]
        return None
    top = block(b, -hw, -hd, hw, hd, 0.0, [(2.8, "Wall"), (2.6, "Wall"), (1.6, "Wall")],
                bays={FRONT: [1.4, 2.0, 1.2, 1.4] * 3 + [1.4]}, paint=paint)
    ridge = gable_roof(b, hd, hw, top, 1.0, EAVE, 0.35, "Wall", "Roof", along="x")
    for x in (-7.4, 7.4):
        chimney(b, x, 0.0, ridge - 0.35, height=1.0)
    return [("", b)]


def house_d():
    """D, 14 x 13 x 14, two storeys: a square villa under a low teal hip
    with a flat deck, tall blue-shuttered windows, an orange door, a shaded
    loggia behind a teal rail upstairs, and a stair tower at the back
    corner under a terracotta pyramid."""
    b = Builder()
    hw = 7.0 - EAVE - 0.3
    top = block(b, -hw, -hw, hw, hw, 0.0,
                [(2.8, "Wall"), (1.4, "Wall"), (1.0, "Wall"), (1.8, "Wall"), (1.0, "Wall")],
                bays={FRONT: [1.4, 2.2, 1.4, 1.8, 1.4, 2.2, 1.4], RIGHT: [2.0, 2.4, 8.2]},
                paint=cells({(FRONT, 1, 0): "AwningBlue", (FRONT, 5, 0): "AwningBlue", (FRONT, 3, 0): "Orange",
                             (FRONT, 1, 2): "Teal", (FRONT, 2, 2): "Teal", (FRONT, 3, 2): "Teal",
                             (FRONT, 4, 2): "Teal", (FRONT, 5, 2): "Teal",
                             (FRONT, 1, 3): "GlassDark", (FRONT, 2, 3): "GlassDark", (FRONT, 3, 3): "GlassDark",
                             (FRONT, 4, 3): "GlassDark", (FRONT, 5, 3): "GlassDark",
                             (RIGHT, 1, 0): "AwningBlue", (RIGHT, 1, 3): "AwningBlue"}))
    hip_roof(b, -hw - EAVE, -hw - EAVE, hw + EAVE, hw + EAVE, top - SINK, 10.0, "Teal", inset=4.5)
    # The tower, proud of the back and right faces (past the eave, so no
    # sliver of roof shows on its walls), through the roof.
    b.box(hw - 3.6, hw - 3.6, 0.0, hw + 0.6, hw + 0.6, 11.2, "Wall")
    hip_roof(b, hw - 4.0, hw - 4.0, hw + 1.0, hw + 1.0, 11.2 - SINK, 13.0, "Roof")
    return [("", b)]


# --- Kit_Town_Hall: town and village halls (18 x 16 x 26, 800 tris) -----------------------
def hall():
    """A civic hall: a cream two-storey body with a painted arcade all round
    the ground floor under stone string courses and tall windows, a
    terracotta hip, and a square clock tower proud of the front under a teal
    dome. The footprint is 18 x 26 (eaves and the tower included)."""
    b = Builder()
    hw, hd = 9.0 - EAVE, 13.0 - 0.5
    storeys = [(4.4, "Cream"), (0.5, "Stone"), (3.4, "Cream"), (0.5, "Stone"), (0.6, "Cream")]

    def arcade(side, col, row):
        if not odd(col):
            return "Stone" if row == 0 else None            # the arcade's pillars
        return "GlassDark" if row == 0 else ("Glass" if row == 2 else None)
    top = block(b, -hw, -hd, hw, hd, 0.0, storeys,
                bays={FRONT: bays_of(3, 1.6, 3.2), RIGHT: bays_of(5, 1.6, 3.2), LEFT: bays_of(5, 1.6, 3.2)},
                paint=arcade)
    hip_roof(b, -hw - EAVE, -hd - EAVE, hw + EAVE, hd + EAVE, top - SINK, 12.8, "Roof")
    # The tower: the entrance, a tall window, the clock faces, a stone cornice.
    tower = storeys + [(2.8, "Cream"), (0.6, "Stone"), (0.6, "Cream")]
    side_bays = {s: [1.2, 3.6, 1.2] for s in (FRONT, RIGHT, LEFT)}
    z = block(b, -3.0, -hd - 0.6, 3.0, -hd + 5.0, 0.0, tower, bays=side_bays,
              paint=lambda s, c, r: ({0: "GlassDark", 2: "Glass", 4: "Marking"}.get(r)
                                     if c == 1 and s in side_bays and (s == FRONT or r == 4) else None))
    lathe_rows(b, [(3.3, z - SINK, "Cream"), (3.3, z + 0.4, "Teal"), (3.1, z + 1.1, "Teal"), (2.5, z + 1.7, "Teal"),
                   (1.5, z + 2.1, "Teal"), (0.5, z + 2.3, "Cream"), (0.5, z + 2.7, "Cream"), (0.0, z + 2.9, None)],
               segments=12, cap_mat="Cream")
    return [("", b)]


# --- Kit_Town_Shed: harbour sheds (150 tris) ------------------------------------------------
def shed_a():
    """A, 12 x 9 x 10, a boathouse: steel walls, a teal gable to the water
    (the front), one big dark door in an orange frame."""
    b = Builder()
    hw, hd = 6.0 - EAVE, 5.0 - EAVE
    top = block(b, -hw, -hd, hw, hd, 0.0, [(4.2, "Steel"), (1.0, "Steel")],
                bays={FRONT: [1.6, 1.0, 6.0, 1.0, 1.6]},
                paint=cells({(FRONT, 2, 0): "RoofDark", (FRONT, 1, 0): "Orange", (FRONT, 3, 0): "Orange",
                             (FRONT, 2, 1): "Orange"}))
    gable_roof(b, hw, hd, top, 0.66, EAVE, 0.3, "Steel", "Teal")
    return [("", b)]


def shed_b():
    """B, 22 x 10 x 16, a fish shed: a long steel shed with a dark eave band,
    two big doors in orange frames on the front, a dark low-pitched roof
    with a raised ridge monitor."""
    b = Builder()
    hw, hd = 11.0 - EAVE, 8.0 - EAVE
    top = block(b, -hw, -hd, hw, hd, 0.0, [(5.0, "Steel"), (1.0, "RoofDark")],
                bays={FRONT: [2.5, 1.0, 5.0, 1.0, 2.0, 1.0, 5.0, 1.0, 2.5]},
                paint=cells({(FRONT, 2, 0): "RoofDark", (FRONT, 6, 0): "RoofDark", (FRONT, 1, 0): "Orange",
                             (FRONT, 3, 0): "Orange", (FRONT, 5, 0): "Orange", (FRONT, 7, 0): "Orange"}))
    ridge = gable_roof(b, hd, hw, top, 0.4, EAVE, 0.3, "Steel", "RoofDark", along="x")
    b.box(-6.0, -1.3, ridge - 0.9, 6.0, 1.3, 10.4, "Steel", top_mat="RoofDark")
    return [("", b)]


# --- Kit_Town_Lighthouse: the lighthouse (10 x 36 x 10, lantern to 40; 1,500 tris) ----------
LH_SEG = 16


def lighthouse():
    """A round white tower on a concrete plinth (a painted door on the front),
    tapering under two red bands to a gallery with a solid railing, the
    lantern (glowing lamp panes between steel mullions) under a dark cap and
    finial; a small store with a terracotta roof at its foot."""
    b = Builder()
    door = lambda k: "RoofDark" if k == 12 else "Concrete"       # segment 12 faces -Y
    panes = lambda k: "Lamp" if k % 2 == 0 else "Steel"
    rows = [(5.0, 0.0, door), (5.0, 2.2, "Wall"), (4.3, 2.2, "Wall"), (4.3, 7.0, "Lighthouse"), (4.1, 12.0, "Wall"),
            (3.8, 18.0, "Lighthouse"), (3.5, 23.0, "Wall"), (3.1, 31.0, "Wall"),
            # The gallery: its underside out to the rim, the rim, the railing up, in and down, the deck in.
            (4.7, 31.0, "Wall"), (4.7, 31.8, "Wall"), (4.7, 33.0, "Wall"), (4.1, 33.0, "Wall"), (4.1, 31.8, "Wall"),
            # The lantern and its cap.
            (2.6, 31.8, "Steel"), (2.6, 32.5, panes), (2.6, 35.3, "Steel"), (2.6, 35.9, "RoofDark"),
            (3.0, 35.9, "RoofDark"), (3.0, 36.3, "RoofDark"), (0.7, 38.6, "RoofDark"), (0.7, 39.3, "RoofDark"),
            (0.0, 39.7, None)]
    lathe_rows(b, rows, LH_SEG, cap_mat="Concrete")
    # The store: a corner of it shows out of the round plinth and tower (the
    # rest is inside), within the 10 x 10 footprint.
    top = block(b, 1.0, 1.5, 5.0, 5.0, 0.0, [(2.6, "Wall")], bays={RIGHT: [0.9, 1.6, 1.0]},
                paint=cells({(RIGHT, 1, 0): "Teal"}))
    hip_roof(b, 0.6, 1.1, 5.4, 5.4, top - SINK, 4.4, "Roof")
    return [("", b)]


# --- Kit_Town_Jetty and Kit_Town_Post: jetty decks and legs (60 / 12 tris) --------------------
def jetty():
    """A 6 x 2 x 60 timber deck: a plank slab with a pale kerb strip along
    each edge, carried on two edge beams reaching down to the origin, where
    gen_town stands the posts. Uniform along y (it is stretched 3.3-4.1x)."""
    b = Builder()
    hw, hl, kerb = 3.0, 30.0, 0.5
    cuts = [kerb / (2 * hw), 1.0 - kerb / (2 * hw)]
    b.box(-hw, -hl, 1.4, hw, hl, 2.0, "Trunk", top=False,
          columns=lambda s, _l: cuts if s in (FRONT, BACK) else [],
          cell=lambda s, c, r, u, z: "Stone" if s in (FRONT, BACK) and c != 1 else None)
    xs = [-hw, -hw + kerb, hw - kerb, hw]              # the top's strips share the sides' cuts
    for i in range(3):
        b.face([(xs[i], -hl, 2.0), (xs[i + 1], -hl, 2.0), (xs[i + 1], hl, 2.0), (xs[i], hl, 2.0)],
               "Trunk" if i == 1 else "Stone")
    for x in (-2.2, 2.2):
        b.box(x - 0.6, -hl, 0.0, x + 0.6, hl, 1.4 + SINK, "Trunk")
    return [("", b)]


def post():
    """A square 0.8 x 4 timber post (stretched 0.3-2x in height)."""
    b = Builder()
    b.box(-0.4, -0.4, 0.0, 0.4, 0.4, 4.0, "Trunk")
    return [("", b)]


# --- Kit_Town_Boat: moored boats (5 x 3 x 14, 400 tris) -------------------------------------
def hull(b, stations, gunwale, chine, mats, deck_mat):
    """A hull lofted through `stations` [(y, half width, deck z, keel z)]
    from the transom (first) to the stem (last: half width 0), each section a
    U of seven points: deck edge, gunwale, chine, keel and up the other side.
    Its three strips a side take `mats` (gunwale band, topsides, bottom).
    Closed by the deck and the transom. Smooth-shaded."""
    secs = []
    for y, hw, zd, zk in stations:
        zc = zk + (zd - zk) * chine
        secs.append([(-hw, y, zd), (-hw, y, zd - gunwale), (-hw * 0.8, y, zc), (0.0, y, zk),
                     (hw * 0.8, y, zc), (hw, y, zd - gunwale), (hw, y, zd)])
    strips = mats + mats[::-1]
    for a, c in zip(secs, secs[1:]):
        for k in range(6):
            b.face([a[k], a[k + 1], c[k + 1], c[k]], strips[k], True)
    b.face([s[0] for s in secs] + [s[6] for s in secs[::-1]], deck_mat)
    b.face(secs[0], mats[1])


def boat_a():
    """A, a fishing boat: a beamy blue hull with a white gunwale, a cream
    deck, a wheelhouse aft with a dark window band and a hold hatch forward."""
    b = Builder()
    hull(b, [(7.0, 1.9, 1.75, 0.55), (4.5, 2.3, 1.65, 0.15), (1.5, 2.5, 1.6, 0.0), (-1.5, 2.5, 1.65, 0.0),
             (-4.5, 2.1, 1.85, 0.2), (-6.3, 1.2, 2.1, 0.55), (-7.0, 0.0, 2.3, 1.0)],
         0.4, 0.45, ["Wall", "AwningBlue", "RoofDark"], "Cream")
    block(b, -1.7, 1.6, 1.7, 5.0, 1.5, [(0.75, "Wall"), (0.6, "GlassDark"), (0.2, "Wall")], top_mat="RoofDark")
    b.box(-1.2, -3.4, 1.4, 1.2, -0.8, 2.0, "RoofDark")
    b.box(-0.5, 5.4, 1.5, 0.5, 6.4, 2.3, "Orange")              # a buoy stack at the stern
    return [("", b)]


def boat_b():
    """B, a motor yacht: a sleek white hull with a teal boot stripe, a long
    low cabin with a dark window band, a flybridge and a radar arch."""
    b = Builder()
    hull(b, [(7.0, 2.2, 1.6, 0.7), (4.0, 2.5, 1.55, 0.2), (0.5, 2.5, 1.6, 0.0), (-3.0, 2.3, 1.75, 0.05),
             (-5.5, 1.6, 2.0, 0.35), (-7.0, 0.0, 2.3, 0.95)],
         0.9, 0.5, ["Wall", "Teal", "RoofDark"], "Wall")
    block(b, -1.9, -3.2, 1.9, 3.6, 1.45, [(0.45, "Wall"), (0.6, "GlassDark"), (0.15, "Wall")], top_mat="Wall")
    block(b, -1.4, 0.4, 1.4, 3.2, 2.65 - SINK, [(0.4, "GlassDark"), (0.1, "Wall")], top_mat="Wall")
    for x in (-1.7, 1.7):
        bar(b, (x, 3.4, 2.4), (x, 3.9, 2.95), 0.3, "Wall")
    bar(b, (-1.7, 3.9, 2.85), (1.7, 3.9, 2.85), 0.3, "Wall")
    return [("", b)]


# --- Kit_Farm_Barn: barns (16 x 10 x 26, 400 tris) ------------------------------------------
def isect(p, u, q, v):
    """Where the line through p along u meets the line through q along v (2D)."""
    px, pz = p
    ux, uz = u
    qx, qz = q
    vx, vz = v
    t = ((qx - px) * vz - (qz - pz) * vx) / (ux * vz - uz * vx)
    return (px + ux * t, pz + uz * t)


def braced_door(dw, dh, w):
    """A cross-braced door panel 2dw x dh, as polygons in the (x, z) plane:
    ([(polygon, material)], the vertices it leaves on the door's edges from
    (-dw, 0) anticlockwise, so the wall round it can share them). The X is
    two strips `w` either side of the diagonals: a diamond where they cross,
    four arms to the corners, four dark triangles between."""
    length = math.hypot(2 * dw, dh)
    xb = -dw + w * length / dh            # where a strip's edge meets the bottom (and top) edge
    zl = w * length / (2 * dw)            # ...and the side edges
    zb = dh / 2 - w * length / (2 * dw)   # the diamond's bottom corner
    xl = -w * length / dh                 # ...and left corner
    B, T, L, R = (0.0, zb), (0.0, dh - zb), (xl, dh / 2), (-xl, dh / 2)
    bl, br, tr, tl = (-dw, 0.0), (dw, 0.0), (dw, dh), (-dw, dh)
    polys = [
        ([bl, (xb, 0.0), B, L, (-dw, zl)], "Wall"), ([(-xb, 0.0), br, (dw, zl), R, B], "Wall"),
        ([(-dw, dh - zl), L, T, (xb, dh), tl], "Wall"), ([(-xb, dh), T, R, (dw, dh - zl), tr], "Wall"),
        ([B, R, T, L], "Wall"),
        ([(xb, 0.0), (-xb, 0.0), B], "RoofDark"), ([(-xb, dh), (xb, dh), T], "RoofDark"),
        ([(-dw, zl), L, (-dw, dh - zl)], "RoofDark"), ([(dw, dh - zl), R, (dw, zl)], "RoofDark"),
    ]
    edge = [bl, (xb, 0.0), (-xb, 0.0), br, (dw, zl), (dw, dh - zl), tr, (-xb, dh), (xb, dh), tl,
            (-dw, dh - zl), (-dw, zl)]
    return polys, edge


def barn():
    """A gambrel barn, red (Roof) with white trims: a white band under the
    eaves, a white frame round the big dark door on the front gable end with
    a white X brace painted on it, a dark roof with a ridge cupola."""
    b = Builder()
    hw, hd, ze = 7.5, 12.5, 5.6
    dw, dh, f, zb = 3.0, 3.6, 0.8, ze - 1.0
    polys, edge = braced_door(dw, dh, 0.4)
    y = -hd
    at = lambda pts: [(x, y, z) for x, z in pts]
    for poly, mat in polys:
        b.face(at(poly), mat)
    # The frame (sharing the door's edge vertices), then the walls round it.
    e = {p: p for p in edge}
    left_edge = [p for p in edge if p[0] == -dw and 0.0 < p[1] < dh]           # bottom to top
    right_edge = [p for p in edge if p[0] == dw and 0.0 < p[1] < dh]
    top_edge = sorted([p for p in edge if p[1] == dh and -dw < p[0] < dw])
    bottom_edge = sorted([p for p in edge if p[1] == 0.0 and -dw < p[0] < dw])
    b.face(at([(-dw - f, 0.0), (-dw, 0.0)] + sorted(left_edge, key=lambda p: p[1]) + [(-dw, dh), (-dw - f, dh)]), "Wall")
    b.face(at([(dw, 0.0), (dw + f, 0.0), (dw + f, dh), (dw, dh)] + sorted(right_edge, key=lambda p: -p[1])), "Wall")
    b.face(at([(-dw - f, dh), (-dw, dh)] + top_edge + [(dw, dh), (dw + f, dh), (dw + f, dh + f), (-dw - f, dh + f)]), "Wall")
    b.face(at([(-hw, 0.0), (-dw - f, 0.0), (-dw - f, dh), (-dw - f, dh + f), (-hw, dh + f)]), "Roof")
    b.face(at([(dw + f, 0.0), (hw, 0.0), (hw, dh + f), (dw + f, dh + f), (dw + f, dh)]), "Roof")
    b.face(at([(-hw, dh + f), (-dw - f, dh + f), (dw + f, dh + f), (hw, dh + f), (hw, zb), (-hw, zb)]), "Roof")
    # The other walls, the eave band round all four, the caps (the bottom
    # carrying every vertex along the front's foot).
    b.face([(hw, hd, 0.0), (-hw, hd, 0.0), (-hw, hd, zb), (hw, hd, zb)], "Roof")
    b.face([(-hw, hd, 0.0), (-hw, -hd, 0.0), (-hw, -hd, dh + f), (-hw, -hd, zb), (-hw, hd, zb)], "Roof")
    b.face([(hw, -hd, 0.0), (hw, hd, 0.0), (hw, hd, zb), (hw, -hd, zb), (hw, -hd, dh + f)], "Roof")
    corners = [(-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd)]
    for k in range(4):
        (x0, y0), (x1, y1) = corners[k], corners[(k + 1) % 4]
        b.face([(x0, y0, zb), (x1, y1, zb), (x1, y1, ze), (x0, y0, ze)], "Wall")
    b.face([(x, yy, ze) for x, yy in corners], "Roof")
    foot = [(-hw, 0.0), (-dw - f, 0.0), (-dw, 0.0)] + bottom_edge + [(dw, 0.0), (dw + f, 0.0), (hw, 0.0)]
    b.face(at(foot)[::-1] + [(-hw, hd, 0.0), (hw, hd, 0.0)], "Roof")
    gambrel_roof(b, hw, hd, ze, 5.0, 8.1, 9.4, 0.5, 0.35, "Roof", "RoofDark")
    # The cupola on the ridge.
    b.box(-0.8, -0.8, 8.6, 0.8, 0.8, 9.9, "Wall")
    hip_roof(b, -1.1, -1.1, 1.1, 1.1, 9.9 - SINK, 10.45, "RoofDark")
    return [("", b)]


# --- Kit_Farm_Silo: silos (7 x 18 x 7, 200 tris) --------------------------------------------
def silo():
    """A steel drum with a pale band at the top under a domed teal cap."""
    b = Builder()
    lathe_rows(b, [(3.5, 0.0, "Steel"), (3.5, 13.2, "Wall"), (3.5, 14.8, "Teal"), (3.2, 16.2, "Teal"),
                   (2.3, 17.3, "Teal"), (1.0, 17.9, "Teal"), (0.0, 18.0, None)], 12, cap_mat="Steel")
    return [("", b)]


# --- Previews from the air ------------------------------------------------------------------
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


def stand(scene, name, at, turn, scale=(1.0, 1.0, 1.0)):
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


def fitted(family, letters, size, rng):
    """The variant of `family` that `size` (w, h, d) stretches the least (one
    of the near-best at random, as settlement.Placer.put()), and its scale."""
    found = []
    for letter in letters:
        name = "%s_%s" % (family, letter)
        lo, hi = bounds(bpy.data.collections[name])
        own = (hi.x - lo.x, hi.z - lo.z, hi.y - lo.y)
        cost = sum(abs(math.log(size[i] / own[i])) for i in range(3))
        found.append((cost, name, (size[0] / own[0], size[2] / own[2], size[1] / own[1])))
    least = min(c for c, _, _ in found)
    near = [f for f in found if f[0] <= least + 0.2]
    _, name, scale = near[rng.randrange(len(near))]
    return name, scale


def slab(scene, name, x0, y0, z0, x1, y1, z1, mat):
    b = Builder()
    b.box(x0, y0, z0, x1, y1, z1, mat)
    scene.collection.objects.link(b.object(name))


def ground(scene, half, z, mat):
    b = Builder()
    b.face([(-half, -half, z), (half, -half, z), (half, half, z), (-half, half, z)], mat)
    scene.collection.objects.link(b.object("Ground"))


def headland(scene, at, r0, r1, z0, z1):
    """A faceted rock mound for the lighthouse to stand on."""
    b = Builder()
    rng = random.Random(5)
    rings = []
    for r, z in ((r0, z0), (r1, z1)):
        rings.append([(at[0] + r * (1 + rng.uniform(-0.15, 0.15)) * math.cos(2 * math.pi * k / 8),
                       at[1] + r * (1 + rng.uniform(-0.15, 0.15)) * math.sin(2 * math.pi * k / 8), z) for k in range(8)])
    for k in range(8):
        k1 = (k + 1) % 8
        b.face([rings[0][k], rings[0][k1], rings[1][k1], rings[1][k]], "Rock")
    b.face(rings[0][::-1], "Rock")
    b.face(rings[1], "TreeLight")
    scene.collection.objects.link(b.object("Headland"))


def render(scene, eye, target, path, size=(1280, 720), lens=35):
    """Renders `scene` (Workbench, palette colours, outlines, shadows) from `eye` towards `target`."""
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
    shading.show_object_outline = True
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


def town_previews(out):
    """A street of houses fitted to lots of the sizes gen_town asks for (with
    the hall and a shed), and the harbour: the jetty stretched 3.7x on its
    posts, boats beside it, the sheds on the quay, the lighthouse on its
    headland; each seen from 150 m away and 40 m up, and from higher."""
    os.makedirs(out, exist_ok=True)
    rng = random.Random(7)
    # The street: lots either side of a road, fronts to the road.
    scene = bpy.data.scenes.new("Street")
    ground(scene, 600.0, 0.0, "FieldGreen")
    slab(scene, "Road", -140.0, -6.0, -0.5, 140.0, 6.0, 0.05, "Road")
    for side in (1.0, -1.0):
        x = -120.0
        while x < 110.0:
            w, h, d = rng.uniform(8.0, 22.0), rng.uniform(7.0, 14.0), rng.uniform(6.0, 16.0)
            name, scale = fitted("Kit_Town_House", "ABCD", (w, h, d), rng)
            stand(scene, name, (x + w / 2, side * (10.0 + d / 2), 0.0), 0.0 if side > 0 else math.pi, scale)
            x += w + rng.uniform(3.0, 7.0)
    stand(scene, "Kit_Town_Hall", (0.0, 60.0, 0.0), 0.0)
    stand(scene, "Kit_Farm_Barn", (-60.0, 70.0, 0.0), 0.4)
    stand(scene, "Kit_Farm_Silo", (-40.0, 85.0, 0.0), 0.0)
    for k in range(5):
        stand(scene, "Kit_Tree_Broadleaf_%s" % rng.choice("ABC"), (-110.0 + 55.0 * k, 45.0, -0.3), rng.uniform(0, 6.0),
              (1.1, 1.1, 1.1))
    render(scene, (0.0, -165.0, 40.0), (0.0, 5.0, 4.0), os.path.join(out, "street_low.png"))
    render(scene, (70.0, -150.0, 130.0), (0.0, 10.0, 0.0), os.path.join(out, "street_high.png"))
    render(scene, (25.0, -62.0, 20.0), (0.0, 12.0, 4.0), os.path.join(out, "street_close.png"))
    bpy.data.scenes.remove(scene)
    # The harbour: the sea at 0, the quay 4 m up, the jetty from its edge.
    scene = bpy.data.scenes.new("Harbour")
    ground(scene, 900.0, 0.0, "Water")
    slab(scene, "Quay", -260.0, 0.0, -3.0, 260.0, 320.0, 4.0, "Pavement")
    top, jt = 4.6, 2.0
    for jx, stretch in ((0.0, 3.7), (90.0, 3.4)):
        length = 60.0 * stretch
        stand(scene, "Kit_Town_Jetty", (jx, -length / 2, top - jt), 0.0, (1.0, stretch, 1.0))
        for k in range(int(length // 15.0) + 1):
            along = -min(k * 15.0 + 2.0, length - 1.0)
            for sx in (-2.2, 2.2):
                stand(scene, "Kit_Town_Post", (jx + sx, along, -6.0), 0.0, (1.0, 1.0, (top - jt + 6.0) / 4.0))
        for n in range(2):
            side = -1.0 if n else 1.0
            stand(scene, "Kit_Town_Boat_%s" % rng.choice("AB"), (jx + side * 7.5, -rng.uniform(60.0, length - 20.0), -BOAT_SUNK),
                  0.0, (1.0, 1.0, 1.0))
    stand(scene, "Kit_Town_Boat_B", (-40.0, -70.0, -BOAT_SUNK), 0.6)
    for x, name, w, h, d in ((-60.0, "Kit_Town_Shed_A", 12.0, 9.0, 10.0), (-30.0, "Kit_Town_Shed_B", 22.0, 10.0, 16.0),
                             (40.0, "Kit_Town_Shed_A", 9.0, 8.0, 8.0), (60.0, "Kit_Town_Shed_B", 18.0, 11.0, 12.0)):
        own = bounds(bpy.data.collections[name])
        size = (own[1].x - own[0].x, own[1].z - own[0].z, own[1].y - own[0].y)
        stand(scene, name, (x, 12.0 + d / 2, 4.0), 0.0, (w / size[0], d / size[2], h / size[1]))
    for x in (-110.0, -85.0, 110.0, 135.0):
        w, h, d = rng.uniform(9.0, 16.0), rng.uniform(7.0, 12.0), rng.uniform(8.0, 14.0)
        name, scale = fitted("Kit_Town_House", "ABCD", (w, h, d), rng)
        stand(scene, name, (x, 14.0 + d / 2, 4.0), 0.0, scale)
    headland(scene, (200.0, -60.0), 55.0, 32.0, -3.0, 12.0)
    stand(scene, "Kit_Town_Lighthouse", (200.0, -60.0, 11.5), 0.0)
    stand(scene, "Kit_Town_House_A", (214.0, -44.0, 11.6), 0.0)
    render(scene, (-30.0, -300.0, 40.0), (30.0, -60.0, 4.0), os.path.join(out, "harbour_low.png"))
    render(scene, (120.0, -330.0, 150.0), (40.0, -40.0, 0.0), os.path.join(out, "harbour_high.png"))
    render(scene, (-30.0, -170.0, 18.0), (5.0, -40.0, 4.0), os.path.join(out, "harbour_close.png"))
    render(scene, (120.0, -220.0, 40.0), (200.0, -60.0, 20.0), os.path.join(out, "lighthouse.png"))
    bpy.data.scenes.remove(scene)
    print("town previews in " + out)


# --- The batch ------------------------------------------------------------------------------
PIECES = [
    ("Kit_Town_House_A", house_a), ("Kit_Town_House_B", house_b),
    ("Kit_Town_House_C", house_c), ("Kit_Town_House_D", house_d),
    ("Kit_Town_Hall", hall),
    ("Kit_Town_Shed_A", shed_a), ("Kit_Town_Shed_B", shed_b),
    ("Kit_Town_Lighthouse", lighthouse),
    ("Kit_Town_Jetty", jetty), ("Kit_Town_Post", post),
    ("Kit_Town_Boat_A", boat_a), ("Kit_Town_Boat_B", boat_b),
    ("Kit_Farm_Barn", barn), ("Kit_Farm_Silo", silo),
]


def main():
    kt.begin("kit_town", 4)
    for name, build in PIECES:
        kt.piece(name, build())
    kt.finish()
    if os.environ.get("KIT_TOWN_PREVIEW"):
        town_previews(os.environ["KIT_TOWN_PREVIEW"])


if __name__ == "__main__":
    main()
