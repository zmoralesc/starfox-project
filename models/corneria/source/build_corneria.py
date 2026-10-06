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

The buildings, bridges, arches, stacks, trees and the falls are hand-made kit
pieces from corneria_kit.blend (specified in ../ASSETS.md; see load_kit()): this
script decides where they go, how big, and merges them into one object per
group. The terrain, lake and river surfaces, the road and the bridge ramp are
still built here.
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
        self.smooth = []
        self.sharp = []      # sharp edges, as pairs of vertex indices

    def add(self, points, faces, mat, xf=None, away_from=None):
        """`away_from` (a world point): make these faces point away from it. Needed
        for open surfaces (sheets, domes), which recalculated normals may turn
        inward; the game draws only the front of a face."""
        base = len(self.verts)
        self.verts += [G(*(xf(p) if xf else p)) for p in points]
        self.faces += [tuple(base + i for i in f) for f in faces]
        self.face_mats += [mat] * len(faces)
        self.facing += [G(*away_from) if away_from else None] * len(faces)
        self.smooth += [False] * len(faces)

    def kit(self, name, xf, scale=(1.0, 1.0, 1.0), height=None, only=None, swap=None):
        """Kit piece `name` (see load_kit()), scaled by `scale` (x, y, z) about its
        origin, then placed by `xf` (a placer). `height(y)` maps its heights instead
        of scaling them, for pieces whose top keeps its size when stretched;
        `only(centre)` keeps just the faces whose local centre passes; `swap` renames
        materials. The faces keep the way they were modelled to face, and their
        smooth shading."""
        pts, faces, mats, smooth, sharp = KIT[name]
        sx, sy, sz = scale
        local = [(x * sx, height(y) if height else y * sy, z * sz) for x, y, z in pts]
        keep = [k for k, f in enumerate(faces)
                if only is None or only(tuple(sum(pts[i][c] for i in f) / len(f) for c in range(3)))]
        used = sorted({i for k in keep for i in faces[k]})
        index = {i: len(self.verts) + n for n, i in enumerate(used)}
        self.verts += [G(*xf(local[i])) for i in used]
        mirrored = sx * sz * (1 if height else sy) < 0     # mirroring turns faces inside out
        for k in keep:
            f = tuple(index[i] for i in faces[k])
            self.faces.append(f[::-1] if mirrored else f)
            self.face_mats.append(swap.get(mats[k], mats[k]) if swap else mats[k])
            self.facing.append(KEEP)
            self.smooth.append(smooth[k])
        self.sharp += [(index[a], index[b]) for a, b in sharp if a in index and b in index]

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
        me.polygons.foreach_set("use_smooth", self.smooth)
        if self.sharp:
            edges = {frozenset(e.vertices): e for e in me.edges}
            for a, b in self.sharp:
                e = edges.get(frozenset((a, b)))
                if e:
                    e.use_edge_sharp = True
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.faces.ensure_lookup_table()
        # Kit faces already face the right way; the rest are worked out.
        bmesh.ops.recalc_face_normals(bm, faces=[f for f, away in zip(bm.faces, self.facing) if away is not KEEP])
        for face, away in zip(bm.faces, self.facing):
            if away is not None and away is not KEEP and face.normal.dot(face.calc_center_median() - away) < 0:
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
    # Added with the kit (ASSETS.md).
    "TaxiYellow": ((0.95, 0.8, 0.2), 0), "MilitaryDark": ((0.3, 0.34, 0.28), 0),
    "HazardBlack": ((0.12, 0.12, 0.14), 0), "CarBody": ((0.22, 0.52, 0.82), 0),
    "Trunk": ((0.4, 0.28, 0.18), 0), "AwningBlue": ((0.2, 0.5, 0.85), 0),
}
MATERIALS = {}


def make_materials():
    for name, (srgb, emit) in PALETTE.items():
        MATERIALS[name] = material("Corneria_" + name, srgb, emit)


# --- The kit ----------------------------------------------------------------
# Hand-made pieces (corneria_kit.blend, specified in ../ASSETS.md), placed by the
# builders below where they used to put boxes. Each is read once, into game
# coordinates: (points, faces, face materials as PALETTE names, face smooth
# flags, sharp edges). The kit's own material colours are ignored: every face
# gets the palette material of its name, so the kit can't drift from it.
KIT_FILE = os.path.join(HERE, "corneria_kit.blend")
# Parts whose origin is a pivot apart from the rest of their asset (the radar
# dish, the barrier arm): read where they stand. The others are read about their
# own origin (some are laid out side by side in the file).
KIT_PIVOTED = ("Kit_RadarDish_Dish", "Kit_GuardPost_Arm")
KIT = {}
KEEP = "keep"   # Batch.facing for a kit face: it already faces the right way
SHAFT = 20.0    # height of every kit tower's repeating shaft section


def load_kit():
    with bpy.data.libraries.load(KIT_FILE, link=False) as (src, dst):
        dst.objects = [n for n in src.objects if n.startswith("Kit_")]
    loaded = set()
    for o in dst.objects:
        me = o.data
        xf = o.matrix_world if o.name in KIT_PIVOTED else Matrix.Identity(4)
        pts = []
        for v in me.vertices:
            p = xf @ v.co
            pts.append((p.x, p.z, -p.y))    # Blender (Z up, +Y north) to game
        # Material names without the prefix or Blender's ".001" for a clash.
        names = [m.name.split(".")[0].removeprefix("Corneria_") for m in me.materials]
        loaded |= set(me.materials)
        KIT[o.name] = (pts, [tuple(p.vertices) for p in me.polygons],
                       [names[p.material_index] for p in me.polygons],
                       [p.use_smooth for p in me.polygons],
                       [tuple(e.vertices) for e in me.edges if e.use_edge_sharp])
        bpy.data.objects.remove(o)
        bpy.data.meshes.remove(me)
    for m in loaded:
        if m not in MATERIALS.values():
            bpy.data.materials.remove(m)


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

    # The falls (a kit piece: its lip at the origin, 120 m up, the water flowing
    # towards its local +Z), turned to pour down the river.
    fx, fz = FALLS
    d = Vector((LOWER_RIVER[1][0] - fx, LOWER_RIVER[1][1] - fz)).normalized()
    b.kit("Kit_Waterfall", placer(fx, LAKE_LEVEL - 120, fz, math.atan2(d.x, d.y)))
    b.flush(col)


# --- Arches and the bay bridge ----------------------------------------------
def arch(b, x, z, scale, rot):
    """A stone arch standing on the seabed, flown through along its local Z (the
    kit piece: an 80 m wide, 120 m high opening at scale 1; origin at sea level)."""
    b.kit("Kit_StoneArch", placer(x, 0, z, rot), (scale, scale, scale))


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
    xm, zm = city_xy((u0 + u1) / 2, v)
    assert u1 - u0 == 300 and deck == 30, "BRIDGE must match the kit bridge (300 m, deck at 30 m)"
    # The kit bridge: 300 m along its local X (here east along the street), deck
    # top 30 m above its origin at sea level, tower feet 10 m below it.
    b.kit("Kit_RiverBridge", placer(xm, 0, zm, -CITY_ANGLE))
    for px in (-75, 75):
        for side in (-1, 1):
            x, _, z = placer(xm, 0, zm, -CITY_ANGLE)((px, 0, side * 11))
            if ground(x, z) < -10:
                print("warning: a river bridge tower stands in %.0f m of water" % -ground(x, z))

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
    b.kit("Kit_RoofLight", placer(x, y, z))


def shafts(body, fixed):
    """How many SHAFT sections bring a tower's body nearest `body` metres, given
    `fixed` metres of base and crown, and the vertical stretch that then hits it."""
    n = max(round((body - fixed) / SHAFT), 1)
    return n, body / (fixed + n * SHAFT)


# The tower builders return the point their warning light goes on (the antenna tip).
def stepped(b, x, y, z, w, d, h, rot):
    """The stepped kit tower (55 × 52 m; a 20 m base, shafts, and a crown of two
    setbacks, 100 m, under a 20 m antenna), stretched to a body `h` high."""
    n, f = shafts(h, 120)
    s = (w / 55, f, d / 52)
    b.kit("Kit_SteppedTower_Base", placer(x, y, z, rot), s)
    for k in range(n):
        b.kit("Kit_SteppedTower_Shaft", placer(x, y + (20 + k * SHAFT) * f, z, rot), s)
    b.kit("Kit_SteppedTower_Crown", placer(x, y + (20 + n * SHAFT) * f, z, rot), s)
    return (x, y + (140 + n * SHAFT) * f, z)


def round_tower(b, x, y, z, r, h):
    """The round kit tower (radius 22 m; a 12 m drum, shafts, then a dome and
    antenna 39 m tall, which keep their proportions), glass `h` high."""
    n, f = shafts(h, 12)
    s = r / 22
    b.kit("Kit_RoundTower_Base", placer(x, y, z), (s, f, s))
    for k in range(n):
        b.kit("Kit_RoundTower_Shaft", placer(x, y + (12 + k * SHAFT) * f, z), (s, f, s))
    b.kit("Kit_RoundTower_Crown", placer(x, y + h, z), (s, s, s))
    return (x, y + h + 39 * s, z)


def slab(b, x, y, z, w, d, h, rot):
    """The slab kit tower (55 × 38 m; a 10 m base, shafts, then a 4 m roof cap
    with plant rooms, unstretched), body `h` high."""
    n, f = shafts(h, 10)
    s = (w / 55, f, d / 38)
    b.kit("Kit_SlabTower_Base", placer(x, y, z, rot), s)
    for k in range(n):
        b.kit("Kit_SlabTower_Shaft", placer(x, y + (10 + k * SHAFT) * f, z, rot), s)
    b.kit("Kit_SlabTower_Crown", placer(x, y + h, z, rot), (w / 55, 1, d / 38))
    return (x, y + h + 4, z)


def twin(b, x, y, z, w, h, rot):
    """The twin kit towers (a 63 × 38 m, 14 m podium; shafts at local x ±20; the
    west one `h` high, the east one 86 %; a sky bridge at 62 %). The kit's shaft
    section holds both towers, so each tower stacks its own half."""
    s = w / 63
    xf = placer(x, y, z, rot)
    b.kit("Kit_TwinTowers_Base", xf, (s, 1, s))
    for side, frac, crown in ((-1, 1.0, "Kit_TwinTowers_CrownWest"), (1, 0.86, "Kit_TwinTowers_CrownEast")):
        top = h * frac
        n, f = shafts(top - 14, 0)
        for k in range(n):
            b.kit("Kit_TwinTowers_Shaft", placer(x, y + 14 + k * SHAFT * f, z, rot), (s, f, s),
                  only=lambda c, side=side: c[0] * side > 0)
        b.kit(crown, placer(x, y + top, z, rot), (s, 1, s))
    b.kit("Kit_TwinTowers_Bridge", placer(x, y + h * 0.62, z, rot), (s, 1, s))
    tip = xf((-20 * s, 0, 0))
    return (tip[0], y + h + 10, tip[2])


# Low blocks: the kit variant for each wall colour the builders ask for.
LOW_KIT = {"Tower": "Kit_LowBuilding_A", "Wall": "Kit_LowBuilding_B", "Concrete": "Kit_LowBuilding_C"}


def low(b, x, y, z, w, d, h, rot, mat):
    """A low block: the kit's 10 m unit block stretched to w × h × d; what stands
    on its roof keeps its height."""
    b.kit(LOW_KIT[mat], placer(x, y, z, rot), (w / 10, 1, d / 10),
          height=lambda yy: yy * h / 10 if yy <= 10 else h + yy - 10)


def spire(b, x, y, z):
    b.kit("Kit_Spire", placer(x, y, z))


# Street kit pieces: their length along the street; straight stretches are cut
# into pieces about STREET_TILE long (stretched to fit).
STREET_PIECE = {"Kit_Street_Straight": 10.0, "Kit_Street_Crossing": 24.0}
STREET_TILE = 30.0


def crossing(i, j):
    """Whether a crossing piece goes where grid lines i (u) and j (v) meet."""
    u, v = (i + 0.5) * PITCH, (j + 0.5) * PITCH
    return math.hypot(u, v) < CITY_EDGE - STREET and ground(*city_xy(u, v)) >= 12


def street_piece(b, name, axis, line, along, length):
    """A street kit piece centred `along` grid line `line` (axis 0: the line is a
    u, the street runs along v), stretched to `length` along the street."""
    u, v = (line, along) if axis == 0 else (along, line)
    x, z = city_xy(u, v)
    rot = -CITY_ANGLE + (0 if axis == 0 else math.pi / 2)
    b.kit(name, placer(x, CITY[3] - 0.3, z, rot), (1, 1, length / STREET_PIECE[name]))


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
                for _ in range(6):   # a park: just (round) trees
                    trees.append((*city_xy(u + rng.uniform(-35, 35), v + rng.uniform(-35, 35)), y, True))
                continue
            if t > 0.42:
                h = 85 + 160 * t * rng.uniform(0.6, 1.0)
                kind = rng.random()
                if kind < 0.3:
                    tip = stepped(b, x, y, z, rng.uniform(48, 62), rng.uniform(44, 60), h, rot)
                elif kind < 0.55:
                    tip = round_tower(b, x, y, z, rng.uniform(18, 26), h)
                elif kind < 0.8:
                    tip = slab(b, x, y, z, rng.uniform(46, 64), rng.uniform(32, 44), h, rot)
                else:
                    tip = twin(b, x, y, z, rng.uniform(56, 70), h, rot)
                if h > 100:
                    warning_light(b, *tip)
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
    crossed = set()
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
                # Crossings cut the run into straight stretches; each crossing
                # piece is laid once, by whichever street gets there first.
                cuts = []
                for j in range(-span - 1, span + 1):
                    c = (j + 0.5) * PITCH
                    key = (k, j) if axis == 0 else (j, k)
                    if a0 <= c <= a1 and crossing(*key):
                        cuts.append(c)
                        if key not in crossed:
                            crossed.add(key)
                            street_piece(roads, "Kit_Street_Crossing", axis, line, c, STREET)
                start = a0
                for c in cuts + [None]:
                    end = a1 if c is None else c - STREET / 2
                    if end - start > 2:
                        n = max(round((end - start) / STREET_TILE), 1)
                        for t in range(n):
                            street_piece(roads, "Kit_Street_Straight", axis, line,
                                         start + (t + 0.5) * (end - start) / n, (end - start) / n)
                    if c is not None:
                        start = c + STREET / 2
            # Every other street crossing the river gets a bridge: kit spans of
            # about 70 m from bank to bank, a pier down to the river bed at each
            # joint over the water.
            for (a0, a1), (b0, b1) in zip(runs, runs[1:]):
                if b0 - a1 > 400 or k % 2:
                    continue
                bridged += 1
                length = b0 - a1
                n = max(round(length / 70), 1)
                deck = CITY[3] + 0.3
                rot = -CITY_ANGLE + (0 if axis == 0 else math.pi / 2)
                for p in range(n + 1):
                    if p < n:
                        u, v = (line, a1 + (p + 0.5) * length / n)
                        x, z = city_xy(*((u, v) if axis == 0 else (v, u)))
                        b.kit("Kit_StreetBridge_Span", placer(x, deck, z, rot), (1, 1, length / n / 70))
                    u, v = (line, a1 + p * length / n)
                    x, z = city_xy(*((u, v) if axis == 0 else (v, u)))
                    g = ground(x, z)
                    if g < CITY[3] - 4:
                        depth = deck - g + 2   # from the deck to 2 m into the river bed
                        b.kit("Kit_StreetBridge_Pier", placer(x, deck, z, rot),
                              height=lambda yy, depth=depth: -3 + (yy + 3) * (depth - 3) / 17)
    b.flush(col)
    roads.flush(col)
    return bridged


# --- Harbour town ---------------------------------------------------------------
def house(b, x, y, z, w, d, h, rot, variant):
    """A kit house (`variant` A to D: an 18 × 24 m footprint, 10 m walls) stretched
    to w × d with h high walls; the roof stretches with them."""
    b.kit("Kit_House_" + variant, placer(x, y, z, rot), (w / 18, h / 10, d / 24))


def build_town(col):
    b = Batch("Town")
    rng = random.Random(42)
    styles = random.Random(43)   # which house goes where (apart from rng, so the layout stays put)
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
        house(b, x, ground(x, z), z, w, w * rng.uniform(1.0, 1.6), rng.uniform(7, 14), rng.uniform(0, math.pi),
              styles.choice("ABCD"))
    for k in range(3):
        px = tx - 200 + k * 200
        pz = coast_z(px)
        # The kit pier runs 240 m out to sea (+Z) from its shore end.
        b.kit("Kit_Pier", placer(px, 0, pz - 60))
        for s in range(2):
            b.kit("Kit_Boat_" + "AB"[s], placer(px + (24 if s else -24), 0, pz + 80 + s * 70 + k * 15,
                                                 rng.uniform(-0.3, 0.3)))
    # The lighthouse on the point east of the harbour (its keeper's cottage on
    # the landward side).
    lx = tx + 420
    lz = coast_z(lx) - 70
    b.kit("Kit_Lighthouse", placer(lx, ground(lx, lz), lz))
    b.flush(col)


# --- Military base ----------------------------------------------------------------
def build_base(col):
    b = Batch("Base")
    bx, bz, r, y = BASE
    # Paved kit pieces (0.6 m slabs) at slightly different heights where they
    # overlap, so their markings don't flicker: runway on top, then the parallel
    # taxiway and aprons, then the cross taxiways.
    rx = bx - 150
    b.kit("Kit_Runway_Main", placer(rx, y - 0.25, bz))
    for k in range(9):
        b.kit("Kit_Runway_Taxiway", placer(bx + 50, y - 0.3, bz - 400 + k * 100))
    for k in range(3):
        for t in range(2):
            b.kit("Kit_Runway_Taxiway", placer(bx - 100 + t * 100, y - 0.35, bz - 350 + k * 350, math.pi / 2),
                  (26 / 30, 1, 1))
    # Hangars with their doors to the runway (west), each on an apron reaching
    # from the taxiway to its door.
    for k in range(4):
        hz = bz - 330 + k * 220
        b.kit("Kit_Hangar_Large", placer(bx + 200, y, hz, -math.pi / 2))
        b.kit("Kit_Runway_Apron", placer(bx + 110, y - 0.3, hz, -math.pi / 2), (1, 1, 1.5))
    # Control tower, a radar dish, fuel tanks.
    b.kit("Kit_ControlTower", placer(bx + 200, y, bz + 520))
    for part in ("Kit_RadarDish_Base", "Kit_RadarDish_Dish"):
        b.kit(part, placer(bx + 300, y, bz + 380, 0.4))
    for k in range(3):
        b.kit("Kit_FuelTank", placer(bx + 330, y, bz - 520 + k * 28))
    build_base_admin(b, bx, bz, y)
    b.flush(col)


def build_base_admin(b, bx, bz, y):
    """The base's working side, east of the hangars: headquarters, barracks, depot."""
    rng = random.Random(21)
    # Headquarters: the kit's L of three storeys, its main wing (22 × 92 m, local
    # x -22 to 0) centred on (hx, hz), mirrored north-south so its second wing
    # lies south, away from the parking lot; porch and flagpole face west.
    hx, hz = bx + 440, bz + 40
    b.kit("Kit_Headquarters", placer(hx + 11, y, hz), (1, 1, -1))
    # Parking lot with cars, noses to the middle aisle; the kit car's body
    # colour (CarBody) is swapped per car.
    px, pz = hx + 60, hz - 60
    b.kit("Kit_ParkingLot", placer(px, y - 0.1, pz))
    for row in (-1, 1):
        for k in range(8):
            if rng.random() < 0.3:
                continue
            body = rng.choice(("Wall", "CarBody", "Lighthouse", "RoofDark"))
            b.kit("Kit_Car", placer(px - 24 + k * 6.5, y + 0.3, pz + row * 10, 0 if row < 0 else math.pi),
                  swap={"CarBody": body})
    # Barracks in two rows, and a mess hall.
    for col_x in (bx + 500, bx + 550):
        for k in range(4):
            low(b, col_x, y, bz - 300 + k * 70, 15, 50, 8, 0.0, "Concrete")
    b.kit("Kit_Hangar_Small", placer(bx + 400, y, bz - 160))
    # Maintenance depot with trucks out front (doors and noses south).
    dx, dz = bx + 360, bz - 360
    b.kit("Kit_Depot", placer(dx, y, dz))
    for k in range(4):
        b.kit("Kit_Truck", placer(dx - 22 + k * 12, y, dz + 28))
    # Helipad between the hangars and the headquarters.
    b.kit("Kit_Helipad", placer(bx + 320, y - 0.1, bz - 20))
    # Radio mast.
    b.kit("Kit_RadioMast", placer(bx + 440, y, bz - 430))
    # A guard post and barrier where the road comes in.
    s = 0.0
    while s < ROAD_LENGTHS[-1] and math.hypot(road_point(s)[0] - bx, road_point(s)[1] - bz) > BASE[2] - 60:
        s += 5
    gx, gz = road_point(s)
    ax, az = road_point(s + 5)
    d = Vector((ax - gx, az - gz)).normalized()
    side = Vector((d.y, -d.x))
    # The kit's hinge at its origin, the booth along its local +X (here off the
    # road's side) and the 14 m arm along -X, across the road.
    for part in ("Kit_GuardPost", "Kit_GuardPost_Arm"):
        b.kit(part, placer(gx + side.x * 9, y, gz + side.y * 9, math.atan2(-side.y, side.x)))


# --- Sea stacks ----------------------------------------------------------------------
# The kit's sea stacks and their heights above the water.
STACK_KIT = (("Kit_SeaStack_B", 160.0), ("Kit_SeaStack_C", 195.0), ("Kit_SeaStack_A", 230.0))


def build_sea_stacks(col):
    """Each stack is the kit variant nearest its random height, scaled to it and
    turned at random."""
    b = Batch("SeaStacks")
    rng = random.Random(11)
    for x, z in SEA_STACKS:
        h = rng.uniform(150, 230)
        name, kit_h = min(STACK_KIT, key=lambda v: abs(v[1] - h))
        s = h / kit_h
        b.kit(name, placer(x, 0, z, rng.uniform(0, 2 * math.pi)), (s, s, s))
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
    """Kit trees 11 to 19 m tall (the kit's are 15 m; their trunks reach 1 m into
    the ground): mostly dark conifers, round trees in the city's parks."""
    b = Batch("Trees")
    rng = random.Random(9)
    for x, z, g, *park in trees:
        h = rng.uniform(11, 19)
        if park:
            name = "Kit_Tree_Round"
        else:
            name = "Kit_Tree_Conifer" if rng.random() < 0.6 else "Kit_Tree_ConiferLight"
        s = h / 15
        b.kit(name, placer(x, g, z, rng.uniform(0, 2 * math.pi)), (s, s, s))
    b.flush(col)
    return len(trees)


def build_props(root):
    make_materials()
    load_kit()
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
