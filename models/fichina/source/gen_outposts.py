"""Outposts generator for fichina.blend: the spaceport, the research station,
the mining outpost, the dish array on the ice shelf, the stations on the
highest peaks, and the roads and pipelines linking them to the colony.

    blender --background fichina.blend --python gen_outposts.py

Run it after gen_terrain.py and gen_colony.py (its roads stop at the colony's
edge). Re-running it REPLACES what it made before (objects and collections
with generator = "outposts", and the paving it painted: "outposts_paved").
Set OUTPOSTS_PLAN=<file.png> for a plan of the whole map instead (a dry run).

    spaceport   on its plain in the south-east (gen_terrain.PORT), laid out
                in the plain's own frame (u along the runway, v across it):
                a runway with markings, the apron (paved), landing pads,
                hangars, the terminal, the control tower, radars, tanks, depots
    research    modules on stilts, a radar and a mast in the taiga (south-west)
    mine        drilling rigs, depots, tanks and modules on the mine's shelf up
                the north-west pass (gen_terrain.MINE)
    dishes      an array of dish antennas on the ice shelf, facing north
    peaks       a radar and a mast on each of the highest summits inside the
                play area
    roads       draped on the terrain (ROADS), with pipelines on supports
                beside some of them (each pipe lies from support to support,
                tilted with the ground)
"""

import math
import os
import sys
import time

import bpy
import numpy as np
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fichina_common as cc  # noqa: E402
import gen_colony  # noqa: E402
import gen_terrain as gt  # noqa: E402
import settlement as st  # noqa: E402

GENERATOR = "outposts"
SEED = 23

# --- The spaceport (in its plain's frame: u along the runway, v across it) ------------------
RUNWAY = (-1000.0, 1000.0, -230.0, 30.0)   # from u, to u, at v, half width
RUNWAY_DASH = (30.0, 1.2, 60.0)          # centreline dashes: length, half width, spacing
THRESHOLD_BARS = (8, 3.0, 40.0)          # at each end: bars, half width, length
APRON = (-800.0, 820.0, -270.0, 520.0)   # paved: u from, to, v from, to
# (piece, u, v, facing: "runway" = towards -v, or degrees from +u, scale)
PORT_LAYOUT = (
    [("pad", u, v, "runway", 1.0) for u in (-650.0, -530.0, -410.0, -290.0) for v in (60.0, 180.0)]
    + [("port_hangar", u, 150.0, "runway", 1.0) for u in (-80.0, 15.0, 110.0, 205.0)]
    + [("terminal", 410.0, 190.0, "runway", 1.0), ("port_tower", 560.0, 40.0, "runway", 1.0),
       ("radar", 700.0, 330.0, "runway", 1.0), ("radar", -760.0, 350.0, "runway", 1.0),
       ("mast", 640.0, 420.0, "runway", 1.1), ("mast", -700.0, 430.0, "runway", 0.9)]
    + [("depot", u, 400.0, "runway", 1.0) for u in (-180.0, -80.0, 20.0)]
    + [("tank", u, v, 0.0, 1.0) for u in (180.0, 215.0, 250.0) for v in (390.0, 430.0)]
)

# --- The other outposts --------------------------------------------------------------
RESEARCH = (-3800.0, 4300.0)             # centre
MINE = gt.MINE[:2]
DISHES = (6400.0, -1700.0, 95.0)         # centre, spacing (a 3 x 2 array)
PEAKS = (4, 600.0, 2600.0, 6300.0)       # how many, lowest summit, least distance apart, furthest from the centre

# --- Roads and pipelines -------------------------------------------------------------------
# Waypoints (rounded off), and whether a pipeline runs beside it.
ROADS = [
    ([(850, 1500), (1800, 2200), (2700, 2650), (3500, 2950)], True),            # colony - spaceport
    ([(-1100, 0), (-1500, -500), (-2150, -2100), (-2650, -3600), (-3250, -4900)], True),   # colony - mine (the pass)
    ([(-1700, 1500), (-1900, 2650), (-3000, 2400), (-4100, 2700), (-3900, 3600), (-3800, 4200)], False),   # colony - research
    ([(4500, 2500), (5100, 1100), (5750, -250), (6300, -1500)], True),          # spaceport - dish array
    ([(-150, 1850), (100, 2700), (300, 3500), (450, 4100)], False),             # colony - the approach valley
]
ROAD_HALF_WIDTH = 5.0
ROAD_LIFT = 0.25
PIPE = dict(offset=14.0, spacing=32.0, support_height=2.2)   # beside the road (right), supports this far apart

PIECES = dict(pad="Kit_Port_Pad", terminal="Kit_Port_Terminal", port_hangar="Kit_Port_Hangar",
              port_tower="Kit_Port_Tower", radar="Kit_Outpost_Radar", module="Kit_Outpost_Module",
              drill="Kit_Outpost_Drill", dish="Kit_Outpost_Dish", mast="Kit_Colony_Mast",
              depot="Kit_Colony_Depot", tank="Kit_Colony_Tank", cabin="Kit_Colony_Cabin",
              pipe="Kit_Pipe", support="Kit_Pipe_Support")


# --- Helpers ---------------------------------------------------------------------------
def port_frame():
    t = math.radians(gt.PORT[4])
    u = (math.cos(t), math.sin(t))
    v = (-math.sin(t), math.cos(t))
    return (gt.PORT[0], gt.PORT[1]), u, v


def port_at(pu, pv):
    (cx, cz), u, v = port_frame()
    return (cx + u[0] * pu + v[0] * pv, cz + u[1] * pu + v[1] * pv)


def facing(dx, dz):
    """The turn that points a piece's front (its local +z) along (dx, dz)."""
    return math.atan2(dx, dz)


def ground_y(ground, x, z, sink=0.2):
    return float(ground.surface([x], [z])[0]) - sink


def put_tilted(placer, key, a, b, group):
    """Kit piece pieces[key] (its length along its z) lying from game point a
    to b (its bottom's middle line), tilted to follow them."""
    v = placer.kit.variants[PIECES[key]][0]
    name = v.parts[0]
    w, h, d = v.size
    a, b = Vector(a), Vector(b)
    along = b - a
    length = along.length
    if length < 0.5:
        return
    zz = along / length
    xx = Vector((0.0, 1.0, 0.0)).cross(zz).normalized()
    yy = zz.cross(xx)
    basis = Matrix((xx, yy, zz)).transposed().to_4x4()
    m = Matrix.Translation((a + b) / 2) @ basis @ Matrix.Diagonal((1.0, 1.0, length / d, 1.0))
    placer.items.append((name, m, group))
    placer.family_of[name] = PIECES[key]


# --- The spaceport ------------------------------------------------------------------------
def build_port(ground, placer, paving, rng):
    (_, _), u, v = port_frame()
    for key, pu, pv, face, s in PORT_LAYOUT:
        x, z = port_at(pu, pv)
        turn = facing(-v[0], -v[1]) if face == "runway" else math.radians(face)
        placer.put(key, x, ground_y(ground, x, z), z, turn, None, "Outposts", scale=(s, s, s))
    u0, u1, v0, v1 = APRON
    paving.polygon([port_at(u0, v0), port_at(u1, v0), port_at(u1, v1), port_at(u0, v1)], 0.0)
    # The runway and its markings, laid on the ground.
    ru0, ru1, rv, hw = RUNWAY
    strip = [[port_at(ru0, rv - hw), port_at(ru1, rv - hw), port_at(ru1, rv + hw), port_at(ru0, rv + hw)]]
    marks = []
    length, dash_hw, spacing = RUNWAY_DASH
    pu = ru0 + 120.0
    while pu + length < ru1 - 120.0:
        marks.append([port_at(pu, rv - dash_hw), port_at(pu + length, rv - dash_hw),
                      port_at(pu + length, rv + dash_hw), port_at(pu, rv + dash_hw)])
        pu += spacing
    bars, bar_hw, bar_len = THRESHOLD_BARS
    for end, sign in ((ru0 + 20.0, 1.0), (ru1 - 20.0, -1.0)):
        for k in range(bars):
            bv = rv - hw + 4.0 + (k + 0.5) * (2 * hw - 8.0) / bars
            e2 = end + sign * bar_len
            marks.append([port_at(min(end, e2), bv - bar_hw), port_at(max(end, e2), bv - bar_hw),
                          port_at(max(end, e2), bv + bar_hw), port_at(min(end, e2), bv + bar_hw)])
    return strip, marks


# --- Outposts -------------------------------------------------------------------------------
def ring_spots(ground, centre, count, radius, rng, max_slope=0.25):
    """Up to `count` spots round `centre` at about `radius`, on gentle ground."""
    spots = []
    for k in range(count * 6):
        if len(spots) >= count:
            break
        t = rng.uniform(0, 2 * math.pi)
        r = radius * rng.uniform(0.5, 1.2)
        x, z = centre[0] + r * math.cos(t), centre[1] + r * math.sin(t)
        if ground.steepness([x], [z])[0] > max_slope or ground.height([x], [z])[0] < 3.0:
            continue
        if all(math.dist((x, z), s) > 34.0 for s in spots):
            spots.append((x, z))
    return spots


def build_research(ground, placer, rng):
    cx, cz = RESEARCH
    for x, z in ring_spots(ground, RESEARCH, 7, 90.0, rng):
        placer.put("module", x, ground_y(ground, x, z), z, facing(cx - x, cz - z), None, "Outposts")
    for key, (dx, dz) in (("radar", (0.0, 0.0)), ("mast", (60.0, -70.0))):
        x, z = cx + dx, cz + dz
        placer.put(key, x, ground_y(ground, x, z, 1.0), z, 0.0, None, "Outposts")
    for x, z in ring_spots(ground, RESEARCH, 5, 200.0, rng):
        s = rng.uniform(0.9, 1.2)
        placer.put("cabin", x, ground_y(ground, x, z, 0.3), z, rng.uniform(0, 6.28), None, "Outposts", scale=(s, s, s))


def build_mine(ground, placer, paving, rng):
    cx, cz = MINE
    for dx, dz in [(-80.0, -40.0), (20.0, -110.0), (110.0, -20.0)]:
        placer.put("drill", cx + dx, ground_y(ground, cx + dx, cz + dz), cz + dz, rng.uniform(0, 6.28), None, "Outposts")
    for dx, dz in [(-120.0, 90.0), (-20.0, 120.0), (80.0, 100.0)]:
        x, z = cx + dx, cz + dz
        placer.put("depot", x, ground_y(ground, x, z), z, facing(-dx, -dz), (44.0, 13.0, 30.0), "Outposts")
    for dx, dz in [(160.0, 60.0), (190.0, 90.0), (160.0, 120.0), (190.0, 150.0)]:
        x, z = cx + dx, cz + dz
        placer.put("tank", x, ground_y(ground, x, z), z, 0.0, (18.0, 14.0, 18.0), "Outposts")
    for x, z in ring_spots(ground, (cx - 40.0, cz + 30.0), 4, 150.0, rng):
        placer.put("module", x, ground_y(ground, x, z), z, facing(cx - x, cz - z), None, "Outposts")
    placer.put("mast", cx - 170.0, ground_y(ground, cx - 170.0, cz - 120.0, 1.0), cz - 120.0, 0.0, None, "Outposts",
               scale=(1.0, 1.3, 1.0))
    paving.polygon([(cx + 200 * math.cos(t), cz + 170 * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 16, endpoint=False)], 0.0)


def build_dishes(ground, placer, rng):
    cx, cz, sp = DISHES
    for i in range(3):
        for j in range(2):
            x, z = cx + (i - 1) * sp, cz + (j - 0.5) * sp
            # Facing north, towards the aurora (the dish tilts towards its front).
            placer.put("dish", x, ground_y(ground, x, z, 0.5), z, facing(0.0, -1.0) + rng.uniform(-0.25, 0.25), None, "Outposts")
    for dx, dz, key in ((0.0, 120.0, "module"), (90.0, 130.0, "module"), (-120.0, 110.0, "mast")):
        x, z = cx + dx, cz + dz
        placer.put(key, x, ground_y(ground, x, z), z, facing(0.0, -1.0), None, "Outposts")


def find_peaks(ground):
    """The highest summits inside the play area, far enough apart."""
    count, lowest, apart, reach = PEAKS
    h = ground.h
    n = cc.POINTS
    coords = -cc.HALF + np.arange(n) * cc.CELL
    X, Z = np.meshgrid(coords, coords)
    cand = (h > lowest) & (np.hypot(X, Z) < reach)
    # Local maxima over a 7 x 7 neighbourhood.
    peak = cand.copy()
    for dj in range(-3, 4):
        for di in range(-3, 4):
            if di or dj:
                peak &= h >= np.roll(np.roll(h, dj, 0), di, 1)
    jj, ii = np.nonzero(peak)
    order = np.argsort(-h[jj, ii])
    chosen = []
    for k in order:
        p = (coords[ii[k]], coords[jj[k]])
        if all(math.dist(p, q) > apart for q in chosen):
            chosen.append(p)
        if len(chosen) >= count:
            break
    return chosen


def build_peaks(ground, placer):
    peaks = find_peaks(ground)
    for x, z in peaks:
        placer.put("radar", x, ground_y(ground, x, z, 2.5), z, 0.0, None, "Outposts")
        placer.put("mast", x + 22.0, ground_y(ground, x + 22.0, z + 8.0, 3.0), z + 8.0, 0.0, None, "Outposts", scale=(1.0, 0.7, 1.0))
    return peaks


# --- Roads and pipelines ----------------------------------------------------------------------
def outside_colony(ground):
    def keep(x, z):
        return gen_colony.zone_of([x], [z])[0] < 0 and ground.height([x], [z])[0] >= st.WATER_BELOW
    return keep


def build_roads(ground, placer):
    keep = outside_colony(ground)
    lines = [(st.road_line(pts), pipe) for pts, pipe in ROADS]
    polys = st.road_polys([(line, ROAD_HALF_WIDTH) for line, _ in lines], keep)
    supports = 0
    for line, pipe in lines:
        if not pipe:
            continue
        pts = st.densify(line, PIPE["spacing"])
        prev = None
        for k, (x, z) in enumerate(pts):
            a = pts[max(k - 1, 0)]
            b = pts[min(k + 1, len(pts) - 1)]
            dx, dz = b[0] - a[0], b[1] - a[1]
            d = math.hypot(dx, dz) or 1.0
            # To the right of the road (seen along it), PIPE["offset"] out.
            px, pz = x - dz / d * PIPE["offset"], z + dx / d * PIPE["offset"]
            if not keep(px, pz):
                prev = None
                continue
            gy = ground_y(ground, px, pz, 0.3)
            sw, sh, sd = placer.size("support")
            placer.put("support", px, gy, pz, facing(dx, dz), (sw, PIPE["support_height"], sd), "Outposts")
            supports += 1
            top = (px, gy + PIPE["support_height"], pz)
            if prev is not None:
                put_tilted(placer, "pipe", prev, top, "Outposts")
            prev = top
    return polys, supports


PLAN_PIECES = {"Kit_Port_Pad": (0.6, 0.6, 0.62), "Kit_Port_Hangar": (0.5, 0.52, 0.56),
               "Kit_Pipe": (0.85, 0.4, 0.2), "Kit_Pipe_Support": (0.3, 0.3, 0.35),
               "Kit_Outpost_Dish": (0.95, 0.95, 0.98), "Kit_Outpost_Drill": (0.95, 0.8, 0.2)}


def main():
    if os.path.normcase(bpy.data.filepath) != os.path.normcase(cc.MAP_FILE):
        bpy.ops.wm.open_mainfile(filepath=cc.MAP_FILE)
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    ground = st.Ground()
    placer = st.Placer(PIECES, SEED)
    paving = st.Paving()
    strip, marks = build_port(ground, placer, paving, rng)
    build_research(ground, placer, rng)
    build_mine(ground, placer, paving, rng)
    build_dishes(ground, placer, rng)
    peaks = build_peaks(ground, placer)
    road_polys, supports = build_roads(ground, placer)
    print("  peaks at %s; %d pipeline supports; pieces: %s  %.1f s" % (
        ", ".join("(%.0f, %.0f)" % p for p in peaks), supports, placer.counts(), time.time() - t0))
    plan = os.environ.get("OUTPOSTS_PLAN")
    if plan:
        st.save_plan(plan, ground, (-cc.HALF, -cc.HALF, cc.HALF, cc.HALF), res=8.0,
                     polygons=[(p, st.PLAN_COLOURS["road"]) for p in road_polys + strip],
                     placer=placer, colours=PLAN_PIECES)
        print("plan saved to %s (dry run: map not changed)" % plan)
        return
    st.remove_generated(GENERATOR)
    cols = {"Outposts": st.own_collection("Outposts_Buildings", "Outposts", GENERATOR)}
    st.instantiate(placer, cols, GENERATOR)
    ground_col = st.own_collection("Outposts_Ground", "Roads", GENERATOR)
    ground_col.objects.link(st.draped_object("Outposts_Roads", road_polys, ground, "Road", ROAD_LIFT, GENERATOR))
    ground_col.objects.link(st.draped_object("Outposts_Runway", strip, ground, "Road", ROAD_LIFT, GENERATOR))
    ground_col.objects.link(st.draped_object("Outposts_Markings", marks, ground, "Marking", ROAD_LIFT + 0.08, GENERATOR))
    cells = paving.write(ground, GENERATOR)
    print("  placed, %d cells paved  %.1f s" % (cells, time.time() - t0))
    bpy.ops.wm.save_as_mainfile(filepath=cc.MAP_FILE, relative_remap=True)
    print("outposts generated in %.1f s" % (time.time() - t0))


if __name__ == "__main__":
    main()
