"""Base generator for corneria.blend: the Cornerian military base on its flat
ground in the west, laid out square to its main runway.

    blender --background corneria.blend --python gen_base.py

Run it after gen_terrain.py (which wipes the paving). Re-running it REPLACES
what it made before (objects and collections with generator = "base", and
the paving it painted, remembered in the terrain's "base_paved" attribute);
anything else is left alone. Set BASE_PLAN=<file.png> for a plan of the
result instead (a dry run: the map isn't changed).

Everything is placed in the base's own frame (base_point(a, b)): a along the
main runway (east, turned BASE_ANGLE), b across it (south). In it:
    airfield    the main runway along a, a second one crossing it, a
                parallel taxiway with links to both, the concrete apron north
                of the taxiway; all laid on the terrain (drape()), with
                markings (centre dashes, edge lines, threshold bars, the
                taxiway's yellow line).
    hangars     in a row along the apron's north edge, doors to the apron;
                the control tower at the apron's east end.
    compound    north of the hangars: a grid of paved blocks (slabs) holding
                the HQ beside an open parade ground, barracks in rows and
                motor-pool sheds; the fuel depot east of it, radar dishes
                west of it.
    the rest    bunkers by the runway ends; the access road from the city's
                western highway, along its valley, to the compound.
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

GENERATOR = "base"   # tag on what this script owns
SEED = 31

# --- The frame ---------------------------------------------------------------------------
BASE_ORIGIN = (-5000.0, -650.0)          # on gen_terrain's flat ground (BASE there, 34 m)
BASE_ANGLE = -0.06                       # the main runway's turn from due east (radians)

# --- The airfield (base frame: a along, b across, metres) ------------------------------
# Runways: centre (a, b), length, width, turn from the main runway (radians).
RUNWAYS = [((-150.0, 250.0), 2400.0, 60.0, 0.0),
           ((-650.0, 380.0), 1600.0, 45.0, 0.56)]          # crosses west of the apron
TAXIWAY = dict(b=135.0, a=(-1300.0, 1000.0), width=25.0)    # parallel to the main runway
TAXI_LINKS = [-1300.0, -450.0, 350.0, 1000.0]                  # a: links from the taxiway to the main runway
APRON = dict(a=(-700.0, 700.0), b=(-200.0, 122.0))            # up to the taxiway's edge
MARKINGS = dict(dash=(30.0, 1.5, 60.0), edge=1.0, threshold=(30.0, 3.0, 8), taxi_line=0.8)
GROUND_LIFT = 0.25                       # runways, taxiway, apron, roads above the terrain
MARK_LIFT = 0.35                         # markings above them

# --- Buildings ---------------------------------------------------------------------------
HANGARS = dict(b=-225.0, a=(-540.0, 540.0), count=10)        # centre line, first and last centre
CONTROL_TOWER = (790.0, -150.0)
# The compound: a grid of blocks, columns of `block` a by rows of b, streets between.
COMPOUND = dict(a=(-820.0, 820.0), b=(-660.0, -290.0), block=(150.0, 120.0), street=14.0)
CURB = 0.25
FUEL_DEPOT = dict(a=(900.0, 1180.0), b=(-560.0, -300.0), tank=(22.0, 14.0))
RADARS = [(-1100.0, -450.0), (-1250.0, -250.0), (-1020.0, -650.0)]
BUNKERS = [(-1420.0, 170.0), (-1420.0, 330.0), (1120.0, 170.0), (1120.0, 330.0), (-1060.0, -160.0), (130.0, 860.0)]
# The access road: from the city's western arterial's end, along the highway
# valley gen_terrain cut, round the fuel depot's east side to the compound (game x, z; the last
# point in the base frame).
ACCESS_ROAD = [(-2600.0, -320.0), (-2950.0, -480.0), (-3500.0, -470.0), (-3750.0, -900.0), (-3800.0, -1400.0)]
ACCESS_END = (835.0, -675.0)                # the compound's north-east corner, north of the fuel depot
ROAD_WIDTH = 12.0
PAVE_MARGIN = 6.0

PIECES = dict(hangar="Kit_Base_Hangar", tower="Kit_Base_ControlTower", hq="Kit_Base_HQ",
              barracks="Kit_Base_Barracks", shed="Kit_Base_Shed", radar="Kit_Base_Radar",
              bunker="Kit_Base_Bunker", tank="Kit_City_Tank")


# --- The frame ------------------------------------------------------------------------
def axes(turn=0.0):
    """The base frame's unit a and b directions in game (x, z), turned by `turn`."""
    t = BASE_ANGLE + turn
    return (math.cos(t), math.sin(t)), (-math.sin(t), math.cos(t))


def base_point(a, b):
    (ux, uz), (vx, vz) = axes()
    return (BASE_ORIGIN[0] + a * ux + b * vx, BASE_ORIGIN[1] + a * uz + b * vz)


def rect(centre, length, width, turn=0.0):
    """A rectangle in game (x, z): centre in the base frame, length along a
    (turned), width across."""
    cx, cz = base_point(*centre)
    (ux, uz), (vx, vz) = axes(turn)
    l, w = length / 2, width / 2
    return [(cx + sl * l * ux + sw * w * vx, cz + sl * l * uz + sw * w * vz)
            for sl, sw in ((-1, -1), (1, -1), (1, 1), (-1, 1))]


def frame_rect(a0, a1, b0, b1):
    """A rectangle given by its extents in the base frame."""
    return rect(((a0 + a1) / 2, (b0 + b1) / 2), a1 - a0, b1 - b0)


# --- The airfield -----------------------------------------------------------------------
def runway_marks(centre, length, width, turn):
    """A runway's markings: centre dashes, edge lines, threshold bars at both ends."""
    marks = []
    (ux, uz), _ = axes(turn)
    dash_len, dash_w, dash_step = MARKINGS["dash"]
    bar_len, bar_w, bars = MARKINGS["threshold"]
    ca, cb = centre

    def along(t, off=0.0):
        # A point t metres along the runway from its centre, off metres across, in the base frame.
        c, s = math.cos(turn), math.sin(turn)
        return (ca + t * c - off * s, cb + t * s + off * c)

    for t in np.arange(-length / 2 + 100.0, length / 2 - 100.0, dash_step):
        marks.append(rect(along(t + dash_len / 2), dash_len, dash_w, turn))
    for side in (-1.0, 1.0):
        marks.append(rect(along(0.0, side * (width / 2 - 2.0)), length - 4.0, MARKINGS["edge"], turn))
    for end in (-1.0, 1.0):
        t = end * (length / 2 - 10.0 - bar_len / 2)
        for k in range(bars):
            off = (k - (bars - 1) / 2) * (width - 12.0) / (bars - 1)
            marks.append(rect(along(t, off), bar_len, bar_w, turn))
    return marks


def airfield():
    """(dark surfaces, concrete, white markings, yellow markings) as convex
    polygons in game (x, z)."""
    dark, concrete, white, yellow = [], [], [], []
    for centre, length, width, turn in RUNWAYS:
        dark.append(rect(centre, length, width, turn))
        white += runway_marks(centre, length, width, turn)
    t = TAXIWAY
    a0, a1 = t["a"]
    dark.append(rect(((a0 + a1) / 2, t["b"]), a1 - a0 + t["width"], t["width"]))
    yellow.append(rect(((a0 + a1) / 2, t["b"]), a1 - a0, MARKINGS["taxi_line"]))
    main_b = RUNWAYS[0][0][1]
    for a in TAXI_LINKS:
        b0, b1 = t["b"], main_b
        dark.append(rect((a, (b0 + b1) / 2), t["width"], b1 - b0, 0.0))
        yellow.append(rect((a, (b0 + b1) / 2), MARKINGS["taxi_line"], b1 - b0, 0.0))
    concrete.append(frame_rect(APRON["a"][0], APRON["a"][1], APRON["b"][0], APRON["b"][1]))
    return dark, concrete, white, yellow


# --- Buildings ----------------------------------------------------------------------------
def put(placer, key, a, b, ground, size=None, turn=0.0, group="Base"):
    """A piece at (a, b) in the base frame, square to it (plus `turn`),
    standing on the lowest ground under its footprint."""
    x, z = base_point(a, b)
    w, h, d = size or placer.size(key)
    (ux, uz), _ = axes(turn)
    corners = st.rect_corners((x, z), (ux, uz), w / 2, d / 2)
    y = float(ground.surface(np.array([c[0] for c in corners] + [x]), np.array([c[1] for c in corners] + [z])).min())
    placer.put(key, x, y - 0.2, z, st.turn_of((ux, uz)), size, group)


def compound_lots(ground, rng):
    """The compound's blocks as lots: [(Lot, kind)], kind "hq", "parade",
    "barracks" or "sheds"."""
    c = COMPOUND
    bw, bd = c["block"]
    cols = int((c["a"][1] - c["a"][0] + c["street"]) // (bw + c["street"]))
    rows = int((c["b"][1] - c["b"][0] + c["street"]) // (bd + c["street"]))
    lots = []
    middle = cols // 2
    for i in range(cols):
        for j in range(rows):
            a0 = c["a"][0] + i * (bw + c["street"])
            b0 = c["b"][0] + j * (bd + c["street"])
            poly = frame_rect(a0, a0 + bw, b0, b0 + bd)
            if j == rows - 1 and i == middle:
                kind = "hq"
            elif j == rows - 1 and i == middle - 1:
                kind = "parade"
            else:
                kind = "barracks" if rng.random() < 0.65 else "sheds"
            lot = st.Lot(poly, 0, park=False)
            pts = st.lot_samples(poly)
            h = ground.height(np.array([p[0] for p in pts]), np.array([p[1] for p in pts]))
            lot.top, lot.bottom = float(h.max()) + CURB, float(h.min()) - 0.6
            lots.append((lot, kind, (a0, b0)))
    return lots


def place_buildings(lots, ground, placer, rng):
    hw, _, hd = placer.size("hangar")
    a0, a1 = HANGARS["a"]
    for k in range(HANGARS["count"]):
        a = a0 + (a1 - a0) * k / (HANGARS["count"] - 1)
        put(placer, "hangar", a, HANGARS["b"], ground)
    put(placer, "tower", *CONTROL_TOWER, ground)
    bw, bd = COMPOUND["block"]
    for lot, kind, (la, lb) in lots:
        if kind == "hq":
            put(placer, "hq", la + bw / 2, lb + bd / 2, ground)
        elif kind == "barracks":
            w, _, d = placer.size("barracks")
            n = int((bw + 8.0) // (w + 8.0))
            for i in range(n):
                for b in (lb + 20.0, lb + bd - 20.0):
                    put(placer, "barracks", la + (i + 0.5) * bw / n, b, ground)
        elif kind == "sheds":
            w, _, d = placer.size("shed")
            n, m = int(bw // (w + 12.0)), int(bd // (d + 16.0))
            for i in range(n):
                for j in range(m):
                    put(placer, "shed", la + (i + 0.5) * bw / n, lb + (j + 0.5) * bd / m, ground)
    f = FUEL_DEPOT
    size, gap = f["tank"]
    na = int((f["a"][1] - f["a"][0]) // (size + gap))
    nb = int((f["b"][1] - f["b"][0]) // (size + gap))
    for i in range(na):
        for j in range(nb):
            a = f["a"][0] + (i + 0.5) * (f["a"][1] - f["a"][0]) / na
            b = f["b"][0] + (j + 0.5) * (f["b"][1] - f["b"][0]) / nb
            put(placer, "tank", a, b, ground, (size, rng.uniform(12.0, 16.0), size))
    for a, b in RADARS:
        put(placer, "radar", a, b, ground)
    for a, b in BUNKERS:
        put(placer, "bunker", a, b, ground)


def access_road():
    return st.road_line(ACCESS_ROAD + [base_point(*ACCESS_END)])


# --- Into the map -----------------------------------------------------------------------
def main():
    if os.path.normcase(bpy.data.filepath) != os.path.normcase(cc.MAP_FILE):
        bpy.ops.wm.open_mainfile(filepath=cc.MAP_FILE)
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    ground = st.Ground()
    placer = st.Placer(PIECES)
    dark, concrete, white, yellow = airfield()
    lots = compound_lots(ground, rng)
    place_buildings(lots, ground, placer, rng)
    road = access_road()
    flat = [(x, z) for x, z in (base_point(a, b) for a in (-1350, 0, 1050) for b in (-660, 250))]
    print("  ground at the base: %s m" % ", ".join("%.1f" % h for h in ground.height(
        np.array([p[0] for p in flat]), np.array([p[1] for p in flat]))))
    print("  %d runway/taxiway pieces, %d markings, %d compound blocks; pieces: %s  %.1f s" % (
        len(dark), len(white) + len(yellow), len(lots), placer.counts(), time.time() - t0))

    plan = os.environ.get("BASE_PLAN")
    if plan:
        polys = ([(p, (0.3, 0.3, 0.32)) for p in dark] + [(p, (0.72, 0.68, 0.6)) for p in concrete]
                 + [(l.poly, (0.55, 0.55, 0.5) if k == "parade" else st.PLAN_COLOURS["lot"]) for l, k, _ in lots]
                 + [(p, (0.95, 0.95, 0.9)) for p in white] + [(p, (0.95, 0.8, 0.2)) for p in yellow])
        st.save_plan(plan, ground, (-6800.0, -1800.0, -2400.0, 900.0), res=2.0, polygons=polys,
                     lines=[(road, ROAD_WIDTH / 2, st.PLAN_COLOURS["road"])], placer=placer,
                     colours={"Kit_Base_Hangar": (0.3, 0.34, 0.28), "Kit_Base_Radar": (0.6, 0.62, 0.66)})
        print("plan saved to %s (dry run: map not changed)" % plan)
        return

    st.remove_generated(GENERATOR)
    cols = {"Base": st.own_collection("Base_Buildings", "Base", GENERATOR)}
    st.instantiate(placer, cols, GENERATOR)
    ground_col = st.own_collection("Base_Ground", "Roads", GENERATOR)
    ground_col.objects.link(st.draped_object("Base_Runways", dark + st.road_polys([(road, ROAD_WIDTH / 2)]),
                                             ground, "Road", GROUND_LIFT, GENERATOR))
    ground_col.objects.link(st.draped_object("Base_Apron", concrete, ground, "Concrete", GROUND_LIFT, GENERATOR))
    ground_col.objects.link(st.draped_object("Base_Markings", white, ground, "Marking", MARK_LIFT, GENERATOR))
    ground_col.objects.link(st.draped_object("Base_TaxiLines", yellow, ground, "TaxiYellow", MARK_LIFT, GENERATOR))
    ground_col.objects.link(st.slab_mesh("Base_Blocks", [l for l, k, _ in lots], "Pavement", GENERATOR))
    paving = st.Paving()
    c = COMPOUND
    paving.polygon(frame_rect(c["a"][0], c["a"][1], c["b"][0], c["b"][1]), PAVE_MARGIN + c["street"])
    paving.polygon(frame_rect(FUEL_DEPOT["a"][0], FUEL_DEPOT["a"][1], FUEL_DEPOT["b"][0], FUEL_DEPOT["b"][1]), PAVE_MARGIN)
    paving.polygon(frame_rect(APRON["a"][0], APRON["a"][1], HANGARS["b"] - 40.0, APRON["b"][0]), PAVE_MARGIN)
    cells = paving.write(ground, GENERATOR)
    print("  placed, %d cells paved  %.1f s" % (cells, time.time() - t0))
    bpy.ops.wm.save_as_mainfile(filepath=cc.MAP_FILE, relative_remap=True)
    print("base generated in %.1f s" % (time.time() - t0))


if __name__ == "__main__":
    main()
