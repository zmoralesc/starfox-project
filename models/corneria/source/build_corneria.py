"""Builds the Corneria map in Blender: the terrain height grid and the props on it.

Run inside Blender (Scripting tab, or through the Blender MCP):
    exec(open(r"<project>/models/corneria/source/build_corneria.py").read())

Like build_destroyer.py, everything is in GAME coordinates (Godot: +X east,
+Y up, -Z north), in metres, converted to Blender's Z-up frame by G(). The map
is a SIZE x SIZE square centred on the origin; sea level is 0.

Layout (north is -Z):
    south          open sea, the mission's approach, with sea stacks
    bay            an inlet running north from the coast, spanned by stone arches
    centre         Corneria City on the east bank where the river meets the bay
    north-east     a plateau with a lake; its river drops off the cliff as a waterfall
    east coast     a harbour town
    west           rolling hills, mesas and the Cornerian military base
    edges          a ring of mountains (north, east, west), opening to the sea

Run with FORCE_EXPORT = True in the exec globals (or from the command line:
    blender --background --python build_corneria.py -- --export
) to write, next to the source folder:
    corneria_map.tres    the TerrainMap Terrain loads: ground heights, which cells
                         are paved or under the plateau's water, and the height of
                         the structures on each cell (the AI flies over those)
    corneria_props.glb   the props: city, town, base, arches, bridge, road, sea
                         stacks, trees, and the plateau lake, river and falls
The sea is not exported: Terrain makes it.
"""

import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector, noise

EXPORT = "--export" in sys.argv or globals().get("FORCE_EXPORT", False)
HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else \
    r"C:\Users\zemc7\OneDrive\Documentos\spaceship-project\models\corneria\source"

SIZE = 8000.0
HALF = SIZE / 2
CELL = 25.0                       # terrain grid spacing, as Terrain.cell_size
POINTS = int(SIZE / CELL) + 1

# --- Layout (game x, z) ---------------------------------------------------
CITY = (750.0, 100.0, 900.0, 14.0)            # centre x, z, radius, ground height
BASE = (-2300.0, -400.0, 700.0, 20.0)
PLATEAU_H = 130.0
PLATEAU = [(1250, -4000), (4000, -4000), (4000, -900), (3000, -1000), (2400, -1400),
           (1900, -1800), (1500, -2300), (1250, -2900)]
LAKE = (2300.0, -2450.0, 450.0, 300.0)        # centre x, z, radius x, radius z
LAKE_LEVEL = 120.0
UPPER_RIVER = [(2050, -2300), (1960, -2050), (1890, -1860)]
FALLS = (1870.0, -1830.0)                     # where the river leaves the cliff
LOWER_RIVER = [(1850, -1800), (1500, -1450), (1100, -1150), (600, -850), (150, -500),
               (-150, -50), (-300, 500), (-340, 800)]
BAY = [(-450, 2700), (-480, 1900), (-400, 1300), (-330, 800)]
MESAS = [(-1700, 1100, 220, 150), (-2700, 500, 260, 190), (-1100, -1900, 200, 170),
         (1700, 700, 180, 120), (-600, -2700, 230, 200)]
# A dry canyon from the north-west mountains down to the river; its floor
# falls from the first height to the second.
CANYON = [(-2700, -2700), (-2200, -2000), (-1600, -1650), (-1100, -1200), (-800, -500), (-450, 50)]
CANYON_FLOOR = (90.0, -8.0)
# The road bridge over the river mouth, on the line of one of the city's streets
# (city grid coordinates: west end u, east end u, street v; see city_xy), its deck
# height, and the road on from its west end to the base's taxiway.
BRIDGE = (-1060.0, -760.0, 385.0, 30.0)
ROAD_WAYPOINTS = [(-700, 240), (-1000, 330), (-1350, 230), (-1700, 60), (-1950, -150), (-2235, -150)]
ROAD_STEP = 20.0
ROAD = []            # the road's centreline, made by make_road()
ROAD_LENGTHS = []    # distance along the road at each ROAD point
ROAD_PROFILE = []    # the road's height every ROAD_STEP metres
LOW_LAKES = [(-1300, -150, 260, 180), (2050, -350, 230, 160)]   # x, z, radius x, radius z
ISLANDS = [(1500, 3050, 260, 45), (-2250, 3250, 320, 70)]       # x, z, radius, height
SEA_STACKS = [(-1300, 2750), (-1650, 2500), (-1100, 3150), (-2100, 2950), (-850, 2550),
              (1000, 2950), (1400, 2650), (300, 3300)]
START = (-450.0, 120.0, 3400.0)               # where the mission begins, heading north


def coast_z(x):
    """The coastline: land north of it (smaller z), sea south."""
    return 2150 + 220 * math.sin(x / 650 + 0.5) + 120 * math.sin(x / 280 + 2.0)


TOWN = (2450.0, coast_z(2450.0) - 400.0, 380.0, 8.0)

# Preview colours (sRGB), as Terrain colours faces.
SAND = (0.86, 0.79, 0.55)
GRASS = (0.42, 0.66, 0.3)
GRASS_DARK = (0.3, 0.52, 0.24)
ROCK = (0.5, 0.47, 0.44)
SNOW = (0.94, 0.96, 1.0)
PAVED = (0.55, 0.55, 0.58)


def G(x, y, z):
    """Game (Y up, -Z north) to Blender (Z up, +Y north)."""
    return Vector((x, -z, y))


# --- Helpers ---------------------------------------------------------------
def smoothstep(a, b, x):
    t = min(max((x - a) / (b - a), 0.0), 1.0)
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def fbm(x, z, scale, octaves=4, seed=0):
    p = Vector((x / scale + seed * 17.3, z / scale + seed * 31.7, seed * 5.1))
    total, amp, norm = 0.0, 1.0, 0.0
    for _ in range(octaves):
        total += noise.noise(p) * amp
        norm += amp
        amp *= 0.5
        p *= 2.0
    return total / norm


def seg_dist(px, pz, a, b):
    ax, az = a
    bx, bz = b
    dx, dz = bx - ax, bz - az
    t = max(0.0, min(1.0, ((px - ax) * dx + (pz - az) * dz) / (dx * dx + dz * dz)))
    return math.hypot(px - ax - t * dx, pz - az - t * dz), t


def line_dist(px, pz, pts):
    """Distance to a polyline, and how far along it (0..1) the nearest point is."""
    best, along = 1e18, 0.0
    n = len(pts) - 1
    for k in range(n):
        d, t = seg_dist(px, pz, pts[k], pts[k + 1])
        if d < best:
            best, along = d, (k + t) / n
    return best, along


def polygon_sdist(px, pz, poly):
    """Signed distance to a polygon's edge: positive inside."""
    inside = False
    d = 1e18
    n = len(poly)
    for k in range(n):
        a, b = poly[k], poly[(k + 1) % n]
        if (a[1] > pz) != (b[1] > pz):
            if px < a[0] + (pz - a[1]) * (b[0] - a[0]) / (b[1] - a[1]):
                inside = not inside
        d = min(d, seg_dist(px, pz, a, b)[0])
    return d if inside else -d


def bay_x(z):
    """The bay's centreline x at a given z (the BAY points run north as z falls)."""
    if z >= BAY[0][1]:
        return BAY[0][0]
    for a, b in zip(BAY, BAY[1:]):
        if b[1] <= z <= a[1]:
            return lerp(a[0], b[0], (a[1] - z) / (a[1] - b[1]))
    return BAY[-1][0]


def flatten(h, x, z, zone, blend):
    cx, cz, r, target = zone
    t = smoothstep(r + blend, r, math.hypot(x - cx, z - cz))
    return lerp(h, target, t)


# --- The landscape ---------------------------------------------------------
def height(x, z, road=True):
    # Warped coordinates: bends every noise layer below so nothing lines up.
    wx = x + fbm(x, z, 1500, 3, 10) * 500
    wz = z + fbm(x, z, 1500, 3, 11) * 500
    # Hills everywhere but the city, rougher in some regions than others.
    away = smoothstep(CITY[2] + 50, CITY[2] + 450, math.hypot(x - CITY[0], z - CITY[1]))
    rough = 0.45 + 0.55 * smoothstep(-0.4, 0.4, fbm(x, z, 2600, 2, 12))
    h = 26 + fbm(wx, wz, 1100, 4, 1) * 32
    h += max(0.0, fbm(wx, wz, 650, 5, 2) + 0.15) * 150 * rough * away
    # Sharp ridgelines in patches, the rock outcrops between the hills.
    ridge = (1 - abs(fbm(wx, wz, 1100, 4, 3))) ** 3
    ridges = smoothstep(0.05, 0.45, fbm(x, z, 2200, 2, 13)) * away
    h += (1 - abs(fbm(wx, wz, 800, 4, 14))) ** 4 * 240 * ridges
    # Ridged inland mountains in the north-west.
    h += ridge * smoothstep(-600, -1800, x) * smoothstep(-1000, -2200, z) * 380

    # Boundary mountains on the north, east and west. The edge is warped and its
    # start varies, so the range wanders in and out with spurs and bays; peaks
    # and saddles come from the height noise. It fades out toward the sea.
    ex = abs(x + fbm(x, z, 1800, 3, 15) * 750)
    ez = abs(z + fbm(x, z, 1800, 3, 16) * 750)
    edge = lerp(max(ex, ez), math.hypot(ex, ez) * 0.82, 0.35) / HALF
    start = 0.7 + 0.12 * fbm(x, z, 2000, 2, 17)
    peaks = 400 + 320 * fbm(wx, wz, 1300, 3, 18)
    ring = smoothstep(start, start + 0.24, edge) * peaks * (0.55 + 0.45 * ridge)
    h += max(0.0, ring) * (1 - smoothstep(1300, 2500, z + fbm(x, z, 900, 2, 19) * 400))

    # The canyon: raise the land along it so it has walls, then cut it.
    d, along = line_dist(x, z, CANYON)
    h += smoothstep(450, 150, d) * 70 * (1 - along * 0.6)
    floor = lerp(*CANYON_FLOOR, along) + fbm(x, z, 300, 2, 20) * 6
    h = lerp(h, min(h, floor), smoothstep(115, 45, d + fbm(x, z, 250, 2, 21) * 25))

    # North-east plateau with a lake and the river that feeds the falls.
    plateau = smoothstep(-40, 40, polygon_sdist(x, z, PLATEAU))
    knolls = max(0.0, fbm(wx, wz, 350, 4, 4) + 0.1) * 70 + (1 - abs(fbm(wx, wz, 500, 3, 25))) ** 5 * 60
    h = lerp(h, max(h, PLATEAU_H + knolls), plateau)
    lx, lz, rx, rz = LAKE
    e = ((x - lx) / rx) ** 2 + ((z - lz) / rz) ** 2
    h = lerp(h, 100, (1 - smoothstep(0.7, 1.1, e)) * plateau)
    d, _ = line_dist(x, z, UPPER_RIVER)
    h = lerp(h, 108, smoothstep(90, 30, d) * plateau)

    for mx, mz, r, mh in MESAS:
        t = smoothstep(r + 40, r - 40, math.hypot(x - mx, z - mz))
        h = lerp(h, max(h, mh + fbm(x, z, 200, 2, 5) * 8), t)

    # Flat ground for the city, the base and the town.
    h = flatten(h, x, z, CITY, 300)
    h = flatten(h, x, z, BASE, 300)
    h = flatten(h, x, z, TOWN, 200)

    # The lower river, from the foot of the falls to the bay.
    d, _ = line_dist(x, z, LOWER_RIVER)
    h = lerp(h, -8, smoothstep(170, 35, d) * (1 - plateau))
    # The road from the river bridge to the base runs on a graded bed, cutting a
    # valley through the hills (or banking up over dips) on its way.
    if road and ROAD_PROFILE:
        d, s = road_dist(x, z)
        if d < 260:
            h = lerp(h, road_height(s), smoothstep(170, 30, d + fbm(x, z, 220, 2, 26) * 20))
    # The bay, narrowing inland.
    d, along = line_dist(x, z, BAY)
    r = lerp(380, 220, along)
    h = lerp(h, -22, smoothstep(r + 220, r, d))
    # Lowland lakes (the sea plane fills anything below sea level).
    for lx, lz, rx, rz in LOW_LAKES:
        e = ((x - lx) / rx) ** 2 + ((z - lz) / rz) ** 2 + fbm(x, z, 200, 2, 22) * 0.25
        h = lerp(h, -10, 1 - smoothstep(0.6, 1.3, e))
    # The coast: seabed south of it. Beaches in the east, bluffs in the west.
    bluff = smoothstep(-900, -1900, x)
    inland = coast_z(x) - z
    h += bluff * smoothstep(0, 300, inland) * smoothstep(1000, 500, inland) * 70
    h = lerp(-28 + fbm(x, z, 500, 2, 6) * 6, h, smoothstep(lerp(-200, -30, bluff), lerp(260, 50, bluff), inland))
    for ix, iz, r, ih in ISLANDS:
        t = smoothstep(r + 150, r * 0.4, math.hypot(x - ix, z - iz) + fbm(x, z, 180, 2, 23) * 80)
        h = max(h, lerp(-28, ih + fbm(x, z, 150, 2, 24) * 20, t))
    # Sink the very edge so it meets the far ground.
    return lerp(h, -6, smoothstep(0.96, 1.0, max(abs(x), abs(z)) / HALF))


def face_color(centre, normal_y, x, z):
    if centre < 6:
        return SAND
    if normal_y < 0.78:
        return ROCK
    if centre > 260:
        return SNOW
    for zone in (CITY, TOWN):
        if math.hypot(x - zone[0], z - zone[1]) < zone[2] * 0.9:
            return PAVED
    # The base is grass between the runways, with a paved apron by the buildings.
    bx, bz = x - BASE[0], z - BASE[1]
    if (120 < bx < 270 and abs(bz) < 580) or (270 <= bx < 600 and -580 < bz < 110):
        return PAVED
    return GRASS_DARK if fbm(x, z, 350, 1, 7) > 0.15 else GRASS


# --- Blender building ------------------------------------------------------
def material(name, srgb, emit=0.0, alpha=1.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    rgb = tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb)
    m.use_nodes = True
    bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.8
    bsdf.inputs["Emission Strength"].default_value = emit
    if emit > 0:
        bsdf.inputs["Emission Color"].default_value = (*rgb, 1.0)
    bsdf.inputs["Alpha"].default_value = alpha
    m.diffuse_color = (*rgb, alpha)
    return m


def vertex_color_material():
    m = bpy.data.materials.get("Corneria_Ground") or bpy.data.materials.new("Corneria_Ground")
    m.use_nodes = True
    nodes = m.node_tree.nodes
    bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Roughness"].default_value = 0.9
    attr = next((n for n in nodes if n.type == "VERTEX_COLOR"), None) or nodes.new("ShaderNodeVertexColor")
    attr.layer_name = "Col"
    m.node_tree.links.new(attr.outputs["Color"], bsdf.inputs["Base Color"])
    return m


def collection(name, parent):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        parent.children.link(c)
    for o in list(c.objects):
        bpy.data.objects.remove(o)
    return c


def link(col, name, me, mat):
    o = bpy.data.objects.new(name, me)
    col.objects.link(o)
    if mat:
        me.materials.append(mat)
    return o


def build_terrain(col):
    global HEIGHTS
    heights = HEIGHTS = [[height(-HALF + i * CELL, -HALF + j * CELL) for i in range(POINTS)] for j in range(POINTS)]
    verts = [G(-HALF + i * CELL, heights[j][i], -HALF + j * CELL) for j in range(POINTS) for i in range(POINTS)]
    faces = []
    for j in range(POINTS - 1):
        for i in range(POINTS - 1):
            p00 = j * POINTS + i
            p10, p01, p11 = p00 + 1, p00 + POINTS, p00 + POINTS + 1
            # Split along the (0,0)-(1,1) diagonal, as Terrain does.
            faces.append((p00, p10, p11))
            faces.append((p00, p11, p01))
    me = bpy.data.meshes.new("Terrain")
    me.from_pydata(verts, [], faces)
    me.validate()
    # The game-to-Blender conversion mirrors the winding: make every face point up.
    if me.polygons[0].normal.z < 0:
        me.flip_normals()
    colors = me.color_attributes.new("Col", "BYTE_COLOR", "CORNER")
    srgb_to_lin = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    for poly in me.polygons:
        c = poly.center  # Blender coords
        gx, gy, gz = c.x, c.z, -c.y
        rgb = face_color(gy, poly.normal.z, gx, gz)
        rgba = (*[srgb_to_lin(v) for v in rgb], 1.0)
        for li in poly.loop_indices:
            colors.data[li].color = rgba
    return link(col, "Terrain", me, vertex_color_material())


def ground(x, z):
    """Terrain height at (x, z) from the built grid, exactly as Terrain.height_at()."""
    gx = min(max((x + HALF) / CELL, 0.0), POINTS - 1.001)
    gz = min(max((z + HALF) / CELL, 0.0), POINTS - 1.001)
    i, j = int(gx), int(gz)
    u, v = gx - i, gz - j
    h00, h11 = HEIGHTS[j][i], HEIGHTS[j + 1][i + 1]
    if u >= v:
        return h00 + (HEIGHTS[j][i + 1] - h00) * u + (h11 - HEIGHTS[j][i + 1]) * v
    return h00 + (HEIGHTS[j + 1][i] - h00) * v + (h11 - HEIGHTS[j + 1][i]) * u


def ellipse(cx, cz, rx, rz, n=40):
    return [(cx + rx * math.cos(a), cz + rz * math.sin(a)) for a in (2 * math.pi * k / n for k in range(n))]


def placer(x, y, z, rot=0.0, tilt=0.0):
    """A function taking local game-space points to the world: tilt about X, turn about Y, move."""
    c, s = math.cos(rot), math.sin(rot)
    ct, st = math.cos(tilt), math.sin(tilt)

    def f(p):
        px, py, pz = p
        py, pz = py * ct - pz * st, py * st + pz * ct
        return (x + px * c + pz * s, y + py, z - px * s + pz * c)
    return f


class Batch:
    """Collects geometry (in game coordinates) for one Blender object with several materials."""

    def __init__(self, name):
        self.name = name
        self.verts = []
        self.faces = []
        self.face_mats = []
        self.facing = []

    def add(self, points, faces, mat, xf=None, away_from=None):
        """`away_from` (a world point): make these faces point away from it. Needed
        for open surfaces (sheets, domes), which recalculated normals may turn
        inward; the game draws only the front of a face."""
        base = len(self.verts)
        self.verts += [G(*(xf(p) if xf else p)) for p in points]
        self.faces += [tuple(base + i for i in f) for f in faces]
        self.face_mats += [mat] * len(faces)
        self.facing += [G(*away_from) if away_from else None] * len(faces)

    def box(self, size, mat, xf, y0=0.0):
        """A box standing on the local origin (base at y0), size (x, y, z)."""
        sx, sy, sz = size[0] / 2, size[1], size[2] / 2
        pts = [(x, y0 + y, z) for y in (0, sy) for z in (-sz, sz) for x in (-sx, sx)]
        self.add(pts, [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)], mat, xf)

    def cylinder(self, r0, r1, h, mat, xf, y0=0.0, segments=12, cap=True):
        pts = []
        for y, r in ((y0, r0), (y0 + h, r1)):
            pts += [(r * math.cos(2 * math.pi * k / segments), y, r * math.sin(2 * math.pi * k / segments))
                    for k in range(segments)]
        n = segments
        faces = [(k, (k + 1) % n, n + (k + 1) % n, n + k) for k in range(n)]
        if cap:
            faces += [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))]
        # Open tubes and cones face out from their axis.
        self.add(pts, faces, mat, xf, None if cap else xf((0, y0 + h * 0.3, 0)))

    def dome(self, r, h, mat, xf, y0=0.0, segments=12, rings=4, away_from=None):
        pts = []
        for k in range(rings):
            a = math.pi / 2 * k / rings
            pts += [(r * math.cos(a) * math.cos(2 * math.pi * s / segments), y0 + h * math.sin(a),
                     r * math.cos(a) * math.sin(2 * math.pi * s / segments)) for s in range(segments)]
        pts.append((0, y0 + h, 0))
        n = segments
        faces = [(k * n + s, k * n + (s + 1) % n, (k + 1) * n + (s + 1) % n, (k + 1) * n + s)
                 for k in range(rings - 1) for s in range(n)]
        top = len(pts) - 1
        faces += [((rings - 1) * n + s, (rings - 1) * n + (s + 1) % n, top) for s in range(n)]
        self.add(pts, faces, mat, xf, away_from)

    def rod(self, a, b, thickness, mat):
        """A thin square beam from world point a to b."""
        d = Vector(b) - Vector(a)
        up = Vector((0, 1, 0)) if abs(d.normalized().y) < 0.9 else Vector((1, 0, 0))
        s1 = d.cross(up).normalized() * thickness / 2
        s2 = d.cross(s1).normalized() * thickness / 2
        pts = [tuple(Vector(p) + o1 + o2) for p in (a, b) for o1 in (s1, -s1) for o2 in (s2, -s2)]
        self.add(pts, [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)], mat)

    def flush(self, col):
        me = bpy.data.meshes.new(self.name)
        me.from_pydata(self.verts, [], self.faces)
        names = sorted(set(self.face_mats))
        for name in names:
            me.materials.append(MATERIALS[name])
        index = {name: k for k, name in enumerate(names)}
        me.polygons.foreach_set("material_index", [index[m] for m in self.face_mats])
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.faces.ensure_lookup_table()
        for face, away in zip(bm.faces, self.facing):
            if away is not None and face.normal.dot(face.calc_center_median() - away) < 0:
                face.normal_flip()
        bm.to_mesh(me)
        bm.free()
        o = bpy.data.objects.new(self.name, me)
        col.objects.link(o)
        return o


# sRGB colour, emission strength
PALETTE = {
    "Tower": ((0.84, 0.86, 0.9), 0), "Glass": ((0.3, 0.55, 0.8), 0), "Concrete": ((0.72, 0.68, 0.6), 0),
    "RoofDark": ((0.36, 0.37, 0.42), 0), "Road": ((0.27, 0.27, 0.3), 0), "Stone": ((0.76, 0.68, 0.53), 0),
    "WarningLight": ((1.0, 0.2, 0.15), 6), "Wall": ((0.93, 0.91, 0.86), 0), "Roof": ((0.75, 0.38, 0.28), 0),
    "Lighthouse": ((0.82, 0.18, 0.14), 0), "Lamp": ((1.0, 0.9, 0.5), 8), "Military": ((0.45, 0.5, 0.42), 0),
    "Marking": ((0.95, 0.95, 0.9), 0), "Foam": ((0.95, 0.98, 1.0), 0), "Falls": ((0.8, 0.9, 1.0), 0),
    "Water": ((0.25, 0.5, 0.75), 0), "Tree": ((0.18, 0.4, 0.2), 0), "TreeLight": ((0.27, 0.5, 0.22), 0),
    "Rock": ((0.55, 0.5, 0.46), 0), "Steel": ((0.6, 0.62, 0.66), 0), "BridgeRed": ((0.75, 0.25, 0.18), 0),
    "Marker": ((1.0, 0.85, 0.1), 2),
}
MATERIALS = {}


def make_materials():
    for name, (srgb, emit) in PALETTE.items():
        MATERIALS[name] = material("Corneria_" + name, srgb, emit)


# --- Water -----------------------------------------------------------------
def build_water(col, preview):
    # The sea is only for the preview here: in the game Terrain makes its own.
    sea = Batch("Sea")
    s = 15000
    sea.add([(-s, 0, -s), (s, 0, -s), (s, 0, s), (-s, 0, s)], [(0, 1, 2, 3)], "Water")
    sea.flush(preview)
    # The plateau lake, its river and the falls (above sea level, so they're props).
    b = Batch("Water")
    lx, lz, rx, rz = LAKE
    below = (lx, -1000, lz)   # water faces up
    b.add([(x, LAKE_LEVEL, z) for x, z in ellipse(lx, lz, rx * 0.95, rz * 0.95)], [tuple(range(40))], "Water",
          away_from=below)
    left, right = [], []
    for k, (x, z) in enumerate(UPPER_RIVER):
        a = UPPER_RIVER[max(k - 1, 0)]
        c = UPPER_RIVER[min(k + 1, len(UPPER_RIVER) - 1)]
        d = Vector((c[0] - a[0], c[1] - a[1])).normalized()
        n = Vector((d.y, -d.x)) * 45
        left.append((x + n.x, LAKE_LEVEL, z + n.y))
        right.append((x - n.x, LAKE_LEVEL, z - n.y))
    b.add(left + right[::-1], [tuple(range(len(left) * 2))], "Water", away_from=below)

    # The falls: a sheet bowing out from the lip as it drops, foam at the foot.
    fx, fz = FALLS
    d = Vector((LOWER_RIVER[1][0] - fx, LOWER_RIVER[1][1] - fz)).normalized()
    n = Vector((d.y, -d.x))
    rows = [(LAKE_LEVEL, 0, 40), (85, 16, 43), (45, 26, 46), (0, 32, 50)]
    pts = []
    for y, out, half in rows:
        for side in (1, -1):
            pts.append((fx + n.x * half * side + d.x * out, y, fz + n.y * half * side + d.y * out))
    faces = [(2 * k, 2 * k + 1, 2 * k + 3, 2 * k + 2) for k in range(len(rows) - 1)]
    b.add(pts, faces, "Falls", away_from=(fx - d.x * 300, 60, fz - d.y * 300))   # facing downstream
    foot = (fx + d.x * 45, fz + d.y * 45)
    b.dome(60, 14, "Foam", placer(foot[0], -2, foot[1]), segments=10, rings=3, away_from=(foot[0], -30, foot[1]))
    rng = random.Random(7)
    for _ in range(5):
        ox, oz = rng.uniform(-60, 60), rng.uniform(10, 90)
        p = (foot[0] + n.x * ox + d.x * oz, foot[1] + n.y * ox + d.y * oz)
        b.dome(rng.uniform(12, 22), rng.uniform(4, 8), "Foam", placer(p[0], -1, p[1]), segments=7, rings=2,
               away_from=(p[0], -20, p[1]))
    b.flush(col)


# --- Arches and the bay bridge ----------------------------------------------
def arch(b, x, z, scale, rot):
    """A stone arch standing on the seabed: square pillars rising into a round arch."""
    xf = placer(x, -22, z, rot)
    inner, outer, spring, depth = 40 * scale, 62 * scale, 82 * scale, 10 * scale
    ring = [(-inner, 0), (-inner, spring)]
    ring_out = [(-outer, 0), (-outer, spring)]
    for k in range(1, 12):
        a = math.pi - math.pi * k / 12
        ring.append((inner * math.cos(a), spring + inner * math.sin(a)))
        ring_out.append((outer * math.cos(a), spring + outer * math.sin(a)))
    ring += [(inner, spring), (inner, 0)]
    ring_out += [(outer, spring), (outer, 0)]
    n = len(ring)
    pts = []
    for zz in (-depth, depth):
        pts += [(u, v, zz) for u, v in ring] + [(u, v, zz) for u, v in ring_out]
    faces = []
    for k in range(n - 1):
        for f in (0, 2 * n):          # front and back faces
            faces.append((f + k, f + k + 1, f + n + k + 1, f + n + k))
        faces.append((k, k + 1, 2 * n + k + 1, 2 * n + k))                 # underside of the arch
        faces.append((n + k, n + k + 1, 3 * n + k + 1, 3 * n + k))         # outer surface
    faces.append((0, n, 3 * n, 2 * n))                                       # pillar feet
    faces.append((n - 1, 2 * n - 1, 4 * n - 1, 3 * n - 1))
    b.add(pts, faces, "Stone", xf)
    # A capstone ledge along the top.
    b.box((outer * 0.5, 6 * scale, depth * 2.4), "Stone", placer(x, -22 + spring + outer - 3 * scale, z, rot))


def build_arches(col):
    b = Batch("Arches")
    rng = random.Random(3)
    zs = (2150, 1930, 1710, 1490, 1270, 1050)
    for k, z in enumerate(zs):
        # Face along the bay so you fly through them heading north.
        slope = (bay_x(z - 50) - bay_x(z + 50)) / 100
        arch(b, bay_x(z), z, rng.uniform(0.92, 1.08), math.atan(slope))
    b.flush(col)


def ribbon(b, pts, width, thick, mat):
    """A flat strip of road along world points, `thick` deep below them."""
    left, right = [], []
    for k, p in enumerate(pts):
        a, c = pts[max(k - 1, 0)], pts[min(k + 1, len(pts) - 1)]
        d = Vector((c[0] - a[0], c[2] - a[2])).normalized() * (width / 2)
        left.append((p[0] + d.y, p[1], p[2] - d.x))
        right.append((p[0] - d.y, p[1], p[2] + d.x))
    n = len(pts)
    verts = left + right + [(x, y - thick, z) for x, y, z in left] + [(x, y - thick, z) for x, y, z in right]
    faces = []
    for k in range(n - 1):
        faces.append((k, k + 1, n + k + 1, n + k))                          # top
        faces.append((2 * n + k, 3 * n + k, 3 * n + k + 1, 2 * n + k + 1))  # underside
        faces.append((k, 2 * n + k, 2 * n + k + 1, k + 1))                  # left edge
        faces.append((n + k, n + k + 1, 3 * n + k + 1, 3 * n + k))          # right edge
    b.add(verts, faces, mat)


def build_river_bridge(col):
    """A suspension bridge over the river mouth, carrying a city street west to the
    base road. High enough to fly under."""
    b = Batch("RiverBridge")
    u0, u1, v, deck = BRIDGE
    length = u1 - u0
    xm, zm = city_xy((u0 + u1) / 2, v)
    local = placer(xm, 0, zm, -CITY_ANGLE)     # local +X runs east along the street

    def world(px, y, pz):
        x, _, z = local((px, 0, pz))
        return (x, y, z)

    b.box((length, 3, 20), "Steel", placer(xm, deck - 3, zm, -CITY_ANGLE))
    towers = (-length / 2 + 75, length / 2 - 75)
    top = 98
    for px in towers:
        for side in (-1, 1):
            x, _, z = world(px, 0, side * 11)
            base = min(ground(x, z), 0) - 2
            b.box((6, top + 6 - base, 6), "BridgeRed", placer(x, base, z, -CITY_ANGLE))
        for y in (deck - 6, top - 6, top):
            x, _, z = world(px, 0, 0)
            b.box((6, 5, 28), "BridgeRed", placer(x, y, z, -CITY_ANGLE))
    for side in (-1, 1):
        pz = side * 9
        pts = [world(-length / 2, deck, pz), world(towers[0], top + 2, pz)]
        for k in range(1, 8):
            t = k / 8
            pts.append(world(lerp(towers[0], towers[1], t), top + 2 - 58 * math.sin(math.pi * t), pz))
        pts += [world(towers[1], top + 2, pz), world(length / 2, deck, pz)]
        for a, c in zip(pts, pts[1:]):
            b.rod(a, c, 1.4, "Steel")
        for p in pts[2:-2]:
            b.rod(p, (p[0], deck, p[2]), 0.7, "Steel")

    # On the city side, a ramp down from the deck onto the street, on piers.
    ramp = []
    for k in range(9):
        t = k / 8
        x, z = city_xy(lerp(u1, u1 + 160, t), v)
        ramp.append((x, lerp(deck, CITY[3] + 0.4, t), z))
    ribbon(b, ramp, 18, 2.5, "Road")
    for x, y, z in ramp[:-2]:
        g = ground(x, z)
        if g < y - 4:
            b.box((5, y - 2.5 - g, 12), "Concrete", placer(x, g, z, -CITY_ANGLE))
    b.flush(col)


def build_road(col):
    """The road surface from the bridge's west end to the base, on its graded bed."""
    b = Batch("Road")
    pts = []
    s = 0.0
    while s <= ROAD_LENGTHS[-1]:
        x, z = road_point(s)
        pts.append((x, road_height(s) + 0.4, z))
        s += 15.0
    ribbon(b, pts, 14, 1.5, "Road")
    for k in range(0, len(pts) - 1, 4):    # centre line dashes
        a, c = pts[k], pts[k + 1]
        b.rod((a[0], a[1] + 0.1, a[2]), (lerp(a[0], c[0], 0.6), a[1] + 0.1, lerp(a[2], c[2], 0.6)), 0.6, "Marking")
    b.flush(col)


# --- The road's course and grade -----------------------------------------------
def road_point(s):
    """The point s metres along the road."""
    for k in range(len(ROAD) - 1):
        if s <= ROAD_LENGTHS[k + 1] or k == len(ROAD) - 2:
            t = (s - ROAD_LENGTHS[k]) / (ROAD_LENGTHS[k + 1] - ROAD_LENGTHS[k])
            return lerp(ROAD[k][0], ROAD[k + 1][0], t), lerp(ROAD[k][1], ROAD[k + 1][1], t)


def road_dist(x, z):
    """Distance from (x, z) to the road's centreline, and how far along it the nearest point is."""
    best, along = 1e18, 0.0
    for k in range(len(ROAD) - 1):
        d, t = seg_dist(x, z, ROAD[k], ROAD[k + 1])
        if d < best:
            best, along = d, ROAD_LENGTHS[k] + t * (ROAD_LENGTHS[k + 1] - ROAD_LENGTHS[k])
    return best, along


def road_height(s):
    f = min(max(s / ROAD_STEP, 0.0), len(ROAD_PROFILE) - 1.001)
    k = int(f)
    return lerp(ROAD_PROFILE[k], ROAD_PROFILE[k + 1], f - k)


def make_road():
    """Lays out the road (corners rounded off) and grades it: follow the lie of the
    land, smoothed, no steeper than 8%, from the bridge deck down to the base."""
    global ROAD, ROAD_LENGTHS, ROAD_PROFILE
    pts = [city_xy(BRIDGE[0], BRIDGE[2])] + [tuple(map(float, p)) for p in ROAD_WAYPOINTS]
    for _ in range(3):   # Chaikin corner cutting
        out = [pts[0]]
        for a, c in zip(pts, pts[1:]):
            out += [(0.75 * a[0] + 0.25 * c[0], 0.75 * a[1] + 0.25 * c[1]),
                    (0.25 * a[0] + 0.75 * c[0], 0.25 * a[1] + 0.75 * c[1])]
        pts = out + [pts[-1]]
    ROAD = pts
    ROAD_LENGTHS = [0.0]
    for a, c in zip(pts, pts[1:]):
        ROAD_LENGTHS.append(ROAD_LENGTHS[-1] + math.hypot(c[0] - a[0], c[1] - a[1]))
    n = int(ROAD_LENGTHS[-1] / ROAD_STEP) + 1
    natural = [height(*road_point(k * ROAD_STEP), road=False) for k in range(n)]
    smooth = [sum(natural[max(0, k - 12):k + 13]) / len(natural[max(0, k - 12):k + 13]) for k in range(n)]
    start, end = BRIDGE[3], BASE[3]
    for k in range(8):
        t = smoothstep(0, 8, k)
        smooth[k] = lerp(start, smooth[k], t)
        smooth[n - 1 - k] = lerp(end, smooth[n - 1 - k], t)
    rise = 0.08 * ROAD_STEP
    for k in range(1, n):
        smooth[k] = min(smooth[k], smooth[k - 1] + rise)
    for k in range(n - 2, -1, -1):
        smooth[k] = min(smooth[k], smooth[k + 1] + rise)
    ROAD_PROFILE = [max(p, 4.0) for p in smooth]


# --- Corneria City ------------------------------------------------------------
PITCH, STREET, CITY_ANGLE = 110.0, 24.0, 0.26
CITY_EDGE = 860.0


def city_xy(u, v):
    cx, cz = CITY[0], CITY[1]
    c, s = math.cos(CITY_ANGLE), math.sin(CITY_ANGLE)
    return cx + u * c - v * s, cz + u * s + v * c


def warning_light(b, x, y, z):
    b.box((3, 3, 3), "WarningLight", placer(x, y, z))


def stepped(b, x, y, z, w, d, h, rot):
    for k, (frac, scale) in enumerate(((0.0, 1.0), (0.5, 0.78), (0.8, 0.56))):
        top = (0.5, 0.8, 1.0)[k]
        b.box((w * scale, h * (top - frac), d * scale), "Tower", placer(x, y + h * frac, z, rot))
        b.box((w * scale + 1, 3, d * scale + 1), "Glass", placer(x, y + h * top - 6, z, rot))
    b.cylinder(1.5, 0.5, h * 0.15, "Steel", placer(x, y + h, z), segments=5)
    return h * 1.15


def round_tower(b, x, y, z, r, h):
    b.cylinder(r * 1.35, r * 1.35, 12, "Concrete", placer(x, y, z))
    b.cylinder(r, r, h, "Glass", placer(x, y, z))
    for k in range(1, 4):
        b.cylinder(r + 1, r + 1, 2.5, "Tower", placer(x, y + h * k / 4, z), cap=False)
    b.dome(r, r * 0.6, "Tower", placer(x, y + h, z))
    b.cylinder(1.2, 0.4, r * 1.2, "Steel", placer(x, y + h + r * 0.55, z), segments=5)
    return h + r * 1.7


def slab(b, x, y, z, w, d, h, rot):
    b.box((w - 4, h, d - 4), "Glass", placer(x, y, z, rot))
    for sx in (-1, 1):
        for sz in (-1, 1):
            p = placer(x, y, z, rot)((sx * (w / 2 - 3), 0, sz * (d / 2 - 3)))
            b.box((6, h, 6), "Tower", placer(p[0], y, p[2], rot))
    b.box((w, 4, d), "Tower", placer(x, y + h, z, rot))
    return h + 4


def twin(b, x, y, z, w, h, rot):
    t = w * 0.38
    b.box((w, 14, w * 0.6), "Concrete", placer(x, y, z, rot))
    for side in (-1, 1):
        p = placer(x, y, z, rot)((side * w * 0.32, 0, 0))
        b.box((t, h * (1 if side < 0 else 0.86), t), "Glass", placer(p[0], y, p[2], rot))
        b.box((t + 1, 3, t + 1), "Tower", placer(p[0], y + h * (1 if side < 0 else 0.86), p[2], rot))
    b.box((w * 0.3, 7, 9), "Tower", placer(x, y + h * 0.62, z, rot))
    return h


def low(b, x, y, z, w, d, h, rot, mat):
    b.box((w, h, d), mat, placer(x, y, z, rot))
    b.box((w * 0.8, 2, d * 0.8), "RoofDark", placer(x, y + h, z, rot))


def spire(b, x, y, z):
    b.cylinder(62, 62, 18, "Concrete", placer(x, y, z), segments=16)
    for y0, y1, r0, r1 in ((18, 130, 30, 22), (130, 225, 22, 14), (225, 295, 14, 5)):
        b.cylinder(r0, r1, y1 - y0, "Glass", placer(x, y + y0, z), segments=12)
        b.cylinder(r1 + 6, r1 + 6, 3, "Tower", placer(x, y + y1 - 1.5, z), segments=12)
    b.cylinder(1.6, 0.4, 45, "Steel", placer(x, y + 295, z), segments=5)
    warning_light(b, x, y + 340, z)


def build_city(col, trees):
    b = Batch("City")
    roads = Batch("Streets")
    rng = random.Random(1985)
    cx, cz, r, base = CITY
    spire(b, cx, base, cz)
    span = int(CITY_EDGE / PITCH) + 1
    for i in range(-span, span + 1):
        for j in range(-span, span + 1):
            u, v = i * PITCH, j * PITCH
            dist = math.hypot(u, v)
            if dist > CITY_EDGE - 40 or (i == 0 and j == 0):
                continue
            x, z = city_xy(u, v)
            corners = [city_xy(u + su * 43, v + sv * 43) for su in (-1, 1) for sv in (-1, 1)]
            if min(ground(*c) for c in corners) < 12 or line_dist(x, z, LOWER_RIVER)[0] < 150:
                continue
            y = ground(x, z)
            rot = -CITY_ANGLE + rng.choice((0, math.pi / 2))
            t = math.exp(-(dist / 430) ** 2)
            if dist > 280 and rng.random() < 0.1:
                for _ in range(6):   # a park: just trees
                    trees.append((*city_xy(u + rng.uniform(-35, 35), v + rng.uniform(-35, 35)), y))
                continue
            if t > 0.42:
                h = 85 + 160 * t * rng.uniform(0.6, 1.0)
                kind = rng.random()
                if kind < 0.3:
                    top = stepped(b, x, y, z, rng.uniform(48, 62), rng.uniform(44, 60), h, rot)
                elif kind < 0.55:
                    top = round_tower(b, x, y, z, rng.uniform(18, 26), h)
                elif kind < 0.8:
                    top = slab(b, x, y, z, rng.uniform(46, 64), rng.uniform(32, 44), h, rot)
                else:
                    top = twin(b, x, y, z, rng.uniform(56, 70), h, rot)
                if h > 100:
                    warning_light(b, x, y + top, z)
            elif t > 0.12:
                for side in (-1, 1):
                    p = placer(x, y, z, rot)((side * 22, 0, 0))
                    h = rng.uniform(35, 90) * (0.6 + t)
                    if rng.random() < 0.5:
                        slab(b, p[0], y, p[2], 36, rng.uniform(56, 76), h, rot)
                    else:
                        low(b, p[0], y, p[2], 38, 76, h, rot, rng.choice(("Tower", "Concrete")))
            else:
                for su in (-1, 1):
                    for sv in (-1, 1):
                        if rng.random() < 0.15:
                            continue
                        p = placer(x, y, z, rot)((su * 21, 0, sv * 21))
                        low(b, p[0], y, p[2], 34, 34, rng.uniform(10, 32), rot, rng.choice(("Wall", "Concrete", "Tower")))

    # Streets on the grid lines between blocks; bridges where a street crosses the river.
    bridged = 0
    for k in range(-span - 1, span + 1):
        line = (k + 0.5) * PITCH
        half = math.sqrt(max(CITY_EDGE ** 2 - line ** 2, 0))
        for axis in (0, 1):
            samples = []
            steps = int(2 * half / 10)
            for s in range(steps + 1):
                along = -half + s * 10
                u, v = (line, along) if axis == 0 else (along, line)
                x, z = city_xy(u, v)
                samples.append((along, ground(x, z) >= 12))
            runs, start = [], None
            for along, ok in samples + [(None, False)]:
                if ok and start is None:
                    start = along
                elif not ok and start is not None:
                    runs.append((start, prev))
                    start = None
                prev = along
            for a0, a1 in runs:
                if a1 - a0 < 20:
                    continue
                mid = (a0 + a1) / 2
                u, v = (line, mid) if axis == 0 else (mid, line)
                x, z = city_xy(u, v)
                size = (STREET, 0.6, a1 - a0) if axis == 0 else (a1 - a0, 0.6, STREET)
                roads.box(size, "Road", placer(x, CITY[3] - 0.3, z, -CITY_ANGLE))
            # Every other street crossing the river gets a bridge.
            for (a0, a1), (b0, b1) in zip(runs, runs[1:]):
                if b0 - a1 > 400 or k % 2:
                    continue
                bridged += 1
                mid = (a1 + b0) / 2
                u, v = (line, mid) if axis == 0 else (mid, line)
                x, z = city_xy(u, v)
                length = b0 - a1 + 10
                size = (STREET, 3, length) if axis == 0 else (length, 3, STREET)
                b.box(size, "Steel", placer(x, CITY[3] - 3, z, -CITY_ANGLE))
                for p in range(int(length / 70) + 1):
                    off = -length / 2 + p * 70
                    pu, pv = (line, mid + off) if axis == 0 else (mid + off, line)
                    px, pz = city_xy(pu, pv)
                    g = ground(px, pz)
                    if g < CITY[3] - 4:
                        b.box((6, CITY[3] - 3 - g, 6), "Concrete", placer(px, g, pz, -CITY_ANGLE))
    b.flush(col)
    roads.flush(col)
    return bridged


# --- Harbour town ---------------------------------------------------------------
def house(b, x, y, z, w, d, h, rot):
    b.box((w, h, d), "Wall", placer(x, y, z, rot))
    xf = placer(x, y + h, z, rot)
    pts = [(-w / 2 - 1, 0, -d / 2 - 1), (w / 2 + 1, 0, -d / 2 - 1), (w / 2 + 1, 0, d / 2 + 1),
           (-w / 2 - 1, 0, d / 2 + 1), (0, w * 0.35, -d / 2 - 1), (0, w * 0.35, d / 2 + 1)]
    b.add(pts, [(0, 4, 5, 3), (1, 2, 5, 4), (0, 1, 4), (3, 5, 2), (0, 3, 2, 1)], "Roof", xf)


def build_town(col):
    b = Batch("Town")
    rng = random.Random(42)
    tx, tz, r, base = TOWN
    placed = []
    tries = 0
    while len(placed) < 45 and tries < 3000:
        tries += 1
        a, d = rng.uniform(0, 2 * math.pi), r * math.sqrt(rng.random())
        x, z = tx + d * math.cos(a), tz + d * math.sin(a)
        w = rng.uniform(14, 24)
        if ground(x, z) < 4 or any(math.hypot(x - px, z - pz) < (w + pw) * 0.5 + 14 for px, pz, pw in placed):
            continue
        placed.append((x, z, w))
        house(b, x, ground(x, z), z, w, w * rng.uniform(1.0, 1.6), rng.uniform(7, 14), rng.uniform(0, math.pi))
    for k in range(3):
        px = tx - 200 + k * 200
        pz = coast_z(px)
        b.box((14, 3, 240), "Stone", placer(px, 0, pz + 60))
        for s in range(2):
            boat = placer(px + (24 if s else -24), 0, pz + 80 + s * 70 + k * 15, rng.uniform(-0.3, 0.3))
            b.box((6, 3, 16), "Wall", boat)
            b.box((4, 3, 6), "Glass", placer(*boat((0, 0, 2)), rng.uniform(-0.3, 0.3)), y0=3)
    # The lighthouse on the point east of the harbour.
    lx = tx + 420
    lz = coast_z(lx) - 70
    g = ground(lx, lz)
    for k in range(4):
        b.cylinder(9 - k * 0.6, 8.4 - k * 0.6, 11, "Lighthouse" if k % 2 == 0 else "Wall", placer(lx, g + k * 11, lz))
    b.cylinder(10, 10, 2, "RoofDark", placer(lx, g + 44, lz))
    b.cylinder(4.5, 4.5, 6, "Lamp", placer(lx, g + 46, lz), segments=8)
    b.cylinder(6, 0.5, 6, "Lighthouse", placer(lx, g + 52, lz), segments=8)
    b.flush(col)


# --- Military base ----------------------------------------------------------------
def quonset(b, x, y, z, r, length, mat):
    xf = placer(x, y, z)
    pts = []
    seg = 8
    for zz in (-length / 2, length / 2):
        pts += [(r * math.cos(math.pi * k / seg), r * math.sin(math.pi * k / seg), zz) for k in range(seg + 1)]
    n = seg + 1
    faces = [(k, k + 1, n + k + 1, n + k) for k in range(seg)]
    faces += [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))]
    b.add(pts, faces, mat, xf)


def build_base(col):
    b = Batch("Base")
    bx, bz, r, y = BASE
    rx = bx - 150
    b.box((70, 0.6, 1300), "Road", placer(rx, y - 0.3, bz))
    for k in range(20):
        b.box((2, 0.3, 30), "Marking", placer(rx, y + 0.3, bz - 600 + k * 63))
    for end in (-1, 1):
        for s in range(6):
            b.box((4, 0.3, 40), "Marking", placer(rx - 25 + s * 10, y + 0.3, bz + end * 610))
    b.box((30, 0.5, 900), "Road", placer(bx + 50, y - 0.25, bz))
    for k in range(3):
        b.box((200, 0.5, 26), "Road", placer(bx - 50, y - 0.25, bz - 350 + k * 350))
    for k in range(4):
        quonset(b, bx + 200, y, bz - 330 + k * 220, 30, 90, "Military")
    # Control tower with a glass cab, a radar dish, fuel tanks.
    tx, tz = bx + 200, bz + 520
    b.cylinder(6, 5, 45, "Concrete", placer(tx, y, tz), segments=8)
    b.cylinder(11, 12, 8, "Glass", placer(tx, y + 45, tz), segments=8)
    b.cylinder(13, 13, 2, "RoofDark", placer(tx, y + 53, tz), segments=8)
    warning_light(b, tx, y + 55, tz)
    b.cylinder(1.5, 1.5, 20, "Steel", placer(bx + 300, y, bz + 380), segments=6)
    b.cylinder(14, 2, 4, "Steel", placer(bx + 300, y + 20, bz + 380, 0.4, 0.6), segments=12)
    for k in range(3):
        b.cylinder(10, 10, 14, "Wall", placer(bx + 330, y, bz - 520 + k * 26))
        b.dome(10, 3, "Wall", placer(bx + 330, y + 14, bz - 520 + k * 26))
    build_base_admin(b, bx, bz, y)
    b.flush(col)


def build_base_admin(b, bx, bz, y):
    """The base's working side, east of the hangars: headquarters, barracks, depot."""
    rng = random.Random(21)
    # Headquarters: an L of three storeys with window bands, a flagpole out front.
    hx, hz = bx + 440, bz + 40
    for size, (ox, oz) in (((22, 15, 92), (0, 0)), ((54, 15, 22), (32, 35))):
        b.box(size, "Wall", placer(hx + ox, y, hz + oz))
        for floor in (3.0, 8.0, 12.5):
            b.box((size[0] + 0.6, 1.8, size[2] + 0.6), "Glass", placer(hx + ox, y + floor, hz + oz))
        b.box((size[0] - 2, 1.2, size[2] - 2), "RoofDark", placer(hx + ox, y + 15, hz + oz))
    b.box((8, 4, 12), "Concrete", placer(hx - 15, y, hz))                 # entrance porch
    b.cylinder(0.4, 0.3, 18, "Steel", placer(hx - 32, y, hz), segments=5)
    b.box((0.3, 3, 5), "BridgeRed", placer(hx - 32, y + 14.5, hz - 2.6))  # the flag
    b.cylinder(1.2, 0.5, 14, "Steel", placer(hx, y + 15, hz - 30), segments=5)
    # Parking lot with cars.
    px, pz = hx + 60, hz - 60
    b.box((56, 0.4, 36), "Road", placer(px, y - 0.1, pz))
    for row in (-1, 1):
        for k in range(8):
            if rng.random() < 0.3:
                continue
            b.box((2.2, 1.6, 4.4), rng.choice(("Wall", "Glass", "Lighthouse", "RoofDark")),
                  placer(px - 24 + k * 6.5, y + 0.3, pz + row * 10))
    # Barracks in two rows, and a mess hall.
    for col_x in (bx + 500, bx + 550):
        for k in range(4):
            low(b, col_x, y, bz - 300 + k * 70, 15, 50, 8, 0.0, "Concrete")
    quonset(b, bx + 400, y, bz - 160, 11, 44, "Military")
    # Maintenance depot with trucks out front.
    dx, dz = bx + 360, bz - 360
    low(b, dx, y, dz, 64, 36, 11, 0.0, "Military")
    for k in range(4):
        b.box((3.4, 3.2, 8), "Military", placer(dx - 22 + k * 12, y, dz + 28))
    # Helipad between the hangars and the headquarters.
    hpx, hpz = bx + 320, bz - 20
    b.cylinder(15, 15, 0.4, "Road", placer(hpx, y - 0.1, hpz), segments=16)
    for ox in (-3.5, 3.5):
        b.box((1.4, 0.2, 10), "Marking", placer(hpx + ox, y + 0.3, hpz))
    b.box((7, 0.2, 1.4), "Marking", placer(hpx, y + 0.3, hpz))
    # Radio mast: a tapering lattice with cross braces.
    mx, mz, height_ = bx + 440, bz - 430, 64
    legs = []
    for sx, sz in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        legs.append([(mx + sx * lerp(4, 0.8, f), y + height_ * f, mz + sz * lerp(4, 0.8, f)) for f in (0, 0.25, 0.5, 0.75, 1)])
    for leg in legs:
        for a, c in zip(leg, leg[1:]):
            b.rod(a, c, 0.6, "BridgeRed")
    for level in range(4):
        for k in range(4):
            b.rod(legs[k][level], legs[(k + 1) % 4][level + 1], 0.3, "Steel")
    warning_light(b, mx, y + height_, mz)
    # A guard post and barrier where the road comes in.
    s = 0.0
    while s < ROAD_LENGTHS[-1] and math.hypot(road_point(s)[0] - bx, road_point(s)[1] - bz) > BASE[2] - 60:
        s += 5
    gx, gz = road_point(s)
    ax, az = road_point(s + 5)
    d = Vector((ax - gx, az - gz)).normalized()
    side = Vector((d.y, -d.x))
    b.box((4, 3, 4), "Wall", placer(gx + side.x * 11, y, gz + side.y * 11))
    b.box((5, 0.6, 5), "RoofDark", placer(gx + side.x * 11, y + 3, gz + side.y * 11))
    b.rod((gx + side.x * 9, y + 1.2, gz + side.y * 9), (gx - side.x * 5, y + 1.2, gz - side.y * 5), 0.4, "Lighthouse")


# --- Sea stacks ----------------------------------------------------------------------
def build_sea_stacks(col):
    b = Batch("SeaStacks")
    rng = random.Random(11)
    for x, z in SEA_STACKS:
        h, r = rng.uniform(150, 230), rng.uniform(38, 55)
        lean = (rng.uniform(-20, 20), rng.uniform(-20, 20))
        seg = 7
        pts = []
        levels = ((0.0, 1.0), (0.3, 0.8), (0.6, 0.55), (0.85, 0.35), (1.0, 0.14))
        for f, s in levels:
            for k in range(seg):
                a = 2 * math.pi * k / seg + rng.uniform(-0.2, 0.2)
                rr = r * s * rng.uniform(0.8, 1.2)
                pts.append((x + lean[0] * f + rr * math.cos(a), -25 + h * f, z + lean[1] * f + rr * math.sin(a)))
        faces = [(l * seg + k, l * seg + (k + 1) % seg, (l + 1) * seg + (k + 1) % seg, (l + 1) * seg + k)
                 for l in range(len(levels) - 1) for k in range(seg)]
        faces.append(tuple(range((len(levels) - 1) * seg + seg - 1, (len(levels) - 1) * seg - 1, -1)))
        b.add(pts, faces, "Rock")
    b.flush(col)


# --- Forests ---------------------------------------------------------------------------
def scatter_trees(trees):
    """Clumps of trees on gentle grass slopes, away from towns, rivers and the coast."""
    rng = random.Random(5)
    step = 32.0
    n = int(SIZE / step)
    for j in range(n):
        for i in range(n):
            x = -HALF + (i + rng.random()) * step
            z = -HALF + (j + rng.random()) * step
            clump = fbm(x, z, 650, 3, 30)
            if clump < 0.08 and rng.random() > 0.02:
                continue
            g = ground(x, z)
            if not 9 < g < 230 or abs(ground(x + 25, z) - g) > 12 or abs(ground(x, z + 25) - g) > 12:
                continue
            if any(math.hypot(x - zx, z - zz) < zr + 120 for zx, zz, zr, _ in (CITY, BASE, TOWN)):
                continue
            if line_dist(x, z, LOWER_RIVER)[0] < 110 or coast_z(x) - z < 120 or road_dist(x, z)[0] < 60:
                continue
            trees.append((x, z, g))


def build_trees(col, trees):
    b = Batch("Trees")
    rng = random.Random(9)
    for x, z, g in trees:
        h = rng.uniform(11, 19)
        r = h * rng.uniform(0.3, 0.4)
        b.cylinder(r, 0.0, h, "Tree" if rng.random() < 0.6 else "TreeLight", placer(x, g - 1, z, rng.uniform(0, 1)),
                   segments=5, cap=False)
    b.flush(col)
    return len(trees)


def build_props(root):
    make_materials()
    preview = collection("Preview", root)
    build_water(collection("Water", root), preview)
    build_arches(collection("Arches", root))
    build_river_bridge(collection("RiverBridge", root))
    build_road(collection("Road", root))
    trees = []
    bridges = build_city(collection("City", root), trees)
    build_town(collection("Town", root))
    build_base(collection("Base", root))
    build_sea_stacks(collection("SeaStacks", root))
    scatter_trees(trees)
    count = build_trees(collection("Trees", root), trees)
    m = Batch("Start")
    m.cylinder(15, 0, 40, "Marker", placer(*START), segments=4)
    m.flush(preview)
    print("city bridges:", bridges, "trees:", count)


def build():
    scene = bpy.data.scenes.get("Corneria") or bpy.data.scenes.new("Corneria")
    if bpy.context.window:
        bpy.context.window.scene = scene
    root = bpy.data.collections.get("Corneria")
    if root is None:
        root = bpy.data.collections.new("Corneria")
        scene.collection.children.link(root)
    # Old blockout collections that no longer exist in the build.
    for name in ("BayBridge", "Markers"):
        collection(name, root)
    make_road()
    terrain = build_terrain(collection("Terrain", root))
    build_props(root)
    for me in list(bpy.data.meshes):
        if me.users == 0:
            bpy.data.meshes.remove(me)
    return terrain


# --- Export ----------------------------------------------------------------------
# Prop groups that go into the game (the rest is preview only), and the ones the
# AI must fly over: they're rasterised into the map's structure heights.
EXPORT_GROUPS = ("Water", "Arches", "RiverBridge", "Road", "City", "Town", "Base", "SeaStacks", "Trees")
STRUCTURE_GROUPS = ("City", "Town", "Base", "Arches", "RiverBridge", "SeaStacks")
PAINT_AUTO, PAINT_PAVED, PAINT_HIGH_WATER = 0, 1, 2


def cell_paint(x, z):
    """What a terrain cell is, besides its height: paved, or under the plateau's water."""
    if face_color(20, 1.0, x, z) == PAVED:
        return PAINT_PAVED
    lx, lz, rx, rz = LAKE
    if ((x - lx) / (rx * 0.95)) ** 2 + ((z - lz) / (rz * 0.95)) ** 2 < 1 or line_dist(x, z, UPPER_RIVER)[0] < 45:
        return PAINT_HIGH_WATER
    return PAINT_AUTO


def structure_heights():
    """The top of the tallest structure over each terrain cell (0 where there's none),
    conservatively: any face whose outline overlaps the cell counts."""
    cells = POINTS - 1
    tops = [0.0] * (cells * cells)
    for name in STRUCTURE_GROUPS:
        for o in bpy.data.collections[name].objects:
            me = o.data
            co = [(v.co.x, v.co.z, -v.co.y) for v in me.vertices]   # back to game coordinates
            for poly in me.polygons:
                pts = [co[i] for i in poly.vertices]
                top = max(p[1] for p in pts)
                i0 = max(int((min(p[0] for p in pts) + HALF) / CELL), 0)
                i1 = min(int((max(p[0] for p in pts) + HALF) / CELL), cells - 1)
                j0 = max(int((min(p[2] for p in pts) + HALF) / CELL), 0)
                j1 = min(int((max(p[2] for p in pts) + HALF) / CELL), cells - 1)
                for j in range(j0, j1 + 1):
                    for i in range(i0, i1 + 1):
                        if top > tops[j * cells + i]:
                            tops[j * cells + i] = top
    return tops


def number(v):
    s = "%.2f" % v
    return s.rstrip("0").rstrip(".") if "." in s else s


def export_map():
    """corneria_map.tres (a TerrainMap: heights, paint, structure heights) and
    corneria_props.glb (everything built on it)."""
    out = os.path.dirname(HERE)
    cells = POINTS - 1
    heights = [HEIGHTS[j][i] for j in range(POINTS) for i in range(POINTS)]
    paint = [cell_paint(-HALF + (i + 0.5) * CELL, -HALF + (j + 0.5) * CELL) for j in range(cells) for i in range(cells)]
    tops = structure_heights()
    with open(os.path.join(out, "corneria_map.tres"), "w", newline="\n") as f:
        f.write('[gd_resource type="Resource" script_class="TerrainMap" format=3]\n\n')
        f.write('[ext_resource type="Script" path="res://world/terrain_map.gd" id="1_map"]\n\n')
        f.write('[resource]\nscript = ExtResource("1_map")\n')
        f.write("size = %s\npoints = %d\nhigh_water_level = %s\n" % (number(SIZE), POINTS, number(LAKE_LEVEL)))
        f.write("heights = PackedFloat32Array(%s)\n" % ", ".join(number(h) for h in heights))
        f.write("paint = PackedByteArray(%s)\n" % ", ".join(str(p) for p in paint))
        f.write("structures = PackedFloat32Array(%s)\n" % ", ".join(number(t) for t in tops))

    bpy.ops.object.select_all(action="DESELECT")
    objects = [o for name in EXPORT_GROUPS for o in bpy.data.collections[name].objects]
    for o in objects:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.export_scene.gltf(filepath=os.path.join(out, "corneria_props.glb"), export_format="GLB",
                              use_selection=True, use_active_scene=True, export_apply=True, export_yup=True,
                              export_materials="EXPORT", export_cameras=False, export_lights=False)
    print("exported: %d structure cells, %d paved, %d high water" % (
        sum(1 for t in tops if t > 0), paint.count(PAINT_PAVED), paint.count(PAINT_HIGH_WATER)))


build()
if EXPORT:
    export_map()
print("corneria built")
