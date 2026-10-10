"""Fichina's domes, greenhouses, power plant and Climate Control Center
(models/fichina/ASSETS.md, "Batch 2"): Kit_Colony_Dome_A..C,
Kit_Colony_Greenhouse_A..B, Kit_Colony_Plant and Kit_Colony_ClimateCenter.

    KIT_OUT=<copy.blend> KIT_PREVIEW=<dir> blender --background --python kit_domes.py
    (KIT_PREVIEW also gets colony_far.png and climate_center_tall.png: the
    Climate Control Center seen from afar among the batch, and up close)

Every piece stands on Z = 0 with its origin at the centre of its footprint
and its entrance on the -Y front. A round body is one smooth lathe (its
drum, dome, decks, core and antenna in one closed shell, so nothing meets
along a shared plane); vestibules, slabs, pipes, fins, masts and the halo are
their own closed shells sunk SINK into what they stand on. Windows, bands,
ribs, doors and vents are painted: cells of a surface's own faces in another
material, so they draw no ink line. Snow lies on every flat top (a slab on
the plant's hall, the top faces painted Snow elsewhere, a snow shoulder on
the big domes); CoreGlow is kept for the Climate Control Center's core and
the plant's vents.

Domes that carry a vestibule stand a little back from the footprint's front
so the vestibule reaches it without the piece growing past its size.
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # models/fichina/source
import fichina_common as cc  # noqa: E402,F401  first: makes kit_tools serve Fichina
import kit_tools as kt  # noqa: E402
from kit_tools import Builder  # noqa: E402

import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

SINK = 0.2                               # a part sinks this far into the one it stands on
FRONT, RIGHT, BACK, LEFT = 0, 1, 2, 3    # a box's sides, as prism() numbers them


# --- Helpers ----------------------------------------------------------------------------
def block(b, x0, y0, x1, y1, z0, storeys, bays=None, paint=None, top_mat=None, bottom=True):
    """A walled box from z0: `storeys` [(height, material)] stack up its sides
    and paint them all round. `bays` {side: [widths]} cuts a side into bays,
    and paint(side, bay, row) -> a material (None: the storey's) paints single
    cells: windows, doors, stripes. Returns the top z."""
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


def centred(segments):
    """The lathe turn that centres segment 0 on the -Y front."""
    return -math.pi / 2 - math.pi / segments


def lathe_rows(b, rows, segments=16, angles=None, turn=0.0, bottom=True, top=True, bottom_mat=None,
               top_mat=None, smooth=True):
    """A round shape from `rows` [(radius, z, material of the band above the
    ring)]: the material may be a function of the segment (ribs, windows
    painted round). `angles` gives uneven segments (thin ribs between wide
    panes); an end may be left open."""
    if angles is None:
        angles = [turn + 2 * math.pi * k / segments for k in range(segments)]
    n = len(angles)
    rings = []
    for r, z, _ in rows:
        if r <= 0.0:
            rings.append([(0.0, 0.0, z)] * n)
        else:
            rings.append([(r * math.cos(a), r * math.sin(a), z) for a in angles])
    for i in range(len(rings) - 1):
        m = rows[i][2]
        for k in range(n):
            k1 = (k + 1) % n
            b.face([rings[i][k], rings[i][k1], rings[i + 1][k1], rings[i + 1][k]],
                   (m(k) if callable(m) else m) or "Panel", smooth)
    plain = lambda m: m if isinstance(m, str) else "Panel"
    if bottom and rows[0][0] > 0.0:
        b.face(rings[0][::-1], bottom_mat or plain(rows[0][2]))
    if top and rows[-1][0] > 0.0:
        b.face(rings[-1], top_mat or plain(rows[-2][2]))


def sphere_cap(r_base, z_base, z_top, rings):
    """Rings [(r, z)] (the base ring left out, the apex included) of a
    spherical cap from radius r_base at z_base to its apex at z_top."""
    h = z_top - z_base
    rs = (r_base * r_base + h * h) / (2.0 * h)
    zc = z_top - rs
    a0 = math.asin((z_base - zc) / rs)
    out = []
    for k in range(1, rings + 1):
        a = a0 + (math.pi / 2 - a0) * k / rings
        out.append((rs * math.cos(a) if k < rings else 0.0, zc + rs * math.sin(a)))
    return out


def saucer(r_base, z_base, base_angle, rings):
    """Rings of a spherical cap that leaves its base at `base_angle` above the
    horizontal: a flattened dome with a crease at its rim."""
    rs = r_base / math.cos(base_angle)
    zc = z_base - rs * math.sin(base_angle)
    out = []
    for k in range(1, rings + 1):
        a = base_angle + (math.pi / 2 - base_angle) * k / rings
        out.append((rs * math.cos(a) if k < rings else 0.0, zc + rs * math.sin(a)))
    return out


def ellipse_cap(r_base, z_base, height, rings, r_top=0.0):
    """Rings of an elliptical cap (tangent to a drum at its base) from r_base
    at z_base, `height` tall at its apex, ending at a flat top of radius
    r_top (or the apex)."""
    t1 = math.pi / 2 if r_top <= 0.0 else math.acos(r_top / r_base)
    out = []
    for k in range(1, rings + 1):
        t = t1 * k / rings
        r = r_base * math.cos(t) if (k < rings or r_top > 0.0) else 0.0
        out.append((r, z_base + height * math.sin(t)))
    return out


def ring(b, r_in, r_out, z0, z1, mat, segments=16, rim_mat=None, top_mat=None, turn=0.0):
    """A flat ring (a hollow drum) from r_in to r_out, z0 to z1, its rims smooth."""
    def p(r, z, k):
        a = turn + 2 * math.pi * k / segments
        return (r * math.cos(a), r * math.sin(a), z)
    for k in range(segments):
        k1 = (k + 1) % segments
        b.face([p(r_out, z0, k), p(r_out, z0, k1), p(r_out, z1, k1), p(r_out, z1, k)], rim_mat or mat, True)
        b.face([p(r_in, z0, k1), p(r_in, z0, k), p(r_in, z1, k), p(r_in, z1, k1)], mat, True)
        b.face([p(r_out, z1, k), p(r_out, z1, k1), p(r_in, z1, k1), p(r_in, z1, k)], top_mat or mat)
        b.face([p(r_in, z0, k), p(r_in, z0, k1), p(r_out, z0, k1), p(r_out, z0, k)], mat)


def blade(b, stations, angle, mats):
    """A fin standing out from a round body at `angle` round Z: a closed
    flat-sided strip through `stations` [(inner radius, outer radius, z,
    half width)], its inner edge sunk inside the body. `mats`: one material,
    or (left side, outer face, right side, inner face)."""
    if isinstance(mats, str):
        mats = (mats,) * 4
    u = Vector((math.cos(angle), math.sin(angle), 0.0))
    t = Vector((-math.sin(angle), math.cos(angle), 0.0))
    rings = []
    for ri, ro, z, hw in stations:
        up = Vector((0.0, 0.0, z))
        rings.append([tuple(u * ri - t * hw + up), tuple(u * ro - t * hw + up),
                      tuple(u * ro + t * hw + up), tuple(u * ri + t * hw + up)])
    for a, c in zip(rings, rings[1:]):
        for j in range(4):
            j1 = (j + 1) % 4
            b.face([a[j], a[j1], c[j1], c[j]], mats[j])
    b.face(rings[0][::-1], mats[1])
    b.face(rings[-1], mats[1])


def pipe(b, p0, p1, r, mat="Steel", segments=8):
    """A round pipe from p0 to p1 (both ends inside what they join)."""
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    m = Matrix.Translation(p0) @ d.to_track_quat("Z", "Y").to_matrix().to_4x4()
    with b.at(m):
        b.lathe([(r, 0.0), (r, d.length)], mat, segments=segments)


def floodlight(b, x, y, height, r=0.6):
    """A Steel pole on the ground with a lamp head facing the front."""
    with b.at(Matrix.Translation((x, y, 0.0))):
        b.lathe([(r, 0.0), (r, height - 0.6)], "Steel", segments=8)
        b.box(-1.3, -0.8, height - 1.2, 1.3, 0.8, height, "DarkMetal", bottom_mat="Lamp",
              cell=lambda s, c, rw, u, z: "Lamp" if s == FRONT else None)


def vestibule(b, hw, y_in, y_out, h, door_w=3.0, door_h=3.2, mat="Signal"):
    """An entrance block 2hw wide and h tall from y_in (inside the body it
    serves) out to its front at y_out, a lit door painted on it, snow on top."""
    block(b, -hw, y_out, hw, y_in, 0.0, [(door_h, mat), (h - door_h, mat)],
          bays={FRONT: [hw - door_w / 2, door_w, hw - door_w / 2]},
          paint=cells({(FRONT, 1, 0): "WindowLit"}), top_mat="Snow")


def circle_arc(hw, rise, z0, segments, apex=0.0):
    """Points of a circular arc from (-hw, z0) over (0, z0 + rise) to (hw, z0),
    turning the same angle at every step; `apex` > 0 splits the top into a
    flat strip that wide."""
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
    cell(side, strip) -> material. Ribs across a vault are cells of its shell."""
    ys = [y0] + [y0 + (y1 - y0) * f for f in sorted(strips)] + [y1]
    n = len(profile)
    for s in range(n):
        (ax, az), (bx, bz) = profile[s], profile[(s + 1) % n]
        for j in range(len(ys) - 1):
            m = (cell(s, j) if cell else None) or mat
            b.face([(ax, ys[j], az), (ax, ys[j + 1], az), (bx, ys[j + 1], bz), (bx, ys[j], bz)], m, smooth)
    b.face([(x, y0, z) for x, z in profile], cap_mat or mat)
    b.face([(x, y1, z) for x, z in profile[::-1]], cap_mat or mat)


# --- Kit_Colony_Dome: 40 x 20 x 40, 600 tris each ---------------------------------------------
def dome_a():
    """A: a white dome with eight grey ribs painted up it and a snow cap, on a
    short drum with a lit window row and a cornice ledge, an orange
    vestibule on the front."""
    R, seg = 18.5, 24
    b = Builder()
    ribs = lambda k: "PanelGrey" if k % 3 == 0 else "Panel"
    windows = lambda k: "WindowLit" if k % 2 == 0 else "Panel"
    rows = [(R, 0.0, "Concrete"), (R, 0.8, "Panel"), (R, 2.6, windows), (R, 4.6, "Panel"),
            (R, 6.0, "Panel"), (R - 0.5, 6.0, ribs)]
    cap = sphere_cap(R - 0.5, 6.0, 20.0, 6)
    for j, (r, z) in enumerate(cap):
        rows.append((r, z, None if j == len(cap) - 1 else ("Snow" if j >= 3 else ribs)))
    with b.at(Matrix.Translation((0.0, 1.5, 0.0))):
        lathe_rows(b, rows, seg, turn=centred(seg), bottom_mat="Concrete")
    vestibule(b, 4.5, -12.0, -20.0, 4.6)
    return [("", b)]


def dome_b():
    """B: a tall drum with a continuous lit window band and a painted lit
    doorway in an orange frame, a lower dome with a grey band and a snow
    top, and an oculus lantern with a light strip at its crown."""
    R, seg = 20.0, 20
    b = Builder()
    lit = lambda k: "GlassDark" if k % 5 == 2 else "WindowLit"
    door = lambda k: "WindowLit" if k == 0 else ("Signal" if k in (1, seg - 1) else "Panel")
    plinth = lambda k: "Signal" if k in (0, 1, seg - 1) else "Concrete"
    rows = [(R, 0.0, plinth), (R, 0.8, door), (R, 4.0, lit), (R, 6.5, "Panel"), (R, 9.0, "Panel")]
    cap = ellipse_cap(R, 9.0, 9.6, 7, r_top=5.5)
    for j, (r, z) in enumerate(cap):
        rows.append((r, z, None if j == len(cap) - 1 else ("Snow" if j >= 4 else ("PanelGrey" if j == 2 else "Panel"))))
    lathe_rows(b, rows, seg, turn=centred(seg), bottom_mat="Concrete", top_mat="Glass")
    lathe_rows(b, [(6.2, 17.7, "DarkMetal"), (6.2, 18.3, "LightStrip"), (6.2, 19.3, "DarkMetal"), (5.4, 20.0, None)],
               12, bottom_mat="DarkMetal", top_mat="Glass")
    return [("", b)]


def dome_c():
    """C: a flattened saucer dome in alternating white and grey bands with a
    snow top, on a low drum with a window row, and three small orange
    vestibules (front, back-left, back-right)."""
    R, seg = 18.0, 20
    b = Builder()
    windows = lambda k: "WindowLit" if k % 2 == 1 else "Panel"
    rows = [(R, 0.0, "Concrete"), (R, 1.0, "Panel"), (R, 2.0, windows), (R, 3.5, "Panel"), (R, 4.5, "Panel")]
    cap = saucer(R, 4.5, math.radians(35.0), 6)
    for j, (r, z) in enumerate(cap):
        rows.append((r, z, None if j == len(cap) - 1 else ("Snow" if j >= 3 else ("PanelGrey" if j % 2 == 0 else "Panel"))))
    with b.at(Matrix.Translation((0.0, 1.0, 0.0))):
        lathe_rows(b, rows, seg, turn=centred(seg), bottom_mat="Concrete")
        for ang in (-90.0, 30.0, 150.0):
            with b.at(Matrix.Rotation(math.radians(ang + 90.0), 4, "Z")):
                vestibule(b, 3.5, -12.0, -21.0, 3.6, door_w=2.4, door_h=2.8)
    return [("", b)]


# --- Kit_Colony_Greenhouse: A 36 x 18 x 36, B 60 x 14 x 24, 600 tris each -----------------------
def greenhouse_a():
    """A: a glazed dome: twelve wide glowing panes between narrow dark ribs
    (uneven lathe segments), three dark ring ribs, on a concrete base ring,
    a dark vent lantern at the apex, an orange vestibule on the front."""
    R, panels = 17.0, 12
    b = Builder()
    half = 0.5 / R                                   # ribs 1 m wide
    angles = []
    for i in range(panels):
        a = math.radians(-105.0 + 360.0 * i / panels)   # a pane centred on the front
        angles += [a - half, a + half]
    glass = lambda k: "DarkMetal" if k % 2 == 0 else "Greenhouse"
    t1 = math.acos(2.5 / R)
    rows = [(R, 0.0, "Concrete"), (R, 1.5, glass)]
    fractions = [0.26, 0.30, 0.56, 0.60, 0.86, 0.90, 1.0]
    for j, f in enumerate(fractions):
        t = f * t1
        rows.append((R * math.cos(t), 1.5 + 16.0 * math.sin(t),
                     None if j == len(fractions) - 1 else ("DarkMetal" if j % 2 == 0 else glass)))
    with b.at(Matrix.Translation((0.0, 1.0, 0.0))):
        lathe_rows(b, rows, angles=angles, bottom_mat="Concrete", top_mat="DarkMetal")
        lathe_rows(b, [(2.2, 17.0, "DarkMetal"), (2.2, 17.5, "LightStrip"), (2.2, 17.8, "DarkMetal"), (1.6, 18.0, None)],
                   8, bottom_mat="DarkMetal", top_mat="DarkMetal")
    vestibule(b, 4.0, -11.0, -18.0, 4.2)
    return [("", b)]


def greenhouse_b():
    """B: a glazed barrel vault 60 m long: glowing panes between dark ribs
    painted across it every 10 m, a dark ridge strip, concrete base walls,
    white end walls, an orange vestibule on the front flank."""
    b = Builder()
    hw, hl, wall, top = 10.8, 30.0, 1.5, 13.8
    segs = 12
    arc = circle_arc(hw, top - wall, wall, segs, apex=1.6)
    profile = [(-hw, 0.0), (hw, 0.0)] + arc[::-1]
    ridge = 2 + segs // 2
    n = len(profile)
    strips = []
    for k in range(1, 6):
        strips += [(10.0 * k - 0.4) / 60.0, (10.0 * k + 0.4) / 60.0]

    def paint(s, j):
        if s in (0, 1, n - 1):
            return "Concrete"
        return "DarkMetal" if s == ridge or j % 2 == 1 else "Greenhouse"
    with b.at(Matrix.Translation((0.0, 1.2, 0.0)) @ Matrix.Rotation(-math.pi / 2, 4, "Z")):
        vault(b, profile, -hl, hl, "Greenhouse", strips=strips, cell=paint, cap_mat="Panel")
    vestibule(b, 4.0, -6.0, -12.0, 4.5)
    return [("", b)]


# --- Kit_Colony_Plant: 80 x 40 x 60 (stacks to 70), 2,000 tris ---------------------------------
def stack(b, x, y, z0, h, r):
    """A tapering chimney standing on z0: dark below, Signal and Panel
    bands, a WarningLight collar under its lip."""
    bands = [(0.0, "DarkMetal"), (0.3, "Signal"), (0.38, "Panel"), (0.6, "Signal"), (0.68, "Panel"),
             (0.92, "WarningLight"), (0.97, "DarkMetal"), (1.0, None)]
    rows = []
    for f, m in bands:
        z = z0 + f * (h - z0)
        rows.append((r * (1.0 - 0.2 * f), z - SINK if f == 0.0 else z, m))
    with b.at(Matrix.Translation((x, y, 0.0))):
        lathe_rows(b, rows, 12, bottom_mat="DarkMetal", top_mat="DarkMetal")


def plant():
    """The geothermal plant: a grey hall with a dark vent band of glowing
    CoreGlow vents along both long sides and a snow slab on its roof
    carrying three cooling units and a row of glowing vent hoods; a white
    control annex with a lit window band and an orange-framed door, an
    orange stair tower, a dark machinery block with hazard stripes; three
    banded stacks on a plinth at the right; a steel separator tank at the
    left joined by pipes; two floodlights at the front."""
    b = Builder()
    hx0, hx1, hy0, hy1, hz = -24.0, 24.0, -16.0, 22.0, 24.0
    # The hall and its snow slab.
    block(b, hx0, hy0, hx1, hy1, 0.0, [(3.0, "DarkMetal"), (14.0, "PanelGrey"), (3.0, "DarkMetal"), (4.0, "PanelGrey")],
          bays={FRONT: [4.0] * 12, BACK: [4.0] * 12},
          paint=lambda s, c, r: "CoreGlow" if r == 2 and s in (FRONT, BACK) and c % 2 == 1 else None,
          top_mat="RoofDark")
    b.box(hx0 + 0.6, hy0 + 0.6, hz - SINK, hx1 - 0.6, hy1 - 0.6, hz + 0.8, "Snow")
    # Cooling units (louvred steel boxes with a fan drum) and vent hoods on the roof.
    for x in (-15.0, -1.0, 13.0):
        top = block(b, x - 4.0, 3.0, x + 4.0, 11.0, hz + 0.6, [(0.8, "DarkMetal"), (3.2, "Steel"), (0.8, "DarkMetal")],
                    bays={FRONT: [1.6] * 5, BACK: [1.6] * 5},
                    paint=lambda s, c, r: "GlassDark" if r == 1 and s in (FRONT, BACK) and c % 2 == 1 else None,
                    top_mat="Snow")
        with b.at(Matrix.Translation((x, 7.0, 0.0))):
            lathe_rows(b, [(2.8, top - SINK, "DarkMetal"), (2.8, top + 0.5, None)], 8,
                       bottom_mat="DarkMetal", top_mat="RoofDark")
    for x in (-18.0, -10.0, -2.0, 6.0, 14.0):
        b.box(x - 1.5, 15.0, hz + 0.6, x + 1.5, 17.0, hz + 2.2, "DarkMetal", top_mat="CoreGlow")
    # The control annex, the stair tower and the machinery block along the front.
    block(b, -24.0, -30.0, 0.0, hy0 + SINK, 0.0,
          [(1.0, "Concrete"), (3.0, "Panel"), (2.0, "WindowLit"), (1.4, "Panel"), (1.2, "GlassDark"), (0.4, "Panel")],
          bays={FRONT: [3.0, 1.0, 3.0, 1.0, 16.0]},
          paint=lambda s, c, r: ("Signal" if s == FRONT and c in (1, 3) and r <= 1 else (
              "WindowLit" if s == FRONT and c == 2 and r == 1 else None)),
          top_mat="Snow")
    block(b, -0.5, -30.0, 5.0, hy0 + SINK, 0.0, [(25.4, "Signal"), (0.8, "LightStrip")], top_mat="Snow")
    block(b, 7.0, -28.0, hx1 - 0.4, hy0 + SINK, 0.0,
          [(1.4, "SignalYellow"), (1.4, "HazardBlack"), (7.6, "DarkMetal"), (1.6, "Steel")],
          bays={FRONT: [1.5] * 11},
          paint=lambda s, c, r: "Steel" if r == 2 and s == FRONT and c % 2 == 1 else None, top_mat="Snow")
    # The stacks on their plinth at the right.
    block(b, hx1 - SINK, -18.0, 38.0, hy1 - 0.4, 0.0, [(1.4, "SignalYellow"), (1.4, "HazardBlack"), (7.2, "DarkMetal")],
          top_mat="Snow")
    for y, h, r in ((-10.0, 70.0, 4.0), (3.0, 61.0, 3.6), (15.5, 52.0, 3.2)):
        stack(b, 31.5, y, 10.0, h, r)
    # The separator tank at the left and its pipes into the hall.
    with b.at(Matrix.Translation((-32.0, 10.0, 0.0))):
        lathe_rows(b, [(8.0, 0.0, "Concrete"), (8.0, 1.2, "Steel"), (8.0, 8.0, "Signal"), (8.0, 10.0, "Steel"),
                       (8.0, 15.0, "Steel"), (7.0, 16.6, "Snow"), (4.5, 17.6, "Snow"), (0.0, 18.0, None)], 16,
                   bottom_mat="Concrete")
    pipe(b, (-27.0, 7.0, 5.0), (-23.0, 7.0, 5.0), 1.0)
    pipe(b, (-27.0, 13.0, 9.0), (-23.0, 13.0, 9.0), 1.0)
    floodlight(b, -22.0, -29.0, 16.0)
    floodlight(b, 22.0, -29.3, 16.0)
    return [("", b)]


# --- Kit_Colony_ClimateCenter: 120 across, 240 tall, 8,000 tris --------------------------------
CC_SEG = 40
CC_R_PLINTH, CC_R_DRUM = 58.0, 56.0
CC_Z_DRUM, CC_DOME_H = 13.0, 19.0            # the dome rises from the drum's top, this high at its apex
CC_R_TOWER0, CC_R_TOWER1 = 22.0, 14.0        # the tower's radius where it leaves the dome / at the collar
CC_Z_COLLAR = 158.0
CC_DECKS = ((72.0, 8.0), (115.0, 7.0))       # (z, how far the deck flares out)
CC_CORE_R, CC_CORE_Z = 12.5, 184.5
CC_FINS = 8


def climate_center():
    """The Climate Control Center, one lathe from the plinth to the antenna
    tip: a concrete plinth with a snow ledge, a drum with a lit window band,
    a broad elliptical dome (grey ribs painted up it, snow on its shoulder),
    the white tapering tower with lit window bands and two ring decks (dark
    underside, light-strip edge, snow on top), a wide collar, a dark neck,
    the glowing CoreGlow core sphere, and the antenna with light-strip bands
    and a WarningLight tip. Four orange ribs run from the dome's shoulder
    to the first deck; eight white fins with glowing inner faces rise from
    the collar round the core and carry a halo ring; four orange entrance
    blocks with lit doorways stand at the cardinal points."""
    b = Builder()
    seg = CC_SEG
    lit = lambda k: ("WindowLit", "WindowLit", "WindowLit", "GlassDark", "Panel")[k % 5]
    ribs = lambda k: "PanelGrey" if k % 5 == 4 else "Panel"      # over the window band's piers
    win = lambda k: "WindowLit" if k % 2 == 0 else "GlassDark"
    rows = [(CC_R_PLINTH, 0.0, "Concrete"), (CC_R_PLINTH, 2.5, "Snow"), (CC_R_DRUM, 2.5, "Panel"),
            (CC_R_DRUM, 5.5, lit), (CC_R_DRUM, 9.5, ribs), (CC_R_DRUM, CC_Z_DRUM, ribs)]
    cap = ellipse_cap(CC_R_DRUM, CC_Z_DRUM, CC_DOME_H, 8, r_top=CC_R_TOWER0)
    for j, (r, z) in enumerate(cap):
        rows.append((r, z, "Panel" if j == len(cap) - 1 else ("Snow" if j >= 3 else ribs)))
    z_tower = cap[-1][1]
    rt = lambda z: CC_R_TOWER0 + (CC_R_TOWER1 - CC_R_TOWER0) * (z - z_tower) / (CC_Z_COLLAR - z_tower)

    def section(za, zb):
        """Lit window bands every 12 m up a stretch of the tower."""
        z = za + 7.0
        while z + 4.0 <= zb - 4.0:
            rows.append((rt(z), z, win))
            rows.append((rt(z + 4.0), z + 4.0, "Panel"))
            z += 12.0

    def deck(zd, flare):
        r = rt(zd)
        rows.extend([(r, zd, "DarkMetal"), (r + flare, zd, "DarkMetal"), (r + flare, zd + 1.2, "LightStrip"),
                     (r + flare, zd + 3.0, "Snow"), (rt(zd + 3.0), zd + 3.0, "Panel")])
    za = z_tower
    for zd, flare in CC_DECKS:
        section(za, zd)
        deck(zd, flare)
        za = zd + 3.0
    section(za, CC_Z_COLLAR)
    # The collar, the neck, the core and the antenna.
    rows.extend([(CC_R_TOWER1, CC_Z_COLLAR, "DarkMetal"), (24.0, CC_Z_COLLAR, "DarkMetal"),
                 (24.0, CC_Z_COLLAR + 2.0, "LightStrip"), (24.0, CC_Z_COLLAR + 5.0, "Panel"),
                 (24.0, CC_Z_COLLAR + 6.0, "Snow"), (8.0, CC_Z_COLLAR + 6.0, "DarkMetal")])
    zn = CC_CORE_Z - math.sqrt(CC_CORE_R ** 2 - 64.0)
    zt = CC_CORE_Z + math.sqrt(CC_CORE_R ** 2 - 16.0)
    a0, a1 = math.asin((zn - CC_CORE_Z) / CC_CORE_R), math.asin((zt - CC_CORE_Z) / CC_CORE_R)
    rows.append((8.0, zn, "CoreGlow"))
    for i in range(1, 8):
        a = a0 + (a1 - a0) * i / 7
        rows.append((CC_CORE_R * math.cos(a), CC_CORE_Z + CC_CORE_R * math.sin(a), "CoreGlow" if i < 7 else "DarkMetal"))
    rows.extend([(4.0, 200.0, "Panel"), (3.2, 212.0, "LightStrip"), (3.2, 214.0, "Panel"), (2.4, 226.0, "LightStrip"),
                 (2.4, 228.0, "Panel"), (2.0, 236.0, "WarningLight"), (1.3, 239.3, "WarningLight"), (0.0, 240.0, None)])
    lathe_rows(b, rows, seg, turn=centred(seg), bottom_mat="Concrete")
    # Four orange ribs from inside the dome up to the first deck.
    zd1, flare1 = CC_DECKS[0]
    for k in range(4):
        blade(b, [(18.0, 40.0, 24.0, 2.5), (rt(40.0) - 2.4, 27.0, 40.0, 2.5), (rt(zd1) - 2.9, rt(zd1) + flare1 - 5.0, zd1 + 0.5, 1.8)],
              -math.pi / 2 + k * math.pi / 2, "Signal")
    # The crown: eight fins (their inner faces glowing) through a halo ring.
    z_fin = CC_Z_COLLAR + 6.0 - SINK
    for k in range(CC_FINS):
        blade(b, [(17.5, 21.5, z_fin, 3.0), (18.0, 22.5, 185.0, 2.6), (20.5, 24.5, 205.0, 1.4)],
              -math.pi / 2 + 2 * math.pi * k / CC_FINS, ("Panel", "Panel", "Panel", "LightStrip"))
    ring(b, 18.4, 25.2, 196.0, 199.0, "DarkMetal", seg, rim_mat="LightStrip", top_mat="Snow", turn=centred(seg))
    # Four entrance blocks at the cardinal points.
    for k in range(4):
        with b.at(Matrix.Rotation(k * math.pi / 2, 4, "Z")):
            block(b, -7.0, -60.0, 7.0, -46.0, 0.0, [(5.5, "Signal"), (3.5, "Signal")],
                  bays={FRONT: [3.5, 7.0, 3.5]}, paint=cells({(FRONT, 1, 0): "WindowLit"}), top_mat="Snow")
    return [("", b)]


# --- Extra previews ----------------------------------------------------------------------------
def render_view(scene, eye, target, path, size=(1600, 900), lens=35):
    """Renders `scene` as kit_tools.preview() does, from `eye` looking at `target`."""
    cam_data = bpy.data.cameras.new("DomesCam")
    cam_data.lens = lens
    cam = bpy.data.objects.new("DomesCam", cam_data)
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
    world = bpy.data.worlds.new("DomesWorld")
    world.color = (0.55, 0.65, 0.8)
    scene.world = world
    eye, target = Vector(eye), Vector(target)
    cam.location = eye
    cam.rotation_euler = (target - eye).to_track_quat("-Z", "Y").to_euler()
    cam_data.clip_end = 20000.0
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True, scene=scene.name)
    bpy.data.objects.remove(cam)
    bpy.data.cameras.remove(cam_data)
    bpy.data.worlds.remove(world)


def extra_previews(out):
    """The batch standing round the Climate Control Center on snow, seen
    from 1.2 km and from 5 km, and the Center up close."""
    scene = bpy.data.scenes.new("Colony")
    me = bpy.data.meshes.new("Ground")
    me.from_pydata([(-3000, -3000, -0.3), (3000, -3000, -0.3), (3000, 3000, -0.3), (-3000, 3000, -0.3)], [],
                   [(0, 1, 2, 3)])
    me.materials.append(cc.material("Snow"))
    scene.collection.objects.link(bpy.data.objects.new("Ground", me))

    def stand(name, x, y, turn=0.0):
        inst = bpy.data.objects.new(name, None)
        inst.instance_type = "COLLECTION"
        inst.instance_collection = bpy.data.collections[name]
        inst.location = (x, y, 0.0)
        inst.rotation_euler = (0.0, 0.0, turn)
        scene.collection.objects.link(inst)
    stand("Kit_Colony_ClimateCenter", 0.0, 0.0)
    stand("Kit_Colony_Plant", 220.0, -60.0)
    stand("Kit_Colony_Dome_A", -150.0, -130.0)
    stand("Kit_Colony_Dome_B", -210.0, -60.0)
    stand("Kit_Colony_Dome_C", -110.0, -200.0)
    stand("Kit_Colony_Greenhouse_A", -250.0, -150.0)
    stand("Kit_Colony_Greenhouse_B", 120.0, -200.0)
    render_view(scene, (500.0, -1100.0, 160.0), (0.0, -40.0, 90.0), os.path.join(out, "colony_1km.png"))
    render_view(scene, (1500.0, -4800.0, 300.0), (0.0, 0.0, 110.0), os.path.join(out, "colony_5km.png"), lens=50)
    render_view(scene, (260.0, -330.0, 60.0), (0.0, 0.0, 115.0), os.path.join(out, "climate_center_tall.png"),
                size=(900, 1400), lens=40)
    bpy.data.scenes.remove(scene)
    print("extra previews in " + out)


# --- The batch ----------------------------------------------------------------------------------
PIECES = [
    ("Kit_Colony_Dome_A", dome_a), ("Kit_Colony_Dome_B", dome_b), ("Kit_Colony_Dome_C", dome_c),
    ("Kit_Colony_Greenhouse_A", greenhouse_a), ("Kit_Colony_Greenhouse_B", greenhouse_b),
    ("Kit_Colony_Plant", plant), ("Kit_Colony_ClimateCenter", climate_center),
]


def main():
    kt.begin("kit_domes", 1)
    for name, build in PIECES:
        kt.piece(name, build())
    kt.finish()
    if os.environ.get("KIT_PREVIEW"):
        extra_previews(os.environ["KIT_PREVIEW"])


if __name__ == "__main__":
    main()
