"""The colony's buildings (models/fichina/ASSETS.md, batch 1, row 0): the
habitat blocks Kit_Colony_Hab_A..D, the tower stacks Kit_Colony_Tower_A/B
(_Base, _Shaft, _Crown with joint plugs), the cabins Kit_Colony_Cabin_A..C,
the depots Kit_Colony_Depot_A..C, the tanks Kit_Colony_Tank_A/B, the comms
mast Kit_Colony_Mast, the walkway Kit_Colony_Tube, and the pipeline pieces
Kit_Pipe and Kit_Pipe_Support.

    KIT_OUT=<copy.blend> KIT_PREVIEW=<dir> blender --background --python kit_colony.py

Every piece stands on Z = 0 with its origin at the centre of its footprint
and its front (entrance, doors) on -Y. Stack parts have their origin at the
centre of their own bottom; the shafts repeat seamlessly (one outline top and
bottom, bands in whole storeys), joints are open (no caps where parts join
flush) and every shaft and crown carries a "<part>_Plug" sleeve, as the
Corneria stacks do (kit_city_high.py).

Shells: legs, roof boxes, masts and annexes are their own closed shells sunk
SINK into what they stand on (nothing floats, nothing shares a plane), and a
roof block's ends stand PROUD of the wall faces under it. Windows, doors,
bands and stripes are painted: cells of the walls' own faces in another
material, so they draw no ink line. Snow lies on the roofs as a painted top
face or a sunk slab.

Arctic look: Panel / PanelGrey bodies raised on DarkMetal legs or Concrete
plinths, Signal orange accents (whole modules, stair towers, roof bands),
WindowLit painted generously for the polar dusk, GlassDark for unlit glazing.
"""

import math
import os
import sys

import bmesh
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # models/fichina/source
import fichina_common as cc  # noqa: E402,F401  first: makes kit_tools serve Fichina
import kit_tools as kt  # noqa: E402
from kit_tools import Builder  # noqa: E402

SINK = 0.1                         # a part sinks this far into the one it stands on
PROUD = 0.02                       # a roof block's ends stand this far out from the walls under it
STOREY = 4.0                       # one floor
TOWER_SHAFT = 2 * STOREY           # tower shafts: two storeys (see tower_a's docstring)
TIP = 2.0                          # the WarningLight at a mast's tip is this tall
PLUG_INSET = 0.05                  # a joint plug sits this far inside the wall...
PLUG_BELOW, PLUG_ABOVE = 0.4, 0.1  # ...from this far into the part below to this far into its own part


# --- Outlines and painting -----------------------------------------------------------------
def rect(hw, hd):
    """A 2hw x 2hd rectangle anticlockwise from above: (outline, side tags
    R, B, L, F: right, back, left, front)."""
    return [(hw, -hd), (hw, hd), (-hw, hd), (-hw, -hd)], ["R", "B", "L", "F"]


def rounded(hw, hd, r, segs=4, corners="FR BR BL FL"):
    """The rectangle with the named corners rounded off by `r` in `segs` arcs
    (1: a chamfer): (outline, side tags: the flats R/B/L/F, each arc's
    sides its corner's name, "FR" etc.)."""
    out, tags = [], []
    for name, (cx, cy), a0, after in (("FR", (hw - r, -hd + r), -90.0, "R"), ("BR", (hw - r, hd - r), 0.0, "B"),
                                        ("BL", (-hw + r, hd - r), 90.0, "L"), ("FL", (-hw + r, -hd + r), 180.0, "F")):
        if name in corners.split():
            for i in range(segs + 1):
                a = math.radians(a0 + 90.0 * i / segs)
                out.append((cx + r * math.cos(a), cy + r * math.sin(a)))
                tags.append(name if i < segs else after)
        else:
            out.append((cx + (r if "R" in name else -r), cy + (r if "B" in name else -r)))
            tags.append(after)
    return out, tags


def stadium(hw, hd, segs=7):
    """A 2hw x 2hd slab with semicircular ends (radius hd) in `segs` arcs
    each (7: 25.7 degree facets, smooth-shaded): (outline anticlockwise
    from above, side tags: the arcs "R" / "L", the flats "B" / "F")."""
    out, tags = [], []
    cx = hw - hd
    for i in range(segs + 1):
        a = math.radians(-90.0 + 180.0 * i / segs)
        out.append((cx + hd * math.cos(a), hd * math.sin(a)))
        tags.append("R" if i < segs else "B")
    for i in range(segs + 1):
        a = math.radians(90.0 + 180.0 * i / segs)
        out.append((-cx + hd * math.cos(a), hd * math.sin(a)))
        tags.append("L" if i < segs else "F")
    return out, tags


def soften(col, max_angle=math.radians(30.5)):
    """Clears the sharp mark on the edges of `col`'s meshes whose smooth
    faces meet at up to `max_angle`. kit_tools creases at 30 degrees, and
    a quarter circle in three segments meets at exactly that, where float
    noise creases some facets and not others (measured: 4 of 12)."""
    if col is None:
        return
    for o in col.objects:
        if o.type != "MESH":
            continue
        me = o.data
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.edges.index_update()
        soft = {e.index for e in bm.edges
                if len(e.link_faces) == 2 and all(f.smooth for f in e.link_faces)
                and e.calc_face_angle(0.0) <= max_angle}
        bm.free()
        for e in me.edges:
            if e.index in soft:
                e.use_edge_sharp = False


def fit(widths, length):
    """Column cut fractions for bays `widths` scaled to fill a side."""
    total, acc, cuts = sum(widths), 0.0, []
    for w in widths[:-1]:
        acc += w
        cuts.append(acc / total)
    return cuts


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


def walls(b, outline, tags, z0, storeys, bays=None, paint=None, top=True, top_mat=None, bottom=True,
          bottom_mat=None, smooth=False):
    """Walls on `outline` from z0: `storeys` [(height, material)] stack up
    the sides and paint them all round. `bays` {side tag: [widths]} cuts a
    side into bays (scaled to fit), and paint(tag, bay, row) -> a material
    (None: the storey's) paints single cells: windows, doors, stripes. The
    top is `top_mat` or the top storey's. Returns the top z."""
    levels, z = [], z0
    for h, _ in storeys[:-1]:
        z += h
        levels.append(z)
    z1 = z0 + sum(h for h, _ in storeys)
    bays = bays or {}
    columns = lambda s, length: fit(bays[tags[s]], length) if tags[s] in bays else []
    cell = lambda s, c, r, _u, _z: (paint(tags[s], c, r) if paint else None) or storeys[r][1]
    b.prism(outline, z0, z1, storeys[-1][1], levels=levels, columns=columns, cell=cell, top=top, bottom=bottom,
            top_mat=top_mat or storeys[-1][1], bottom_mat=bottom_mat, smooth=smooth)
    return z1


def cells(painted):
    """A paint function from {(tag, bay, row): material}."""
    return lambda tag, col, row: painted.get((tag, col, row))


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


def arc(hw, rise, z0, segments, inner=0.0):
    """Points of a half-ellipse from (-hw, z0) over (0, z0 + rise) to (hw, z0),
    left to right, `inner` metres inside it."""
    pts = []
    for k in range(segments + 1):
        t = math.pi - math.pi * k / segments
        pts.append(((hw - inner) * math.cos(t), z0 + (rise - inner) * math.sin(t)))
    return pts


# --- Parts ---------------------------------------------------------------------------------------
def legs(b, spots, z1, size=1.2, mat="DarkMetal"):
    """Chunky square stilts `size` across at `spots` [(x, y)], from the
    ground up into the body that starts at z1."""
    h = size / 2.0
    for x, y in spots:
        b.box(x - h, y - h, 0.0, x + h, y + h, z1 + SINK, mat)


def lathe_rows(b, rows, segments=16, cap_mat=None, bottom=True, top=True, turn=0.0, mat="Panel"):
    """A lathe from `rows` [(radius, z, material of the band above the ring)]:
    the material may be a function of the segment (a strip painted round).
    Unlike Builder.lathe() it can leave an end open (`bottom`, `top`: a
    stack part's joint), so it builds its own faces. `turn` rotates the
    first vertex, so a flat can face the front."""
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
                   (m(k) if callable(m) else m) or mat, True)
    if bottom and rows[0][0] > 0.0:
        b.face(rings[0][::-1], cap_mat or mat)
    if top and rows[-1][0] > 0.0:
        b.face(rings[-1], cap_mat or mat)


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


def mast(b, z0, height, r=0.9, segments=8, mat="DarkMetal"):
    """An antenna standing on z0 (sunk SINK): a drum `r` thick with a
    LightStrip band that steps thinner halfway, and a WarningLight tip."""
    top, mid, r2 = z0 + height, z0 + height * 0.45, r * 0.55
    lathe_rows(b, [(r, z0 - SINK, mat), (r, mid - 1.0, "LightStrip"), (r, mid, mat),
                   (r2, mid, mat), (r2, top - TIP, "WarningLight"), (0.0, top, None)], segments, mat=mat)


def dome(b, cx, cy, z0, r=1.3, mat="Panel", segments=8):
    """A small radar dome on a roof at (cx, cy, z0), sunk SINK."""
    with b.at(Matrix.Translation((cx, cy, 0.0))):
        b.lathe([(r, z0 - SINK), (r, z0 + 0.5 * r), (0.8 * r, z0 + 1.05 * r), (0.0, z0 + 1.4 * r)], mat,
                segments=segments)


def vent(b, x, y, z0, w=2.0, d=2.0, h=1.4, mat="DarkMetal"):
    """A roof vent box standing on z0 (sunk SINK), its top painted Snow."""
    b.box(x - w / 2, y - d / 2, z0 - SINK, x + w / 2, y + d / 2, z0 + h, mat, top_mat="Snow")


def frustum(b, lo, hi, mat):
    """A closed tapered block through four bottom corners `lo` and four top
    corners `hi` (anticlockwise from above)."""
    b.face(lo[::-1], mat)
    for k in range(4):
        k1 = (k + 1) % 4
        b.face([lo[k], lo[k1], hi[k1], hi[k]], mat)
    b.face(hi, mat)


def plug(outline, mat):
    """A joint plug factory for a part whose bottom is `outline`: each call
    makes the sleeve (PLUG_INSET inside the wall, PLUG_BELOW to PLUG_ABOVE
    about the joint) as a new Builder."""
    def make():
        b = Builder()
        b.prism(inset(outline, PLUG_INSET), -PLUG_BELOW, PLUG_ABOVE, mat)
        return b
    return make


def round_plug(r, segments, mat, turn=0.0):
    """The joint plug factory for a drum of radius `r`, lathed like it."""
    def make():
        b = Builder()
        b.lathe([(r - PLUG_INSET, -PLUG_BELOW), (r - PLUG_INSET, PLUG_ABOVE)], mat, segments=segments, turn=turn)
        return b
    return make


# --- Kit_Colony_Hab: habitat blocks (300 tris) -----------------------------------------------------
def hab_a():
    """A, 30 x 12 x 14: a long slab with semicircular ends (smooth) on four
    chunky legs, two lit window bands (dark on the back and the left end),
    a Signal stair tower proud of the left end, a lit entrance under a
    Signal sign on the front and a snowed-over roof."""
    b = Builder()
    outline, tags = stadium(15.0, 7.0)
    legs(b, [(x, y) for x in (-8.0, 8.0) for y in (-3.5, 3.5)], 2.0, size=1.6)

    def paint(tag, c, r):
        if tag == "F" and c == 1:            # the entrance bay: a lit doorway up into the band, a Signal sign above
            return "WindowLit" if r == 0 else ("Signal" if r == 2 else None)
        if r in (1, 3):                      # the window bands: lit on the front and the right end, dark behind
            return "GlassDark" if tag in ("B", "L") else None
        return None
    walls(b, outline, tags, 2.0,
          [(1.0, "PanelGrey"), (2.0, "WindowLit"), (1.8, "Panel"), (2.0, "WindowLit"), (2.8, "Panel")],
          bays={"F": [9.0, 3.0, 8.0]}, paint=paint, top_mat="Snow", smooth=True)
    b.box(-15.3, -3.0, 0.0, -11.0, 3.0, 12.0, "Signal", top_mat="Snow")          # the stair tower, through the end
    vent(b, 6.0, 2.0, 11.6, 3.0, 2.0, 0.4)
    return [("", b)]


def hab_b():
    """B, 20 x 16 x 20: a three-storey block with chamfered corners on a
    solid Concrete plinth, a window band a storey (lit and dark mixed), a
    Signal roof band and stair tower, a radar dome on the snowed roof."""
    b = Builder()
    outline, tags = rounded(10.0, 10.0, 2.5, segs=1)
    b.box(-9.5, -9.5, 0.0, 9.5, 9.5, 2.0 + SINK, "Concrete")
    dark = {("R", 1), ("B", 1), ("L", 1), ("F", 3), ("L", 5), ("BR", 5), ("BL", 5)}

    def paint(tag, c, r):
        if tag == "F" and c == 1:
            return "WindowLit" if r == 0 else ("Signal" if r == 1 else None)
        return "GlassDark" if (tag, r) in dark else None
    walls(b, outline, tags, 2.0,
          [(1.5, "Panel"), (2.3, "WindowLit"), (1.5, "Panel"), (2.3, "WindowLit"), (1.5, "Panel"),
           (2.3, "WindowLit"), (0.6, "Signal")],
          bays={"F": [6.0, 3.0, 11.0]}, paint=paint, top_mat="Snow")
    b.box(5.0, 4.0, 0.0, 10.2, 10.2, 16.0, "Signal", top_mat="Snow")              # the stair tower, proud of the corner
    dome(b, -5.0, -4.0, 14.0, r=1.4)
    vent(b, -2.0, 5.0, 14.0, 3.0, 2.0, 1.0)
    return [("", b)]


def hab_c():
    """C, 14 x 9 x 10: small, two storeys, mostly Signal orange with a Panel
    end, on four legs; a lit doorway on the front, snow on the roof."""
    b = Builder()
    outline, tags = stadium(7.0, 5.0)
    legs(b, [(x, y) for x in (-3.5, 3.5) for y in (-2.5, 2.5)], 1.8)

    def paint(tag, c, r):
        if tag == "F" and c == 1:
            return "WindowLit" if r == 0 else ("Panel" if r == 2 else None)
        if tag == "L":                                                             # the Panel end
            return "GlassDark" if r in (1, 3) else "Panel"
        return None
    walls(b, outline, tags, 1.8,
          [(1.0, "Signal"), (1.6, "WindowLit"), (1.2, "Signal"), (1.6, "WindowLit"), (1.4, "Signal")],
          bays={"F": [3.0, 2.4, 3.6]}, paint=paint, top_mat="Snow", smooth=True)
    vent(b, 3.5, 1.5, 8.6, 2.0, 2.0, 0.4)
    return [("", b)]


def hab_d():
    """D, 24 x 10 x 16: a barrel-vaulted hall on a Concrete plinth, a lit
    window band low on each side of the vault, snow along its top, a
    Signal entrance block with a lit door on the front and a plant box on
    the back."""
    b = Builder()
    hw, hd = 12.0, 7.0
    b.box(-11.0, -6.0, 0.0, 11.0, 6.0, 1.6, "Concrete")
    z0, segs = 1.5, 8
    vault = arc(hw, 10.0 - 4.0, 4.0, segs)       # from the left over to the right
    outline = [(-hw, z0), (hw, z0)] + vault[::-1]
    # Sides: 0 underside, 1 right wall, 2..9 the arc from the right, 10 left wall.
    strip = {0: "DarkMetal", 2: "WindowLit", 5: "Snow", 6: "Snow", 9: "WindowLit"}
    b.extrude(outline, -hd, hd, "Panel", cell=lambda s: strip.get(s), smooth=True)
    with b.at(Matrix.Translation((0.0, -hd - 1.0 + SINK, 0.0))):                 # the entrance block, sunk into the end wall
        walls(b, *rect(6.0, 1.1), z0, [(3.4, "Signal"), (1.0, "Signal")], bays={"F": [4.0, 4.0, 4.0]},
              paint=cells({("F", 1, 0): "WindowLit"}), top_mat="Snow")
    b.box(-4.0, hd - 1.0, z0, 4.0, hd + 1.0, 5.6, "DarkMetal", top_mat="Snow")    # the plant box on the back
    return [("", b)]


# --- Kit_Colony_Tower: colony towers (stacks; base 400, shaft 200, crown 800) --------------------
def tower_a():
    """A, 28 x 28 with rounded corners (16 sides, smooth): Panel with a
    WindowLit and a GlassDark band a storey, a Signal stair core wrapping
    the front-right corner; a snow-topped podium with a lit lobby; a crown
    with a LightStrip band, a snowed roof, a plant house and a mast.

    The shaft is two storeys (8 m), not the brief's three: the 16-sided
    outline at six band rows plus the plug would cost 264 triangles against
    the 200 budget; two storeys fit it at 196, and the generator stacks as
    many as the height asks. The corners' three segments meet at 30
    degrees, kit_tools' crease angle: soften() keeps them smooth."""
    hw, r = 14.0, 4.0
    outline, tags = rounded(hw, hw, r, segs=3)
    podium, _ = rounded(hw + 2.5, hw + 2.5, r + 2.5, segs=3)   # the same side count, so the roof ring can share every vertex
    core = lambda s, length: [1.0 - 4.0 / length] if tags[s] == "F" else []   # the stair strip beside the FR corner
    on_core = lambda s, c: tags[s] == "FR" or (tags[s] == "F" and c == 1)
    storey = [(1.5, "Panel"), (2.5, "WindowLit"), (1.5, "Panel"), (2.5, "GlassDark")]
    paint = lambda s, c, r, u, z: "Signal" if on_core(s, c) else None
    # Base (13 m): the podium (a concrete step, the lit lobby, a Panel edge)
    # with a snowed ring roof, then the drum's bands up to a dark one, so
    # the shaft's Panel floor line sits above it. One open shell, cut at
    # the stair strip's fractions throughout.
    base = Builder()
    base.prism(podium, 0.0, 5.0, "Panel", levels=[1.0, 4.2], columns=core, top=False, bottom_mat="RoofDark",
               cell=lambda s, c, r, u, z: "Concrete" if r == 0 else (
                   "Signal" if on_core(s, c) else ("WindowLit" if r == 1 else None)), smooth=True)
    skirt(base, podium, outline, 5.0, core, "Snow")
    base.prism(outline, 5.0, 13.0, "Panel", levels=[6.5, 9.0, 10.5], columns=core, top=False, bottom=False,
               smooth=True, cell=lambda s, c, r, u, z: paint(s, c, r, u, z) or storey[r][1])
    base.box(-5.0, -hw - 3.1, 3.6, 5.0, -hw - 2.2, 4.4, "Signal")                  # the entrance canopy
    # Shaft (8 m): two storeys of the bands, walls only.
    shaft = Builder()
    levels = [1.5, 4.0, 5.5]
    shaft.prism(outline, 0.0, TOWER_SHAFT, "Panel", levels=levels, columns=core, top=False, bottom=False,
                smooth=True, cell=lambda s, c, r, u, z: paint(s, c, r, u, z) or storey[r][1])
    # Crown (15 m): a Panel parapet under a LightStrip band, the roof
    # snowed, a plant house with a lit band, vents, a dome and the mast.
    crown = Builder()
    crown.prism(outline, 0.0, 3.0, "Panel", levels=[2.0], columns=core, top_mat="Snow", bottom=False, smooth=True,
                cell=lambda s, c, r, u, z: "LightStrip" if r == 1 else ("Signal" if on_core(s, c) else None))
    crown.box(-8.0, -2.0, 3.0 - SINK, 6.0, 9.0, 7.5, "DarkMetal", levels=[4.4, 5.8], top_mat="Snow",
              cell=lambda s, c, r, u, z: "WindowLit" if r == 1 else None)
    vent(crown, -8.0, -9.0, 3.0, 3.0, 3.0, 1.6)
    vent(crown, -2.5, -9.0, 3.0, 3.0, 3.0, 1.6)
    dome(crown, 8.5, -8.5, 3.0, r=2.0)
    with crown.at(Matrix.Translation((9.0, 9.0, 0.0))):
        mast(crown, 3.0, 12.0, 1.0)
    return base, shaft, crown, plug(outline, "Panel")


def tower_b():
    """B, 30 across, a drum (16 segments, smooth): Panel with a WindowLit
    and a GlassDark band a storey and a Signal stair strip up the front; a
    ring podium with a lit lobby under a snowed roof; a crown with a
    LightStrip rim round a glazed observation deck under a snowed dome,
    and a mast. Two-storey shaft, as tower_a."""
    r, seg, turn = 15.0, 16, math.pi / 16          # turned so segment 11 faces the front
    front = 11
    strip = lambda m: (lambda k: "Signal" if k == front else m)
    storey = [("Panel", 1.5), ("WindowLit", 2.5), ("Panel", 1.5), ("GlassDark", 2.5)]
    # Base (13 m): the podium ring, its snowed roof, then the drum's bands.
    base = Builder()
    rows = [(17.0, 0.0, "Concrete"), (17.0, 1.0, strip("WindowLit")), (17.0, 4.2, strip("Panel")), (17.0, 5.0, "Snow")]
    z = 5.0
    for m, h in storey:
        rows.append((r, z, strip(m)))
        z += h
    rows.append((r, z, None))
    lathe_rows(base, rows, seg, cap_mat="RoofDark", top=False, turn=turn)
    base.box(-5.0, -17.6, 3.6, 5.0, -16.4, 4.4, "Signal")                           # the entrance canopy
    # Shaft (8 m): walls only.
    shaft = Builder()
    rows, z = [], 0.0
    for m, h in storey:
        rows.append((r, z, strip(m)))
        z += h
    rows.append((r, z, None))
    lathe_rows(shaft, rows, seg, bottom=False, top=False, turn=turn)
    # Crown (20 m): a Panel band under the LightStrip rim, a snowed ring
    # deck, the glazed observation storey set back, the dome, the mast.
    crown = Builder()
    lathe_rows(crown, [(r, 0.0, strip("Panel")), (r, 2.3, "LightStrip"), (r, 3.0, "Snow"), (11.0, 3.0, "WindowLit"),
                       (11.0, 5.5, "Panel"), (11.0, 6.4, "Panel"), (10.3, 7.5, "Panel"), (8.3, 8.7, "Snow"),
                       (5.0, 9.6, "Snow"), (0.0, 10.0, None)], seg, bottom=False, turn=turn)
    mast(crown, 9.9, 10.1, 1.0)
    return base, shaft, crown, round_plug(r, seg, "Panel", turn)


# --- Kit_Colony_Cabin: outlying cabins (10 x 6 x 8, 120 tris) --------------------------------------
def cabin_a():
    """A: a Panel capsule pod lying along x on four splayed DarkMetal legs,
    a lit window strip along its front, dark glazing behind, Signal end
    caps and a line of snow along its top."""
    b = Builder()
    zc = 3.6                                                         # the pod's axis
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            # A splayed leg: a sheared box, its foot flat on the ground, its top inside the pod.
            foot = [(sx * 3.0 + dx, sy * 3.6 + dy, 0.0) for dx, dy in ((-0.45, -0.45), (0.45, -0.45), (0.45, 0.45), (-0.45, 0.45))]
            head = [(x, y - sy * 2.4, zc - 0.9) for x, y, _ in foot]
            frustum(b, foot, head, "DarkMetal")
    # Lathed about Z, then laid along x: local angle 0 is the bottom, 90
    # the back, 180 the top, 270 the front; 8 segments turned 22.5 degrees
    # so segment k is centred at 45 (k + 1) degrees and one faces each way.
    band = {7: "DarkMetal", 1: "GlassDark", 3: "Snow", 5: "WindowLit"}
    with b.at(Matrix.Translation((0.0, 0.0, zc)) @ Matrix.Rotation(math.pi / 2, 4, "Y")):
        b.lathe([(0.0, -5.0), (1.5, -4.4), (2.4, -3.4), (2.4, 3.4), (1.5, 4.4), (0.0, 5.0)], "Panel", segments=8,
                cell=lambda k, row: band.get(k) if row == 2 else "Signal", turn=math.radians(22.5))
    return [("", b)]


def cabin_b():
    """B: a steep A-frame, its Snow roof shell over recessed Signal gable
    walls on a DarkMetal plinth, a lit door box and a lit window box on the
    front, a vent through the roof."""
    b = Builder()
    b.box(-4.6, -3.6, 0.0, 4.6, 3.6, 0.5, "DarkMetal")
    # The shell: a thick open triangle (outer slopes Snow, the soffit dark).
    shell = [(-5.0, 0.4), (-4.55, 0.4), (0.0, 5.5), (4.55, 0.4), (5.0, 0.4), (0.0, 6.0)]
    b.extrude(shell, -4.0, 4.0, "DarkMetal", cell=lambda s: "Snow" if s in (4, 5) else None)
    b.extrude([(-4.4, 0.35), (4.4, 0.35), (0.0, 5.4)], -3.7, 3.7, "Signal")       # the gable walls, recessed
    b.box(-0.9, -4.5, 0.45, 0.9, -3.5, 2.6, "Signal", cell=lambda s, c, r, u, z: "WindowLit" if s == 0 else None)
    b.box(1.5, -4.3, 1.9, 2.9, -3.5, 3.1, "Signal", cell=lambda s, c, r, u, z: "WindowLit" if s == 0 else None)
    b.box(3.0, 1.0, 1.4, 3.8, 1.8, 3.4, "DarkMetal")                             # the vent
    return [("", b)]


def cabin_c():
    """C: a Panel box cabin with a lit door and window on the front under
    a Signal barrel vault with snow along its top, on a DarkMetal plinth."""
    b = Builder()
    b.box(-4.6, -3.6, 0.0, 4.6, 3.6, 0.6, "DarkMetal")
    walls(b, *rect(4.4, 3.4), 0.5, [(2.4, "Panel"), (0.8, "Panel")],
          bays={"F": [1.0, 1.4, 1.0, 2.4, 3.0]},
          paint=cells({("F", 1, 0): "WindowLit", ("F", 3, 0): "WindowLit"}))
    roof = arc(4.7, 2.6, 3.4, 6)
    b.extrude(roof, -3.4 - PROUD, 3.4 + PROUD, "Signal", smooth=True, cell=lambda s: "Snow" if s in (2, 3) else None)
    b.box(2.0, 0.5, 4.4, 3.0, 1.5, 6.2, "DarkMetal")                             # the flue
    return [("", b)]


# --- Kit_Colony_Depot: depots, garages and hangars (250 tris) --------------------------------------
DOOR_H = 8.0          # the big doors
FRAME = 1.0           # ...and their hazard-painted frames


def shed_front(doors):
    """Bays for a depot front: walls between `doors` [(wall before, door
    width)] and a wall after; and the painter: a DarkMetal door in a
    SignalYellow frame, a yellow-and-black lintel stripe above."""
    bays = []
    for wall, door in doors:
        bays += [wall, FRAME, door, FRAME]
    bays.append(bays[0])

    def paint(tag, col, row):
        if tag != "F" or col % 4 == 0 or row > 1:
            return None
        if col % 4 == 2:
            return "DarkMetal" if row == 0 else "SignalYellow"
        return "SignalYellow" if row == 0 else "HazardBlack"
    return bays, paint


def depot_a():
    """A, 50 x 14 x 36: PanelGrey walls with a lit strip along the sides,
    two big doors, under a smooth RoofDark barrel vault snowed along its
    top, with two vents."""
    b = Builder()
    hw, hd = 25.0, 18.0
    bays, paint = shed_front([(6.0, 12.0), (6.0, 12.0)])
    lit = lambda tag, col, row: "WindowLit" if tag in "RL" and row == 1 else paint(tag, col, row)
    top = walls(b, *rect(hw, hd), 0.0, [(DOOR_H, "PanelGrey"), (1.6, "PanelGrey"), (0.8, "PanelGrey")],
                bays={"F": bays}, paint=lit)
    xe = hw + PROUD
    vault = arc(xe, 14.0 - top, top, 10)
    b.extrude([(-xe, top - SINK)] + vault + [(xe, top - SINK)], -hd - PROUD, hd + PROUD, "RoofDark", smooth=True,
              cell=lambda s: "Snow" if 4 <= s <= 7 else None, cap_mat="PanelGrey")
    for y in (-8.0, 8.0):
        vent(b, 0.0, y, 13.9, 4.0, 3.0, 1.2)
    return [("", b)]


def depot_b():
    """B, 40 x 12 x 30: a flat-roofed PanelGrey garage with one big door,
    a snow slab on the roof, a Signal office block with lit bands proud of
    the front-left corner, and vents."""
    b = Builder()
    hw, hd = 20.0, 15.0
    bays, paint = shed_front([(7.0, 22.0)])
    top = walls(b, *rect(hw, hd), 0.0, [(DOOR_H, "PanelGrey"), (1.2, "PanelGrey"), (1.3, "PanelGrey")],
                bays={"F": bays}, paint=paint, top_mat="RoofDark")
    b.box(-hw + 1.0, -hd + 1.0, top - SINK, hw - 1.0, hd - 1.0, 11.0, "Snow")
    with b.at(Matrix.Translation((-hw + 4.8, -hd + 3.8, 0.0))):                     # proud of the shed's corner
        walls(b, *rect(5.0, 4.0), 0.0,
              [(3.0, "Signal"), (1.8, "WindowLit"), (1.6, "Signal"), (1.8, "WindowLit"), (3.8, "Signal")], top_mat="Snow")
    for x in (2.0, 12.0):
        vent(b, x, 6.0, 11.0, 3.0, 3.0, 1.2)
    return [("", b)]


def depot_c():
    """C, 60 x 16 x 40: a Steel shed with three doors under a sawtooth
    roof, its steep faces glazed and lit, its slopes snowed."""
    b = Builder()
    hw, hd, teeth = 30.0, 20.0, 4
    bays, paint = shed_front([(5.0, 10.0), (6.0, 10.0), (6.0, 10.0)])
    top = walls(b, *rect(hw, hd), 0.0, [(DOOR_H, "Steel"), (1.2, "Steel"), (1.3, "Steel")], bays={"F": bays}, paint=paint)
    xe, low, high = hw + PROUD, top + 0.3, 16.0
    pitch = 2 * xe / teeth
    outline = [(-xe, top - SINK), (xe, top - SINK)]
    for i in reversed(range(teeth)):
        outline += [(-xe + (i + 1) * pitch, high), (-xe + i * pitch, low)]
    # Sides: 0 bottom, 1 right wall, then slope / steep face pairs, last the left wall stub.
    n = len(outline)
    b.extrude(outline, -hd - PROUD, hd + PROUD, "RoofDark", cap_mat="Steel",
              cell=lambda s: None if s in (0, 1, n - 1) else ("Snow" if s % 2 == 0 else "WindowLit"))
    return [("", b)]


# --- Kit_Colony_Tank: fuel and water tanks (150 tris) -----------------------------------------------
def tank_a():
    """A, 20 x 16: a Steel drum with a Signal band under a shallow snowed
    cone, a DarkMetal pump house at its foot."""
    b = Builder()
    mats = ["Steel", "Signal", "Steel", "Snow"]
    b.lathe([(10.0, 0.0), (10.0, 11.0), (10.0, 13.0), (10.0, 14.0), (0.0, 16.0)], "Steel", segments=16,
            cell=lambda k, row: mats[row])
    b.box(6.2, -9.6, 0.0, 9.6, -6.2, 3.0, "DarkMetal", top_mat="Snow")           # the pump house, at the front-right diagonal
    return [("", b)]


def tank_b():
    """B, 16 x 12: squat, a Panel drum with a Signal band and a domed top
    under snow, a DarkMetal valve house at its foot."""
    b = Builder()
    mats = ["Panel", "Signal", "Panel", "Snow"]
    b.lathe([(8.0, 0.0), (8.0, 8.5), (8.0, 10.0), (6.8, 11.2), (0.0, 12.0)], "Panel", segments=16,
            cell=lambda k, row: mats[row])
    b.box(-7.9, -7.9, 0.0, -5.0, -5.0, 2.6, "DarkMetal", top_mat="Snow")        # the valve house, at the front-left diagonal
    return [("", b)]


# --- Kit_Colony_Mast: comms masts (6 x 50 x 6, 150 tris) ---------------------------------------------
def mast_piece():
    """A tapering four-legged tower of solid legs (Signal below, Panel
    above), a DarkMetal collar and a top platform, a dish on the platform's
    front and an antenna with a WarningLight tip."""
    b = Builder()
    z_mid, z_top = 24.0, 44.0
    spread = lambda z: 2.5 - 1.5 * z / z_top         # a leg's centre from the axis
    size = lambda z: 0.5 - 0.05 * z / z_top          # ...and its half-width
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            def ring(z):
                c, h = spread(z), size(z)
                pts = [(sx * c - h, sy * c - h), (sx * c + h, sy * c - h), (sx * c + h, sy * c + h), (sx * c - h, sy * c + h)]
                return [(x, y, z) for x, y in pts]
            lo, mid, hi = ring(0.0), ring(z_mid), ring(z_top)
            b.face(lo[::-1], "Signal")
            for k in range(4):
                k1 = (k + 1) % 4
                b.face([lo[k], lo[k1], mid[k1], mid[k]], "Signal")
                b.face([mid[k], mid[k1], hi[k1], hi[k]], "Panel")
            b.face(hi, "Panel")
    c = spread(z_mid) + size(z_mid) - 0.15
    b.box(-c, -c, z_mid - 0.6, c, c, z_mid + 0.6, "DarkMetal")                  # the collar
    b.box(-1.8, -1.8, z_top - 0.5, 1.8, 1.8, z_top + 0.5, "DarkMetal")            # the platform
    b.box(-0.4, -0.4, z_top + 0.5 - SINK, 0.4, 0.4, 50.0, "DarkMetal", levels=[48.0],
          cell=lambda s, c, r, u, z: "WarningLight" if r == 1 else None)
    with b.at(Matrix.Translation((0.0, -1.6, z_top)) @ Matrix.Rotation(math.radians(50.0), 4, "X")):
        b.lathe([(0.0, 0.0), (2.4, 1.0), (1.6, 1.3), (0.0, 1.3)], "Panel", segments=6)    # the dish, facing front and up
    return [("", b)]


# --- Kit_Colony_Tube: enclosed walkways (4 x 4 x 20, 60 tris) ----------------------------------------
def tube():
    """An octagonal Panel tube along y, a WindowLit band along each side,
    snow on top, dark underneath. Uniform along its length (stretched)."""
    b = Builder()
    rr = 2.0 / math.cos(math.radians(22.5))
    profile = [(rr * math.cos(math.radians(22.5 + 45.0 * k)), 2.0 + rr * math.sin(math.radians(22.5 + 45.0 * k)))
               for k in range(8)]
    # Sides from the first vertex (22.5 degrees): upper-right, top, upper-left, left, lower-left, bottom, lower-right, right.
    mats = ["Panel", "Snow", "Panel", "WindowLit", "DarkMetal", "DarkMetal", "DarkMetal", "WindowLit"]
    b.extrude(profile, -10.0, 10.0, "Panel", cell=lambda s: mats[s])
    return [("", b)]


# --- Kit_Pipe / Kit_Pipe_Support: pipelines (40 tris each) ----------------------------------------------
def pipe():
    """A Steel octagonal pipe along y, 2 m across, a Signal stripe along its top."""
    b = Builder()
    rr = 1.0 / math.cos(math.radians(22.5))
    profile = [(rr * math.cos(math.radians(22.5 + 45.0 * k)), 1.0 + rr * math.sin(math.radians(22.5 + 45.0 * k)))
               for k in range(8)]
    b.extrude(profile, -10.0, 10.0, "Steel", smooth=True, cell=lambda s: "Signal" if s == 1 else None)
    return [("", b)]


def pipe_support():
    """A DarkMetal portal under the pipe: two legs and a cross beam, one shell."""
    b = Builder()
    b.extrude([(-2.0, 0.0), (-1.0, 0.0), (-1.0, 1.2), (1.0, 1.2), (1.0, 0.0), (2.0, 0.0), (2.0, 2.0), (-2.0, 2.0)],
              -1.0, 1.0, "DarkMetal")
    return [("", b)]


# --- The batch ------------------------------------------------------------------------------------------
PIECES = [
    ("Kit_Colony_Hab_A", hab_a), ("Kit_Colony_Hab_B", hab_b), ("Kit_Colony_Hab_C", hab_c), ("Kit_Colony_Hab_D", hab_d),
    ("Kit_Colony_Cabin_A", cabin_a), ("Kit_Colony_Cabin_B", cabin_b), ("Kit_Colony_Cabin_C", cabin_c),
    ("Kit_Colony_Depot_A", depot_a), ("Kit_Colony_Depot_B", depot_b), ("Kit_Colony_Depot_C", depot_c),
    ("Kit_Colony_Tank_A", tank_a), ("Kit_Colony_Tank_B", tank_b),
    ("Kit_Colony_Mast", mast_piece), ("Kit_Colony_Tube", tube),
    ("Kit_Pipe", pipe), ("Kit_Pipe_Support", pipe_support),
]
STACKS = {"Kit_Colony_Tower_A": tower_a, "Kit_Colony_Tower_B": tower_b}


def main():
    kt.begin("kit_colony", 0)
    for name, build in PIECES:
        soften(kt.piece(name, build()))
    for name, build in STACKS.items():
        base, shaft, crown, plug_of = build()
        soften(kt.piece(name + "_Base", [("", base)]))
        soften(kt.piece(name + "_Shaft", [("", shaft), ("Plug", plug_of())]))
        soften(kt.piece(name + "_Crown", [("", crown), ("Plug", plug_of())]))
    kt.finish()


if __name__ == "__main__":
    main()
