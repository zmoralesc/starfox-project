"""Terrain generator for corneria.blend: shapes the whole terrain from the
layout below (the coast, the bay, the rivers, the plateau and its falls, the
city's and the base's ground, the canyon, the mountains), and makes the water
that stands above sea level (the upper river).

    blender --background corneria.blend --python gen_terrain.py

Re-running it REPLACES the terrain (hand sculpting is lost) and its own water
meshes (objects with the custom property generator = "terrain"), resets the
Paint layer to just the high water (re-run the settlement generators after
it), and sets the Waterfall marker on the lip. Other markers are moved only
while they're still where new_map.py put them. Everything else in the map is
left alone. To keep hand work, sculpt after the last run, or copy the terrain
object aside first.

Layout, in game coordinates (x east, z south; north is -z), 16 x 16 km:
    south          open sea with islands; the approach from the south
    bay            an inlet north from the coast to the river mouth
    centre         Corneria City round (0, 0), both banks of the river;
                   the port east of the bay's mouth
    north-east     a 180 m plateau; the river comes down a gorge from beyond
                   the mountains (its source is never in sight), crosses it and falls off the
                   south-west cliff, then winds through the city to the bay
    west           the military base, a highway valley to the city, a canyon
                   down from the north-west mountains
    east           low farmland; the harbour town on the east coast
    north / edges  mountains on three sides, with passes; sea to the south
"""

import math
import os
import sys
import time

import bmesh
import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import corneria_common as cc  # noqa: E402
from fields import chaikin, fbm, lerp, line_dist, ridged, smoothstep  # noqa: E402

GENERATOR = "terrain"   # tag on the objects this script owns

# --- Layout (game x, z) ---------------------------------------------------------
COAST_Z = 3300.0                         # the south coast's mean line
COAST_EAST_X = 4300.0                    # east of here the coast swings north-east
COAST_EAST_SLOPE = 0.85                  # metres north per metre east, past COAST_EAST_X
SEA_FLOOR = (-6.0, -60.0, 1800.0)        # at the shore, far out, how far out it gets there
ISLANDS = [(-4300, 6000, 520, 70), (3000, 5600, 360, 45), (-1300, 7000, 260, 35)]   # x, z, radius, height

WARP = (260.0, 1800.0, 90.0, 500.0)     # outlines bent by noise: metres and size, twice
LOWLAND = 14.0                           # land height at the coast, before hills
LAND_FLOOR = 9.0                         # inland ground never lower (rivers and the bay are cut after)
EDGE_WOBBLE = (110.0, 420.0)             # extra ragging of the plateau's edge: metres, size
NORTH_RISE = 0.012                       # extra metres per metre north of z = 0
HILLS = (110.0, 1800.0)                  # rolling hills: height, size
DALES = (70.0, 2600.0)                   # lowland ridges and dales: height, size
MOUNTAINS = (260.0, 560.0, 1900.0)       # mountain base, extra at the ridges, ridge size
MOUNTAIN_WARP = (1100.0, 3500.0)         # the mountains' outlines are bent much more: metres, size
MOUNTAIN_BAND = (-3600.0, -5600.0)       # the inland range rises between these z (north)
RING = (6300.0, 700.0, 1500.0)           # edge mountains: radius from the centre, its variation round the
                                         # circle, how far they take to rise
RING_SOUTH = (500.0, 2200.0)             # ...fading out between these z, so the south stays open to the sea

PLATEAU = [(2700, -8000), (8000, -8000), (8000, -2700), (6200, -2200), (4800, -2500),
           (3900, -3000), (3300, -3700), (2900, -4800), (2700, -6000)]
PLATEAU_H = 182.0                        # the plateau's lowest ground (rising up to PLATEAU_RELIEF more)
PLATEAU_RELIEF = (18.0, 1200.0)          # its gentle hills: metres, size
PLATEAU_RAGGED = (250.0, 900.0)          # its edge's extra wobble away from the falls: metres, size
RIVER_LEVEL = 172.0                      # the upper river's surface (the scene's high_water_level)
# The upper river comes in from beyond the map's north-east edge down a gorge
# with an S-bend, so its upstream end is never in sight, then crosses the
# plateau to the lip of the falls (on the plateau's edge).
UPPER_RIVER = [(6000, -8250), (6300, -7600), (6900, -7100), (6600, -6450), (5900, -5950), (5500, -5250),
               (4800, -5000), (4500, -4400), (4000, -4050), (3950, -3650), (3600, -3350)]
LIP = UPPER_RIVER[-1]                    # where the river pours off the cliff
UPPER_HALF_WIDTH = (34.0, 40.0)          # the upper river's half width: at the gorge's top, at the lip
GORGE_WALLS = 260.0                      # the gorge's walls rise from the banks to the mountains over this
RIVER_SHORT_OF_LIP = 6.0                 # its water surface stops this far before the lip
POOL = (130.0, -14.0)                    # the plunge pool under the falls: radius, depth
LOWER_RIVER = [(3555, -3310), (3150, -2850), (2500, -2250), (1700, -1750), (1000, -1250),   # from the pool under the falls
               (450, -650), (100, 50), (-250, 650), (-480, 1300)]
LOWER_HALF_WIDTH = (45.0, 85.0)          # at the falls, at the mouth
MEANDER = (130.0, 950.0)                 # the lower river's bends: how far, how long (none at its ends)
RIVER_BED = -8.0                         # the lower river is sea water: its bed is below sea level
VALLEY = (650.0, 160.0)                  # the river valley: width of the slopes, flat floor either side
BAY = [(-480, 1300), (-720, 1950), (-560, 2600), (-780, 3300), (-900, 4200)]
BAY_HALF_WIDTH = (260.0, 420.0)          # at the river mouth, at the sea
BAY_BED = -18.0

CITY = (0.0, 0.0, 2400.0, 1750.0, 12.0)  # centre x, z, radius x, radius z, ground height
CITY_HILLS = (-700.0, -1900.0, 30.0)     # the suburbs climb from this z to this z, rising this much
PORT = (250.0, 2500.0, 2700.0, 3150.0, 7.0)  # x0, z0, x1, z1, ground height (east of the bay's mouth)
BASE = (-5000.0, -600.0, 1600.0, 950.0, 34.0)  # centre x, z, radius x, radius z, ground height
TOWN = (5750.0, 1650.0, 480.0, 9.0)      # centre x, z, radius, ground height
FARMS = (2600.0, -2000.0, 6800.0, 1800.0)  # x0, z0, x1, z1: gentler hills
HIGHWAY = [(-2300, -250), (-2900, -500), (-3500, -450), (-4100, -600)]   # valley from the city to the base
# Landforms placed by hand in the lowland, for variety (outlines bent like the rest).
# Big hills are long ridges: x, z, half length, half width, turn (degrees), height.
BIG_HILLS = [(-3300, 2200, 1300, 600, 25, 210), (3400, 900, 1100, 500, -40, 180),
             (-2300, -3300, 1500, 700, 60, 260), (5600, -800, 900, 450, 15, 160)]
MESAS = [(-5400, -2600, 500, 150), (1500, -4200, 450, 190),        # x, z, radius, height: flat
         (-6300, 1800, 420, 130), (4300, 2200, 350, 100)]          # tops, steep sides
MESA_CLIFF = 70.0                        # how wide a mesa's sides are
MESA_LOBES = (0.4, 320.0)                # how ragged their outline is (share of the radius), lobe size
# Valleys: a path, the floor's height along it (start, end), half width of the
# floor, then of the slopes. Dry; they cut passes through the mountains.
VALLEYS = [([(-600, -7400), (-900, -5700), (-500, -4300), (-700, -2700)], (200.0, 35.0), 90.0, 320.0),
           ([(7500, -1300), (6300, -700), (5200, 250)], (110.0, 18.0), 80.0, 300.0),
           ([(-7700, 500), (-6500, 1150), (-5300, 1700)], (120.0, 20.0), 80.0, 300.0)]
CANYON = [(-6600, -7000), (-5600, -5600), (-4700, -4300), (-4000, -3200), (-3300, -2300), (-2500, -1500)]
CANYON_FLOOR = (230.0, 18.0)             # the floor's height at the top and the bottom
CANYON_WIDTH = (70.0, 220.0)             # half width of the floor, then of the walls

# Markers new_map.py put down, and where they go instead (still untouched).
MARKER_DEFAULTS = {"Start": (0.0, 150.0, 7200.0), "IntroStart": (0.0, 150.0, 7500.0),
                   "IntroCameraSpot": (30.0, 154.0, 7200.0), "GreatFox": (1000.0, 900.0, 9500.0)}
MARKER_PLACES = {"Start": (-650.0, 140.0, 6200.0, 0.0), "IntroStart": (-650.0, 140.0, 6500.0, 0.0),
                 "IntroCameraSpot": (-620.0, 144.0, 6200.0, 0.0), "GreatFox": (1800.0, 750.0, 9400.0, 1.22)}


# --- Layout helpers -------------------------------------------------------------
def polygon_sdist(x, z, poly):
    """Signed distance to a polygon's edge: positive inside."""
    inside = np.zeros(x.shape, dtype=bool)
    d = np.full(x.shape, np.inf)
    for (ax, az), (bx, bz) in zip(poly, poly[1:] + poly[:1]):
        crosses = (az > z) != (bz > z)
        xc = ax + (z - az) * (bx - ax) / ((bz - az) if bz != az else 1e-9)
        inside ^= crosses & (x < xc)
        d = np.minimum(d, line_dist(x, z, [(ax, az), (bx, bz)])[0])
    return np.where(inside, d, -d)


def ellipse_dist(x, z, cx, cz, rx, rz):
    """Roughly how far outside an ellipse a point is (negative inside), in metres."""
    e = np.hypot((x - cx) / rx, (z - cz) / rz)
    return (e - 1.0) * min(rx, rz)


def coast_z(x):
    """The coastline: land north of it (smaller z), sea south."""
    z = COAST_Z + 180 * np.sin(x / 900 + 0.4) + 90 * np.sin(x / 330 + 2.1)
    return z - np.maximum(x - COAST_EAST_X, 0.0) * COAST_EAST_SLOPE


def meander(pts, step=40.0):
    """A polyline resampled every `step` metres and swung from side to side
    (MEANDER: how far, how long a bend), not at all at its two ends."""
    pts = [Vector(p) for p in pts]
    lengths = [(b - a).length for a, b in zip(pts, pts[1:])]
    total = sum(lengths)
    out = []
    s = 0.0
    while s <= total:
        # The point s metres along, and the direction there.
        k, rest = 0, s
        while k < len(lengths) - 1 and rest > lengths[k]:
            rest -= lengths[k]
            k += 1
        a, b = pts[k], pts[k + 1]
        d = (b - a).normalized()
        p = a + d * min(rest, lengths[k])
        taper = min(s / 600.0, (total - s) / 600.0, 1.0)
        swing = MEANDER[0] * math.sin(2 * math.pi * s / MEANDER[1]) * taper
        out.append((p.x + d.y * swing, p.y - d.x * swing))
        s += step
    out.append(tuple(pts[-1]))
    return out


# --- The shape ---------------------------------------------------------------------
def shape():
    """Heights at every grid point (POINTS x POINTS, rows along +z), and the
    high-water mask per point."""
    n = cc.POINTS
    coords = -cc.HALF + np.arange(n) * cc.CELL
    X, Z = np.meshgrid(coords, coords)   # X[j, i], Z[j, i]

    # The falls and the upper river stay exactly where the layout puts them
    # (the Waterfall marker and the river's water mesh are placed from it).
    lip_d = np.hypot(X - LIP[0], Z - LIP[1])
    upper_d, upper_t = line_dist(X, Z, chaikin(UPPER_RIVER))
    # Everything else is laid out in bent coordinates, so no outline is a
    # straight line or a perfect ellipse.
    keep = smoothstep(300, 1100, lip_d) * smoothstep(150, 700, upper_d)
    WX = X + (WARP[0] * fbm(X, Z, WARP[1], 3, 11) + WARP[2] * fbm(X, Z, WARP[3], 2, 13)) * keep
    WZ = Z + (WARP[0] * fbm(X, Z, WARP[1], 3, 12) + WARP[2] * fbm(X, Z, WARP[3], 2, 14)) * keep

    # Where things are.
    lower_d, lower_t = line_dist(WX, WZ, meander(LOWER_RIVER))
    bay_d, bay_t = line_dist(WX, WZ, BAY)
    canyon_d, canyon_t = line_dist(WX, WZ, CANYON)
    highway_d, _ = line_dist(WX, WZ, HIGHWAY)
    plateau_sd = polygon_sdist(WX, WZ, PLATEAU) + (EDGE_WOBBLE[0] * fbm(X, Z, EDGE_WOBBLE[1], 3, 16)
                                                  + PLATEAU_RAGGED[0] * fbm(X, Z, PLATEAU_RAGGED[1], 3, 22)
                                                  * smoothstep(600, 2000, lip_d)) * keep
    city_d = ellipse_dist(WX, WZ, *CITY[:4])
    base_d = ellipse_dist(WX, WZ, *BASE[:4])
    town_d = np.hypot(WX - TOWN[0], WZ - TOWN[1]) - TOWN[2]

    # Land: low near the coast, rising north, with rolling hills and dales
    # (gentler on the farms).
    north = np.maximum(-WZ, 0.0)
    farms = smoothstep(-400, 400, np.minimum.reduce([WX - FARMS[0], FARMS[2] - WX, WZ - FARMS[1], FARMS[3] - WZ]))
    hills = HILLS[0] * fbm(X, Z, HILLS[1], 4, 1) * (1.0 - 0.5 * farms)
    dales = DALES[0] * (ridged(X, Z, DALES[1], 3, 15) - 0.35) * (1.0 - 0.6 * farms)
    # Never below LAND_FLOOR inland: the sea would fill any hollow under sea level.
    land = np.maximum(LOWLAND + north * NORTH_RISE + hills + dales, LAND_FLOOR)

    # Mountains: the inland range in the north (broken by passes) and a ring
    # round the west, north and east; kept off the places below. Their outlines
    # are bent far more than the rest (spurs reaching in, valleys reaching out),
    # and the ring is round with a radius that wanders, so nothing lines up with
    # the map's square edge. The canyon and the upper river's gorge cut
    # through them (further down) rather than clearing them.
    MX = X + MOUNTAIN_WARP[0] * fbm(X, Z, MOUNTAIN_WARP[1], 3, 18)
    MZ = Z + MOUNTAIN_WARP[0] * fbm(X, Z, MOUNTAIN_WARP[1], 3, 19)
    band = smoothstep(MOUNTAIN_BAND[0], MOUNTAIN_BAND[1], MZ) * smoothstep(-0.35, 0.15, fbm(X, Z, 2600, 2, 7))
    r = np.hypot(MX, MZ)
    around = fbm(MX / np.maximum(r, 1.0) * 3000.0, MZ / np.maximum(r, 1.0) * 3000.0, 1400, 3, 20)
    radius = RING[0] + RING[1] * around
    ring = smoothstep(radius, radius + RING[2], r) * smoothstep(RING_SOUTH[1], RING_SOUTH[0], MZ)
    clear = (smoothstep(80, 450, upper_d) * smoothstep(300, 900, lower_d)
             * smoothstep(0, 1200, city_d) * smoothstep(0, 1000, base_d) * smoothstep(300, 900, highway_d))
    mask = np.clip(np.maximum(band * 0.8, ring), 0.0, 1.0) * np.maximum(clear, ring * 0.9)
    peaks = MOUNTAINS[0] + MOUNTAINS[1] * ridged(X, Z, MOUNTAINS[2], 5, 3)
    mountains = mask * peaks * (0.75 + 0.25 * fbm(X, Z, 3000, 2, 4))

    # The plateau: flat, a cliff by the falls, longer slopes elsewhere.
    # Never below PLATEAU_H, so the upper river's banks always stand above its water.
    plateau_top = PLATEAU_H + PLATEAU_RELIEF[0] * (0.5 + 0.5 * np.clip(fbm(X, Z, PLATEAU_RELIEF[1], 3, 5), -1.0, 1.0))
    slope = lerp(30.0, 260.0, smoothstep(250, 1600, lip_d))
    on_plateau = smoothstep(-slope, 0.0, plateau_sd)
    h = lerp(land, np.maximum(plateau_top, land), on_plateau) + mountains * (1.0 - 0.7 * on_plateau * (1 - ring))

    # Placed landforms: big hills (long ridges, roughened), mesas (flat tops,
    # steep sides, lobed), then the valleys cut down to their floors.
    for hx, hz, hl, hw, turn, hh in BIG_HILLS:
        c, s = math.cos(math.radians(turn)), math.sin(math.radians(turn))
        along = ((WX - hx) * c + (WZ - hz) * s) / hl
        across = (-(WX - hx) * s + (WZ - hz) * c) / hw
        d2 = along * along + across * across
        ridge = np.clip(1.0 - d2, 0.0, 1.0) ** 1.5
        h = h + hh * ridge * (0.75 + 0.5 * ridged(X, Z, 700, 3, 23))
    for mx, mz, mr, mh in MESAS:
        d = np.hypot(WX - mx, WZ - mz) - mr * (1.0 + MESA_LOBES[0] * fbm(X, Z, MESA_LOBES[1], 3, 24))
        top = mh + 6.0 * fbm(X, Z, 300, 2, 25)
        h = np.maximum(h, lerp(h, top, smoothstep(MESA_CLIFF, 0.0, d)))
    for path, (f0, f1), floor_hw, slope_hw in VALLEYS:
        d, t = line_dist(WX, WZ, path)
        floor = lerp(f0, f1, t) + 5.0 * fbm(X, Z, 400, 2, 26)
        h = lerp(h, np.minimum(h, floor), smoothstep(floor_hw + slope_hw, floor_hw, d))

    # Flat ground for the city (its suburbs climbing north), the port, the base and the town.
    city_target = CITY[4] + CITY_HILLS[2] * smoothstep(CITY_HILLS[0], CITY_HILLS[1], WZ) + 3.0 * fbm(X, Z, 500, 2, 6)
    h = lerp(h, city_target, smoothstep(500, -200, city_d))
    port_in = np.minimum.reduce([X - PORT[0], PORT[2] - X, Z - PORT[1], PORT[3] - Z])
    h = lerp(h, PORT[4], smoothstep(-250, 50, port_in))
    h = lerp(h, BASE[4], smoothstep(500, -100, base_d))
    h = lerp(h, TOWN[3], smoothstep(300, -50, town_d))

    # The highway valley: eased towards a straight grade between the city and the base.
    grade = lerp(CITY[4], BASE[4], smoothstep(HIGHWAY[0][0], HIGHWAY[-1][0], WX))
    h = lerp(h, np.minimum(h, grade + 15.0), smoothstep(500, 120, highway_d))

    # The canyon: a floor falling south-east, steep walls.
    floor = lerp(CANYON_FLOOR[0], CANYON_FLOOR[1], canyon_t) + 4.0 * fbm(X, Z, 300, 2, 8)
    wall = smoothstep(CANYON_WIDTH[0], CANYON_WIDTH[1], canyon_d)
    h = np.where(canyon_d < CANYON_WIDTH[1], np.minimum(h, lerp(floor, h, wall)), h)

    # The upper river: its channel (bed 10 m under the water), banks up to the
    # plateau, and through the mountains a gorge whose walls rise over
    # GORGE_WALLS metres.
    upper_hw = lerp(UPPER_HALF_WIDTH[0], UPPER_HALF_WIDTH[1], upper_t)
    banks = lerp(RIVER_LEVEL - 10, PLATEAU_H + 2, smoothstep(upper_hw * 0.6, upper_hw + 30, upper_d))
    walls = lerp(PLATEAU_H + 2, h, smoothstep(upper_hw + 30, upper_hw + 30 + GORGE_WALLS, upper_d))
    h = np.where(upper_d < upper_hw + 30 + GORGE_WALLS,
                 np.minimum(h, np.where(upper_d < upper_hw + 30, banks, walls)), h)

    # The lower river: a valley with a flat floor, the channel cut below sea level
    # (the sea's water fills it), and the plunge pool under the falls.
    lower_hw = lerp(LOWER_HALF_WIDTH[0], LOWER_HALF_WIDTH[1], lower_t)
    valley_floor = lerp(16.0, 7.0, lower_t)
    off_plateau = 1.0 - on_plateau
    valley = smoothstep(lower_hw + VALLEY[1] + VALLEY[0], lower_hw + VALLEY[1], lower_d) * off_plateau
    h = lerp(h, np.minimum(h, valley_floor), valley)
    channel = lerp(RIVER_BED, valley_floor, smoothstep(lower_hw * 0.7, lower_hw + 25, lower_d))
    h = np.where(lower_d < lower_hw + 25, np.minimum(h, channel), h)
    pool_d = np.hypot(X - LOWER_RIVER[0][0], Z - LOWER_RIVER[0][1])
    h = np.where(pool_d < POOL[0] + 40, np.minimum(h, lerp(POOL[1], 8.0, smoothstep(POOL[0] * 0.6, POOL[0] + 40, pool_d))), h)

    # The bay: from the river mouth out to the sea.
    bay_hw = lerp(BAY_HALF_WIDTH[0], BAY_HALF_WIDTH[1], bay_t)
    h = lerp(h, np.minimum(h, BAY_BED), smoothstep(bay_hw + 220, bay_hw, bay_d))

    # The sea: south of the coast the ground falls to the sea floor; islands rise from it.
    out = WZ - coast_z(WX)
    land_w = smoothstep(150.0, -300.0, out)
    sea = lerp(SEA_FLOOR[0], SEA_FLOOR[1], smoothstep(0.0, SEA_FLOOR[2], out))
    for ix, iz, r, ih in ISLANDS:
        # From the island's height in the middle down to 100 m under water at
        # 1.6 radii (the sea floor wins long before), so the shore lies near the
        # radius; ragged outline.
        d = np.hypot(X - ix, Z - iz) * (1.0 + 0.25 * fbm(X, Z, 300, 2, 9))
        sea = np.maximum(sea, ih - (ih + 100.0) * smoothstep(r * 0.3, r * 1.6, d))
    h = lerp(sea, h, land_w)

    # High water: the ground that lies under the upper river.
    high_water = (upper_d < upper_hw + 40) & (h < RIVER_LEVEL)
    return h, high_water


# --- Into the map ----------------------------------------------------------------------
def remove_generated():
    for o in list(bpy.data.objects):
        if o.get("generator") == GENERATOR and o.library is None:
            data = o.data
            bpy.data.objects.remove(o)
            if isinstance(data, bpy.types.Mesh) and data.users == 0:
                bpy.data.meshes.remove(data)


def write_terrain(h, high_water):
    t = bpy.data.objects["Terrain"]
    me = t.data
    n = cc.POINTS
    if len(me.vertices) != n * n:
        raise RuntimeError("the Terrain mesh isn't the %d x %d grid new_map.py makes" % (n, n))
    t.matrix_world.identity()
    coords = -cc.HALF + np.arange(n) * cc.CELL
    X, Z = np.meshgrid(coords, coords)
    co = np.stack([X, -Z, h], axis=-1).astype(np.float32).reshape(-1)   # game to Blender
    me.vertices.foreach_set("co", co)
    paint = me.color_attributes.get(cc.PAINT_ATTRIBUTE) or me.color_attributes.new(cc.PAINT_ATTRIBUTE, "BYTE_COLOR", "POINT")
    colors = np.zeros((n * n, 4), dtype=np.float32)
    colors[:, 3] = 1.0
    colors[high_water.reshape(-1), 2] = 1.0
    if paint.domain == "POINT":
        paint.data.foreach_set("color", colors.reshape(-1))
    me.update()


def water_sheet(name, outline, col):
    """A flat water surface from an outline of game points, facing up."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([cc.G(*p) for p in outline], [], [tuple(range(len(outline)))])
    me.materials.append(cc.material("Water"))
    me.validate()
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.triangulate(bm, faces=bm.faces)   # concave outlines: triangles, not one n-gon
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        if p.normal.z < 0:
            p.flip()
    me.update()
    o = bpy.data.objects.new(name, me)
    o["generator"] = GENERATOR
    col.objects.link(o)
    return o


def build_water():
    col = bpy.data.collections["Water"]
    # The upper river: a ribbon along the same rounded path as its channel,
    # from past the map's edge to just short of the lip; a little wider than
    # the water's edge on the banks, which hide its sides.
    pts = [Vector(p) for p in chaikin(UPPER_RIVER)]
    d = (pts[-1] - pts[-2]).normalized()
    pts[-1] = pts[-1] - d * RIVER_SHORT_OF_LIP
    along = [0.0]
    for a, b in zip(pts, pts[1:]):
        along.append(along[-1] + (b - a).length)
    left, right = [], []
    for k, p in enumerate(pts):
        a, b = pts[max(k - 1, 0)], pts[min(k + 1, len(pts) - 1)]
        t = (b - a).normalized()
        hw = lerp(UPPER_HALF_WIDTH[0], UPPER_HALF_WIDTH[1], along[k] / along[-1]) * 1.15
        side = Vector((t.y, -t.x)) * hw
        left.append((p.x + side.x, RIVER_LEVEL, p.y + side.y))
        right.append((p.x - side.x, RIVER_LEVEL, p.y - side.y))
    me = bpy.data.meshes.new("Terrain_UpperRiver")
    m = len(left)
    me.from_pydata([cc.G(*p) for p in left + right], [], [(k, k + 1, m + k + 1, m + k) for k in range(m - 1)])
    me.materials.append(cc.material("Water"))
    for p in me.polygons:
        if p.normal.z < 0:
            p.flip()
    o = bpy.data.objects.new("Terrain_UpperRiver", me)
    o["generator"] = GENERATOR
    col.objects.link(o)


def place_markers():
    # The falls: on the lip, a little above the river, flowing towards the pool.
    lip = Vector(LIP)
    flow = (Vector(LOWER_RIVER[0]) - lip).normalized()
    turn = math.atan2(flow.x, flow.y)
    falls = bpy.data.objects["Waterfall"]
    falls.matrix_world = cc.TO_BLENDER @ cc.game_transform(lip.x, RIVER_LEVEL + 0.3, lip.y, turn) @ cc.TO_GAME
    for name, default in MARKER_DEFAULTS.items():
        o = bpy.data.objects.get(name)
        if o is not None and (o.location - cc.G(*default)).length < 0.5:
            x, y, z, turn = MARKER_PLACES[name]
            o.matrix_world = cc.TO_BLENDER @ cc.game_transform(x, y, z, turn) @ cc.TO_GAME


def preview_material():
    """The terrain in Blender coloured roughly as the game colours it (sand by
    the water, grass, rock on steep slopes, snow up high), plus the Paint
    layer added on top. Only for the preview: the game colours it itself."""
    m = bpy.data.materials.get("Corneria_Ground") or bpy.data.materials.new("Corneria_Ground")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.9
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    xyz = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Position"], xyz.inputs["Vector"])
    lin = lambda c: (*[cc.srgb_to_linear(v) for v in c], 1.0)
    height = nt.nodes.new("ShaderNodeValToRGB")
    ramp = height.color_ramp
    ramp.interpolation = "CONSTANT"
    ramp.elements[0].position = 0.0
    ramp.elements[0].color = lin((0.86, 0.79, 0.55))      # sand
    ramp.elements[1].position = 6.0 / 300.0
    ramp.elements[1].color = lin((0.42, 0.66, 0.3))       # grass
    snow = ramp.elements.new(260.0 / 300.0)
    snow.color = lin((0.94, 0.96, 1.0))
    scale = nt.nodes.new("ShaderNodeMath")
    scale.operation = "DIVIDE"
    scale.inputs[1].default_value = 300.0
    nt.links.new(xyz.outputs["Z"], scale.inputs[0])
    nt.links.new(scale.outputs[0], height.inputs["Fac"])
    # Rock where the normal tips more than ~39 degrees (Terrain.rock_slope 0.78).
    nz = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Normal"], nz.inputs["Vector"])
    steep = nt.nodes.new("ShaderNodeMath")
    steep.operation = "LESS_THAN"
    steep.inputs[1].default_value = 0.78
    nt.links.new(nz.outputs["Z"], steep.inputs[0])
    rock = nt.nodes.new("ShaderNodeMix")
    rock.data_type = "RGBA"
    rock.inputs["B"].default_value = lin((0.5, 0.47, 0.44))
    nt.links.new(steep.outputs[0], rock.inputs["Factor"])
    nt.links.new(height.outputs["Color"], rock.inputs["A"])
    paint = nt.nodes.new("ShaderNodeVertexColor")
    paint.layer_name = cc.PAINT_ATTRIBUTE
    add = nt.nodes.new("ShaderNodeMix")
    add.data_type = "RGBA"
    add.blend_type = "ADD"
    add.inputs["Factor"].default_value = 1.0
    nt.links.new(rock.outputs["Result"], add.inputs["A"])
    nt.links.new(paint.outputs["Color"], add.inputs["B"])
    nt.links.new(add.outputs["Result"], bsdf.inputs["Base Color"])
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return m


def main():
    if os.path.normcase(bpy.data.filepath) != os.path.normcase(cc.MAP_FILE):
        bpy.ops.wm.open_mainfile(filepath=cc.MAP_FILE)
    t0 = time.time()
    h, high_water = shape()
    print("  shaped in %.1f s: heights %.0f to %.0f m" % (time.time() - t0, h.min(), h.max()))
    remove_generated()
    write_terrain(h, high_water)
    build_water()
    place_markers()
    terrain = bpy.data.objects["Terrain"]
    terrain.data.materials.clear()
    terrain.data.materials.append(preview_material())
    bpy.context.scene["high_water_level"] = RIVER_LEVEL
    bpy.ops.wm.save_as_mainfile(filepath=cc.MAP_FILE, relative_remap=True)
    print("terrain generated in %.1f s" % (time.time() - t0))


if __name__ == "__main__":
    main()
