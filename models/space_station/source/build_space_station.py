"""Builds the Cornerian space station (asteroid field scenery) in Blender and exports it.

Run inside Blender (Scripting tab, or through the Blender MCP):
    exec(open(r"<project>/models/space_station/source/build_space_station.py").read())
(set FORCE_EXPORT = True in the exec globals to export), or from the command line:
    blender --background --python build_space_station.py -- --export

Like build_destroyer.py, everything is in GAME coordinates (Godot: +X right,
+Y up, -Z forward), in metres, converted to Blender's Z-up frame by G(). The
origin is the station's centre, where the spokes meet the spindle.

Layout: a spindle along Z (bow at -Z) with a wheel round its middle, about
800 m across, joined by four spokes; the wheel's open quarters are wide enough
to fly through. Docking arms and a hangar sit at the bow, solar wings and a
comms dish at the stern. Surface detail (add_*_detail: frames, conduits,
plates, radiator fins, cargo, tanks, roof machinery) breaks up the large
faces; it is solid like the rest. Curved hulls are smooth-shaded, corners
hard (SMOOTH_ANGLE).

Each component is one mesh object, modelled around its own pivot (PIVOTS), so
the game can later char, hide or detach it on its own, like the destroyer's
parts. Node names: Core, Ring, Spoke0-3, Hangar, SolarL, SolarR, Dish.

Exports space_station.glb next to the source folder, and writes proxies.txt
next to this script: the `proxies` line for world/space_station.tscn (AI
avoidance spheres, from the layout values here). Paste it in after a layout
change.
"""

import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Vector

EXPORT = "--export" in sys.argv or globals().get("FORCE_EXPORT", False)
HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else \
    r"C:\Users\zemc7\OneDrive\Documentos\spaceship-project\models\space_station\source"
OUT = os.path.dirname(HERE)

# ---------------------------------------------------------------- layout
# The wheel's cross-section (radius, z), a chamfered box: inner face at
# RING_IN, outer face at RING_OUT, sides at +-RING_HALF.
RING_IN = 352.0
RING_OUT = 400.0
RING_HALF = 20.0
RING_CHAMFER = 6.0
HUB_RADIUS = 70.0
SPOKE_ANGLES = [45.0, 135.0, 225.0, 315.0]    # degrees round Z, from +X towards +Y
SPOKE_SIZE = (28.0, 20.0)                     # across (tangent), deep (along Z)
# Habitat modules on the outside of the wheel, between the spokes.
MODULE_ANGLES = [22.5 + 45.0 * i for i in range(8)]
# Blue collars round the wheel: at every spoke and at the quarter points.
COLLAR_ANGLES = SPOKE_ANGLES + [0.0, 90.0, 180.0, 270.0]
COLLAR_SPAN = 5.0                             # degrees
DOCK_Z = -168.0                               # docking arms and hangar, on the forward drum
HANGAR_CENTER = (0.0, -72.0, DOCK_Z)
HANGAR_SIZE = (70.0, 40.0, 90.0)
SOLAR_Z = 180.0
SOLAR_REACH = 380.0                           # wing tip, |x|
DISH_Z = 272.0
# The spindle, bow to stern, as (z, radius) profiles: one section per colour.
SPINDLE_SECTIONS = [
    ([(-272, 14), (-266, 22), (-250, 22), (-246, 30), (-200, 34)], "Hull"),
    ([(-200, 34), (-196, 44), (-140, 44), (-136, 34)], "HullLight"),
    ([(-136, 34), (-80, 34), (-70, 46), (-40, 56), (-30, HUB_RADIUS)], "Hull"),
    ([(-30, HUB_RADIUS), (30, HUB_RADIUS)], "HullLight"),
    ([(30, HUB_RADIUS), (40, 56), (70, 46), (80, 34), (150, 34)], "Hull"),
    ([(150, 34), (154, 44), (210, 44), (214, 34)], "HullLight"),
    ([(214, 34), (250, 30), (262, 18), (DISH_Z, 18)], "Hull"),
]
SPINDLE_PROFILE = [pt for profile, _ in SPINDLE_SECTIONS for pt in profile]
# Length of spindle each AI avoidance sphere covers.
SPINDLE_STEP = 30.0

# ---------------------------------------------------------------- detail
# Surface detail (see the add_*_detail functions): decoration that breaks up
# the large plain faces, solid like the rest of the hull.
RING_ARCS = 32                                # light/dark arcs round the wheel
RING_ARC_SEGMENTS = 3                         # lathe segments per arc
# Frames wrapped round the wheel at the arc joints that have no collar or module.
FRAME_ANGLES = [360.0 * k / RING_ARCS for k in range(1, RING_ARCS, 2)]
FRAME_SPAN = 0.5                              # degrees
# Radiator fin clusters on the outside of the wheel, one per 45 degrees,
# alternating either side of the habitat module.
FIN_ANGLES = [45.0 * m + (5.625 if m % 2 == 0 else 39.375) for m in range(8)]
FIN_COUNT, FIN_STEP = 4, 1.2                  # fins per cluster, degrees apart
# Spoke frames, from the hub outwards (between the blue bands).
SPOKE_RIBS = [HUB_RADIUS + 40.0 + 28.0 * k for k in range(8)]
# Fittings on the spindle's narrow sections: cargo containers forward, tanks
# aft, as (z from, z to, reach from the axis). The AI proxies cover them.
CONTAINER_ROWS = [-124.0, -102.0]             # row centres (z); containers 20 m long
TANK_Z = (86.0, 144.0)
FITTINGS = [(-134.0, -92.0, 44.0), (TANK_Z[0], TANK_Z[1], 49.0)]
# Faces meeting at less than this stay smoothly shaded (curved hulls); sharper
# edges (box corners, chamfers, steps in the spindle) stay hard.
SMOOTH_ANGLE = 30.0

PIVOTS = {
    "Core": (0.0, 0.0, 0.0),
    "Ring": (0.0, 0.0, 0.0),
    "Hangar": HANGAR_CENTER,
    "SolarL": (-44.0, 0.0, SOLAR_Z),
    "SolarR": (44.0, 0.0, SOLAR_Z),
    "Dish": (0.0, 0.0, DISH_Z),
}
for _i, _a in enumerate(SPOKE_ANGLES):
    PIVOTS["Spoke%d" % _i] = (HUB_RADIUS * math.cos(math.radians(_a)),
                              HUB_RADIUS * math.sin(math.radians(_a)), 0.0)

# ---------------------------------------------------------------- colours
# (sRGB colour as the game shows it, emission strength); material() converts
# to linear. The toon light is bright, so even the "white" hull is a mid grey.
COLORS = {
    "Hull": ((0.30, 0.32, 0.35), 0.0),
    "HullLight": ((0.40, 0.42, 0.45), 0.0),
    "HullDark": ((0.22, 0.235, 0.26), 0.0),    # detail: plates, frames, machinery
    "Dark": ((0.08, 0.09, 0.11), 0.0),
    "Accent": ((0.08, 0.20, 0.50), 0.0),       # Cornerian blue
    "Trim": ((0.80, 0.58, 0.12), 0.0),         # hazard yellow at docks and the hangar
    "Solar": ((0.05, 0.08, 0.22), 0.0),
    "Window": ((0.62, 0.85, 1.0), 3.0),
    "HangarGlow": ((0.45, 0.75, 1.0), 4.0),
    "NavRed": ((1.0, 0.12, 0.08), 6.0),
    "NavGreen": ((0.15, 1.0, 0.3), 6.0),
    "NavWhite": ((1.0, 1.0, 1.0), 6.0),
}

X = Vector((1.0, 0.0, 0.0))
Y = Vector((0.0, 1.0, 0.0))
Z = Vector((0.0, 0.0, 1.0))
TAU = 2.0 * math.pi


def G(v):
    """Game (Y up, -Z forward) to Blender (Z up, +Y forward)."""
    return Vector((v[0], -v[2], v[1]))


def material(name):
    full = "Station_" + name
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
    m.diffuse_color = (*rgb, 1.0)
    return m


def radial(deg):
    a = math.radians(deg)
    return Vector((math.cos(a), math.sin(a), 0.0))


def tangent(deg):
    a = math.radians(deg)
    return Vector((-math.sin(a), math.cos(a), 0.0))


# ---------------------------------------------------------------- primitives
# Each returns (verts, faces) in game coordinates; Part.add() collects them.
def box(center, size, axes=(X, Y, Z)):
    """A box of `size` along the three `axes` (unit vectors), about `center`."""
    c = Vector(center)
    hx, hy, hz = (s / 2 for s in size)
    ex, ey, ez = axes
    verts = [c + ex * (sx * hx) + ey * (sy * hy) + ez * (sz * hz)
             for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    return verts, faces


def beam(a, b, width, height, up=Y):
    """A box from a to b: `width` across, `height` towards `up`."""
    a, b = Vector(a), Vector(b)
    ez = (b - a).normalized()
    ex = up.cross(ez)
    if ex.length < 1e-6:
        ex = X.cross(ez)
    ex.normalize()
    ey = ez.cross(ex)
    return box((a + b) / 2, (width, height, (b - a).length), (ex, ey, ez))


def lathe(profile, segments, closed=False, a0=0.0, a1=TAU, origin=(0, 0, 0), axis=Z, ref=X):
    """Revolves a profile of (along-axis, radius) points round `axis` through
    `origin`, from angle a0 to a1 (measured from `ref`). An open profile (a
    spindle) gets end caps; a closed one (a ring's cross-section) is capped at
    the ends of a partial sweep."""
    o = Vector(origin)
    w = Vector(axis).normalized()
    u = (Vector(ref) - w * Vector(ref).dot(w)).normalized()
    v = w.cross(u)
    full = abs(a1 - a0 - TAU) < 1e-6
    n_ang = segments if full else segments + 1
    m = len(profile)
    verts = []
    for j in range(n_ang):
        a = a0 + (a1 - a0) * j / segments
        d = u * math.cos(a) + v * math.sin(a)
        verts += [o + w * t + d * r for t, r in profile]
    faces = []
    for j in range(segments):
        j2 = (j + 1) % n_ang
        for i in range(m if closed else m - 1):
            i2 = (i + 1) % m
            faces.append((j * m + i, j * m + i2, j2 * m + i2, j2 * m + i))
    if full and not closed:
        if profile[0][1] > 0:
            faces.append(tuple(j * m for j in range(n_ang)))
        if profile[-1][1] > 0:
            faces.append(tuple(j * m + m - 1 for j in range(n_ang)))
    if not full and closed:
        faces.append(tuple(range(m)))
        faces.append(tuple((n_ang - 1) * m + i for i in range(m)))
    return verts, faces


class Part:
    """One exported node: all its pieces in one mesh, one material slot per colour."""

    def __init__(self, name):
        self.name = name
        self.pivot = Vector(PIVOTS[name])
        self.verts = []
        self.faces = []
        self.mats = []

    def add(self, piece, mat):
        verts, faces = piece
        start = len(self.verts)
        self.verts += [Vector(p) for p in verts]
        for f in faces:
            self.faces.append(tuple(start + i for i in f))
            self.mats.append(mat)

    def build(self, collection):
        me = bpy.data.meshes.new(self.name)
        me.from_pydata([G(p - self.pivot) for p in self.verts], [], self.faces)
        names = sorted(set(self.mats))
        for n in names:
            me.materials.append(material(n))
        for poly, mat in zip(me.polygons, self.mats):
            poly.material_index = names.index(mat)
            poly.use_smooth = True
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()
        # Curved hulls shade smoothly (flat-shaded, the wheel and spindle broke
        # into a light or dark band per lathe segment); corners stay hard.
        me.set_sharp_from_angle(angle=math.radians(SMOOTH_ANGLE))
        o = bpy.data.objects.new(self.name, me)
        o.location = G(self.pivot)
        collection.objects.link(o)
        return o


def near_angle(deg, angles, span):
    return any(abs((deg - a + 180.0) % 360.0 - 180.0) < span for a in angles)


# ---------------------------------------------------------------- components
def build_core(rng):
    p = Part("Core")
    for profile, mat in SPINDLE_SECTIONS:
        p.add(lathe(profile, 32), mat)
    # Blue bands: round the hub and both drums.
    for z0, z1, r in ((-6, 6, HUB_RADIUS + 0.6), (-176, -164, 44.6), (176, 188, 44.6)):
        p.add(lathe([(z0, r), (z1, r)], 32), "Accent")
    # Dark docking collar at the very bow, with a white beacon.
    p.add(lathe([(-276, 8), (-272, 16)], 16), "Dark")
    p.add(box((0, 0, -277), (4, 4, 2)), "NavWhite")

    # Window rows round the hub and the drums.
    for z, r, n in ((-18, HUB_RADIUS, 40), (18, HUB_RADIUS, 40), (-188, 44, 24), (-152, 44, 24),
                    (164, 44, 24), (198, 44, 24)):
        for k in range(n):
            deg = 360.0 * (k + 0.5) / n
            if rng.random() < 0.15 or (r == HUB_RADIUS and near_angle(deg, SPOKE_ANGLES, 9.0)):
                continue
            p.add(box(radial(deg) * (r + 0.1) + Z * z, (0.6, 3.0, 1.8),
                      (radial(deg), tangent(deg), Z)), "Window")

    # Docking arms on the forward drum: sides and top (the hangar hangs below).
    for deg in (0.0, 90.0, 180.0):
        d = radial(deg)
        t = tangent(deg)
        p.add(beam(d * 40 + Z * DOCK_Z, d * 92 + Z * DOCK_Z, 8, 8, up=Z), "Hull")
        clamp = d * 98 + Z * DOCK_Z
        p.add(box(clamp, (14, 16, 22), (d, t, Z)), "HullLight")
        p.add(box(clamp + d * 7.3, (1, 10, 14), (d, t, Z)), "Dark")
        # Hazard stripes round the clamp, a light on its tip.
        for dz in (-8.5, 8.5):
            p.add(box(clamp + Z * dz, (14.4, 16.4, 2), (d, t, Z)), "Trim")
        p.add(box(clamp + d * 8.5 + t * 6, (2, 2, 2), (d, t, Z)), "NavGreen" if deg == 0 else
              ("NavRed" if deg == 180 else "NavWhite"))

    # Antenna masts off the bow, each tipped with a red light.
    for tip in ((0, 0, -330), (14, 10, -312), (-14, 10, -312)):
        base = Vector((tip[0] * 0.3, tip[1] * 0.3, -262))
        p.add(beam(base, tip, 1.6, 1.6), "HullLight")
        p.add(box(tip, (3, 3, 3)), "NavRed")
    add_core_detail(p)
    return p


def build_ring(rng):
    p = Part("Ring")
    c = RING_CHAMFER
    section = [(-RING_HALF + c, RING_IN), (-RING_HALF, RING_IN + c), (-RING_HALF, RING_OUT - c),
               (-RING_HALF + c, RING_OUT), (RING_HALF - c, RING_OUT), (RING_HALF, RING_OUT - c),
               (RING_HALF, RING_IN + c), (RING_HALF - c, RING_IN)]
    # Alternating light and dark arcs give the wheel a panelled rhythm.
    arcs = RING_ARCS
    for k in range(arcs):
        a0 = TAU * k / arcs
        p.add(lathe(section, RING_ARC_SEGMENTS, closed=True, a0=a0, a1=a0 + TAU / arcs),
              "Hull" if k % 2 else "HullLight")
    # Blue collars, a little proud of the wheel.
    collar =[(t + (1.5 if t > 0 else -1.5), r + (2.0 if r > (RING_IN + RING_OUT) / 2 else -2.0))
              for t, r in section]
    half = math.radians(COLLAR_SPAN / 2)
    for deg in COLLAR_ANGLES:
        a = math.radians(deg)
        p.add(lathe(collar, 2, closed=True, a0=a - half, a1=a + half), "Accent")

    # Windows: two rows on each side face (these face anyone flying through)
    # and two rows on the inner face.
    for side in (-1, 1):
        for r in (366.0, 386.0):
            n = int(TAU * r / 9.0)
            for k in range(n):
                deg = 360.0 * (k + 0.5) / n
                if rng.random() < 0.15 or near_angle(deg, COLLAR_ANGLES, COLLAR_SPAN / 2 + 1.0) \
                        or near_angle(deg, FRAME_ANGLES, FRAME_SPAN / 2 + 0.6):
                    continue
                p.add(box(radial(deg) * r + Z * side * (RING_HALF + 0.1), (1.4, 3.2, 0.6),
                          (radial(deg), tangent(deg), Z)), "Window")
    for z in (-7.0, 7.0):
        n = int(TAU * RING_IN / 9.0)
        for k in range(n):
            deg = 360.0 * (k + 0.5) / n
            if rng.random() < 0.15 or near_angle(deg, COLLAR_ANGLES, COLLAR_SPAN / 2 + 1.0) \
                    or near_angle(deg, FRAME_ANGLES, FRAME_SPAN / 2 + 0.6):
                continue
            p.add(box(radial(deg) * (RING_IN - 0.1) + Z * z, (0.6, 3.2, 1.6),
                      (radial(deg), tangent(deg), Z)), "Window")

    # Habitat modules on the outside, between the spokes, with lit sides and a
    # navigation light on top: red on the left (-X) half, green on the right.
    for deg in MODULE_ANGLES:
        d, t = radial(deg), tangent(deg)
        base = d * RING_OUT
        p.add(box(base + d * 7, (16, 34, 30), (d, t, Z)), "HullLight")
        p.add(box(base + d * 15.5, (1.2, 26, 22), (d, t, Z)), "Hull")
        p.add(box(base + d * 7, (4, 34.4, 30.4), (d, t, Z)), "Accent")
        for side in (-1, 1):
            for dx in range(-3, 4):
                p.add(box(base + d * 11 + t * (dx * 4.2) + Z * side * 15.1, (1.6, 2.6, 0.5), (d, t, Z)),
                      "Window")
        p.add(box(base + d * 17.5, (3, 3, 3), (d, t, Z)), "NavRed" if d.x < 0 else "NavGreen")
    add_ring_detail(p, section)
    return p


def build_spoke(i, deg, rng):
    p = Part("Spoke%d" % i)
    d, t = radial(deg), tangent(deg)
    w, h = SPOKE_SIZE
    p.add(beam(d * (HUB_RADIUS - 4), d * (RING_IN + 4), w, h, up=Z), "Hull")
    # Conduits along both faces, and blue bands near either end.
    for side in (-1, 1):
        p.add(beam(d * (HUB_RADIUS + 4) + Z * side * (h / 2 + 1.5), d * (RING_IN - 4) + Z * side * (h / 2 + 1.5),
                   5, 3, up=Z), "Dark")
    for r in (HUB_RADIUS + 26, RING_IN - 26):
        p.add(box(d * r, (8, w + 1.2, h + 7), (d, t, Z)), "Accent")
    # Frames round the spoke at intervals, standing a little proud.
    for r in SPOKE_RIBS:
        p.add(box(d * r, (2.4, w + 1.6, h + 1.6), (d, t, Z)), "HullLight")
    # Lit windows down the leading and trailing sides (the transit tube).
    for side in (-1, 1):
        r = HUB_RADIUS + 40
        while r < RING_IN - 36:
            if rng.random() > 0.2 and all(abs(r - rib) > 2.5 for rib in SPOKE_RIBS):
                p.add(box(d * r + t * side * (w / 2 + 0.1), (3.0, 0.6, 1.8), (d, t, Z)), "Window")
            r += 8.0
    # White strobes where the spoke meets the wheel.
    for side in (-1, 1):
        p.add(box(d * (RING_IN - 10) + Z * side * (h / 2 + 4), (2.5, 2.5, 2.5), (d, t, Z)), "NavWhite")
    return p


def build_hangar(rng):
    p = Part("Hangar")
    cx, cy, cz = HANGAR_CENTER
    sx, sy, sz = HANGAR_SIZE
    front = cz - sz / 2
    # Bay block, tapering a little towards its bottom.
    outline = [(cx - sx / 2, cz + sz / 2), (cx - sx / 2, front), (cx + sx / 2, front), (cx + sx / 2, cz + sz / 2)]
    bottom = [(x * 0.82, z) for x, z in outline]
    verts = [Vector((x, cy - sy / 2, z)) for x, z in bottom] + [Vector((x, cy + sy / 2, z)) for x, z in outline]
    faces = [(0, 1, 2, 3), (4, 5, 6, 7)] + [(i, (i + 1) % 4, 4 + (i + 1) % 4, 4 + i) for i in range(4)]
    p.add((verts, faces), "HullLight")
    # Pylon up into the forward drum.
    p.add(box((cx, cy + sy / 2 + 8, cz + 6), (30, 18, 50)), "Hull")
    # The mouth on the bow face: a dark opening framed in yellow, lit along the
    # floor and ceiling.
    mouth = Vector((cx, cy + 1, front - 0.2))
    p.add(box(mouth, (48, 22, 0.6)), "Dark")
    p.add(box(mouth + Y * 12.5 - Z * 0.3, (54, 3, 1)), "Trim")
    p.add(box(mouth - Y * 12.5 - Z * 0.3, (50, 3, 1)), "Trim")
    for side in (-1, 1):
        p.add(box(mouth + X * side * 25.5 - Z * 0.3, (3, 22, 1)), "Trim")
    p.add(box(mouth + Y * 9.8 - Z * 0.4, (44, 1.2, 0.6)), "HangarGlow")
    p.add(box(mouth - Y * 9.8 - Z * 0.4, (44, 1.2, 0.6)), "HangarGlow")
    # An apron sticking out under the mouth, with approach lights along it.
    apron_y = cy - sy / 2 + 3
    p.add(box((cx, apron_y, front - 24), (30, 6, 50)), "Hull")
    for k in range(5):
        p.add(box((cx, apron_y + 3.4, front - 6 - k * 9), (6, 0.8, 1.2)), "HangarGlow")
    # A blue stripe and a window row along each (sloping) side.
    def side_x(y):
        return sx / 2 * (0.82 + 0.18 * (y - (cy - sy / 2)) / sy)

    for side in (-1, 1):
        p.add(box((cx + side * side_x(cy + 16), cy + 16, cz), (1.2, 5, sz - 2)), "Accent")
        for z in range(int(front + 14), int(cz + sz / 2 - 6), 7):
            if rng.random() > 0.2:
                p.add(box((cx + side * (side_x(cy + 8) + 0.1), cy + 8, z), (0.6, 1.8, 3.2)), "Window")
    add_hangar_detail(p)
    return p


def build_solar(side, rng):
    p = Part("SolarL" if side < 0 else "SolarR")
    root = Vector((side * 44.0, 0.0, SOLAR_Z))
    # A gimbal drum where the wing meets the drum.
    p.add(lathe([(side * 40, 12), (side * 62, 12)], 16, axis=X), "Dark")
    p.add(lathe([(side * 62, 9), (side * 74, 7)], 16, axis=X), "HullLight")
    # The truss: four longerons and braced bays.
    x0, x1 = side * 70.0, side * SOLAR_REACH
    s = 5.0
    corners = [(-s, -s), (-s, s), (s, -s), (s, s)]
    for cy, cz in corners:
        p.add(beam((x0, cy, SOLAR_Z + cz), (x1, cy, SOLAR_Z + cz), 1.4, 1.4), "HullLight")
    bay = 20.0
    n = int(abs(x1 - x0) / bay)
    for k in range(n + 1):
        x = x0 + side * k * bay
        for (ya, za), (yb, zb) in (((-s, -s), (s, -s)), ((-s, s), (s, s)), ((-s, -s), (-s, s)), ((s, -s), (s, s))):
            p.add(beam((x, ya, SOLAR_Z + za), (x, yb, SOLAR_Z + zb), 1.0, 1.0, up=X), "HullLight")
        if k < n:
            xn = x + side * bay
            for z in (-s, s):
                p.add(beam((x, -s, SOLAR_Z + z), (xn, s, SOLAR_Z + z), 0.8, 0.8, up=Z), "Hull")
    # Panels above and below the truss, framed, facing the bow and stern.
    length, gap = 48.0, 4.0
    x = side * 84.0
    while abs(x) + length <= SOLAR_REACH + 0.1:
        mid_x = x + side * length / 2
        for up in (-1, 1):
            y0, y1 = up * 8.0, up * 72.0
            mid = Vector((mid_x, (y0 + y1) / 2, SOLAR_Z))
            p.add(box(mid, (length, 64, 0.8)), "Solar")
            # Frame and cell dividers, standing proud on both faces.
            for dy in (-32, 32):
                p.add(box(mid + Y * dy, (length, 1.2, 1.4)), "HullLight")
            for dx in (-length / 2, 0.0, length / 2):
                p.add(box(mid + X * dx, (1.2, 64, 1.4)), "HullLight")
            for dy in (-16.0, 0.0, 16.0):
                p.add(box(mid + Y * dy, (length, 0.6, 1.1)), "Dark")
        x += side * (length + gap)
    # Tip lights.
    p.add(box((side * (SOLAR_REACH + 2), 0, SOLAR_Z), (3, 3, 3)), "NavRed" if side < 0 else "NavGreen")
    return p


def build_dish(rng):
    p = Part("Dish")
    # Mast off the stern, then a parabolic dish facing aft (+Z).
    p.add(lathe([(DISH_Z, 10), (DISH_Z + 22, 7)], 16), "HullLight")
    base = DISH_Z + 20.0
    depth, rim, inner, thick = 24.0, 60.0, 8.0, 3.0
    front = [(base + 4 + depth * (r / rim) ** 2, r) for r in [inner + (rim - inner) * k / 10 for k in range(11)]]
    back = [(z - thick, r) for z, r in reversed(front)]
    p.add(lathe(front + back, 32, closed=True), "HullLight")
    # A dark rim band, the feed horn on three struts.
    z0, z1 = front[-1][0] - thick - 0.5, front[-1][0] + 0.5
    p.add(lathe([(z0, rim - 2), (z0, rim + 0.8), (z1, rim + 0.8), (z1, rim - 2)], 32, closed=True), "Accent")
    focus = base + 4 + rim * rim / (4 * depth)
    for k in range(3):
        a = TAU * k / 3 + math.pi / 2
        rim_pt = Vector((math.cos(a) * rim * 0.95, math.sin(a) * rim * 0.95, front[-1][0] - 1))
        p.add(beam(rim_pt, (0, 0, focus - 4), 1.4, 1.4, up=Z), "HullLight")
    p.add(lathe([(focus - 6, 5), (focus + 2, 3)], 12), "Dark")
    p.add(box((0, 0, focus + 3), (2.5, 2.5, 2.5)), "NavWhite")
    return p


# ---------------------------------------------------------------- detail
# Seeded on their own (not the windows' rng), so changing detail never moves a
# window.
def ring_box(deg, r, z, size):
    """A box at angle `deg` round the Z axis, `r` out and `z` along it; `size`
    is (radial, round the axis, along Z)."""
    return box(radial(deg) * r + Z * z, size, (radial(deg), tangent(deg), Z))


def free_arcs(blocked, step=0.25):
    """The stretches round the wheel, (start, end) in degrees, clear of every
    (angle, half-width) in `blocked`."""
    arcs, start = [], None
    n = int(360.0 / step)
    for k in range(n + 1):
        deg = k * step
        clear = k < n and not any(near_angle(deg, [a], w) for a, w in blocked)
        if clear and start is None:
            start = deg
        elif not clear and start is not None:
            arcs.append((start, deg - step))
            start = None
    return arcs


def conduit_runs(p, rng, blocked, r, z, size):
    """A pipe laid round the wheel at radius `r` and height `z`, `size` (radial,
    Z) in cross-section, broken into straight runs of 2-3.5 degrees with a
    junction box between them, and kept out of `blocked`."""
    for a0, a1 in free_arcs(blocked):
        deg = a0
        while deg < a1 - 1.0:
            run = min(rng.uniform(2.0, 3.5), a1 - deg)
            half = math.radians(run / 2)
            p.add(ring_box(deg + run / 2, r * math.cos(half), z, (size[0], 2.0 * r * math.sin(half), size[1])),
                  "Dark")
            end = deg + run
            if end < a1 - 0.5:
                p.add(ring_box(end, r, z, (size[0] + 1.2, 3.0, size[1] + 1.2)), "HullDark")
            deg = end + rng.uniform(0.3, 0.8)


def add_ring_detail(p, section):
    """Frames, conduits, hull plates, radiator fins and a guide rail on the wheel."""
    rng = random.Random(31)
    # Frames: the cross-section a little proud, wrapped round the wheel at the
    # arc joints that have no collar or module.
    frame = [(t + (0.7 if t > 0 else -0.7), r + (0.9 if r > (RING_IN + RING_OUT) / 2 else -0.9))
             for t, r in section]
    half = math.radians(FRAME_SPAN / 2)
    for deg in FRAME_ANGLES:
        a = math.radians(deg)
        p.add(lathe(frame, 1, closed=True, a0=a - half, a1=a + half), "HullDark")
    collars = [(a, COLLAR_SPAN / 2 + 1.5) for a in COLLAR_ANGLES]
    frames = [(a, FRAME_SPAN / 2 + 1.0) for a in FRAME_ANGLES]
    modules = [(a, 3.5) for a in MODULE_ANGLES]
    fins = [(a, FIN_COUNT / 2 * FIN_STEP + 1.5) for a in FIN_ANGLES]

    # Side faces (what you see head on): a conduit between the window rows.
    for side in (-1, 1):
        conduit_runs(p, rng, collars + frames, (RING_IN + RING_OUT) / 2, side * (RING_HALF + 0.5), (3.0, 1.0))

    # Outside: a plate on each lathe segment (flush with its flat face) in
    # one of the two tones its arc isn't, a conduit either side of them, and
    # clusters of radiator fins, which break up the wheel's silhouette.
    segments = RING_ARCS * RING_ARC_SEGMENTS
    seg = 360.0 / segments
    for j in range(segments):
        deg = (j + 0.5) * seg
        if rng.random() < 0.25 or any(near_angle(deg, [a], w + seg / 2) for a, w in collars + modules + fins):
            continue
        base = "Hull" if (j // RING_ARC_SEGMENTS) % 2 else "HullLight"
        tone = rng.choice([t for t in ("Hull", "HullLight", "HullDark") if t != base])
        p.add(ring_box(deg, RING_OUT * math.cos(math.radians(seg / 2)) + 0.25, 0.0,
                       (0.5, 1.6 * RING_OUT * math.sin(math.radians(seg / 2)), 13.0)), tone)
    for z in (-9.5, 9.5):
        conduit_runs(p, rng, collars + modules, RING_OUT + 1.0, z, (2.0, 2.2))
    for c in FIN_ANGLES:
        span = math.radians(FIN_COUNT / 2 * FIN_STEP + 0.6)
        p.add(ring_box(c, RING_OUT + 0.5, 0.0, (1.0, 2.0 * RING_OUT * math.sin(span), 18.0)), "HullDark")
        for i in range(FIN_COUNT):
            p.add(ring_box(c + (i - (FIN_COUNT - 1) / 2) * FIN_STEP, RING_OUT + 5.0, 0.0, (9.0, 0.8, 16.0)),
                  "HullLight")

    # Inside (what you see flying through): a rail down the middle, lit every
    # other segment, broken where the spokes meet the wheel.
    in_r = RING_IN * math.cos(math.radians(seg / 2))
    chord = 2.0 * RING_IN * math.sin(math.radians(seg / 2))
    for j in range(segments):
        deg = (j + 0.5) * seg
        if any(near_angle(deg, [a], w) for a, w in collars):
            continue
        p.add(ring_box(deg, in_r - 0.6, 0.0, (1.2, chord * 0.96, 3.0)), "Dark")
        if j % 2 == 0:
            p.add(ring_box(deg, in_r - 1.4, 0.0, (0.6, 1.6, 1.6)), "Window")


def add_core_detail(p):
    """Ribs down the hub's cones, cargo containers and tanks on the spindle."""
    rng = random.Random(53)
    # Ribs down both cones, on the lathe's vertex lines (where the surface is
    # at its full radius), standing out along the cone's normal.
    aft = [(30.0, HUB_RADIUS), (40.0, 56.0), (70.0, 46.0), (80.0, 34.0)]
    for cone in (aft, [(-z, r) for z, r in reversed(aft)]):
        for k in range(16):
            d = radial(22.5 * k)
            for (za, ra), (zb, rb) in zip(cone, cone[1:]):
                n = Vector((-(rb - ra), zb - za)).normalized()   # (z, r)
                a = Z * (za + n.x * 0.8) + d * (ra + n.y * 0.8)
                b = Z * (zb + n.x * 0.8) + d * (rb + n.y * 0.8)
                p.add(beam(a, b, 2.2, 1.6, up=d), "HullLight")
    # Cargo containers in two rows round the narrow section ahead of the hub,
    # each with a dark band round its middle.
    for z in CONTAINER_ROWS:
        for k in range(8):
            if rng.random() < 0.15:
                continue
            deg = 22.5 + 45.0 * k
            p.add(ring_box(deg, 38.1, z, (9.0, 12.0, 20.0)),
                  rng.choice(("Hull", "HullLight", "HullDark", "HullLight", "Accent")))
            p.add(ring_box(deg, 38.1, z, (9.4, 12.4, 1.2)), "Dark")
    # Tanks round the narrow section behind it, with a blue band.
    z0, z1 = TANK_Z
    for k in range(6):
        o = radial(30.0 + 60.0 * k) * 41.0
        p.add(lathe([(z0, 3.0), (z0 + 4, 7.0), (z1 - 4, 7.0), (z1, 3.0)], 12, origin=o), "HullLight")
        mid = (z0 + z1) / 2
        p.add(lathe([(mid - 3, 7.3), (mid + 3, 7.3)], 12, origin=o), "Accent")


def add_hangar_detail(p):
    """Plates under the hangar, machinery on its roof (clear of the pylon)."""
    rng = random.Random(71)
    cx, cy, cz = HANGAR_CENTER
    sx, sy, sz = HANGAR_SIZE
    front = cz - sz / 2
    for i in range(4):
        for j in range(6):
            if rng.random() < 0.2:
                continue
            p.add(box((cx + (i - 1.5) * 14.0, cy - sy / 2 - 0.25, front + 8.0 + j * 15.0), (12.5, 0.5, 13.5)),
                  rng.choice(("Hull", "HullDark")))
    top = cy + sy / 2
    placed = 0
    for _ in range(200):
        if placed >= 9:
            break
        w, length = rng.uniform(4.0, 9.0), rng.uniform(4.0, 10.0)
        x = rng.uniform(cx - sx / 2 + w / 2 + 2, cx + sx / 2 - w / 2 - 2)
        z = rng.uniform(front + length / 2 + 2, cz + sz / 2 - length / 2 - 2)
        # The pylon (30 x 50, centred 6 m aft of the hangar's centre).
        if abs(x - cx) < 15 + w / 2 + 2 and abs(z - (cz + 6)) < 25 + length / 2 + 2:
            continue
        h = rng.uniform(1.5, 4.0)
        p.add(box((x, top + h / 2, z), (w, h, length)), rng.choice(("Dark", "HullDark", "Hull")))
        placed += 1


def build():
    scene =bpy.data.scenes.get("SpaceStation") or bpy.data.scenes.new("SpaceStation")
    if bpy.context.window:
        bpy.context.window.scene = scene
    col = bpy.data.collections.get("SpaceStation")
    if col is None:
        col = bpy.data.collections.new("SpaceStation")
        scene.collection.children.link(col)
    for o in list(col.objects):
        bpy.data.objects.remove(o)
    for me in list(bpy.data.meshes):
        if me.users == 0:
            bpy.data.meshes.remove(me)
    # Seeded, so re-running gives the same windows.
    rng = random.Random(2077)
    parts = [build_core(rng), build_ring(rng)]
    parts += [build_spoke(i, a, rng) for i, a in enumerate(SPOKE_ANGLES)]
    parts += [build_hangar(rng), build_solar(-1, rng), build_solar(1, rng), build_dish(rng)]
    return [part.build(col) for part in parts]


# ---------------------------------------------------------------- AI proxies
def spindle_radius(z):
    """The spindle's radius at z (0 beyond its ends)."""
    for (z0, r0), (z1, r1) in zip(SPINDLE_PROFILE, SPINDLE_PROFILE[1:]):
        if z0 <= z <= z1:
            if z1 == z0:  # a step in the profile (or a repeated point between sections)
                return max(r0, r1)
            return r0 + (r1 - r0) * (z - z0) / (z1 - z0)
    return 0.0


def proxies():
    """AI avoidance spheres (x, y, z, radius), game coordinates: a chain round
    the wheel, rows down the spokes, the spindle, bow and stern fittings, and two
    rows over each solar wing. The AI pads each by 1.3x plus a margin, so the
    open quarters of the wheel stay open to fly through."""
    spheres = []
    ring_mid = (RING_IN + RING_OUT) / 2
    n = math.ceil(TAU * ring_mid / 40.0)
    for k in range(n):
        a = TAU * k / n
        spheres.append((ring_mid * math.cos(a), ring_mid * math.sin(a), 0.0, 28.0))
    # Spheres must enclose what they cover, not just match its radius: the AI
    # ground against the hub's rims when its sphere was the hub's radius.
    for deg in SPOKE_ANGLES:
        r = HUB_RADIUS + 22.0
        while r < RING_IN - 10.0:
            p = radial(deg) * r
            spheres.append((p.x, p.y, 0.0, 18.0))
            r += 22.0
    # Spindle: a sphere per SPINDLE_STEP slice, enclosing the widest part of it.
    z = SPINDLE_PROFILE[0][0] + SPINDLE_STEP / 2
    while z < SPINDLE_PROFILE[-1][0]:
        half = SPINDLE_STEP / 2
        widest = max(spindle_radius(z + t * half / 4) for t in range(-4, 5))
        for z0, z1, reach in FITTINGS:
            if z0 < z + half and z1 > z - half:
                widest = max(widest, reach)
        spheres.append((0.0, 0.0, z, round(math.hypot(widest, half) + 2.0)))
        z += SPINDLE_STEP
    spheres.append((0.0, 0.0, -312.0, 22.0))     # bow antennas
    for deg in (0.0, 90.0, 180.0):           # docking clamps
        p = radial(deg) * 92
        spheres.append((p.x, p.y, DOCK_Z, 16.0))
    cx, cy, cz = HANGAR_CENTER
    for dz in (-24.0, 24.0):
        spheres.append((cx, cy, cz + dz, 36.0))
    spheres.append((cx, cy - 17, cz - HANGAR_SIZE[2] / 2 - 26, 18.0))   # apron
    spheres.append((0.0, 0.0, DISH_Z + 38, 62.0))                         # dish
    for side in (-1, 1):
        x = 90.0
        while x < SOLAR_REACH + 10:
            for y in (-38.0, 38.0):
                spheres.append((side * x, y, SOLAR_Z, 40.0))
            x += 50.0
    return spheres


def write_proxies():
    spheres = proxies()
    text = ", ".join("Vector4(%g, %g, %g, %g)" % tuple(round(c, 1) for c in s) for s in spheres)
    with open(os.path.join(HERE, "proxies.txt"), "w") as f:
        f.write("proxies = Array[Vector4]([%s])\n" % text)
    return len(spheres)


def export(objects):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objects:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "space_station.glb"), export_format="GLB",
                              use_selection=True, use_active_scene=True, export_apply=True, export_yup=True,
                              export_materials="EXPORT", export_cameras=False, export_lights=False)
    print("AI proxies written:", write_proxies())


station = build()
if EXPORT:
    export(station)
print("space station built:", len(station), "objects,",
      sum(len(o.data.polygons) for o in station), "faces", "exported" if EXPORT else "")
