"""Colony generator for fichina.blend: lays the colony out in the basin round
the Climate Control Center (streets, blocks, lots, buildings, domes and their
walkways, cabins, paving).

    blender --background fichina.blend --python gen_colony.py

Run it after gen_terrain.py (which wipes the paving). Re-running it REPLACES
what it made before: the objects and collections with the custom property
generator = "colony" (under Props/Colony and Props/Roads), and the paving it
painted (the terrain's "colony_paved" attribute remembers which points).
Anything else in the map is left alone. Set COLONY_PLAN=<file.png> for a plan
of the result instead (a dry run: the map isn't saved).

How the colony is laid out (game coordinates, x east, z south), on Corneria's
settlement tools (models/corneria/source/settlement.py):
    plaza       a round plaza at the middle, the Climate Control Center on it
                (the ClimateCenter marker follows it, for the level's
                avoidance box)
    districts   zone_of(): the core round the plaza (towers, tallest nearest
                it), the dome quarter (north-east: domes and greenhouses
                joined by walkway tubes), the industrial edge (south-east,
                towards the spaceport: depots, tank farms, the power plants),
                and habitat blocks everywhere else
    blocks      a Voronoi diagram of seed points on each district's lattice
                (the planned colony on one grid angle; the domes looser), the
                streets the gaps between cells
    avenues     radial avenues from the plaza and a ring road cut through the
                blocks; past the colony's edge gen_outposts.py's roads carry on
    cabins      scattered on the snow round the colony's edge
    paving      the terrain's Paint layer, red under the lots and streets: the
                colony's heated streets are clear of snow
"""

import math
import os
import sys
import time

import bpy
import numpy as np
from mathutils import Matrix

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fichina_common as cc  # noqa: E402
import settlement as st  # noqa: E402
from fields import fbm  # noqa: E402

GENERATOR = "colony"
SEED = 7

# --- Layout ---------------------------------------------------------------------
CENTRE = (-150.0, 700.0)                 # the plaza's middle: the Climate Control Center
RADII = (1500.0, 1050.0)                 # the colony's extent: an ellipse...
RAGGED = (0.16, 800.0)                   # ...with a ragged edge: share of the radius, size
PLAZA_RADIUS = 175.0                     # the plaza: no other block's seed within 1.6 times this (the plaza is its cell)
CORE = 520.0                             # towers within this of the middle
DOMES = (25.0, 105.0, 0.32)              # the dome quarter: from bearing, to bearing (degrees, 0 = east,
                                         # 90 = north), past this share of the radius
INDUSTRY = (-75.0, -15.0, 0.5)           # the industrial edge: bearings, past this share of the radius
GRID_ANGLE = 0.35                        # the planned colony's street grid (radians)
LATTICE_WARP = (90.0, 1600.0)

# Per district: block seed spacing (along, across) and jitter (share of the
# spacing), lattice angle, street width, lot size (frontage, depth), setback.
DISTRICTS = {
    "plaza": dict(spacing=(450.0, 450.0), jitter=0.0, angle=0.0, street=22.0, lot=(999.0, 999.0), setback=0.0),
    "core": dict(spacing=(95.0, 85.0), jitter=0.04, angle=GRID_ANGLE, street=20.0, lot=(42.0, 38.0), setback=4.0),
    "habs": dict(spacing=(100.0, 72.0), jitter=0.12, angle=GRID_ANGLE, street=15.0, lot=(34.0, 24.0), setback=3.0),
    "domes": dict(spacing=(115.0, 105.0), jitter=0.3, angle=GRID_ANGLE + 0.5, street=16.0, lot=(999.0, 999.0), setback=6.0),
    "industry": dict(spacing=(150.0, 120.0), jitter=0.06, angle=GRID_ANGLE, street=18.0, lot=(62.0, 48.0), setback=5.0),
}
ZONES = ["plaza", "core", "habs", "domes", "industry"]
Z_PLAZA, Z_CORE, Z_HABS, Z_DOMES, Z_INDUSTRY = range(5)

AVENUES = 5                              # radial avenues from the plaza, evenly round it (turned AVENUE_TURN)
AVENUE_TURN = 0.35
RING_ROAD = (0.55, 90.0)                 # the ring road: share of the radii, wobble (metres)
AVENUE_WIDTH = 26.0

# --- Ground -----------------------------------------------------------------------
CURB = 0.25
SKIRT = 0.8
BUILDABLE = dict(min_height=2.5, max_slope=0.14, water_clearance=60.0)
PAVE_MARGIN = 3.0

# --- Buildings ----------------------------------------------------------------------
TOWER_HEIGHT = (45.0, 70.0)              # a tower's least height, and the most it adds nearest the plaza
TOWER_WIDTH = (22.0, 36.0)               # a tower's footprint side
HAB_HEIGHT = (8.0, 20.0)                 # habitat blocks: low to high (bigger lots get taller blocks)
MAST_CHANCE = 0.03                       # a habitat lot holds a comms mast instead, this often
PARK_CHANCE = {Z_CORE: 0.04, Z_HABS: 0.06}   # blocks left as snowy squares with a few pines, this often
PARK_PINES = (4, 12)
DOME_SIZE = (36.0, 62.0)                 # a dome's diameter, fitted to its block
GREENHOUSE_CHANCE = 0.4                  # dome-quarter blocks holding greenhouses instead of a dome
TUBE = dict(reach=130.0, height=4.5, sink=0.75)   # walkways: longest gap bridged, height of their middle,
                                                  # how far into each dome (share of its radius) they reach
TANK_FARM_CHANCE = 0.25
PLANTS = 2                               # power plants, on the largest industrial lots
CABINS = dict(spacing=40.0, chance=0.55, ring=(1.02, 1.5), scale=(0.8, 1.3), hamlets=(450.0, 0.28))
                                         # outskirts: on a jittered grid between these shares of the colony's
                                         # (ragged) radius, in hamlets (where noise of this size is over this)

PIECES = dict(climate="Kit_Colony_ClimateCenter", tower="Kit_Colony_Tower", hab="Kit_Colony_Hab",
              dome="Kit_Colony_Dome", greenhouse="Kit_Colony_Greenhouse", tube="Kit_Colony_Tube",
              cabin="Kit_Colony_Cabin", depot="Kit_Colony_Depot", tank="Kit_Colony_Tank",
              plant="Kit_Colony_Plant", mast="Kit_Colony_Mast", pine="Kit_Tree_SnowPine")


def district(zone):
    return DISTRICTS[ZONES[zone]]


# --- Districts -------------------------------------------------------------------------
def edge_share(x, z):
    """How far out a point is: 1 at the colony's (ragged) edge."""
    return (np.hypot((x - CENTRE[0]) / RADII[0], (z - CENTRE[1]) / RADII[1])
            + RAGGED[0] * fbm(x, z, RAGGED[1], 3, 61))


def bearing(x, z):
    """Degrees round the middle: 0 east, 90 north."""
    return np.degrees(np.arctan2(-(z - CENTRE[1]), x - CENTRE[0]))


def zone_of(x, z):
    """The zone (index into ZONES) of each point; -1 outside the colony."""
    x, z = np.atleast_1d(np.asarray(x, float)), np.atleast_1d(np.asarray(z, float))
    e = edge_share(x, z)
    b = bearing(x, z)
    d = np.hypot(x - CENTRE[0], z - CENTRE[1])
    out = np.full(x.shape, -1)
    inside = e < 1.0
    out[inside] = Z_HABS
    out[inside & (b > DOMES[0]) & (b < DOMES[1]) & (e > DOMES[2])] = Z_DOMES
    out[inside & (b > INDUSTRY[0]) & (b < INDUSTRY[1]) & (e > INDUSTRY[2])] = Z_INDUSTRY
    out[inside & (d < CORE)] = Z_CORE
    out[d < PLAZA_RADIUS] = Z_PLAZA
    return out


# --- Streets and blocks -------------------------------------------------------------
def lattice_seeds(ground, rng):
    seeds = [(CENTRE[0], CENTRE[1], Z_PLAZA)]
    for zone in range(1, len(ZONES)):
        d = district(zone)
        sa, sb = d["spacing"]
        c, s = math.cos(d["angle"]), math.sin(d["angle"])
        reach = 2400.0
        U, V = np.meshgrid(np.arange(-reach, reach, sa), np.arange(-reach, reach, sb))
        U = U + rng.uniform(-0.5, 0.5, U.shape) * sa * d["jitter"] * 2
        V = V + rng.uniform(-0.5, 0.5, V.shape) * sb * d["jitter"] * 2
        x = CENTRE[0] + 37.0 + U * c - V * s
        z = CENTRE[1] + 19.0 + U * s + V * c
        x = x + LATTICE_WARP[0] * fbm(x, z, LATTICE_WARP[1], 2, 62)
        z = z + LATTICE_WARP[0] * fbm(x, z, LATTICE_WARP[1], 2, 63)
        x, z = x.ravel(), z.ravel()
        keep = (zone_of(x, z) == zone) & (np.hypot(x - CENTRE[0], z - CENTRE[1]) > PLAZA_RADIUS * 1.6)
        x, z = x[keep], z[keep]
        keep = ground.height(x, z) >= st.WATER_BELOW
        seeds += [(float(a), float(b), zone) for a, b in zip(x[keep], z[keep])]
    return seeds


def road_lines():
    """The radial avenues (from the plaza out past the edge) and the ring road."""
    lines = [radial(AVENUE_TURN + 2 * math.pi * k / AVENUES) for k in range(AVENUES)]
    share, wobble = RING_ROAD
    ring = []
    for k in range(48):
        t = 2 * math.pi * k / 48
        x, z = CENTRE[0] + share * RADII[0] * math.cos(t), CENTRE[1] - share * RADII[1] * math.sin(t)
        w = wobble * float(fbm(np.array([x]), np.array([z]), 600, 2, 64)[0])
        ring.append((x + w * math.cos(t), z - w * math.sin(t)))
    lines.append(st.densify(ring + ring[:1]))
    return lines


def radial(t):
    """An avenue at angle t (radians, 0 east, anticlockwise from above): from
    the plaza's edge out to 1.15 of the colony's radius, bending a little."""
    pts = []
    for s in np.linspace(0.0, 1.0, 9):
        rx = PLAZA_RADIUS + s * (1.15 * RADII[0] - PLAZA_RADIUS)
        rz = PLAZA_RADIUS + s * (1.15 * RADII[1] - PLAZA_RADIUS)
        bend = 0.12 * s * s * math.sin(3.0 * t)
        pts.append((CENTRE[0] + rx * math.cos(t + bend), CENTRE[1] - rz * math.sin(t + bend)))
    return st.road_line(pts, 2)


def make_lots(blocks, roads, ground, rng):
    lots = []
    for poly, zone, (sx, sz) in blocks:
        d = district(zone)
        if zone == Z_PLAZA:
            lot = st.Lot(poly, zone, False)
            lot.plaza = True
            lots.append(lot)
            continue
        for piece in roads.split(poly):
            parts = []
            park = rng.random() < PARK_CHANCE.get(zone, 0.0)
            if zone == Z_DOMES or park:
                parts = [piece]
            else:
                st.subdivide(piece, d["lot"][0], d["lot"][1], rng, parts)
            lots += [st.Lot(p, zone, park) for p in parts if abs(st.area(p)) > 60.0]
    return st.fit_lots(lots, ground, lambda x, z: zone_of(x, z) >= 0, BUILDABLE, CURB, SKIRT)


# --- Buildings -----------------------------------------------------------------------
def place_buildings(lots, placer, rng):
    domes = []
    industry = []
    for lot in lots:
        zone = lot.zone
        c, u, a, b = st.inscribed(lot.poly)
        if lot.park:
            plant_square(lot, placer, rng)
            continue
        if getattr(lot, "plaza", False):
            # The Climate Control Center at the plaza's middle, its front to the south.
            placer.put("climate", CENTRE[0], lot.top, CENTRE[1], 0.0, None, "Colony")
            continue
        a -= district(zone)["setback"]
        b -= district(zone)["setback"]
        if a < 3.0 or b < 3.0:
            continue
        turn = st.turn_of(u)
        y = lot.top
        if zone == Z_CORE:
            d = math.dist(c, CENTRE)
            hgt = TOWER_HEIGHT[0] + TOWER_HEIGHT[1] * math.exp(-2.0 * (d / CORE) ** 2) * rng.uniform(0.6, 1.1)
            if min(a, b) * 2 >= TOWER_WIDTH[0]:
                side = min(2 * min(a, b), TOWER_WIDTH[1])
                placer.put("tower", c[0], y, c[1], turn, (side, hgt, side), "Colony")
            else:
                place_hab(c, turn, a, b, y, placer, rng)
        elif zone == Z_HABS:
            if rng.random() < MAST_CHANCE:
                placer.put("mast", c[0], y, c[1], turn, None, "Colony", scale=(1.0, rng.uniform(0.6, 1.2), 1.0))
            else:
                place_hab(c, turn, a, b, y, placer, rng)
        elif zone == Z_DOMES:
            size = min(2 * min(a, b), DOME_SIZE[1])
            if size < DOME_SIZE[0] * 0.75:
                place_hab(c, turn, a, b, y, placer, rng)
            elif rng.random() < GREENHOUSE_CHANCE:
                s = float(np.clip(size / 40.0, 0.8, 1.3))
                placer.put("greenhouse", c[0], y, c[1], turn, None, "Colony", scale=(s, s, s))
            else:
                dw, dh, _ = placer.size("dome")
                s = size / dw
                placer.put("dome", c[0], y, c[1], turn, (size, dh * s, size), "Colony")
                domes.append((c, size / 2, y))
        elif zone == Z_INDUSTRY:
            industry.append((abs(st.area(lot.poly)), c, u, a, b, y))
    place_industry(industry, placer, rng)
    return link_domes(domes, placer)


def plant_square(lot, placer, rng):
    """A snowy square: left unpaved, with a few pines."""
    planes = st.offset_out(lot.poly, -6.0)
    c, u, hu, hv = st.oriented_box(lot.poly)
    for _ in range(int(rng.integers(*PARK_PINES))):
        du, dv = rng.uniform(-hu, hu), rng.uniform(-hv, hv)
        x, z = c[0] + u[0] * du - u[1] * dv, c[1] + u[1] * du + u[0] * dv
        if all(nx * x + nz * z <= d for nx, nz, d in planes):
            s = rng.uniform(0.9, 1.5)
            placer.put("pine", x, (lot.top - CURB + lot.bottom + SKIRT) / 2, z, rng.uniform(0, 6.28), None, "Trees", scale=(s, s, s))


def place_hab(c, turn, a, b, y, placer, rng):
    big = min(max(a, b) / 20.0, 1.0)
    hgt = HAB_HEIGHT[0] + (HAB_HEIGHT[1] - HAB_HEIGHT[0]) * big * rng.uniform(0.6, 1.0)
    placer.put("hab", c[0], y, c[1], turn, (2 * a, hgt, 2 * b), "Colony")


def place_industry(lots, placer, rng):
    lots.sort(key=lambda l: -l[0])
    for k, (_, c, u, a, b, y) in enumerate(lots):
        turn = st.turn_of(u)
        if k < PLANTS:
            placer.put("plant", c[0], y, c[1], turn, None, "Colony")
        elif rng.random() < TANK_FARM_CHANCE:
            size = rng.uniform(16.0, 24.0)
            na, nb = max(1, int(2 * a // (size + 6))), max(1, int(2 * b // (size + 6)))
            for i in range(na):
                for j in range(nb):
                    du = -a + (i + 0.5) * 2 * a / na
                    dv = -b + (j + 0.5) * 2 * b / nb
                    placer.put("tank", c[0] + u[0] * du - u[1] * dv, y, c[1] + u[1] * du + u[0] * dv, 0.0,
                               (size, rng.uniform(11.0, 18.0), size), "Colony")
        else:
            placer.put("depot", c[0], y, c[1], turn, (2 * a, rng.uniform(10.0, 17.0), 2 * b), "Colony")


def link_domes(domes, placer):
    """Walkway tubes between neighbouring domes: each dome to its nearest
    unlinked neighbour within TUBE["reach"] of its wall, the tube's ends sunk
    into both domes."""
    links = set()
    count = 0
    for k, (c, r, y) in enumerate(domes):
        best = None
        for m, (c2, r2, y2) in enumerate(domes):
            if m == k or (min(k, m), max(k, m)) in links:
                continue
            gap = math.dist(c, c2) - r - r2
            if gap < TUBE["reach"] and (best is None or gap < best[0]):
                best = (gap, m)
        if best is None:
            continue
        m = best[1]
        links.add((min(k, m), max(k, m)))
        c2, r2, y2 = domes[m]
        dx, dz = c2[0] - c[0], c2[1] - c[1]
        dist = math.hypot(dx, dz)
        ux, uz = dx / dist, dz / dist
        a = (c[0] + ux * r * TUBE["sink"], c[1] + uz * r * TUBE["sink"])
        b = (c2[0] - ux * r2 * TUBE["sink"], c2[1] - uz * r2 * TUBE["sink"])
        length = math.dist(a, b)
        tw, th, td = placer.size("tube")
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        placer.put("tube", mid[0], max(y, y2) + TUBE["height"] - th / 2, mid[1], math.atan2(ux, uz),
                   (tw, th, length), "Colony")
        count += 1
    return count


def place_cabins(ground, placer, rng):
    sp = CABINS["spacing"]
    xs = np.arange(CENTRE[0] - RADII[0] * 1.6, CENTRE[0] + RADII[0] * 1.6, sp)
    zs = np.arange(CENTRE[1] - RADII[1] * 1.6, CENTRE[1] + RADII[1] * 1.6, sp)
    X, Z = np.meshgrid(xs, zs)
    X = (X + rng.uniform(-0.4, 0.4, X.shape) * sp).ravel()
    Z = (Z + rng.uniform(-0.4, 0.4, Z.shape) * sp).ravel()
    e = edge_share(X, Z)
    keep = (e > CABINS["ring"][0]) & (e < CABINS["ring"][1]) & (rng.random(X.shape) < CABINS["chance"])
    keep &= fbm(X, Z, CABINS["hamlets"][0], 2, 65) > CABINS["hamlets"][1]
    X, Z = X[keep], Z[keep]
    ok = ground.buildable(X, Z, min_height=2.5, max_slope=0.2, water_clearance=40.0)
    count = 0
    for x, z in zip(X[ok], Z[ok]):
        s = rng.uniform(*CABINS["scale"])
        y = float(ground.surface([x], [z])[0]) - 0.3
        placer.put("cabin", float(x), y, float(z), rng.uniform(0, 2 * math.pi), None, "Colony", scale=(s, s, s))
        count += 1
    return count


def place_marker(placer):
    """The ClimateCenter marker (an empty in Markers) onto the Climate Control
    Center's foot, so the level's avoidance box follows it (MarkerPlacer)."""
    at = next((m for name, m, _ in placer.items if name.startswith(PIECES["climate"])), None)
    if at is None:
        return
    o = bpy.data.objects.get("ClimateCenter")
    if o is None:
        o = bpy.data.objects.new("ClimateCenter", None)
        o.empty_display_type = "ARROWS"
        o.empty_display_size = 60.0
        bpy.data.collections["Markers"].objects.link(o)
    loc, rot, _ = (cc.TO_BLENDER @ at @ cc.TO_GAME).decompose()
    o.matrix_world = Matrix.LocRotScale(loc, rot, None)


def pave(lots, lines, ground):
    paving = st.Paving()
    for lot in lots:
        if lot.park:
            continue
        paving.polygon(lot.poly, district(lot.zone)["street"] / 2 + PAVE_MARGIN)
    for line in lines:
        paving.line(line, AVENUE_WIDTH / 2 + PAVE_MARGIN, lambda x, z: zone_of([x], [z])[0] >= 0)
    return paving.write(ground, GENERATOR)


PLAN_PIECES = {"Kit_Colony_Dome": (0.95, 0.95, 0.98), "Kit_Colony_Greenhouse": (0.5, 0.9, 0.45),
               "Kit_Colony_Tube": (0.85, 0.85, 0.9), "Kit_Colony_Cabin": (0.9, 0.35, 0.15),
               "Kit_Colony_Depot": (0.5, 0.52, 0.56), "Kit_Colony_Tank": (0.7, 0.72, 0.76),
               "Kit_Colony_Plant": (0.25, 0.27, 0.32), "Kit_Colony_Mast": (0.9, 0.3, 0.1),
               "Kit_Colony_ClimateCenter": (0.3, 0.9, 1.0)}


def main():
    if os.path.normcase(bpy.data.filepath) != os.path.normcase(cc.MAP_FILE):
        bpy.ops.wm.open_mainfile(filepath=cc.MAP_FILE)
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    ground = st.Ground()
    seeds = lattice_seeds(ground, rng)
    blocks = st.voronoi_blocks(seeds, district)
    lines = road_lines()
    roads = st.Roads(lines, AVENUE_WIDTH / 2)
    placer = st.Placer(PIECES, SEED)
    lots = make_lots(blocks, roads, ground, rng)
    print("  %d seeds, %d blocks, %d lots  %.1f s" % (len(seeds), len(blocks), len(lots), time.time() - t0))
    tubes = place_buildings(lots, placer, rng)
    cabins = place_cabins(ground, placer, rng)
    print("  %d tubes, %d cabins; pieces: %s  %.1f s" % (tubes, cabins, placer.counts(), time.time() - t0))
    plan = os.environ.get("COLONY_PLAN")
    if plan:
        st.save_plan(plan, ground, (CENTRE[0] - 2300, CENTRE[1] - 1700, CENTRE[0] + 2300, CENTRE[1] + 1700),
                     polygons=[(l.poly, st.PLAN_COLOURS["lot"]) for l in lots],
                     lines=[(line, AVENUE_WIDTH / 2, st.PLAN_COLOURS["road"]) for line in lines],
                     placer=placer, colours=PLAN_PIECES)
        print("plan saved to %s (dry run: map not changed)" % plan)
        return
    st.remove_generated(GENERATOR)
    cols = {"Colony": st.own_collection("Colony_Buildings", "Colony", GENERATOR),
            "Trees": st.own_collection("Colony_Trees", "Trees", GENERATOR)}
    st.instantiate(placer, cols, GENERATOR)
    place_marker(placer)
    ground_col = st.own_collection("Colony_Ground", "Roads", GENERATOR)
    ground_col.objects.link(st.slab_mesh("Colony_Lots", [l for l in lots if not getattr(l, "plaza", False) and not l.park],
                                         "Pavement", GENERATOR))
    ground_col.objects.link(st.slab_mesh("Colony_Plaza", [l for l in lots if getattr(l, "plaza", False)],
                                         "Concrete", GENERATOR))
    cells = pave(lots, lines, ground)
    print("  placed, %d cells paved  %.1f s" % (cells, time.time() - t0))
    bpy.ops.wm.save_as_mainfile(filepath=cc.MAP_FILE, relative_remap=True)
    print("colony generated in %.1f s" % (time.time() - t0))


if __name__ == "__main__":
    main()
