"""City generator for corneria.blend: lays Corneria City out on the terrain
that's there (streets, blocks, lots, buildings, bridges, parks, paving).

    blender --background corneria.blend --python gen_city.py

Run it after gen_terrain.py (which wipes the paving). Re-running it REPLACES
what it made before: the objects and collections with the custom property
generator = "city" (under Props/City, Props/Roads and Props/Trees), and the
paving it painted (the terrain's "city_paved" attribute remembers which
points). Anything else in the map is left alone, so hand-placed props next to
the city survive; hand edits to its own buildings do not. To keep edits, stop
re-running it, or move what you edited out of its collections first.

Set CITY_PLAN=<file.png> in the environment to also save a plan of the
result (and not save the map: a dry run).

How the city is laid out (game coordinates, x east, z south):
    districts   zone_of(): downtown (tower clusters), the old town, mid-rise,
                suburbs (the outskirts and the north), industry (the port).
    blocks      a Voronoi diagram of seed points: each district puts its seeds
                on its own lattice (spacing, angle, jitter), bent by a slow
                warp, so downtown's blocks are rectangles, the old town's are
                irregular and streets curve; where districts meet the cells
                go ragged. The streets are the gaps between cells (each pair
                of neighbours sets its street's width).
    arterials   ARTERIALS and the ring road cut through the blocks; where
                one crosses water it gets a bridge.
    lots        each block split across its long side until its pieces are
                lot-sized. A lot on water, a steep slope or the riverbank is
                dropped (leaving the riverside green). Each lot is a flat
                slab a curb above the ground.
    buildings   kit pieces fitted to their lots (scaled to the lot's
                rectangle, height by district), parks with trees.
    paving      the terrain's Paint layer, red under the lots and streets:
                the streets are the paved ground between the slabs.
"""

import math
import os
import sys
import time

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import corneria_common as cc  # noqa: E402
import settlement as st  # noqa: E402
from fields import fbm  # noqa: E402

GENERATOR = "city"   # tag on what this script owns
SEED = 11

# --- Layout ---------------------------------------------------------------------
CITY_CENTRE = (0.0, -150.0)
CITY_RADII = (2300.0, 1550.0)            # the city's extent: an ellipse...
CITY_RAGGED = (0.18, 900.0)              # ...with a ragged edge: share of the radius, size
INDUSTRY = (300.0, 2250.0, 2800.0, 3300.0)   # x0, z0, x1, z1: the port (the coast and slopes trim it)
OLD_TOWN = (-1050.0, 550.0, 560.0)       # x, z, radius: on the west bank, where the river meets the bay
# Tower clusters: x, z, radius, tallest tower near the middle, street grid angle (radians).
DOWNTOWN = [(-450.0, -150.0, 480.0, 230.0, 0.30),
            (750.0, 150.0, 380.0, 170.0, -0.25),
            (-100.0, -950.0, 320.0, 140.0, 0.55)]
SPIRE = 0                                # the spire stands at the middle of this cluster
SPIRE_SEARCH = 400.0                     # its plaza is a whole block whose seed is this near the middle...
SPIRE_MARGIN = 2.0                       # ...with this much room round its footprint
SUBURBS = (0.72, -1100.0)                # suburbs past this share of the radius, and north of this z
PARKS = [(-1350.0, -550.0, 260.0), (1550.0, -350.0, 230.0), (300.0, -1450.0, 200.0)]   # x, z, radius
PARK_CHANCE = {"midrise": 0.05, "suburb": 0.04}   # any other block of these becomes a park this often

# Per district: block seed spacing (along, across) and jitter (share of the
# spacing), lattice angle (radians), street width, lot size (frontage, depth),
# building setback from the lot's edge. Downtown's angle is per cluster.
DISTRICTS = {
    "downtown": dict(spacing=(110.0, 85.0), jitter=0.03, angle=0.0, street=20.0, lot=(45.0, 40.0), setback=4.0),
    "midrise": dict(spacing=(95.0, 75.0), jitter=0.1, angle=0.15, street=15.0, lot=(30.0, 28.0), setback=3.0),
    "oldtown": dict(spacing=(62.0, 55.0), jitter=0.45, angle=0.6, street=9.0, lot=(13.0, 18.0), setback=0.5),
    "suburb": dict(spacing=(140.0, 95.0), jitter=0.12, angle=-0.2, street=12.0, lot=(24.0, 30.0), setback=0.0),
    "industry": dict(spacing=(170.0, 130.0), jitter=0.05, angle=0.05, street=18.0, lot=(60.0, 50.0), setback=5.0),
}
LATTICE_WARP = (170.0, 1800.0)           # every lattice is bent by this much (metres) over this size

# Arterials: polylines (rounded off), ARTERIAL_WIDTH wide, and the ring road
# (centre, radii, wobble). They cut the blocks; over water they're bridges.
ARTERIALS = [
    [(-2600, -320), (-1600, -260), (-800, -160), (-100, -130), (500, -40), (1200, 120), (2000, 380), (2800, 650)],
    [(-650, -2300), (-520, -1500), (-430, -800), (-380, -200), (-560, 380), (-900, 950), (-1250, 1500), (-1400, 2300)],
    [(2100, -1300), (1450, -600), (1050, 0), (950, 700), (1050, 1500), (1350, 2200), (1550, 3000)],
    [(-1600, -1000), (-700, -1000), (-100, -950), (550, -900), (1200, -1050), (2000, -1500)],
]
RING_ROAD = ((100.0, -200.0), (1650.0, 1000.0), 120.0)
ARTERIAL_WIDTH = 28.0
HIGHWAY_WIDTH = 14.0                     # an arterial past the city's edge: a road laid on the terrain
ROAD_LIFT = 0.25

# --- Ground -----------------------------------------------------------------------
CURB = 0.25                              # a lot's slab stands this far above its highest ground
SKIRT = 0.6                              # ...and reaches this far below its lowest
BUILDABLE = dict(min_height=2.5, max_slope=0.14, water_clearance=45.0)   # metres, rise per metre, metres
PAVE_MARGIN = 3.0                        # paving reaches this far past a lot, beyond half the street

# --- Buildings ----------------------------------------------------------------------
# Heights (metres) by district: (lowest, highest).
HEIGHTS = {"oldtown": (8.0, 22.0), "midrise": (14.0, 50.0), "suburb": (6.0, 9.0), "industry": (10.0, 18.0)}
DOWNTOWN_BASE = (30.0, 60.0)             # downtown's low buildings; the clusters add up to their peak
TOWER_FROM = 85.0                        # taller than this, a downtown building is a tower
TOWER_WIDTH = (24.0, 46.0)               # a tower's footprint side
HOUSE_SIZE = (14.0, 12.0)                # a house's largest footprint
TANK_FARM_CHANCE = 0.15                  # industrial lots that are tank farms instead
CRANE_REACH = 110.0                      # industrial lots this near the water get cranes
PARK_TREE_SPACING = 18.0
SUBURB_TREE_CHANCE = 0.7
BRIDGE = dict(margin=25.0, above_banks=1.0, pier_spacing=70.0, pier_foot=-12.0)

# Kit pieces (gen_city fits them by their measured size, so real models with
# other proportions still fill their lots).
PIECES = dict(house="Kit_City_House", shop="Kit_City_Shop", apartment="Kit_City_Apartment",
              office="Kit_City_Office", tower="Kit_City_Tower", round_tower="Kit_City_RoundTower",
              spire="Kit_City_Spire", warehouse="Kit_City_Warehouse", tank="Kit_City_Tank",
              crane="Kit_City_Crane", bridge="Kit_City_Bridge", pier="Kit_City_Pier",
              tree="Kit_Tree_Broadleaf")

ZONES = ["industry", "oldtown", "midrise", "suburb"] + ["downtown%d" % k for k in range(len(DOWNTOWN))]
Z_INDUSTRY, Z_OLD, Z_MID, Z_SUB, Z_DOWN = range(5)


def kind(zone):
    """A zone's district (its DISTRICTS entry name)."""
    return "downtown" if zone >= Z_DOWN else ZONES[zone]


def district(zone):
    d = dict(DISTRICTS[kind(zone)])
    if zone >= Z_DOWN:
        d["angle"] = DOWNTOWN[zone - Z_DOWN][4]
    return d


# --- Districts -------------------------------------------------------------------------
def zone_of(x, z):
    """The zone (index into ZONES) of each point; -1 outside the city."""
    x, z = np.atleast_1d(np.asarray(x, float)), np.atleast_1d(np.asarray(z, float))
    out = np.full(x.shape, -1)
    e = (np.hypot((x - CITY_CENTRE[0]) / CITY_RADII[0], (z - CITY_CENTRE[1]) / CITY_RADII[1])
         + CITY_RAGGED[0] * fbm(x, z, CITY_RAGGED[1], 3, 41))
    inside = e < 1.0
    out[inside] = Z_MID
    out[inside & ((e > SUBURBS[0]) | (z < SUBURBS[1] + 150.0 * fbm(x, z, 700, 2, 42)))] = Z_SUB
    wobble = 1.0 + 0.2 * fbm(x, z, 450, 2, 43)
    out[inside & (np.hypot(x - OLD_TOWN[0], z - OLD_TOWN[1]) < OLD_TOWN[2] * wobble)] = Z_OLD
    for k, (cx, cz, r, _, _) in enumerate(DOWNTOWN):
        out[inside & (np.hypot(x - cx, z - cz) < r * wobble)] = Z_DOWN + k
    ragged = 120.0 * fbm(x, z, 600, 2, 44)
    port = ((x > INDUSTRY[0] + ragged) & (x < INDUSTRY[2] + ragged)
            & (z > INDUSTRY[1] + ragged) & (z < INDUSTRY[3]))
    out[port] = Z_INDUSTRY
    return out


def in_park(x, z):
    return any(math.hypot(x - px, z - pz) < r for px, pz, r in PARKS)


# --- Streets and blocks -------------------------------------------------------------
def lattice_seeds(ground, rng):
    """Block seed points: (x, z, zone) for every zone, each on its own lattice."""
    seeds = []
    for zone in range(len(ZONES)):
        d = district(zone)
        sa, sb = d["spacing"]
        c, s = math.cos(d["angle"]), math.sin(d["angle"])
        reach = 4800.0
        us = np.arange(-reach, reach, sa)
        vs = np.arange(-reach, reach, sb)
        U, V = np.meshgrid(us, vs)
        U = U + rng.uniform(-0.5, 0.5, U.shape) * sa * d["jitter"] * 2
        V = V + rng.uniform(-0.5, 0.5, V.shape) * sb * d["jitter"] * 2
        x = 400.0 + U * c - V * s
        z = 700.0 + U * s + V * c
        x = x + LATTICE_WARP[0] * fbm(x, z, LATTICE_WARP[1], 2, 50)
        z = z + LATTICE_WARP[0] * fbm(x, z, LATTICE_WARP[1], 2, 51)
        x, z = x.ravel(), z.ravel()
        keep = zone_of(x, z) == zone
        x, z = x[keep], z[keep]
        keep = ground.height(x, z) >= st.WATER_BELOW
        seeds += [(float(a), float(b), zone) for a, b in zip(x[keep], z[keep])]
    return seeds


def road_lines():
    """The arterials and the ring road as dense polylines."""
    lines = [st.road_line(a) for a in ARTERIALS]
    (cx, cz), (rx, rz), wobble = RING_ROAD
    ring = []
    for k in range(48):
        t = 2 * math.pi * k / 48
        x, z = cx + rx * math.cos(t), cz + rz * math.sin(t)
        w = wobble * float(fbm(np.array([x]), np.array([z]), 700, 2, 52)[0])
        ring.append((x + w * math.cos(t), z + w * math.sin(t)))
    lines.append(st.densify(ring + ring[:1]))
    return lines


def spire_plaza(blocks, roads, spire_half):
    """The spire's plaza: the whole downtown block (as roads cut it) nearest
    its cluster's middle with room for its footprint, or None."""
    at = DOWNTOWN[SPIRE][:2]
    best = None
    for poly, zone, seed in blocks:
        if zone - Z_DOWN != SPIRE or math.dist(seed, at) > SPIRE_SEARCH:
            continue
        for piece in roads.split(poly):
            d = math.dist(st.centroid(piece), at)
            if min(st.inscribed(piece)[2:]) >= spire_half and (best is None or d < best[0]):
                best = (d, piece)
    return best and best[1]


def make_lots(blocks, roads, ground, rng, plaza=None):
    lots = []
    if plaza is not None:
        lots.append(st.Lot(plaza, Z_DOWN + SPIRE, False))
        lots[-1].spire = True
    for poly, zone, (sx, sz) in blocks:
        park = in_park(sx, sz) or rng.random() < PARK_CHANCE.get(kind(zone), 0.0)
        d = district(zone)
        for piece in roads.split(poly):
            if piece == plaza:
                continue
            parts = [piece] if park else []
            if not park:
                st.subdivide(piece, d["lot"][0], d["lot"][1], rng, parts)
            lots += [st.Lot(p, zone, park) for p in parts if abs(st.area(p)) > 40.0]
    # Keep lots whose every sample is buildable and inside the city.
    return st.fit_lots(lots, ground, lambda x, z: zone_of(x, z) >= 0, BUILDABLE, CURB, SKIRT)


# --- Buildings -----------------------------------------------------------------------
def place_buildings(lots, ground, placer, rng):
    # The spire: alone on its plaza (spire_plaza()), at the plaza's middle.
    spire_lot = next((l for l in lots if getattr(l, "spire", False)), None)
    if spire_lot is None:
        print("  warning: no downtown block has room for the spire")
    cents = np.array([st.centroid(l.poly) for l in lots])
    near_water = ground.water_distance(cents[:, 0], cents[:, 1]) < CRANE_REACH
    for lot, waterside in zip(lots, near_water):
        if lot.park:
            plant_park(lot, placer, rng)
            continue
        k = kind(lot.zone)
        c, u, a, b = st.inscribed(lot.poly)
        a -= DISTRICTS[k]["setback"]
        b -= DISTRICTS[k]["setback"]
        if a < 2.5 or b < 2.5:
            continue
        turn = st.turn_of(u)
        y = lot.top
        if lot is spire_lot:
            placer.put("spire", c[0], y, c[1], turn, None, "City")
        elif k == "downtown":
            cx, cz, r, peak, _ = DOWNTOWN[lot.zone - Z_DOWN]
            fall = math.exp(-2.0 * (math.dist(c, (cx, cz)) / r) ** 2)
            hgt = rng.uniform(*DOWNTOWN_BASE) + peak * fall * rng.uniform(0.55, 1.1)
            if hgt > TOWER_FROM and min(a, b) * 2 >= TOWER_WIDTH[0]:
                side = min(2 * min(a, b), TOWER_WIDTH[1])
                piece = "round_tower" if rng.random() < 0.3 else "tower"
                placer.put(piece, c[0], y, c[1], turn, (side, hgt, side), "City")
            else:
                placer.put("office", c[0], y, c[1], turn, (2 * a, min(hgt, TOWER_FROM), 2 * b), "City")
        elif k == "midrise":
            hgt = rng.uniform(*HEIGHTS["midrise"])
            placer.put("apartment" if hgt < 30 else "office", c[0], y, c[1], turn, (2 * a, hgt, 2 * b), "City")
        elif k == "oldtown":
            placer.put("shop", c[0], y, c[1], turn, (2 * a, rng.uniform(*HEIGHTS["oldtown"]), 2 * b), "City")
        elif k == "suburb":
            place_house(c, u, a, b, y, placer, rng)
        elif k == "industry":
            place_industry(c, u, a, b, y, waterside, placer, rng)


def place_house(c, u, a, b, y, placer, rng):
    w, d = min(2 * a, HOUSE_SIZE[0]), min(2 * b, HOUSE_SIZE[1])
    placer.put("house", c[0], y, c[1], st.turn_of(u), (w, rng.uniform(*HEIGHTS["suburb"]), d), "City")
    # A tree in the garden, beside the house along the lot's long side.
    spare = a - w / 2
    if spare > 5.0 and rng.random() < SUBURB_TREE_CHANCE:
        side = rng.choice((-1.0, 1.0))
        along = side * (w / 2 + spare / 2)
        placer.put("tree", c[0] + u[0] * along, y, c[1] + u[1] * along, rng.uniform(0, 2 * math.pi),
                   None, "Trees", scale=tree_scale(rng))


def place_industry(c, u, a, b, y, waterside, placer, rng):
    turn = st.turn_of(u)
    if waterside:
        # Cranes in a row along the lot.
        n = max(1, int(2 * a // 45))
        for k in range(n):
            along = -a + (k + 0.5) * 2 * a / n
            placer.put("crane", c[0] + u[0] * along, y, c[1] + u[1] * along, turn, None, "City")
        return
    if rng.random() < TANK_FARM_CHANCE:
        size = rng.uniform(18.0, 26.0)
        na, nb = max(1, int(2 * a // (size + 6))), max(1, int(2 * b // (size + 6)))
        for i in range(na):
            for j in range(nb):
                du = -a + (i + 0.5) * 2 * a / na
                dv = -b + (j + 0.5) * 2 * b / nb
                x = c[0] + u[0] * du - u[1] * dv
                z = c[1] + u[1] * du + u[0] * dv
                placer.put("tank", x, y, z, 0.0, (size, rng.uniform(12.0, 18.0), size), "City")
        return
    placer.put("warehouse", c[0], y, c[1], turn, (2 * a, rng.uniform(*HEIGHTS["industry"]), 2 * b), "City")


def tree_scale(rng):
    """A tree's scale on its own size: 0.8 to 1.3 (its height a little more or less)."""
    s = rng.uniform(0.8, 1.3)
    return (s, s * rng.uniform(0.9, 1.1), s)


def plant_park(lot, placer, rng):
    c, u, hu, hv = st.oriented_box(lot.poly)
    step = PARK_TREE_SPACING
    planes = st.offset_out(lot.poly, -4.0)
    for i in range(-int(hu // step), int(hu // step) + 1):
        for j in range(-int(hv // step), int(hv // step) + 1):
            if rng.random() < 0.35:
                continue
            du = i * step + rng.uniform(-0.35, 0.35) * step
            dv = j * step + rng.uniform(-0.35, 0.35) * step
            x = c[0] + u[0] * du - u[1] * dv
            z = c[1] + u[1] * du + u[0] * dv
            if all(nx * x + nz * z <= dd for nx, nz, dd in planes):
                placer.put("tree", x, lot.top, z, rng.uniform(0, 2 * math.pi), None, "Trees", scale=tree_scale(rng))


def place_bridges(lines, ground, placer):
    """A bridge wherever a road crosses water: a deck from bank to bank at the
    banks' height, and piers down to the bed."""
    spans = 0
    for line in lines:
        pts = st.densify(line, 5.0)
        xs = np.array([p[0] for p in pts])
        zs = np.array([p[1] for p in pts])
        wet = ground.height(xs, zs) < st.WATER_BELOW
        k = 0
        while k < len(pts):
            if not wet[k]:
                k += 1
                continue
            start = k
            while k < len(pts) and wet[k]:
                k += 1
            if start == 0 or k == len(pts):
                continue   # runs off the line's end: not a crossing
            a, b = np.array(pts[start - 1]), np.array(pts[k])
            along = (b - a) / np.linalg.norm(b - a)
            a = a - along * BRIDGE["margin"]
            b = b + along * BRIDGE["margin"]
            top = max(float(ground.height([a[0]], [a[1]])[0]), float(ground.height([b[0]], [b[1]])[0])) + BRIDGE["above_banks"]
            mid = (a + b) / 2
            length = float(np.linalg.norm(b - a))
            turn = math.atan2(along[0], along[1])    # the deck's length (z) along the road
            t = placer.size("bridge")[1]
            placer.put("bridge", mid[0], top - t, mid[1], turn, (ARTERIAL_WIDTH, t, length), "City")
            n = int(length // BRIDGE["pier_spacing"])
            pd = placer.size("pier")[2]
            for p in range(1, n + 1):
                at = a + along * (length * p / (n + 1))
                placer.put("pier", at[0], BRIDGE["pier_foot"], at[1], turn,
                           (ARTERIAL_WIDTH * 0.6, top - t - BRIDGE["pier_foot"], pd), "City")
            spans += 1
    return spans


def pave(lots, lines, ground):
    """Paves the terrain under the lots and the streets between them, and
    under the arterials (inside the city)."""
    paving = st.Paving()
    for lot in lots:
        paving.polygon(lot.poly, DISTRICTS[kind(lot.zone)]["street"] / 2 + PAVE_MARGIN)
    for line in lines:
        paving.line(line, ARTERIAL_WIDTH / 2 + PAVE_MARGIN, lambda x, z: zone_of([x], [z])[0] >= 0)
    return paving.write(ground, GENERATOR)


def highway_polys(lines, ground):
    """The arterials past the city's edge (not the ring road, not over water),
    as pieces to lay on the terrain: the roads out to the base, the north,
    the bay's west shore and the port."""
    def outside(x, z):
        return zone_of([x], [z])[0] < 0 and ground.height([x], [z])[0] >= st.WATER_BELOW
    return st.road_polys([(line, HIGHWAY_WIDTH / 2) for line in lines[:len(ARTERIALS)]], outside)


PLAN_PIECES = {"Kit_City_House": (0.95, 0.85, 0.6), "Kit_City_Shop": (0.85, 0.55, 0.35),
               "Kit_City_Warehouse": (0.45, 0.45, 0.5), "Kit_City_Tank": (0.7, 0.7, 0.75),
               "Kit_City_Crane": (0.95, 0.8, 0.2), "Kit_City_Bridge": (0.9, 0.3, 0.2),
               "Kit_City_Pier": (0.9, 0.3, 0.2), "Kit_Tree_Broadleaf": (0.15, 0.38, 0.15)}


def main():
    if os.path.normcase(bpy.data.filepath) != os.path.normcase(cc.MAP_FILE):
        bpy.ops.wm.open_mainfile(filepath=cc.MAP_FILE)
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    ground = st.Ground()
    seeds = lattice_seeds(ground, rng)
    blocks = st.voronoi_blocks(seeds, district)
    lines = road_lines()
    roads = st.Roads(lines, ARTERIAL_WIDTH / 2)
    placer = st.Placer(PIECES)
    spire_w, _, spire_d = placer.size("spire")
    plaza = spire_plaza(blocks, roads, max(spire_w, spire_d) / 2 + SPIRE_MARGIN)
    lots = make_lots(blocks, roads, ground, rng, plaza)
    print("  %d seeds, %d blocks, %d lots (%d parks)  %.1f s" % (
        len(seeds), len(blocks), len(lots), sum(l.park for l in lots), time.time() - t0))
    place_buildings(lots, ground, placer, rng)
    spans = place_bridges(lines, ground, placer)
    print("  %d bridges; pieces: %s  %.1f s" % (spans, placer.counts(), time.time() - t0))
    plan = os.environ.get("CITY_PLAN")
    if plan:
        st.save_plan(plan, ground, (-3000.0, -2400.0, 3200.0, 3500.0),
                     polygons=[(l.poly, st.PLAN_COLOURS["park" if l.park else "lot"]) for l in lots],
                     lines=[(line, ARTERIAL_WIDTH / 2, st.PLAN_COLOURS["road"]) for line in lines],
                     placer=placer, colours=PLAN_PIECES)
        print("plan saved to %s (dry run: map not changed)" % plan)
        return

    st.remove_generated(GENERATOR)
    cols = {"City": st.own_collection("City_Buildings", "City", GENERATOR),
            "Trees": st.own_collection("City_Trees", "Trees", GENERATOR)}
    st.instantiate(placer, cols, GENERATOR)
    ground_col = st.own_collection("City_Ground", "Roads", GENERATOR)
    ground_col.objects.link(st.slab_mesh("City_Lots", [l for l in lots if not l.park], "Pavement", GENERATOR))
    ground_col.objects.link(st.slab_mesh("City_Parks", [l for l in lots if l.park], "Park", GENERATOR))
    ground_col.objects.link(st.draped_object("City_Highways", highway_polys(lines, ground), ground, "Road",
                                             ROAD_LIFT, GENERATOR))
    cells = pave(lots, lines, ground)
    print("  placed, %d cells paved  %.1f s" % (cells, time.time() - t0))
    bpy.ops.wm.save_as_mainfile(filepath=cc.MAP_FILE, relative_remap=True)
    print("city generated in %.1f s" % (time.time() - t0))


if __name__ == "__main__":
    main()
