"""The spaceport's and the outposts' kit pieces (models/fichina/ASSETS.md,
"Batch 3: the spaceport and the outposts"): the landing pads, the terminal,
the ship hangars and the control tower of the spaceport in the south-east,
and the radomes, research modules, drilling rigs and dish antennas of the
outposts on the high ground. gen_outposts.py places every one at its own
size (the modules are fitted to their lots), so each keeps the footprint the
brief gives, with its front (doors, the dish's face) on -Y.

    KIT_OUT=<copy.blend> KIT_PREVIEW=<dir> blender --background --python kit_outposts.py

One function per piece, each returning [(suffix, Builder)] for
kit_tools.piece(). Every piece stands on Z = 0 with its origin at the centre
of its footprint.

Shells: a roof slab, a snow cap, a mast, a leg or an annex is its own closed
shell sunk SINK into the part it stands on, and a roof's ends stand PROUD of
the wall faces below, so no two faces of different shells share a plane
(coplanar faces flicker) and no two shells share an edge. Doors, windows,
stripes, number panels and the pad's marks are painted: cells of the
surface's own faces in another material, so they draw no ink line. The
look: white Panel and PanelGrey insulated bodies, Concrete plinths and
decks, DarkMetal frames, legs and machinery, Signal orange end blocks and
bands, SignalYellow / HazardBlack hazard stripes, WindowLit windows for the
polar dusk, Snow caps on every flat or gently sloped roof, Lamp floodlights
and a few LightStrip edges.
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # models/fichina/source
import fichina_common as cc  # noqa: E402,F401  (first: makes kit_tools serve Fichina)
import kit_tools as kt  # noqa: E402
from kit_tools import Builder  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

SINK = 0.1       # how far a part sinks into the one it stands on
PROUD = 0.02     # how far a roof's ends stand out from the wall faces under it
LIGHT = 0.6      # a painted LightStrip edge band is this wide
TIP = 1.6        # the WarningLight at a mast's tip is this tall
SNOW = 0.5       # a snow cap slab is this thick above the roof it sits on

FRONT, RIGHT, BACK, LEFT = 0, 1, 2, 3   # a box's sides, as prism() numbers them


# --- Helpers (block, cells, cut, loft, circle_arc, vault, mast, hazard: as kit_base.py) ----
def block(b, x0, y0, x1, y1, z0, storeys, bays=None, paint=None, top_mat=None, bottom=True, bottom_mat=None):
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
          top_mat=top_mat or storeys[-1][1], bottom=bottom, bottom_mat=bottom_mat)
    return z1


def cells(painted):
    """A paint function from {(side, bay, row): material}."""
    return lambda side, col, row: painted.get((side, col, row))


def snow_cap(b, x0, y0, x1, y1, z_roof, inset=0.4, thick=SNOW):
    """A Snow slab lying on a flat roof: inset from its edges (so no side
    shares the wall's plane) and sunk SINK into it. Returns its top z."""
    b.box(x0 + inset, y0 + inset, z_roof - SINK, x1 - inset, y1 - inset, z_roof + thick, "Snow")
    return z_roof + thick


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
    the origin: `rows` [(scale, z, material of the band above)]; a collar,
    a canted cab. cell(side, column, row) -> material paints single cells."""
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
    Bands across a vault and along it are cells of the same shell."""
    ys = [y0] + [y0 + (y1 - y0) * f for f in sorted(strips)] + [y1]
    n = len(profile)
    for s in range(n):
        (ax, az), (bx, bz) = profile[s], profile[(s + 1) % n]
        for j in range(len(ys) - 1):
            m = (cell(s, j) if cell else None) or mat
            b.face([(ax, ys[j], az), (ax, ys[j + 1], az), (bx, ys[j + 1], bz), (bx, ys[j], bz)], m, smooth)
    b.face([(x, y0, z) for x, z in profile], cap_mat or mat)
    b.face([(x, y1, z) for x, z in profile[::-1]], cap_mat or mat)


def mast(b, x, y, z0, height, r=0.6, segments=8, mat="Steel"):
    """A round mast standing on z0 (sunk SINK) with a WarningLight tip."""
    with b.at(Matrix.Translation((x, y, 0.0))):
        b.lathe([(r, z0 - SINK), (r, z0 + height - TIP), (r, z0 + height - 0.3), (0.0, z0 + height)], mat,
                segments=segments, cell=lambda k, row: "WarningLight" if row > 0 else None)


def hazard(c):
    """SignalYellow / HazardBlack alternating by column: a painted hazard stripe."""
    return "SignalYellow" if c % 2 == 0 else "HazardBlack"


def frustum(b, c0, s0, z0, c1, s1, z1, mat):
    """A solid tapering leg: a square section `s0` wide centred on (x, y) `c0`
    at z0 to one `s1` wide centred on `c1` at z1 (its sides stay planar, as
    both sections are axis-aligned squares)."""
    def ring(c, s, z):
        h = s / 2
        return [(c[0] - h, c[1] - h, z), (c[0] + h, c[1] - h, z), (c[0] + h, c[1] + h, z), (c[0] - h, c[1] + h, z)]
    lo, hi = ring(c0, s0, z0), ring(c1, s1, z1)
    for i in range(4):
        j = (i + 1) % 4
        b.face([lo[i], lo[j], hi[j], hi[i]], mat)
    b.face(lo[::-1], mat)
    b.face(hi, mat)


def beam(b, p0, p1, w, mat, ext=0.0):
    """A square `w` beam from point p0 to p1 (a strut), each end pushed `ext`
    further so it sinks into what it joins."""
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    up = "Y" if abs(d.normalized().y) < 0.9 else "X"
    m = Matrix.Translation(p0) @ d.to_track_quat("Z", up).to_matrix().to_4x4()
    with b.at(m):
        b.box(-w / 2, -w / 2, -ext, w / 2, w / 2, d.length + ext, mat)


def lamp(b, x0, y0, z0, x1, y1, z1, side=FRONT):
    """A floodlight head: a DarkMetal box whose `side` face and underside glow Lamp."""
    b.box(x0, y0, z0, x1, y1, z1, "DarkMetal", cell=lambda s, c, r, u, z: "Lamp" if s == side else None,
          bottom_mat="Lamp")


# --- Kit_Port_Pad: 60 x 3 x 60, 500 tris ----------------------------------------------------
def pad():
    """A round landing pad: a smooth drum, DarkMetal rim under a Concrete
    deck edge, its top painted from the edge in: a ring of Lamp edge lights
    (every other cell), a white Marking ring, then the deck with an orange
    Signal chevron pointing to the front and a white T at the back, painted
    on a square grid inside the ring (its corners on the ring's polygon at
    45 degrees); four fans fill between the square and the ring."""
    b = Builder()
    R, segs, z_rim, z_top = 30.0, 24, 1.0, 3.0
    r_lamp, r_mark = 28.4, 25.4

    def p(rr, z, k):
        a = 2 * math.pi * k / segs
        return (rr * math.cos(a), rr * math.sin(a), z)
    for k in range(segs):
        k1 = (k + 1) % segs
        b.face([p(R, 0.0, k), p(R, 0.0, k1), p(R, z_rim, k1), p(R, z_rim, k)], "DarkMetal", True)
        b.face([p(R, z_rim, k), p(R, z_rim, k1), p(R, z_top, k1), p(R, z_top, k)], "Concrete", True)
        b.face([p(R, z_top, k), p(R, z_top, k1), p(r_lamp, z_top, k1), p(r_lamp, z_top, k)],
               "Lamp" if k % 2 == 0 else "Concrete")
        b.face([p(r_lamp, z_top, k), p(r_lamp, z_top, k1), p(r_mark, z_top, k1), p(r_mark, z_top, k)], "Marking")
    b.face([p(R, 0.0, k) for k in range(segs)][::-1], "DarkMetal")
    q, n = segs // 8, 9
    for c in range(4):                      # the fans: the arc from one corner to the next, back along the
        k0 = q + 2 * q * c                  # chord through the grid's edge points (no T-junctions)
        a, d = Vector(p(r_mark, z_top, k0)), Vector(p(r_mark, z_top, (k0 + 2 * q) % segs))
        b.face([p(r_mark, z_top, (k0 + i) % segs) for i in range(2 * q + 1)]
               + [tuple(d.lerp(a, i / n)) for i in range(1, n)], "Concrete")
    h = r_mark * math.cos(math.pi / 4)

    def mark(i, j):                         # i along x, j along y from the front (-Y)
        if j == 0 and i == 4 or 1 <= j <= 3 and abs(i - 4) in (j - 1, j):
            return "Signal"                 # the chevron, two cells thick, its point at the front
        if j == 7 and 2 <= i <= 6 or i == 4 and 5 <= j <= 6:
            return "Marking"                # the T at the back
        return None
    b.grid((-h, -h, z_top), (2 * h, 0.0, 0.0), (0.0, 2 * h, 0.0), n, n, mark, "Concrete")
    return [("", b)]


# --- Kit_Port_Terminal: 90 x 20 x 40, 1,500 tris --------------------------------------------
def terminal():
    """The terminal: a long body whose front bows out in a smooth curve of
    glass (a lit lower band, an upper band of alternating dark and lit
    glazing) on a Concrete plinth, the lit lobby doors in the middle between
    Signal frames; a LightStrip edge under the snow-capped roof; two taller
    Signal end blocks with rows of lit windows; a glass control cab on the
    roof with a warning-light mast, a small radome and roof plant."""
    b = Builder()
    hw, y_back, y_front, z_body = 36.0, 19.7, -12.0, 14.0
    arc_segs = 12
    arc = circle_arc(hw, 8.0, 0.0, arc_segs)                # the front bows 8 m, from y_front to -20
    outline = [(x, y_front - z) for x, z in arc] + [(hw, y_back), (-hw, y_back)]
    n_arc = arc_segs                                        # sides 0..11: the arc; 12 right, 13 back, 14 left
    S_RIGHT, S_BACK, S_LEFT = n_arc, n_arc + 1, n_arc + 2
    rows = [(1.5, "Concrete"), (3.0, "Panel"), (3.0, "WindowLit"), (1.0, "Panel"), (3.5, "GlassDark"),
            (1.4, "Panel"), (LIGHT, "LightStrip")]
    levels, z = [], 0.0
    for h, _ in rows[:-1]:
        z += h
        levels.append(z)

    def columns(s, length):
        k = {S_BACK: 6, S_RIGHT: 3, S_LEFT: 3}.get(s, 1)
        return [i / k for i in range(1, k)]

    def paint(s, c, r):
        if s < n_arc:                                       # the curved glass front
            if r == 1:
                return {5: "WindowLit", 6: "WindowLit", 4: "Signal", 7: "Signal"}.get(s)
            if r == 4:
                return "WindowLit" if s % 2 else None
            return None
        if s == S_BACK:
            if r == 2:
                return "Panel" if c % 2 else None
            if r == 4:
                return "WindowLit" if c % 2 else None
            return "Signal" if (c, r) == (3, 1) else None
        return "Panel" if r == 2 and c % 2 else None
    b.prism(outline, 0.0, z_body, "Panel", levels=levels, columns=columns,
            cell=lambda s, c, r, u, z: paint(s, c, r) or rows[r][1], top_mat="RoofDark")
    # The snow cap: the same outline drawn in towards the origin, so its
    # sides stand clear of the walls' planes.
    b.prism([(x * 0.985, y * 0.985) for x, y in outline], z_body - SINK, z_body + SNOW, "Snow")
    # The end blocks: Signal, with lit windows in rows on the front and the
    # outer side, standing proud of the body's back and front.
    end_rows = [(3.0, "Signal"), (2.5, "Signal"), (1.5, "Signal"), (2.5, "Signal"), (1.5, "Signal"),
                (2.5, "Signal"), (4.5, "Signal")]
    side_bays = [2.65] + [3.0, 2.0] * 4 + [3.0, 2.65]
    for sign in (-1.0, 1.0):
        x0, x1 = min(sign * 35.0, sign * 45.0), max(sign * 35.0, sign * 45.0)
        outer = RIGHT if sign > 0 else LEFT

        def paint_end(s, c, r, outer=outer):
            if r not in (1, 3, 5):
                return None
            if s == FRONT:
                return "WindowLit" if c in (1, 3) else None
            if s == outer:
                return ("WindowLit" if r != 3 else "GlassDark") if c % 2 else None
            return None
        top = block(b, x0, -14.3, x1, 20.0, 0.0, end_rows, bays={FRONT: [1.5, 2.5, 2.0, 2.5, 1.5], outer: side_bays},
                    paint=paint_end, top_mat="RoofDark")
        snow_cap(b, x0, -14.3, x1, 20.0, top)
    # The control cab on the roof: a Panel sill, lit and dark panes between
    # Panel mullions, a dark roof with its snow cap and the mast.
    cx0, cy0, cx1, cy1 = -14.0, -4.0, -4.0, 6.0
    cab_bays = [1.0, 3.5, 1.0, 3.5, 1.0]
    z_cab = block(b, cx0, cy0, cx1, cy1, z_body - SINK, [(1.2, "Panel"), (2.6, "GlassDark"), (0.8, "DarkMetal")],
                  bays={FRONT: cab_bays, RIGHT: cab_bays, BACK: cab_bays, LEFT: cab_bays},
                  paint=lambda s, c, r: ("Panel" if c % 2 == 0 else ("WindowLit" if (s + c) % 4 == 1 else None))
                  if r == 1 else None, top_mat="RoofDark")
    z_snow = snow_cap(b, cx0, cy0, cx1, cy1, z_cab)
    mast(b, cx0 + 1.4, cy1 - 1.4, z_snow, 20.0 - z_snow, r=0.5)
    # A small radome and roof plant on the main roof.
    with b.at(Matrix.Translation((20.0, 8.0, 0.0))):
        zc, rr = z_body + 2.4, 2.6
        profile = [(1.6, z_body + SNOW - SINK), (1.6, zc - 1.8)]
        for k in range(1, 6):
            a = -math.asin(1.8 / rr) + (math.pi / 2 + math.asin(1.8 / rr)) * k / 5
            profile.append((rr * math.cos(a) if k < 5 else 0.0, zc + rr * math.sin(a)))
        b.lathe(profile, "Panel", segments=10, cap_mat="DarkMetal")
    for x, y in ((8.0, 10.0), (14.0, 10.0), (-24.0, 12.0)):
        b.box(x, y, z_body + SNOW - SINK, x + 3.0, y + 4.0, z_body + 2.2, "DarkMetal")
    return [("", b)]


# --- Kit_Port_Hangar: 70 x 26 x 60, 1,000 tris --------------------------------------------
HANGAR_W, HANGAR_H, HANGAR_D = 70.0, 26.0, 60.0
HANGAR_WALL = 15.0           # the walls' top; the vault rises from there to HANGAR_H
DOOR_LEAVES = 6              # columns per door leaf: the lintel's hazard blocks


def hangar():
    """A ship hangar: PanelGrey walls under a smooth Steel barrel vault whose
    top is painted Snow, with a LightStrip ridge and a yellow band over the
    door end. The front is two huge painted DarkMetal door leaves in a
    SignalYellow frame under a yellow-and-black lintel, with a white number
    panel (a black "1") above the seam; the sides carry dark buttress piers
    under a continuous lit window strip, the back a small door. Two
    floodlight masts stand at the front corners."""
    b = Builder()
    hw, hd = HANGAR_W / 2, HANGAR_D / 2
    rows = [(11.0, "PanelGrey"), (1.5, "PanelGrey"), (HANGAR_WALL - 12.5, "PanelGrey")]  # doors, lintel, upper band
    leaf = 28.0 / DOOR_LEAVES
    front = [5.2, 1.2] + [leaf] * DOOR_LEAVES + [1.2] + [leaf] * DOOR_LEAVES + [1.2, 5.2]
    seam, last = DOOR_LEAVES + 2, len(front) - 1
    side = [2.5] + [11.0, 2.0] * 4 + [2.5]
    back = [26.0, 1.0, 6.0, 1.0, 26.0]

    def paint(s, c, r):
        if s == FRONT:
            if c in (0, last):
                return "WindowLit" if r == 1 else None
            if c in (1, last - 1):                                   # the frame
                return "SignalYellow" if r < 2 else None
            if c == seam:                                            # the leaves' seam, the panel's digit
                return ["SignalYellow", "SignalYellow", "HazardBlack"][r]
            if r == 0:
                return "DarkMetal"
            if r == 1:
                return hazard(c)
            return "Marking" if c in (seam - 1, seam + 1) else None
        if r == 1:
            return "WindowLit" if s != BACK or c % 2 == 0 else None   # the lit strip along the sides
        if s == BACK:
            return {1: "SignalYellow", 2: "DarkMetal", 3: "SignalYellow"}.get(c) if r == 0 else None
        return "DarkMetal" if c % 2 == 0 and r == 0 else None        # the piers
    top = block(b, -hw, -hd, hw, hd, 0.0, rows, bays={FRONT: front, RIGHT: side, LEFT: side, BACK: back},
                paint=paint)
    # The vault: a circular arc (the same turn at every step, so only its
    # eaves crease) with a flat ridge strip, from the wall tops to HANGAR_H;
    # its upper half painted Snow.
    xe, segs = hw + PROUD, 10
    arc = circle_arc(xe, HANGAR_H - top, top, segs, apex=1.8)
    profile = [(-xe, top - SINK), (xe, top - SINK)] + arc[::-1]
    ridge = 2 + segs // 2                 # the side index of the ridge strip in the profile
    band = 2.5 / (HANGAR_D + 2 * PROUD)   # the yellow band over the door end

    def roof(s, strip):
        if s < 2 or s == len(profile) - 1:
            return "PanelGrey"                                       # the sunk bottom and the eave slivers
        if s == ridge:
            return "LightStrip"
        if abs(s - ridge) <= 3:
            return "Snow"
        return "SignalYellow" if strip == 0 else None
    vault(b, profile, -hd - PROUD, hd + PROUD, "Steel", strips=[band], cell=roof, cap_mat="PanelGrey")
    # The floodlight masts: a Steel pole with a lit head, at each front corner.
    for x in (-hw + 1.8, hw - 1.8):
        y = -hd + 1.8
        with b.at(Matrix.Translation((x, y, 0.0))):
            b.lathe([(0.6, 0.0), (0.6, 19.0)], "Steel", segments=8)
            lamp(b, -1.4, -0.9, 18.7, 1.4, 0.9, 20.1)
    return [("", b)]


# --- Kit_Port_Tower: 16 x 45 x 16, 1,200 tris ------------------------------------------------
def port_tower():
    """The control tower: a Concrete annex with a lit window band and a
    Signal door under a snowed roof; a Panel shaft with a Signal band and a
    dark stair slit up the front; a flared collar carries a gallery deck
    and the cab: lit and dark glass panes between Panel mullions, canted
    outward, under a dark roof slab edged with a light strip and capped
    with snow; a mast with a warning light and an aerial."""
    b = Builder()
    hw = 8.0
    # The annex: concrete, a lit window band, an orange door; snow on top.
    top = block(b, -hw, -hw, hw, hw, 0.0, [(3.0, "Concrete"), (1.5, "WindowLit")],
                bays={FRONT: [5.0, 2.4, 8.6]}, paint=cells({(FRONT, 1, 0): "Signal"}), top_mat="RoofDark")
    snow_cap(b, -hw, -hw, hw, hw, top)
    # The shaft: 7 x 7, the slit on the front, the orange band.
    s = 3.5
    z_shaft = block(b, -s, -s, s, s, top - SINK, [(20.0, "Panel"), (1.5, "Signal"), (4.5, "Panel")],
                    bays={FRONT: [2.4, 2.2, 2.4]},
                    paint=lambda side, c, r: "GlassDark" if (side, c) == (FRONT, 1) and r != 1 else None)
    # The collar flaring out under the deck slab (its bottom ring inside the
    # shaft, a little smaller so no side shares the shaft's plane).
    square = [(-s, -s), (s, -s), (s, s), (-s, s)]
    pts, tags = cut(square, {})
    loft(b, pts, tags, [(6.8 / 7.0, z_shaft - 0.3, "Concrete"), (10.6 / 7.0, z_shaft + 2.0, "Concrete")])
    z_deck = z_shaft + 2.0
    b.box(-6.0, -6.0, z_deck - SINK, 6.0, 6.0, z_deck + 1.1, "Concrete", top_mat="RoofDark")
    # The cab: a sill ring inside the deck slab, the canted glass storey
    # with a mullion at each corner and two between, a dark top band.
    cab_w = 15.0
    pane = (cab_w - 4.0) / 3.0
    widths = [1.0, pane, 1.0, pane, 1.0, pane, 1.0]
    fr = [sum(widths[:i + 1]) / cab_w for i in range(len(widths) - 1)]
    outline = [(-cab_w / 2, -cab_w / 2), (cab_w / 2, -cab_w / 2), (cab_w / 2, cab_w / 2), (-cab_w / 2, cab_w / 2)]
    pts, tags = cut(outline, {FRONT: fr, RIGHT: fr, BACK: fr, LEFT: fr})
    z_cab = z_deck + 1.0

    def panes(side, c, r):
        if r != 1:
            return None
        if c % 2 == 0:
            return "Panel"
        return "WindowLit" if (side + c) % 4 != 3 else None
    loft(b, pts, tags, [(10.0 / cab_w, z_cab, "Panel"), (10.4 / cab_w, z_cab + 0.8, "GlassDark"),
                        (1.0, z_cab + 5.5, "DarkMetal"), (1.0, z_cab + 6.3, "DarkMetal")],
         cell=panes, top_mat="RoofDark")
    z_roof = z_cab + 6.3
    # The roof slab with its light strip edge, its snow cap, the mast and a short aerial.
    block(b, -hw, -hw, hw, hw, z_roof - SINK, [(0.9, "RoofDark"), (LIGHT, "LightStrip")], top_mat="RoofDark")
    z_top = snow_cap(b, -hw, -hw, hw, hw, z_roof - SINK + 0.9 + LIGHT, inset=0.5)
    mast(b, 5.6, 5.6, z_top, 45.0 - z_top, r=0.5)
    b.box(-6.4, -6.4, z_top - SINK, -5.2, -5.2, z_top + 2.0, "Steel")
    return [("", b)]


# --- Kit_Outpost_Radar: 18 x 22 x 18, 1,000 tris -----------------------------------------
def radar():
    """A radome: a white smooth sphere on a Steel drum (a lit window band,
    an orange band) over a square concrete plinth with a yellow top stripe
    and a dark door, snow on the plinth; a red light at the dome's pole, a
    lit equipment box."""
    b = Builder()
    hw, r_drum, r_dome, zc = 9.0, 6.5, 8.5, 13.5
    top = block(b, -hw, -hw, hw, hw, 0.0, [(2.4, "Concrete"), (1.0, "SignalYellow")],
                bays={FRONT: [7.0, 2.4, 8.6]}, paint=cells({(FRONT, 1, 0): "DarkMetal"}), top_mat="Snow")
    # The drum, then the sphere from where its radius equals the drum's, one lathe.
    z_meet = zc - math.sqrt(r_dome ** 2 - r_drum ** 2)
    profile = [(r_drum, top - SINK), (r_drum, top + 1.6), (r_drum, top + 3.4), (r_drum, z_meet)]
    a0, rings = math.asin((z_meet - zc) / r_dome), 11
    for k in range(1, rings + 1):
        a = a0 + (math.pi / 2 - a0) * k / rings
        profile.append((r_dome * math.cos(a) if k < rings else 0.0, zc + r_dome * math.sin(a)))
    drum_mats = ["Steel", "WindowLit", "Signal"]
    b.lathe(profile, "Panel", segments=16,
            cell=lambda k, row: drum_mats[row] if row < 3 else ("WarningLight" if row == len(profile) - 2 else None),
            cap_mat="Steel")
    b.box(3.0, -8.0, top - SINK, 7.5, -5.0, top + 2.0, "DarkMetal",
          cell=lambda s, c, r, u, z: "WindowLit" if s == FRONT else None)
    return [("", b)]


# --- Kit_Outpost_Module: A 24 x 10 x 12, B 18 x 9 x 12, 250 tris each ---------------------
LEG_H = 2.5      # the modules stand this high on their legs
LEG_W = 1.2      # ...which are this thick


def legs(b, xs, ys, z_body, size=LEG_W):
    """Four chunky DarkMetal legs at x in xs, y in ys, up into the body."""
    for x in xs:
        for y in ys:
            b.box(x - size / 2, y - size / 2, 0.0, x + size / 2, y + size / 2, z_body + SINK, "DarkMetal")


def ramp(b, x0, x1, y_edge, z_body):
    """A DarkMetal ramp (a wedge x0..x1 wide) up into the body's floor from
    its front edge `y_edge`: it runs under the body, from the ground at the
    edge back and up 5 m, so it stays inside the footprint."""
    with b.at(Matrix.Rotation(math.pi / 2, 4, "Z")):      # local x -> world y, local y -> world -x
        b.extrude([(y_edge, 0.0), (y_edge + 5.0, 0.0), (y_edge + 5.0, z_body + SINK)], -x1, -x0, "DarkMetal")


def module_a():
    """A: a long stadium-shaped Signal capsule on four legs: a dark floor
    band, a lit window strip (alternating lit and orange cells round the
    ends), a lit door in the middle of the front, a snowed roof with a
    vent, a ramp to the door."""
    b = Builder()
    rx, ry, segs = 6.0, 6.0, 6                               # the ends' semicircles
    outline = []
    for cx, a0 in ((rx, -math.pi / 2), (-rx, math.pi / 2)):
        for k in range(segs + 1):
            a = a0 + math.pi * k / segs
            outline.append((cx + ry * math.cos(a), ry * math.sin(a)))
    S_BACK, S_FRONT = segs, 2 * segs + 1
    rows = [(0.8, "DarkMetal"), (2.4, "Signal"), (1.4, "WindowLit"), (2.4, "Signal")]
    levels, z = [], LEG_H
    for h, _ in rows[:-1]:
        z += h
        levels.append(z)
    z_top = LEG_H + sum(h for h, _ in rows)

    def columns(s, _length):
        return [1 / 3, 2 / 3] if s in (S_BACK, S_FRONT) else []

    def paint(s, c, r, _u, _z):
        if r == 2:
            return "Signal" if s not in (S_BACK, S_FRONT) and s % 2 else "WindowLit"
        return "WindowLit" if (s, c, r) == (S_FRONT, 1, 1) else rows[r][1]
    b.prism(outline, LEG_H, z_top, "Signal", levels=levels, columns=columns, cell=paint,
            top_mat="Snow", bottom_mat="DarkMetal")
    legs(b, (-7.0, 7.0), (-3.5, 3.5), LEG_H)
    ramp(b, -1.8, 1.8, -ry, LEG_H)
    b.box(3.0, -1.5, z_top - SINK, 6.0, 1.5, z_top + 0.5, "DarkMetal")
    return [("", b)]


def module_b():
    """B: a shorter PanelGrey module under a smooth barrel roof painted Snow
    on top, Signal end walls, wide lit windows and a Signal band along each
    side, on four legs, with a small radome on the roof and a ramp."""
    b = Builder()
    hx, hy, z_wall = 9.0, 6.0, LEG_H + 2.0
    arc = circle_arc(hy, 4.0, z_wall, 8)
    profile = [(-hy, LEG_H), (hy, LEG_H), (hy, z_wall)] + arc[::-1][1:]
    n_arc, S_RIGHT, S_LEFT = 8, 1, 10                        # sides: 0 floor, 1 wall, 2..9 the arc, 10 wall
    strips = [0.15, 0.35, 0.65, 0.85]

    def paint(s, strip):
        if s in (S_RIGHT, S_LEFT):
            return {1: "WindowLit", 3: "WindowLit", 2: "Signal"}.get(strip)
        if 4 <= s <= 7:
            return "Snow"
        return "Signal" if strip == 2 and s != 0 else None
    with b.at(Matrix.Rotation(math.pi / 2, 4, "Z")):      # the vault runs along world x
        vault(b, profile, -hx, hx, "PanelGrey", strips=strips, cell=paint, cap_mat="Signal")
    legs(b, (-5.5, 5.5), (-3.5, 3.5), LEG_H)
    ramp(b, -1.8, 1.8, -hy, LEG_H)
    with b.at(Matrix.Translation((4.0, 0.0, 0.0))):
        z0 = z_wall + 4.0
        b.lathe([(1.4, z0 - 0.6), (1.4, z0 + 0.1), (1.0, z0 + 0.4), (0.0, z0 + 0.5)], "Panel", segments=6,
                cap_mat="DarkMetal")
    return [("", b)]


# --- Kit_Outpost_Drill: 20 x 60 x 20, 1,000 tris -------------------------------------------
def drill():
    """A drilling rig: a DarkMetal machinery house with a painted hazard
    stripe, a lit door and two floodlights, snow on its roof; a tapering
    SignalYellow derrick of four solid legs tied by three rings of chunky
    girth beams, a Steel drill string up its middle to a hazard-striped
    crown platform with a dark crown block, floodlights and a mast with a
    warning light."""
    b = Builder()
    hw, z_house = 10.0, 9.0
    bays = [2.5] * 8

    def paint(s, c, r):
        if r == 1:
            return hazard(c)
        return "WindowLit" if (s, c, r) == (FRONT, 3, 0) else None
    block(b, -hw, -hw, hw, hw, 0.0, [(5.0, "DarkMetal"), (1.5, "DarkMetal"), (2.5, "DarkMetal")],
          bays={FRONT: bays, RIGHT: bays, BACK: bays, LEFT: bays}, paint=paint, top_mat="RoofDark")
    z_snow = snow_cap(b, -hw, -hw, hw, hw, z_house, inset=0.5)
    for x in (-5.5, 5.5):                                   # floodlights on the roof's front edge, between the legs
        lamp(b, x - 0.9, -hw + 0.8, z_snow - SINK, x + 0.9, -hw + 2.0, z_snow + 1.3)
    # The derrick: legs from the roof's corners leaning in to the crown.
    z0, z1 = z_house + SNOW - SINK, 54.0
    c0, c1, s0, s1 = 8.2, 3.4, 1.8, 1.2
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            frustum(b, (sx * c0, sy * c0), s0, z0, (sx * c1, sy * c1), s1, z1 + 0.2, "SignalYellow")
    for z in (21.0, 33.0, 45.0):
        c = c0 + (c1 - c0) * (z - z0) / (z1 - z0)
        for sgn in (-1.0, 1.0):
            b.box(-c, sgn * c - 0.5, z - 0.5, c, sgn * c + 0.5, z + 0.5, "SignalYellow")
            b.box(sgn * c - 0.5, -c, z - 0.5, sgn * c + 0.5, c, z + 0.5, "SignalYellow")
    b.lathe([(0.6, z0), (0.6, z1 + 0.6)], "Steel", segments=8)
    # The crown: a hazard-striped platform, the crown block, floodlights, the mast.
    plat = [2.5] * 4
    block(b, -5.0, -5.0, 5.0, 5.0, z1, [(1.2, "SignalYellow")], bays={FRONT: plat, RIGHT: plat, BACK: plat, LEFT: plat},
          paint=lambda s, c, r: hazard(c), top_mat="RoofDark", bottom_mat="RoofDark")
    z_plat = z1 + 1.2
    b.box(-2.5, -2.5, z_plat - SINK, 2.5, 2.5, z_plat + 2.8, "DarkMetal")
    for x in (-1.6, 1.6):
        lamp(b, x - 0.7, -3.2, z_plat + 0.8, x + 0.7, -2.4, z_plat + 2.0)
    mast(b, 0.0, 0.0, z_plat + 2.8, 60.0 - (z_plat + 2.8), r=0.5)
    return [("", b)]


# --- Kit_Outpost_Dish: 40 x 40 x 40, 1,200 tris -------------------------------------------
DISH_R, DISH_F, DISH_TILT = 19.5, 14.0, math.radians(50.0)   # radius, focal length, tilt from straight up
DISH_PIVOT = 19.2                                             # the tilt axle's height: the rim's top at 40 m


def dish():
    """A large radio dish: a smooth paraboloid (Panel inside, PanelGrey
    behind, a DarkMetal rim, two Signal radial stripes) tilted up towards
    the front on a DarkMetal yoke (a hub behind the dish on a Steel axle
    between two arms over a drum pedestal with a Signal band) standing on a
    Concrete plinth with a hazard stripe and a snowed top; a feed horn on
    three chunky struts at the focus; a lit equipment cabin on the plinth."""
    b = Builder()
    # The plinth, the pedestal, the yoke block and its arms.
    bays = [2.0] * 7
    top = block(b, -7.0, -7.0, 7.0, 7.0, 0.0, [(1.5, "Concrete"), (1.0, "Concrete")],
                bays={FRONT: bays, RIGHT: bays, BACK: bays, LEFT: bays},
                paint=lambda s, c, r: hazard(c) if r == 1 else None, top_mat="Snow")
    z_pivot = DISH_PIVOT
    b.lathe([(3.5, top - SINK), (3.5, 8.0), (3.5, 9.2), (3.5, 12.0)], "DarkMetal", segments=12,
            cell=lambda k, row: "Signal" if row == 1 else None)
    b.box(-5.0, -3.0, 12.0 - SINK, 5.0, 3.0, 14.0, "DarkMetal")
    for sx in (-1.0, 1.0):
        b.box(min(sx * 3.7, sx * 5.3), -1.2, 14.0 - SINK, max(sx * 3.7, sx * 5.3), 1.2, z_pivot + 0.6, "DarkMetal")
    with b.at(Matrix.Translation((0.0, 0.0, z_pivot)) @ Matrix.Rotation(math.pi / 2, 4, "Y")):
        b.lathe([(1.0, -6.5), (1.0, 6.5)], "Steel", segments=8)
    # The equipment cabin on the plinth.
    z_cab = block(b, -6.5, 2.0, -2.5, 6.5, top - SINK, [(1.0, "Panel"), (1.2, "Panel"), (0.9, "Panel")],
                  bays={FRONT: [0.8, 2.4, 0.8], LEFT: [0.8, 2.9, 0.8]},
                  paint=lambda s, c, r: "WindowLit" if r == 1 and c == 1 and s in (FRONT, LEFT) else None,
                  top_mat="RoofDark")
    snow_cap(b, -6.5, 2.0, -2.5, 6.5, z_cab, inset=0.3, thick=0.3)
    # The dish about the pivot: its axis is local Z, tilted DISH_TILT towards the front.
    with b.at(Matrix.Translation((0.0, 0.0, z_pivot)) @ Matrix.Rotation(DISH_TILT, 4, "X")):
        zb = lambda r: 1.5 + r * r / (4.0 * DISH_F)           # the back surface: the vertex 1.5 above the pivot
        rs = [DISH_R * k / 4 for k in range(5)]
        profile = [(r, zb(r)) for r in rs] + [(DISH_R, zb(DISH_R) + 0.8)] + [(r, zb(r) + 0.8) for r in rs[::-1]]

        def skin(k, row):
            if row < 4:
                return "PanelGrey"
            if row == 4:
                return "DarkMetal"
            return "Signal" if k in (0, 12) else "Panel"
        b.lathe(profile, "Panel", segments=24, cell=skin)
        b.box(-5.5, -2.0, -3.5, 5.5, 2.0, 1.6, "DarkMetal")  # the hub, holding the axle, into the dish's back
        focus = (0.0, 0.0, 1.5 + DISH_F)
        b.box(-1.5, -1.5, focus[2] - 1.5, 1.5, 1.5, focus[2] + 1.5, "DarkMetal", bottom_mat="Signal")
        for a in (math.pi / 2, math.pi * 7 / 6, math.pi * 11 / 6):
            rr = DISH_R - 0.5                                     # the strut starts inside the rim band
            beam(b, (rr * math.cos(a), rr * math.sin(a), zb(rr) + 0.4), focus, 1.0, "DarkMetal")
    return [("", b)]


# --- The batch -------------------------------------------------------------------------------
PIECES = [
    ("Kit_Port_Pad", pad), ("Kit_Port_Terminal", terminal), ("Kit_Port_Hangar", hangar),
    ("Kit_Port_Tower", port_tower), ("Kit_Outpost_Radar", radar),
    ("Kit_Outpost_Module_A", module_a), ("Kit_Outpost_Module_B", module_b),
    ("Kit_Outpost_Drill", drill), ("Kit_Outpost_Dish", dish),
]


def main():
    kt.begin("kit_outposts", 2)
    for name, build in PIECES:
        kt.piece(name, build())
    kt.finish()


if __name__ == "__main__":
    main()
