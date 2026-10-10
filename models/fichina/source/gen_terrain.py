"""Terrain generator for fichina.blend: shapes the whole terrain from the
layout below, and makes the high lake's ice (the frozen lake and stream on the
ice shelf, above the sea-level plane).

    blender --background fichina.blend --python gen_terrain.py

Re-running it REPLACES the terrain (hand sculpting is lost), its own ice
meshes (objects with the custom property generator = "terrain") and the Paint
layer (reset to the high lake (blue) and the glacier (green); re-run the
settlement generators after it). Everything else in the map is left alone. To
keep hand work, sculpt after the last run, or copy the terrain object aside
first. Set TERRAIN_PLAN=<file.png> for a shaded top view (a dry run: the map
isn't changed).

Fichina is landlocked: every hollow below 0 m fills with the game's sea-level
plane, drawn as ice, so the frozen lakes are cut below 0 and all other ground
is kept above LAND_FLOOR.

Layout, in game coordinates (x east, z south; north is -z), 16 x 16 km:
    south       the approach: a U-shaped glacial valley in from the map's
                edge, with a long frozen lake, up to the basin
    centre      the colony's basin, flat, round (0, 700)
    north-east  the big frozen lake; a glacier pours into it from a cirque in
                the northern range (the Spine)
    east        the ice shelf: a 300 m plateau, a sheer cliff over the lake
                (the frozen falls come down it from the shelf's high frozen
                lake), long slopes to the south
    west        the Breaks: terraced mesas and buttes, cut by a deep canyon
                winding down from the north-west to the basin
    south-west  rolling taiga hills with frozen tarns
    south-east  the spaceport's plain
    north-west  a pass valley up to the mining outpost's shelf
    edges       a ring of high mountains all round; the Spine across the north
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
import fichina_common as cc  # noqa: E402
from fields import chaikin, fbm, lerp, line_dist, ridged, smoothstep  # noqa: E402

GENERATOR = "terrain"   # tag on the objects this script owns

# --- Layout (game x, z) ---------------------------------------------------------
WARP = (240.0, 1800.0, 80.0, 500.0)      # outlines bent by noise: metres and size, twice
LAND = 46.0                              # the lowland's mean height, before hills
LAND_FLOOR = 12.0                        # dry ground never lower (only the lakes go below 0)
HILLS = (120.0, 1300.0)                  # rolling hills: height, size
DALES = (80.0, 2000.0)                   # ridges and dales: height, size
HIGHLANDS = (150.0, 480.0, 1300.0, 2300.0, (-0.4, 0.1))   # inner highlands: base, extra at the ridges, ridge size,
                                         # where-noise size, and the noise values over which they fade in
MOUNTAINS = (380.0, 820.0, 1900.0)       # mountain base, extra at the ridges, ridge size
MOUNTAIN_WARP = (1000.0, 3400.0)         # the mountains' outlines are bent much more: metres, size
RING = (6200.0, 700.0, 1400.0)           # edge mountains: radius, its wander round the circle, how far they take to rise
SPINE = (-3500.0, -4900.0)               # the northern range rises between these z
SOUTH_RANGE = (2700.0, 3900.0, -1700.0, 2300.0)   # the southern heights: rise between these z, between these x

BASIN = (0.0, 700.0, 2500.0, 1800.0, 24.0)   # the colony's basin: centre x, z, radii, ground height
PORT = (3900.0, 2900.0, 1500.0, 800.0, 30.0, 38.0)   # the spaceport's plain: centre, radii, turn (degrees), height
TAIGA = (-4100.0, 4100.0, 2700.0, 1900.0)    # the south-west hills: centre, radii (mountains kept low)
TARNS = [(-4700, 3500, 260), (-3300, 4700, 190), (-5600, 4700, 220), (-2600, 3300, 150)]   # x, z, radius
TARN_BED = -7.0

# The big frozen lake: its shore (bent like everything else), and its bed.
LAKE = [(400, -1300), (900, -2300), (1800, -2950), (2600, -3150), (3300, -2950), (3720, -2450),
        (3650, -1800), (3200, -1150), (2400, -800), (1400, -650), (700, -800)]
LAKE_BED = -24.0
LAKE_SHORE = (6.0, 380.0)                # ground at the shoreline, how far in it reaches the bed

# The ice shelf: a plateau, a sheer cliff on its west side over the lake,
# long slopes to the south; a high frozen lake on top whose stream spills
# over the lip as the frozen falls.
PLATEAU = [(3700, -7000), (8000, -7000), (8000, -600), (6400, -350), (4800, -500),
           (3950, -1100), (3780, -2000), (3850, -3300), (3650, -5000)]
PLATEAU_H = 300.0                        # its lowest ground (rising up to PLATEAU_RELIEF more)
PLATEAU_RELIEF = (40.0, 1100.0)
NUNATAKS = [(6700, -5300, 420, 300), (5100, -1500, 260, 170), (7000, -2400, 330, 230)]   # rock peaks through the shelf: x, z, radius, rise
CLIFF = (55.0, 460.0, -1200.0, -500.0)   # edge width: the cliff, the southern slopes, and the z between which it changes
HIGH_LEVEL = 292.0                       # the high lake's ice (the scene's high_water_level)
HIGH_LAKE = (5650.0, -3350.0, 820.0, 520.0, 20.0)   # centre, radii, turn (degrees)
HIGH_STREAM = [(4950, -3150), (4600, -2900), (4250, -2600), (3930, -2450)]
LIP = HIGH_STREAM[-1]                    # where the stream comes over the cliff: the frozen falls
STREAM_HALF_WIDTH = 28.0
FALLS_FOOT = (3720.0, -2450.0, 14.0)     # the ground under the falls: x, z, height (the lake's shore)

# The glacier: from a cirque in the Spine down to the lake's north shore.
GLACIER = [(800, -7000), (1500, -6200), (1250, -5300), (1850, -4550), (1750, -3800), (2350, -3150)]
GLACIER_HEIGHT = (1020.0, 40.0, 1.5)     # its surface: at the top, at the foot, and how concave
GLACIER_HALF_WIDTH = (620.0, 280.0)      # at the top (the cirque), at the foot
GLACIER_WALLS = (520.0, 420.0)           # its valley's walls: how far out they rise, how high
MORAINE = (26.0, 45.0)                   # the lateral moraines: height, half width (just outside the ice)

# The Breaks: terraced high ground in the west.
BREAKS = (-4700.0, -900.0, 2100.0, 2700.0)   # centre, radii
TERRACES = (140.0, 500.0, 110.0, 0.6)      # lowest, highest, step height, where on a step its riser starts
BUTTES = [(-5900, -2200, 260, 120), (-3900, 1200, 200, 90), (-4400, -3400, 300, 140), (-3300, -1900, 170, 80)]   # x, z, radius, rise
CANYON = [(-6300, -5600), (-5600, -4500), (-5000, -3300), (-4500, -2200), (-3900, -1300), (-3300, -400),
          (-2700, 300), (-2250, 750)]
CANYON_FLOOR = (330.0, 26.0, 0.8)        # the floor's height at the top and the bottom, and the curve between
CANYON_WIDTH = (55.0, 130.0)             # half width of the floor, then of the walls
CANYON_ARCH_T = 0.47                     # the ice arch stands this far along it (gen_landmarks.py)

# The approach: a U-shaped valley from the map's south edge into the basin.
APPROACH = [(-200, 8400), (250, 7000), (-150, 5600), (350, 4300), (0, 3100), (0, 2300)]
APPROACH_FLOOR = ([0.0, 0.3, 0.45, 0.62, 0.8, 1.0], [62.0, 34.0, 14.0, 14.0, 22.0, 24.0])   # along it: t, height
APPROACH_WIDTH = (300.0, 750.0, 650.0)   # half width of the floor, how far the walls reach, how high they rise
VALLEY_LAKE = (0.38, 0.66, 120.0, -6.0)  # the frozen lake along its floor: from t, to t, half width, bed

# Dry valleys: path, floor height along it (start, end), half width of the
# floor, then of the slopes.
VALLEYS = [([(-1500, -500), (-2150, -2100), (-2650, -3600), (-3250, -4950)], (30.0, 430.0), 110.0, 420.0),   # the pass to the mine
           ([(5100, 2000), (6300, 1500), (7900, 1300)], (45.0, 260.0), 100.0, 380.0),   # east, out of the spaceport
           ([(-1800, 2700), (-3000, 2400), (-4200, 2600)], (30.0, 55.0), 150.0, 450.0)]  # west, from the basin to the taiga
MINE = (-3300.0, -5000.0, 300.0, 430.0)  # the mining outpost's shelf: centre, radius, height
DRUMLINS = [(-1900, -900, 420, 170, 35, 55), (1600, 1900, 380, 150, -30, 45),     # x, z, half length, half width,
            (-2100, 2000, 500, 200, 70, 60), (2500, 300, 350, 140, 20, 40)]       # turn (degrees), height


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


def ellipse_dist(x, z, cx, cz, rx, rz, turn=0.0):
    """Roughly how far outside a (turned) ellipse a point is (negative inside), in metres."""
    c, s = math.cos(math.radians(turn)), math.sin(math.radians(turn))
    u = (x - cx) * c + (z - cz) * s
    v = -(x - cx) * s + (z - cz) * c
    return (np.hypot(u / rx, v / rz) - 1.0) * min(rx, rz)


def terraced(h):
    """Heights stepped into flat terraces with steep risers (TERRACES)."""
    lo, hi, step, riser = TERRACES
    t = (np.clip(h, lo, hi) - lo) / step
    k = np.floor(t)
    return lo + (k + smoothstep(riser, 1.0, t - k)) * step


# --- The shape ---------------------------------------------------------------------
def shape():
    """Heights at every grid point (POINTS x POINTS, rows along +z), the high
    lake mask and the glacier mask, per point."""
    n = cc.POINTS
    coords = -cc.HALF + np.arange(n) * cc.CELL
    X, Z = np.meshgrid(coords, coords)   # X[j, i], Z[j, i]

    # The falls stay exactly where the layout puts them (gen_landmarks.py
    # places the frozen falls from it); everything else is laid out in bent
    # coordinates, so no outline is a straight line or a perfect ellipse.
    lip_d = np.hypot(X - LIP[0], Z - LIP[1])
    stream_d, _ = line_dist(X, Z, chaikin(HIGH_STREAM))
    keep = smoothstep(250, 900, lip_d) * smoothstep(100, 500, stream_d)
    WX = X + (WARP[0] * fbm(X, Z, WARP[1], 3, 11) + WARP[2] * fbm(X, Z, WARP[3], 2, 13)) * keep
    WZ = Z + (WARP[0] * fbm(X, Z, WARP[1], 3, 12) + WARP[2] * fbm(X, Z, WARP[3], 2, 14)) * keep

    # Where things are.
    basin_d = ellipse_dist(WX, WZ, *BASIN[:4])
    port_d = ellipse_dist(WX, WZ, PORT[0], PORT[1], PORT[2], PORT[3], PORT[4])
    taiga_d = ellipse_dist(WX, WZ, *TAIGA)
    breaks_d = ellipse_dist(WX, WZ, *BREAKS)
    lake_sd = polygon_sdist(WX, WZ, LAKE)
    plateau_sd = polygon_sdist(WX, WZ, PLATEAU) + 90.0 * fbm(X, Z, 450, 3, 16) * keep
    approach_d, approach_t = line_dist(WX, WZ, chaikin(APPROACH))
    glacier_d, glacier_t = line_dist(X, Z, chaikin(GLACIER))
    canyon_d, canyon_t = line_dist(WX, WZ, chaikin(CANYON, 2))

    # Land: rolling hills and dales.
    hills = HILLS[0] * fbm(X, Z, HILLS[1], 4, 1)
    dales = DALES[0] * (ridged(X, Z, DALES[1], 3, 15) - 0.35)
    land = np.maximum(LAND + hills + dales, LAND_FLOOR)

    # Mountains: the ring round the map, the Spine across the north, the
    # southern heights either side of the approach; kept off the basin, the
    # lake, the spaceport, low over the taiga and the Breaks. Their outlines
    # are bent far more than the rest.
    MX = X + MOUNTAIN_WARP[0] * fbm(X, Z, MOUNTAIN_WARP[1], 3, 18)
    MZ = Z + MOUNTAIN_WARP[0] * fbm(X, Z, MOUNTAIN_WARP[1], 3, 19)
    r = np.hypot(MX, MZ)
    around = fbm(MX / np.maximum(r, 1.0) * 3000.0, MZ / np.maximum(r, 1.0) * 3000.0, 1400, 3, 20)
    radius = RING[0] + RING[1] * around
    ring = smoothstep(radius, radius + RING[2], r)
    spine = smoothstep(SPINE[0], SPINE[1], MZ) * smoothstep(-0.45, 0.05, fbm(X, Z, 2600, 2, 7))
    south = (smoothstep(SOUTH_RANGE[0], SOUTH_RANGE[1], MZ)
             * smoothstep(SOUTH_RANGE[2] - 500, SOUTH_RANGE[2] + 300, MX)
             * smoothstep(SOUTH_RANGE[3] + 500, SOUTH_RANGE[3] - 300, MX))
    clear = (smoothstep(-100, 650, basin_d) * smoothstep(-150, -600, lake_sd) * smoothstep(-100, 550, port_d)
             * lerp(0.25, 1.0, smoothstep(-400, 400, taiga_d)) * lerp(0.15, 1.0, smoothstep(-200, 600, breaks_d)))
    mask = np.clip(np.maximum(np.maximum(spine * 0.95, south * 0.8) * clear, ring), 0.0, 1.0)
    peaks = MOUNTAINS[0] + MOUNTAINS[1] * ridged(X, Z, MOUNTAINS[2], 5, 3)
    mountains = mask * peaks * (0.75 + 0.25 * fbm(X, Z, 3000, 2, 4))
    # Inner highlands: ridged hills and small ranges between the open places,
    # wherever a slow noise says, so the land inside the ring isn't one plain.
    where = smoothstep(*HIGHLANDS[4], fbm(X, Z, HIGHLANDS[3], 2, 40))
    highlands = where * clear * (HIGHLANDS[0] + HIGHLANDS[1] * ridged(X, Z, HIGHLANDS[2], 4, 41))
    mountains = np.maximum(mountains, highlands)
    h = land + mountains

    # The Breaks: the ground there raised into terraces (mesas and benches
    # with steep risers), with a few buttes standing higher.
    breaks_w = smoothstep(500, -300, breaks_d)
    raw = (TERRACES[0] + (TERRACES[1] - TERRACES[0]) * (0.55 + 0.6 * fbm(X, Z, 1500, 3, 30))
           * smoothstep(400, -1200, breaks_d))
    h = np.maximum(h, lerp(h, terraced(raw + 25.0 * fbm(X, Z, 300, 2, 31)), breaks_w))
    for bx, bz, br, rise in BUTTES:
        d = np.hypot(WX - bx, WZ - bz) - br * (1.0 + 0.35 * fbm(X, Z, 250, 3, 32))
        top = terraced(raw + rise) + 4.0 * fbm(X, Z, 200, 2, 33)
        h = np.maximum(h, lerp(h, top, smoothstep(45.0, 0.0, d)))

    # The ice shelf: flat, rising gently inland; a sheer cliff on the west,
    # long slopes on the south. Mountains of the ring still rise from it.
    top = PLATEAU_H + PLATEAU_RELIEF[0] * (0.5 + 0.5 * np.clip(fbm(X, Z, PLATEAU_RELIEF[1], 3, 5), -1.0, 1.0))
    edge = lerp(CLIFF[0], CLIFF[1], smoothstep(CLIFF[2], CLIFF[3], WZ))
    edge = np.where(lip_d < 400, lerp(30.0, edge, smoothstep(150, 400, lip_d)), edge)
    on_plateau = smoothstep(-edge, 0.0, plateau_sd)
    h = lerp(h, np.maximum(top, land), on_plateau) + mountains * on_plateau * ring * 0.5
    # Nunataks: rocky peaks standing out of the shelf's ice.
    for nx, nz, nr, rise in NUNATAKS:
        d = np.hypot(X - nx, Z - nz) / (nr * (1.0 + 0.3 * fbm(X, Z, 250, 2, 42)))
        h = h + rise * np.clip(1.0 - d, 0.0, 1.0) ** 1.6 * (0.7 + 0.6 * ridged(X, Z, 300, 3, 43))

    # The high lake on the shelf and the stream to the lip: their ground just
    # under the ice, banks standing above it.
    hl_d = ellipse_dist(WX, WZ, *HIGH_LAKE) + 60.0 * fbm(X, Z, 300, 2, 34)
    hl_ground = lerp(HIGH_LEVEL - 9.0, h, smoothstep(-40.0, 30.0, hl_d))
    h = np.where(hl_d < 30.0, np.minimum(h, hl_ground), h)
    stream_ground = lerp(HIGH_LEVEL - 5.0, PLATEAU_H + 2.0, smoothstep(STREAM_HALF_WIDTH * 0.6, STREAM_HALF_WIDTH + 25, stream_d))
    h = np.where((stream_d < STREAM_HALF_WIDTH + 25) & (on_plateau > 0.99), np.minimum(h, stream_ground), h)
    high_water = ((hl_d < 10.0) | ((stream_d < STREAM_HALF_WIDTH + 10) & (on_plateau > 0.99))) & (h < HIGH_LEVEL)

    # Dry valleys and the mine's shelf; drumlins (long low hills) round the basin.
    for path, (f0, f1), floor_hw, slope_hw in VALLEYS:
        d, t = line_dist(WX, WZ, path)
        floor = lerp(f0, f1, t) + 5.0 * fbm(X, Z, 400, 2, 26)
        h = lerp(h, np.minimum(h, floor + 260.0 * smoothstep(floor_hw, floor_hw + slope_hw, d) ** 2),
                 smoothstep(floor_hw + slope_hw, floor_hw, d) ** 0.5)
    mine_d = np.hypot(WX - MINE[0], WZ - MINE[1]) - MINE[2]
    h = lerp(h, MINE[3] + 3.0 * fbm(X, Z, 200, 2, 27), smoothstep(160, -40, mine_d))
    for hx, hz, hl, hw, turn, hh in DRUMLINS:
        c, s = math.cos(math.radians(turn)), math.sin(math.radians(turn))
        along = ((WX - hx) * c + (WZ - hz) * s) / hl
        across = (-(WX - hx) * s + (WZ - hz) * c) / hw
        h = h + hh * np.clip(1.0 - along * along - across * across, 0.0, 1.0) ** 1.5

    # Flat ground: the basin and the spaceport.
    basin_target = BASIN[4] + 3.0 * fbm(X, Z, 500, 2, 6)
    h = lerp(h, basin_target, smoothstep(500, -200, basin_d))
    h = lerp(h, PORT[5] + 2.0 * fbm(X, Z, 500, 2, 28), smoothstep(450, -100, port_d))

    # The approach: a U-shaped valley (walls steepening as they rise), cut
    # through the southern heights and the ring.
    floor_hw, wall_reach, wall_rise = APPROACH_WIDTH
    a_floor = np.interp(approach_t, *APPROACH_FLOOR) + 3.0 * fbm(X, Z, 400, 2, 35)
    s = np.clip((approach_d - floor_hw) / wall_reach, 0.0, 1.0)
    h = np.where(approach_d < floor_hw + wall_reach, np.minimum(h, a_floor + wall_rise * s * s), h)
    lo, hi, lake_hw, bed = VALLEY_LAKE
    in_lake = smoothstep(lo, lo + 0.03, approach_t) * smoothstep(hi, hi - 0.03, approach_t)
    lake_hw = lake_hw * (0.6 + 0.5 * in_lake) * (1.0 + 0.3 * fbm(X, Z, 300, 2, 36))
    valley_lake = lerp(a_floor, bed, smoothstep(lake_hw + 40, lake_hw * 0.5, approach_d) * in_lake)
    h = np.where(approach_d < lake_hw + 40, np.minimum(h, valley_lake), h)

    # The glacier: its valley's walls first (a trough), the ice surface in it
    # (convex across, crevassed), lateral moraines just outside.
    g_hw = lerp(GLACIER_HALF_WIDTH[0], GLACIER_HALF_WIDTH[1], glacier_t)
    g_surface = GLACIER_HEIGHT[1] + (GLACIER_HEIGHT[0] - GLACIER_HEIGHT[1]) * np.clip(1.0 - glacier_t, 0.0, 1.0) ** GLACIER_HEIGHT[2]
    across = np.clip(glacier_d / g_hw, 0.0, 1.0)
    crevasses = 7.0 * (ridged(X, Z, 160, 2, 37) - 0.5) * smoothstep(0.1, 0.4, glacier_t)
    ice = g_surface + 18.0 * (1.0 - across * across) + crevasses
    trough = g_surface + GLACIER_WALLS[1] * smoothstep(g_hw, g_hw + GLACIER_WALLS[0], glacier_d) ** 1.4
    h = np.where(glacier_d < g_hw + GLACIER_WALLS[0], np.minimum(h, trough), h)
    moraine = MORAINE[0] * np.clip(1.0 - np.abs(glacier_d - g_hw - MORAINE[1]) / MORAINE[1], 0.0, 1.0) ** 2
    h = h + moraine * smoothstep(0.15, 0.3, glacier_t)
    on_ice = glacier_d < g_hw
    h = np.where(on_ice, ice, h)

    # The canyon: a floor falling south-east, steep walls.
    floor = CANYON_FLOOR[1] + (CANYON_FLOOR[0] - CANYON_FLOOR[1]) * np.clip(1.0 - canyon_t, 0.0, 1.0) ** CANYON_FLOOR[2]
    floor = floor + 4.0 * fbm(X, Z, 300, 2, 8)
    c_hw = CANYON_WIDTH[0] * (1.0 + 0.25 * fbm(X, Z, 500, 2, 38))
    wall = smoothstep(c_hw, CANYON_WIDTH[1], canyon_d)
    h = np.where(canyon_d < CANYON_WIDTH[1], np.minimum(h, lerp(floor, h, wall)), h)

    # The lake: from the shore down to its bed. Cut last, so the glacier's
    # tongue runs down into it.
    target = lerp(LAKE_SHORE[0], LAKE_BED, smoothstep(0.0, LAKE_SHORE[1], lake_sd))
    h = np.where(lake_sd > -250, lerp(h, np.minimum(h, target), smoothstep(-250, 0, lake_sd)), h)
    # The ground at the falls' foot: the shore under the cliff.
    foot_d = np.hypot(X - FALLS_FOOT[0], Z - FALLS_FOOT[1])
    h = lerp(h, np.minimum(h, FALLS_FOOT[2]), smoothstep(110, 50, foot_d) * (1.0 - on_plateau))

    # The tarns, then keep all other dry ground above LAND_FLOOR.
    lakes = (lake_sd > 0) | (in_lake * smoothstep(lake_hw + 40, lake_hw * 0.5, approach_d) > 0.3)
    for tx, tz, tr in TARNS:
        d = np.hypot(WX - tx, WZ - tz) - tr * (1.0 + 0.3 * fbm(X, Z, 200, 2, 39))
        h = np.where(d < 120, np.minimum(h, lerp(TARN_BED, LAND_FLOOR + 4, smoothstep(-tr * 0.5, 120, d))), h)
        lakes |= d < 60
    h = np.where(lakes, h, np.maximum(h, LAND_FLOOR))
    on_ice &= h > 1.0
    return h, high_water, on_ice


# --- Into the map ----------------------------------------------------------------------
def remove_generated():
    for o in list(bpy.data.objects):
        if o.get("generator") == GENERATOR and o.library is None:
            data = o.data
            bpy.data.objects.remove(o)
            if isinstance(data, bpy.types.Mesh) and data.users == 0:
                bpy.data.meshes.remove(data)


def write_terrain(h, high_water, glacier):
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
    colors[glacier.reshape(-1), 1] = 1.0
    if paint.domain == "POINT":
        paint.data.foreach_set("color", colors.reshape(-1))
    me.update()


def ice_sheet(name, h, mask, col):
    """The high lake's ice: one flat face per grid cell with any masked corner,
    at HIGH_LEVEL (the banks hide its edge), facing up."""
    cells = mask[:-1, :-1] | mask[1:, :-1] | mask[:-1, 1:] | mask[1:, 1:]
    jj, ii = np.nonzero(cells)
    bm = bmesh.new()
    verts = {}

    def vert(i, j):
        if (i, j) not in verts:
            verts[(i, j)] = bm.verts.new(cc.G(-cc.HALF + i * cc.CELL, HIGH_LEVEL, -cc.HALF + j * cc.CELL))
        return verts[(i, j)]

    for i, j in zip(ii, jj):
        bm.faces.new((vert(i, j), vert(i + 1, j), vert(i + 1, j + 1), vert(i, j + 1)))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        if p.normal.z < 0:
            p.flip()
    me.materials.append(cc.material("Water"))
    me.update()
    o = bpy.data.objects.new(name, me)
    o["generator"] = GENERATOR
    col.objects.link(o)
    return o


def preview_material():
    """The terrain in Blender coloured roughly as the game colours it (snow,
    rock on steep slopes, the glacier's ice), plus the Paint layer. Only for
    the preview: the game colours it itself."""
    m = bpy.data.materials.get("Fichina_Ground") or bpy.data.materials.new("Fichina_Ground")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.9
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    lin = lambda c: (*[cc.srgb_to_linear(v) for v in c], 1.0)
    nz = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Normal"], nz.inputs["Vector"])
    steep = nt.nodes.new("ShaderNodeMath")
    steep.operation = "LESS_THAN"
    steep.inputs[1].default_value = 0.72
    nt.links.new(nz.outputs["Z"], steep.inputs[0])
    rock = nt.nodes.new("ShaderNodeMix")
    rock.data_type = "RGBA"
    rock.inputs["A"].default_value = lin((0.88, 0.9, 0.95))
    rock.inputs["B"].default_value = lin((0.42, 0.42, 0.48))
    nt.links.new(steep.outputs[0], rock.inputs["Factor"])
    paint = nt.nodes.new("ShaderNodeVertexColor")
    paint.layer_name = cc.PAINT_ATTRIBUTE
    add = nt.nodes.new("ShaderNodeMix")
    add.data_type = "RGBA"
    add.blend_type = "MULTIPLY"
    add.inputs["Factor"].default_value = 0.5
    nt.links.new(rock.outputs["Result"], add.inputs["A"])
    nt.links.new(paint.outputs["Color"], add.inputs["B"])
    nt.links.new(add.outputs["Result"], bsdf.inputs["Base Color"])
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return m


def save_plan(path, h, high_water, glacier):
    """A shaded top view of the whole map (north up, 25 m a pixel): ground
    tinted by height (green-grey lowland to white peaks), rock on steep
    slopes, lakes and high water in ice blue, the glacier pale blue, contour
    lines every 100 m, the play boundary in red."""
    step = 1
    hs = h[::step, ::step]
    gz, gx = np.gradient(hs, cc.CELL * step)
    nx, nz, ny = -gx, -gz, np.ones_like(hs)
    norm = np.sqrt(nx * nx + ny * ny + nz * nz)
    light = np.array([-0.6, 0.55, -0.6])       # from the north-west, low
    light /= np.linalg.norm(light)
    shade = np.clip((nx * light[0] + ny * light[1] + nz * light[2]) / norm, 0.0, 1.0)
    slope = np.hypot(gx, gz)
    t = np.clip(hs / 1100.0, 0.0, 1.0)[..., None]
    img = (1.0 - t) * np.array([0.55, 0.62, 0.55]) + t * np.array([1.0, 1.0, 1.0])
    img[slope > 0.85] = (0.4, 0.4, 0.47)
    img[glacier[::step, ::step]] = (0.68, 0.84, 0.95)
    img[high_water[::step, ::step] | (hs < 0.0)] = (0.55, 0.75, 0.92)
    img *= (0.25 + 0.75 * shade)[..., None]
    contours = (np.floor(hs / 100.0) != np.floor(np.roll(hs, 1, 0) / 100.0)) | (np.floor(hs / 100.0) != np.floor(np.roll(hs, 1, 1) / 100.0))
    img[contours] *= 0.75
    m = hs.shape[0]
    coords = -cc.HALF + np.arange(m) * cc.CELL * step
    X, Z = np.meshgrid(coords, coords)
    ring = np.abs(np.hypot(X, Z) - 7000.0) < 30.0
    img[ring] = (0.9, 0.2, 0.2)
    image = bpy.data.images.new("plan", m, m)
    rgba = np.concatenate([img[::-1], np.ones((m, m, 1))], axis=2).astype(np.float32)
    image.pixels.foreach_set(rgba.reshape(-1))
    image.filepath_raw = path
    image.file_format = "PNG"
    image.save()
    bpy.data.images.remove(image)


def main():
    if os.path.normcase(bpy.data.filepath) != os.path.normcase(cc.MAP_FILE):
        bpy.ops.wm.open_mainfile(filepath=cc.MAP_FILE)
    t0 = time.time()
    h, high_water, glacier = shape()
    print("  shaped in %.1f s: heights %.0f to %.0f m; %d high-water points, %d glacier points, %d under 0 m" % (
        time.time() - t0, h.min(), h.max(), int(high_water.sum()), int(glacier.sum()), int((h < 0).sum())))
    plan = os.environ.get("TERRAIN_PLAN")
    if plan:
        save_plan(plan, h, high_water, glacier)
        print("plan saved to %s (dry run: map not changed)" % plan)
        return
    remove_generated()
    write_terrain(h, high_water, glacier)
    ice_sheet("Terrain_HighLake", h, high_water, bpy.data.collections["Water"])
    terrain = bpy.data.objects["Terrain"]
    terrain.data.materials.clear()
    terrain.data.materials.append(preview_material())
    bpy.context.scene["high_water_level"] = HIGH_LEVEL
    bpy.ops.wm.save_as_mainfile(filepath=cc.MAP_FILE, relative_remap=True)
    print("terrain generated in %.1f s" % (time.time() - t0))


if __name__ == "__main__":
    main()
