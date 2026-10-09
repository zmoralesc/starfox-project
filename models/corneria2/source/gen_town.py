"""Town generator for corneria.blend: the east of the map, laid out on the
terrain that's there: the harbour town (streets, houses, sheds, jetties and
boats, the lighthouse), the villages, the country roads between them and
the city, and the farmland (fields, hedgerows, farmsteads).

    blender --background corneria.blend --python gen_town.py

Run it after gen_terrain.py (which wipes the paving). Re-running it REPLACES
what it made before (objects and collections with generator = "town", and
the paving it painted, remembered in the terrain's "town_paved" attribute);
anything else is left alone. Set TOWN_PLAN=<file.png> for a plan of the
result instead (a dry run: the map isn't changed).

How it lays things out (game coordinates, x east, z south):
    town        Voronoi blocks inside a ragged ellipse along the coast, cut by
                main streets (the country roads carried on to the middle, and
                a harbour street down to the sea), small irregular lots filled
                with houses (sheds near the water), the hall on the lot
                nearest the middle, streets paved like the city's. Piers fan
                out from the harbour street's end, from the town's edge across
                the beach on legs and out past the shoreline; boats lie beside
                them. The lighthouse stands on the highest modest rise by the
                water near LIGHTHOUSE, its keeper's house beside it.
    roads       COUNTRY_ROADS from the city's arterials to the villages and
                the town, plus each village's side lanes and each farmstead's
                track: ribbons laid on the terrain's own triangles (the
                paving's 25 m cells would make a 9 m road a jagged band).
    villages    houses in a row along the roads and lanes near each village's
                middle, facing the road, standing on the bare ground (sunk to
                their lowest corner), a hall by the middle, garden trees.
    farmland    a patchwork of fields: Voronoi cells of a lattice whose angle
                wanders, cut by the roads, kept on flat open ground inside
                FARMLAND, each laid on the terrain in a crop colour with a
                grass margin; some field edges get a hedgerow of trees.
                Farmsteads (house, barn, silo) stand among them.
"""

import math
import os
import sys
import time

import bpy
import numpy as np
from mathutils.kdtree import KDTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import corneria_common as cc  # noqa: E402
import settlement as st  # noqa: E402
from fields import fbm  # noqa: E402
from gen_city import CITY_CENTRE, CITY_RADII  # noqa: E402

GENERATOR = "town"   # tag on what this script owns
SEED = 23

# --- The harbour town ---------------------------------------------------------------
# The town: an ellipse along the coast (on and round gen_terrain's flattened
# ground): middle x, z, radius along the coast, radius across it.
TOWN = (5750.0, 1650.0, 600.0, 380.0)
TOWN_ANGLE = -0.7                        # the coast's direction here (radians)
TOWN_RAGGED = (0.25, 260.0)              # its edge's wobble: share of the radius, size
# Blocks: seed spacing, jitter (share of the spacing), angle (radians: along the
# coast), street width, lot (frontage, depth), building setback.
TOWN_BLOCKS = dict(spacing=(64.0, 56.0), jitter=0.35, angle=TOWN_ANGLE, street=10.0, lot=(17.0, 22.0), setback=1.5)
MAIN_STREET = 14.0                       # the country roads carry on to the middle, and a street down to the harbour
TOWN_HEIGHTS = (7.0, 14.0)
HARBOUR_SHEDS = 80.0                     # town lots this near the water hold sheds
SHED_HEIGHTS = (8.0, 12.0)
# Piers: from the town's edge (where its ground starts falling to the beach)
# across the beach on legs and `out` metres past the shoreline, the deck
# `above` the ground at its landward end.
JETTIES = dict(count=5, spacing=90.0, out=(60.0, 90.0), reach=350.0, edge_height=6.0, above=0.6,
               legs=15.0, leg_foot=-6.0)
BOATS = dict(per_jetty=(1, 2), sunk=0.8)  # boats beside each pier's seaward half; how deep they sit
LIGHTHOUSE = (6800.0, 1300.0, 1500.0)    # look for a rise by the sea near here: x, z, search radius
LIGHTHOUSE_SHORE = (20.0, 80.0)          # ...this far from the water
LIGHTHOUSE_GROUND = (60.0, 0.35)         # ...no higher than this (not up a mountain), no steeper

# --- Roads and villages ------------------------------------------------------------------
# Country roads (rounded off; they start on the city's arterials: the first round the south of
# the big hill east of the city, from the avenue to the port).
COUNTRY_ROADS = [
    [(1200, 1850), (2100, 2000), (2900, 1850), (3700, 1500), (4600, 1650), (5300, 1650)],
    [(2100, -1300), (3300, -1300), (4100, -500), (4700, 200), (5300, 900), (5400, 1200)],
    [(4700, 200), (5400, -100), (6100, -300), (6500, -500)],
    [(3700, 1500), (4200, 800), (4700, 200)],
]
ROAD_WIDTH = 9.0
LANE_WIDTH = 6.0                         # village side lanes
TRACK_WIDTH = 4.5                        # farm tracks
ROAD_LIFT = 0.25                         # ribbons lie this far above the terrain (fields lower)
VILLAGES = [(3300.0, -1300.0, 230.0), (4700.0, 200.0, 260.0), (3700.0, 1500.0, 200.0), (6100.0, -300.0, 180.0)]  # x, z, radius
LANES = dict(count=(2, 3), length=(140.0, 260.0))
VILLAGE_HOUSES = dict(step=20.0, chance=0.85, setback=6.0, width=(9.0, 12.0), depth=(10.0, 13.0),
                      height=(6.5, 9.5), max_drop=3.0, tree_chance=0.6)

# --- Farmland --------------------------------------------------------------------------
FARMLAND = (4600.0, -100.0, 2400.0, 2200.0)   # centre x, z, radii x, z
FARMLAND_RAGGED = (0.15, 800.0)
FARM_KEEP_OFF = dict(city=1.1, villages=60.0, town=150.0)   # city: share of its radius; metres past the others
FIELDS = dict(spacing=(190.0, 140.0), jitter=0.25, street=8.0)   # "street": the grass margin between fields
FIELD_ANGLE = (0.6, 2500.0)              # the fields' grid angle wanders this much (radians) over this size
FIELD_COLOURS = [("FieldWheat", 0.3), ("FieldGreen", 0.3), ("FieldBrown", 0.2), ("FieldLight", 0.2)]
FIELD_LIFT = 0.15
FIELD_MIN_AREA = 2500.0
HEDGE = dict(chance=0.25, step=14.0, out=4.0)   # field edges with trees, their spacing, offset into the margin
FARMSTEADS = dict(count=22, apart=350.0, from_villages=450.0, road_reach=(50.0, 260.0), yard=45.0)

BUILDABLE = dict(min_height=2.5, max_slope=0.14, water_clearance=30.0)
FIELD_GROUND = dict(min_height=3.0, max_slope=0.12, water_clearance=40.0)
CURB, SKIRT = 0.25, 0.6
PAVE_MARGIN = 3.0
PARK_TREE_SPACING = 18.0

PIECES = dict(house="Kit_Town_House", hall="Kit_Town_Hall", shed="Kit_Town_Shed",
              lighthouse="Kit_Town_Lighthouse", jetty="Kit_Town_Jetty", boat="Kit_Town_Boat",
              post="Kit_Town_Post", barn="Kit_Farm_Barn", silo="Kit_Farm_Silo", tree="Kit_Tree_Broadleaf")


# --- Areas ---------------------------------------------------------------------------
def town_e(x, z):
    """How far out of the town's ellipse a point is (1 on its ragged edge)."""
    x, z = np.atleast_1d(np.asarray(x, float)), np.atleast_1d(np.asarray(z, float))
    c, s = math.cos(TOWN_ANGLE), math.sin(TOWN_ANGLE)
    along = ((x - TOWN[0]) * c + (z - TOWN[1]) * s) / TOWN[2]
    across = (-(x - TOWN[0]) * s + (z - TOWN[1]) * c) / TOWN[3]
    return np.hypot(along, across) - TOWN_RAGGED[0] * fbm(x, z, TOWN_RAGGED[1], 2, 61)


def in_town(x, z):
    return town_e(x, z) < 1.0


def seaward():
    """The unit direction from the town's middle out to sea (across the coast)."""
    return (-math.sin(TOWN_ANGLE), math.cos(TOWN_ANGLE))


def in_farmland(x, z):
    x, z = np.atleast_1d(np.asarray(x, float)), np.atleast_1d(np.asarray(z, float))
    e = (np.hypot((x - FARMLAND[0]) / FARMLAND[2], (z - FARMLAND[1]) / FARMLAND[3])
         + FARMLAND_RAGGED[0] * fbm(x, z, FARMLAND_RAGGED[1], 2, 62))
    city = np.hypot((x - CITY_CENTRE[0]) / CITY_RADII[0], (z - CITY_CENTRE[1]) / CITY_RADII[1])
    out = (e < 1.0) & (city > FARM_KEEP_OFF["city"])
    out &= town_e(x, z) > 1.0 + FARM_KEEP_OFF["town"] / TOWN[3]
    for vx, vz, r in VILLAGES:
        out &= np.hypot(x - vx, z - vz) > r + FARM_KEEP_OFF["villages"]
    return out


class Network:
    """Every road, lane and track as (line, half width), and a tree of points
    along them for distances."""

    def __init__(self):
        self.lines = []

    def add(self, line, width):
        self.lines.append((line, width / 2))

    def build(self):
        pts = []
        for line, hw in self.lines:
            dense = st.densify(line, 8.0)
            for k, p in enumerate(dense):
                pts.append((p, hw, dense, k))
        self.points = pts
        self.tree = KDTree(len(pts))
        for k, (p, *_) in enumerate(pts):
            self.tree.insert((p[0], p[1], 0.0), k)
        self.tree.balance()

    def clearance(self, x, z):
        """How far (x, z) is from the nearest road's edge (negative on it)."""
        best = math.inf
        for _, k, d in self.tree.find_n((x, z, 0.0), 6):
            best = min(best, d - self.points[k][1])
        return best

    def nearest(self, x, z):
        """The nearest road point, its road's half width, and the road's
        direction there (unit x, z)."""
        _, k, _ = self.tree.find((x, z, 0.0))
        p, hw, dense, i = self.points[k]
        return p, hw, direction_at(dense, i)


def direction_at(line, k):
    a, b = line[max(k - 1, 0)], line[min(k + 1, len(line) - 1)]
    dx, dz = b[0] - a[0], b[1] - a[1]
    n = math.hypot(dx, dz) or 1.0
    return dx / n, dz / n


# --- The town ---------------------------------------------------------------------------
def town_lots(ground, rng, streets):
    """The town's lots: Voronoi blocks with the main streets cut through them."""
    d = TOWN_BLOCKS
    sa, sb = d["spacing"]
    c, s = math.cos(d["angle"]), math.sin(d["angle"])
    reach = TOWN[2] * 1.5
    U, V = np.meshgrid(np.arange(-reach, reach, sa), np.arange(-reach, reach, sb))
    U = U + rng.uniform(-1, 1, U.shape) * sa * d["jitter"]
    V = V + rng.uniform(-1, 1, V.shape) * sb * d["jitter"]
    x = (TOWN[0] + U * c - V * s).ravel()
    z = (TOWN[1] + U * s + V * c).ravel()
    keep = in_town(x, z) & (ground.height(x, z) >= st.WATER_BELOW)
    seeds = [(float(a), float(b), 0) for a, b in zip(x[keep], z[keep])]
    roads = st.Roads(streets, MAIN_STREET / 2)
    lots = []
    for poly, zone, _ in st.voronoi_blocks(seeds, lambda zone: d):
        for piece in roads.split(poly):
            parts = []
            st.subdivide(piece, d["lot"][0], d["lot"][1], rng, parts)
            lots += [st.Lot(p, zone) for p in parts if abs(st.area(p)) > 40.0]
    return st.fit_lots(lots, ground, in_town, BUILDABLE, CURB, SKIRT)


def place_town(lots, ground, placer, rng):
    hall = min(lots, key=lambda l: math.dist(st.centroid(l.poly), TOWN[:2]), default=None)
    cents = np.array([st.centroid(l.poly) for l in lots])
    near_water = ground.water_distance(cents[:, 0], cents[:, 1]) < HARBOUR_SHEDS
    for lot, waterside in zip(lots, near_water):
        c, u, a, b = st.inscribed(lot.poly)
        a -= TOWN_BLOCKS["setback"]
        b -= TOWN_BLOCKS["setback"]
        if a < 2.5 or b < 2.5:
            continue
        turn = st.turn_of(u)
        if lot is hall:
            placer.put("hall", c[0], lot.top, c[1], turn, None, "Town")
        elif waterside:
            placer.put("shed", c[0], lot.top, c[1], turn, (2 * a, rng.uniform(*SHED_HEIGHTS), 2 * b), "Town")
        else:
            placer.put("house", c[0], lot.top, c[1], turn, (2 * a, rng.uniform(*TOWN_HEIGHTS), 2 * b), "Town")


def place_harbour(ground, placer, rng):
    """Piers out to sea along lines from the town's middle, the first straight
    down the harbour street and the rest fanning out either side of it: each
    from the town's edge, across the beach on legs, past the shoreline, with
    boats beside its seaward half. Returns how many piers."""
    sx, sz = seaward()
    base = math.atan2(sz, sx)
    candidates = [0.0] + [sign * k * math.radians(3.0) for k in range(1, 25) for sign in (1, -1)]
    chosen = []
    for offset in candidates:
        if len(chosen) == JETTIES["count"]:
            break
        dx, dz = math.cos(base + offset), math.sin(base + offset)
        r = np.arange(0.0, TOWN[2] + JETTIES["reach"], 2.0)
        h = ground.height(TOWN[0] + dx * r, TOWN[1] + dz * r)
        low = np.nonzero(h < JETTIES["edge_height"])[0]
        wet = np.nonzero(h < 0.0)[0]
        if not len(low) or not len(wet) or wet[0] <= low[0]:
            continue
        start = (TOWN[0] + dx * r[low[0]], TOWN[1] + dz * r[low[0]])
        shore = float(r[wet[0]] - r[low[0]])          # metres from the start to the shoreline
        if all(math.dist(start, c[0]) >= JETTIES["spacing"] for c in chosen):
            chosen.append((start, shore, dx, dz, float(h[low[0]])))
    jw, jt, _ = placer.size("jetty")
    pw, _, pd = placer.size("post")
    bw = placer.size("boat")[0]
    for start, shore, dx, dz, ground_y in chosen:
        length = shore + rng.uniform(*JETTIES["out"])
        top = ground_y + JETTIES["above"]
        turn = math.atan2(dx, dz)             # the deck's length (z) out to sea
        mid = (start[0] + dx * length / 2, start[1] + dz * length / 2)
        placer.put("jetty", mid[0], top - jt, mid[1], turn, (jw, jt, length), "Town")
        # Legs in pairs under the deck, wherever it stands clear of the ground.
        for k in range(int(length // JETTIES["legs"]) + 1):
            along = min(k * JETTIES["legs"] + 2.0, length - 1.0)
            for side in (-1.0, 1.0):
                lx = start[0] + dx * along - dz * side * (jw / 2 - pw)
                lz = start[1] + dz * along + dx * side * (jw / 2 - pw)
                floor = float(ground.height([lx], [lz])[0])
                if floor > top - jt - 0.5:
                    continue
                foot = max(floor - 0.5, JETTIES["leg_foot"])
                placer.put("post", lx, foot, lz, turn, (pw, top - jt - foot, pd), "Town")
        for n in range(rng.integers(BOATS["per_jetty"][0], BOATS["per_jetty"][1] + 1)):
            side = -1.0 if n % 2 else 1.0
            along = rng.uniform(shore + 12.0, length - 8.0)
            off = jw / 2 + bw / 2 + 2.0
            bx = start[0] + dx * along - dz * off * side
            bz = start[1] + dz * along + dx * off * side
            placer.put("boat", bx, -BOATS["sunk"], bz, turn, None, "Town")
    return len(chosen)


def place_lighthouse(ground, placer):
    """The lighthouse on the highest ground near the water (within the limits
    of LIGHTHOUSE_GROUND), and its keeper's house beside it, inland."""
    hx, hz, r = LIGHTHOUSE
    xs, zs = np.meshgrid(np.arange(hx - r, hx + r, 10.0), np.arange(hz - r, hz + r, 10.0))
    xs, zs = xs.ravel(), zs.ravel()
    h = ground.height(xs, zs)
    ok = ((np.hypot(xs - hx, zs - hz) < r) & (h > 2.0) & (h <= LIGHTHOUSE_GROUND[0])
          & (ground.steepness(xs, zs) <= LIGHTHOUSE_GROUND[1]) & (town_e(xs, zs) > 1.2))
    xs, zs, h = xs[ok], zs[ok], h[ok]
    d = ground.water_distance(xs, zs)
    ok = (d >= LIGHTHOUSE_SHORE[0]) & (d <= LIGHTHOUSE_SHORE[1])
    if not ok.any():
        print("  warning: no spot for the lighthouse near", LIGHTHOUSE[:2])
        return None
    k = int(np.argmax(np.where(ok, h, -np.inf)))
    x, z = float(xs[k]), float(zs[k])
    w, _, d = placer.size("lighthouse")
    y = float(min(ground.surface([x + sx * w / 2], [z + sz * d / 2])[0] for sx in (-1, 1) for sz in (-1, 1))) - 0.5
    placer.put("lighthouse", x, y, z, 0.0, None, "Town")
    # The keeper's house: the spot round it furthest from the water where the ground is even enough.
    hw, _, hd = placer.size("house")
    best = None
    for a in np.linspace(0, 2 * math.pi, 12, endpoint=False):
        px, pz = x + 16.0 * math.cos(a), z + 16.0 * math.sin(a)
        corners = st.rect_corners((px, pz), (math.cos(a), math.sin(a)), hd / 2, hw / 2)
        g = ground.surface(np.array([c[0] for c in corners]), np.array([c[1] for c in corners]))
        if g.min() < 2.0 or g.max() - g.min() > 3.0:
            continue
        far = float(ground.water_distance([px], [pz])[0])
        if best is None or far > best[0]:
            best = (far, px, pz, float(g.min()), a)
    if best is not None:
        _, px, pz, gy, a = best
        placer.put("house", px, gy - 0.2, pz, st.turn_of((-math.sin(a), math.cos(a))), None, "Town")
    return (x, y, z)


def town_streets(network):
    """Carries the country roads that end at the town on to its middle, and
    adds the harbour street from the middle out to the sea: [line]. Trims
    those roads at the town's edge (the network's lines are changed)."""
    streets = []
    for k, (line, hw) in enumerate(network.lines):
        if math.dist(line[-1], TOWN[:2]) > 1.0:
            continue
        xs, zs = np.array([p[0] for p in line]), np.array([p[1] for p in line])
        inside = np.nonzero(in_town(xs, zs))[0]
        cut = int(inside[0]) if len(inside) else len(line)
        streets.append(st.densify([line[max(cut - 1, 0)], TOWN[:2]], 20.0))
        network.lines[k] = (line[:max(cut, 2)], hw)
    sx, sz = seaward()
    streets.append(st.densify([TOWN[:2], (TOWN[0] + sx * 1200.0, TOWN[1] + sz * 1200.0)], 20.0))
    return streets


# --- Roads and villages -----------------------------------------------------------------------
def village_lanes(network, ground, rng):
    """Side lanes off the road at each village's middle."""
    for vx, vz, r in VILLAGES:
        (px, pz), _, (ux, uz) = network.nearest(vx, vz)
        for _ in range(rng.integers(LANES["count"][0], LANES["count"][1] + 1)):
            side = rng.choice((-1.0, 1.0))
            ang = math.atan2(uz, ux) + side * math.pi / 2 + rng.uniform(-0.5, 0.5)
            # Start a little along the road, so lanes don't all meet at one point.
            off = rng.uniform(-0.6, 0.6) * r
            sx, sz = px + ux * off, pz + uz * off
            length = rng.uniform(*LANES["length"])
            bend = rng.uniform(-0.4, 0.4)
            pts = [(sx, sz)]
            for t in (0.5, 1.0):
                a = ang + bend * t
                pts.append((pts[-1][0] + math.cos(a) * length / 2, pts[-1][1] + math.sin(a) * length / 2))
            # Stop where the ground turns steep or wet.
            dense_lane = st.densify(pts, 8.0)
            xs = np.array([p[0] for p in dense_lane])
            zs = np.array([p[1] for p in dense_lane])
            bad = (ground.steepness(xs, zs) > 0.2) | (ground.height(xs, zs) < 2.0)
            stop = int(np.argmax(bad)) if bad.any() else len(dense_lane)
            if stop >= 4:
                network.add(dense_lane[:stop], LANE_WIDTH)


def house_fits(x, z, w, d, u, ground, network, placed, hw_extra=1.0):
    """Ground under a house's footprint, if it can stand there: (lowest
    surface height) or None."""
    corners = st.rect_corners((x, z), u, w / 2, d / 2)
    xs = np.array([p[0] for p in corners] + [x])
    zs = np.array([p[1] for p in corners] + [z])
    h = ground.surface(xs, zs)
    if h.min() < 2.5 or h.max() - h.min() > VILLAGE_HOUSES["max_drop"]:
        return None
    if ground.water_distance(xs[-1:], zs[-1:])[0] < 25.0:
        return None
    radius = math.hypot(w, d) / 2
    if network.clearance(x, z) < radius * 0.75 + hw_extra:
        return None
    if any(math.hypot(x - px, z - pz) < radius + pr + 1.0 for px, pz, pr in placed):
        return None
    return float(h.min())


def place_villages(network, ground, placer, rng, placed):
    count = 0
    vh = VILLAGE_HOUSES
    for vx, vz, r in VILLAGES:
        # The hall, beside the road nearest the middle (or a little along it,
        # where a lane or the slope is in the way).
        (px, pz), hw, (ux, uz) = network.nearest(vx, vz)
        hall_w, _, hall_d = placer.size("hall")
        spots = [(along, side) for along in (0.0, 25.0, -25.0, 50.0, -50.0, 75.0, -75.0) for side in (1.0, -1.0)]
        for along, side in spots:
            off = hw + 6.0 + hall_d / 2
            hx, hz = px + ux * along - uz * off * side, pz + uz * along + ux * off * side
            y = house_fits(hx, hz, hall_w, hall_d, (ux, uz), ground, network, placed)
            if y is not None:
                placer.put("hall", hx, y - 0.2, hz, st.turn_of((ux, uz)), None, "Town")
                placed.append((hx, hz, math.hypot(hall_w, hall_d) / 2))
                break
        else:
            print("  warning: no room for the hall in the village at (%.0f, %.0f)" % (vx, vz))
        # Houses along every road and lane within the village.
        for line, hw in network.lines:
            dense = st.densify(line, vh["step"])
            for k, (x, z) in enumerate(dense):
                reach = r * (1.0 + 0.25 * float(fbm(np.array([x]), np.array([z]), 150, 2, 63)[0]))
                if math.hypot(x - vx, z - vz) > reach:
                    continue
                ux, uz = direction_at(dense, k)
                for side in (1.0, -1.0):
                    if rng.random() > vh["chance"]:
                        continue
                    w, d = rng.uniform(*vh["width"]), rng.uniform(*vh["depth"])
                    off = hw + vh["setback"] + d / 2
                    hx, hz = x - uz * off * side, z + ux * off * side
                    y = house_fits(hx, hz, w, d, (ux, uz), ground, network, placed)
                    if y is None:
                        continue
                    placer.put("house", hx, y - 0.2, hz, st.turn_of((ux, uz)), (w, rng.uniform(*vh["height"]), d), "Town")
                    placed.append((hx, hz, math.hypot(w, d) / 2))
                    count += 1
                    # A tree behind it, in the garden.
                    if rng.random() < vh["tree_chance"]:
                        back = off + d / 2 + 7.0
                        tx, tz = x - uz * back * side + ux * rng.uniform(-5, 5), z + ux * back * side + uz * rng.uniform(-5, 5)
                        if network.clearance(tx, tz) > 4.0:
                            placer.put("tree", tx, float(ground.surface([tx], [tz])[0]) - 0.3, tz,
                                       rng.uniform(0, 2 * math.pi), None, "Trees", scale=tree_scale(rng))
    return count


def tree_scale(rng):
    s = rng.uniform(0.8, 1.3)
    return (s, s * rng.uniform(0.9, 1.1), s)


# --- Farmland ---------------------------------------------------------------------------------
def place_farmsteads(network, ground, placer, rng, placed):
    """Farmsteads among the fields: a house, a barn and a silo round a yard,
    with a track to the nearest road. Returns their yards [(x, z)]."""
    yards = []
    fs = FARMSTEADS
    for _ in range(4000):
        if len(yards) == fs["count"]:
            break
        x = FARMLAND[0] + rng.uniform(-1, 1) * FARMLAND[2]
        z = FARMLAND[1] + rng.uniform(-1, 1) * FARMLAND[3]
        if not in_farmland(x, z)[0]:
            continue
        if any(math.hypot(x - yx, z - yz) < fs["apart"] for yx, yz in yards):
            continue
        if any(math.hypot(x - vx, z - vz) < r + fs["from_villages"] for vx, vz, r in VILLAGES):
            continue
        reach = network.clearance(x, z)
        if not fs["road_reach"][0] <= reach <= fs["road_reach"][1]:
            continue
        ring = [(x + 30 * math.cos(a), z + 30 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 8, endpoint=False)]
        xs, zs = np.array([x] + [p[0] for p in ring]), np.array([z] + [p[1] for p in ring])
        if not ground.buildable(xs, zs, **FIELD_GROUND).all():
            continue
        # Face the road: the yard's axis points at it.
        (rx, rz), hw, _ = network.nearest(x, z)
        ux, uz = (rx - x), (rz - z)
        n = math.hypot(ux, uz)
        ux, uz = ux / n, uz / n
        vx_, vz_ = -uz, ux
        turn = st.turn_of((vx_, vz_))
        parts = [("house", 0.0, -18.0, None), ("barn", 0.0, 18.0, None), ("silo", 22.0, 14.0, None)]
        ok = True
        spots = []
        for key, sv, su, size in parts:
            px, pz = x + vx_ * sv + ux * su, z + vz_ * sv + uz * su
            w, _, d = placer.size(key)
            y = house_fits(px, pz, w, d, (vx_, vz_), ground, network, placed)
            if y is None:
                ok = False
                break
            spots.append((key, px, y, pz, w, d))
        if not ok:
            continue
        for key, px, y, pz, w, d in spots:
            placer.put(key, px, y - 0.2, pz, turn, None, "Town")
            placed.append((px, pz, math.hypot(w, d) / 2))
        # The track: from the yard to the road.
        network.add([(x, z), (rx - ux * hw, rz - uz * hw)], TRACK_WIDTH)
        yards.append((x, z))
    return yards


def field_seeds(rng):
    sa, sb = FIELDS["spacing"]
    reach = max(FARMLAND[2], FARMLAND[3]) * 1.3
    U, V = np.meshgrid(np.arange(-reach, reach, sa), np.arange(-reach, reach, sb))
    U = U + rng.uniform(-1, 1, U.shape) * sa * FIELDS["jitter"]
    V = V + rng.uniform(-1, 1, V.shape) * sb * FIELDS["jitter"]
    # The grid turns slowly from place to place: rotate each point by the
    # angle where it lands.
    x0, z0 = FARMLAND[0] + U, FARMLAND[1] + V
    angle = FIELD_ANGLE[0] * fbm(x0, z0, FIELD_ANGLE[1], 2, 64)
    c, s = np.cos(angle), np.sin(angle)
    x = (FARMLAND[0] + U * c - V * s).ravel()
    z = (FARMLAND[1] + U * s + V * c).ravel()
    keep = in_farmland(x, z)
    return [(float(a), float(b), 0) for a, b in zip(x[keep], z[keep])]


def make_fields(network, ground, rng, yards):
    blocks = st.voronoi_blocks(field_seeds(rng), lambda zone: FIELDS)
    roads = st.Roads([line for line, _ in network.lines], ROAD_WIDTH / 2 + FIELDS["street"] / 2)
    pieces = [p for poly, _, _ in blocks for p in roads.split(poly) if abs(st.area(p)) > FIELD_MIN_AREA]
    kept = []
    for poly in pieces:
        pts = st.lot_samples(poly)
        xs, zs = np.array([p[0] for p in pts]), np.array([p[1] for p in pts])
        if not ground.buildable(xs, zs, **FIELD_GROUND).all() or not in_farmland(xs, zs).all():
            continue
        if any(min(math.hypot(px - yx, pz - yz) for px, pz in pts) < FARMSTEADS["yard"] for yx, yz in yards):
            continue
        if min(network.clearance(px, pz) for px, pz in pts) < 1.0:
            continue
        kept.append(poly)
    names = [n for n, _ in FIELD_COLOURS]
    weights = np.array([w for _, w in FIELD_COLOURS])
    colours = rng.choice(len(names), size=len(kept), p=weights / weights.sum())
    return [(poly, names[k]) for poly, k in zip(kept, colours)]


def plant_hedges(fields, network, ground, placer, rng):
    for poly, _ in fields:
        planes = st.offset_out(poly, HEDGE["out"])
        for (p, q), (nx, nz, _) in zip(zip(poly, poly[1:] + poly[:1]), planes):
            if rng.random() > HEDGE["chance"]:
                continue
            length = math.hypot(q[0] - p[0], q[1] - p[1])
            for k in range(int(length // HEDGE["step"])):
                t = (k + 0.5) / max(int(length // HEDGE["step"]), 1)
                x = p[0] + (q[0] - p[0]) * t + nx * HEDGE["out"]
                z = p[1] + (q[1] - p[1]) * t + nz * HEDGE["out"]
                if network.clearance(x, z) < 4.0:
                    continue
                placer.put("tree", x, float(ground.surface([x], [z])[0]) - 0.3, z, rng.uniform(0, 2 * math.pi),
                           None, "Trees", scale=tree_scale(rng))


# --- Into the map ---------------------------------------------------------------------------
def main():
    if os.path.normcase(bpy.data.filepath) != os.path.normcase(cc.MAP_FILE):
        bpy.ops.wm.open_mainfile(filepath=cc.MAP_FILE)
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    ground = st.Ground()
    placer = st.Placer(PIECES)

    # Country roads; those ending near the town are led to its middle, then
    # cut at its edge, where its main streets take over.
    network = Network()
    for road in COUNTRY_ROADS:
        to_town = math.dist(road[-1], TOWN[:2]) < TOWN[2] * 1.5
        network.add(st.road_line(road + [TOWN[:2]] if to_town else road), ROAD_WIDTH)
    streets = town_streets(network)

    lots = town_lots(ground, rng, streets)
    place_town(lots, ground, placer, rng)
    jetties = place_harbour(ground, placer, rng)
    lighthouse = place_lighthouse(ground, placer)
    print("  town: %d lots, %d piers, lighthouse at %s  %.1f s" % (
        len(lots), jetties, "none" if lighthouse is None else "(%.0f, %.0f, %.0f)" % lighthouse, time.time() - t0))

    network.build()
    village_lanes(network, ground, rng)
    network.build()
    placed = []
    houses = place_villages(network, ground, placer, rng, placed)
    yards = place_farmsteads(network, ground, placer, rng, placed)
    network.build()
    fields = make_fields(network, ground, rng, yards)
    plant_hedges(fields, network, ground, placer, rng)
    print("  %d village houses, %d farmsteads, %d fields, %d roads/lanes/tracks; pieces: %s  %.1f s" % (
        houses, len(yards), len(fields), len(network.lines), placer.counts(), time.time() - t0))

    plan = os.environ.get("TOWN_PLAN")
    if plan:
        colours = {"FieldWheat": (0.86, 0.76, 0.42), "FieldGreen": (0.4, 0.6, 0.26),
                   "FieldBrown": (0.58, 0.46, 0.3), "FieldLight": (0.62, 0.74, 0.34)}
        st.save_plan(plan, ground, (1800.0, -2700.0, 7800.0, 3000.0), res=4.0,
                     polygons=[(p, colours[c]) for p, c in fields] + [(l.poly, st.PLAN_COLOURS["lot"]) for l in lots],
                     lines=[(line, hw, st.PLAN_COLOURS["road"]) for line, hw in network.lines]
                     + [(s, MAIN_STREET / 2, (0.45, 0.45, 0.5)) for s in streets],
                     placer=placer, colours={"Kit_Tree_Broadleaf": (0.15, 0.38, 0.15), "Kit_Farm_Barn": (0.75, 0.3, 0.2),
                                             "Kit_Town_House": (0.95, 0.9, 0.8), "Kit_Town_Jetty": (0.5, 0.35, 0.2),
                                             "Kit_Town_Lighthouse": (0.9, 0.15, 0.1)})
        print("plan saved to %s (dry run: map not changed)" % plan)
        return

    st.remove_generated(GENERATOR)
    cols = {"Town": st.own_collection("Town_Buildings", "Town", GENERATOR),
            "Trees": st.own_collection("Town_Trees", "Trees", GENERATOR)}
    st.instantiate(placer, cols, GENERATOR)
    ground_col = st.own_collection("Town_Ground", "Roads", GENERATOR)
    ground_col.objects.link(st.slab_mesh("Town_Lots", lots, "Pavement", GENERATOR))
    ground_col.objects.link(st.draped_object("Town_Roads", st.road_polys(network.lines), ground, "Road", ROAD_LIFT, GENERATOR))
    for name, _ in FIELD_COLOURS:
        polys = [p for p, c in fields if c == name]
        if polys:
            ground_col.objects.link(st.draped_object("Town_" + name, polys, ground, name, FIELD_LIFT, GENERATOR))
    paving = st.Paving()
    for lot in lots:
        paving.polygon(lot.poly, TOWN_BLOCKS["street"] / 2 + PAVE_MARGIN)
    for street in streets:
        paving.line(street, MAIN_STREET / 2 + PAVE_MARGIN, lambda x, z: in_town(x, z)[0])
    cells = paving.write(ground, GENERATOR)
    print("  placed, %d cells paved  %.1f s" % (cells, time.time() - t0))
    bpy.ops.wm.save_as_mainfile(filepath=cc.MAP_FILE, relative_remap=True)
    print("town generated in %.1f s" % (time.time() - t0))


if __name__ == "__main__":
    main()
