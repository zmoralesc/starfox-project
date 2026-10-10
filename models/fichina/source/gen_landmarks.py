"""Landmarks generator for fichina.blend: the ice landmarks, placed from the
terrain generator's layout (gen_terrain.py).

    blender --background fichina.blend --python gen_landmarks.py

Run it after gen_terrain.py. Re-running it REPLACES what it made before
(objects and collections with generator = "landmarks").

    falls       the frozen falls (Kit_Ice_Falls) down the ice shelf's cliff
                where the high lake's stream comes over the lip
                (gen_terrain.LIP), its back to the rock, stretched to the drop
    arches      an ice arch out on the big lake, its opening facing north-south
                (the way you fly up from the colony to the glacier), and one
                across the canyon, along it
    spires      clusters of ice pinnacles on the lake and on the glacier
    seracs      blocks of ice scattered over the glacier (its Paint: green),
                densest on its steep icefalls and its tongue
"""

import math
import os
import sys
import time

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fichina_common as cc  # noqa: E402
import gen_terrain as gt  # noqa: E402
import settlement as st  # noqa: E402
from fields import chaikin, line_dist  # noqa: E402

GENERATOR = "landmarks"
SEED = 31

LAKE_ARCH = (2150.0, -2450.0, 0.15)      # x, z, turn (radians): the opening along the game's z, give or take
ARCH_SINK = 3.0
FALLS_SINK = 2.0                         # the falls' foot sunk this far into the ground
FALLS_OUT = 12.0                         # its origin this far out from where the cliff meets the shore
SPIRE_CLUSTERS = [                       # x, z, radius, count, on the lake (True) or the glacier
    (1400.0, -1700.0, 160.0, 7, True), (2900.0, -1500.0, 200.0, 8, True), (2700.0, -2600.0, 130.0, 5, True),
    (1500.0, -5200.0, 220.0, 6, False), (2000.0, -4300.0, 180.0, 5, False)]
SPIRE_SIZE = (20.0, 50.0, 40.0, 150.0)   # width from, to; height from, to
SPIRE_SINK = 3.0
SPIRE_CLEAR = 300.0                      # no spires this near the lake's arch
SERACS = dict(spacing=38.0, base=0.12, steep=(0.12, 0.35, 0.6), tongue=(0.75, 0.5), size=(6.0, 30.0), sink=0.3)
                                         # grid, chance everywhere, more on slopes (from, to, extra),
                                         # more near the foot (from t, extra), width range, sink share

PIECES = dict(falls="Kit_Ice_Falls", arch="Kit_Ice_Arch", spire="Kit_Ice_Spire", serac="Kit_Ice_Serac")


def facing(dx, dz):
    return math.atan2(dx, dz)


def place_falls(ground, placer):
    """The frozen falls: from the lip out towards the shore under it, where
    the ground first falls below the cliff's foot, its back to the rock."""
    lx, lz = gt.LIP
    fx, fz, _ = gt.FALLS_FOOT
    d = math.hypot(fx - lx, fz - lz)
    ux, uz = (fx - lx) / d, (fz - lz) / d
    foot = None
    for s in np.arange(0.0, 400.0, 2.0):
        x, z = lx + ux * s, lz + uz * s
        if ground.height([x], [z])[0] < gt.FALLS_FOOT[2] + 15.0:
            foot = s
            break
    if foot is None:
        print("  warning: no foot found under the lip; falls not placed")
        return
    _, _, depth = placer.size("falls")
    s = foot + FALLS_OUT - depth / 2
    x, z = lx + ux * s, lz + uz * s
    y = float(ground.height([x + ux * depth / 2], [z + uz * depth / 2])[0]) - FALLS_SINK
    w, h, dp = placer.size("falls")
    drop = gt.HIGH_LEVEL + 1.0 - y
    placer.put("falls", x, y, z, facing(ux, uz), (w, drop, dp), "Landmarks")
    return drop


def place_arches(ground, placer):
    x, z, turn = LAKE_ARCH
    if ground.height([x], [z])[0] > -2.0:
        print("  warning: the lake's arch isn't on the lake")
    placer.put("arch", x, -ARCH_SINK, z, turn, None, "Landmarks")
    path = chaikin(gt.CANYON, 2)
    lengths = [math.dist(a, b) for a, b in zip(path, path[1:])]
    target = gt.CANYON_ARCH_T * sum(lengths)
    for (a, b), length in zip(zip(path, path[1:]), lengths):
        if target <= length:
            t = target / length
            cx, cz = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
            floor = float(ground.height([cx], [cz])[0])
            placer.put("arch", cx, floor - ARCH_SINK, cz, facing(b[0] - a[0], b[1] - a[1]), None, "Landmarks")
            return (cx, cz)
        target -= length


def place_spires(ground, placer, rng):
    count = 0
    for cx, cz, r, n, on_lake in SPIRE_CLUSTERS:
        placed = []
        for _ in range(n * 8):
            if len(placed) >= n:
                break
            t, d = rng.uniform(0, 2 * math.pi), r * math.sqrt(rng.random())
            x, z = cx + d * math.cos(t), cz + d * math.sin(t)
            h = float(ground.height([x], [z])[0])
            if on_lake and h > -3.0:
                continue
            if math.dist((x, z), LAKE_ARCH[:2]) < SPIRE_CLEAR or any(math.dist((x, z), p) < 45.0 for p in placed):
                continue
            w = rng.uniform(*SPIRE_SIZE[:2])
            tall = rng.uniform(*SPIRE_SIZE[2:]) * (1.0 - 0.5 * d / r)
            y = (0.0 if on_lake else float(ground.surface([x], [z])[0])) - SPIRE_SINK
            placer.put("spire", x, y, z, rng.uniform(0, 2 * math.pi), (w, tall, w * rng.uniform(0.7, 1.0)), "Landmarks")
            placed.append((x, z))
        count += len(placed)
    return count


def glacier_mask():
    me = bpy.data.objects["Terrain"].data
    layer = me.color_attributes[cc.PAINT_ATTRIBUTE]
    colors = np.empty(len(layer.data) * 4, dtype=np.float32)
    layer.data.foreach_get("color", colors)
    return colors.reshape(cc.POINTS, cc.POINTS, 4)[..., 1] > 0.5


def place_seracs(ground, placer, rng):
    on_ice = glacier_mask()
    s = SERACS
    k = np.arange(-cc.HALF + 40, cc.HALF - 40, s["spacing"])
    X, Z = np.meshgrid(k, k)
    X = (X + rng.uniform(-0.45, 0.45, X.shape) * s["spacing"]).ravel()
    Z = (Z + rng.uniform(-0.45, 0.45, Z.shape) * s["spacing"]).ravel()
    i = np.clip(np.round((X + cc.HALF) / cc.CELL).astype(int), 0, cc.POINTS - 1)
    j = np.clip(np.round((Z + cc.HALF) / cc.CELL).astype(int), 0, cc.POINTS - 1)
    keep = on_ice[j, i]
    X, Z = X[keep], Z[keep]
    slope = ground.steepness(X, Z)
    _, t = line_dist(X, Z, chaikin(gt.GLACIER))
    chance = (s["base"] + s["steep"][2] * np.clip((slope - s["steep"][0]) / (s["steep"][1] - s["steep"][0]), 0, 1)
              + s["tongue"][1] * np.clip((t - s["tongue"][0]) / (1 - s["tongue"][0]), 0, 1))
    keep = rng.random(X.shape) < chance
    count = 0
    for x, z in zip(X[keep], Z[keep]):
        w = rng.uniform(*s["size"])
        tall = w * rng.uniform(0.5, 0.9)
        y = float(ground.surface([x], [z])[0]) - tall * s["sink"]
        placer.put("serac", float(x), y, float(z), rng.uniform(0, 2 * math.pi), (w, tall, w * rng.uniform(0.6, 1.0)), "Rocks")
        count += 1
    return count


def main():
    if os.path.normcase(bpy.data.filepath) != os.path.normcase(cc.MAP_FILE):
        bpy.ops.wm.open_mainfile(filepath=cc.MAP_FILE)
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    ground = st.Ground()
    placer = st.Placer(PIECES, SEED)
    drop = place_falls(ground, placer)
    canyon_arch = place_arches(ground, placer)
    spires = place_spires(ground, placer, rng)
    seracs = place_seracs(ground, placer, rng)
    print("  falls %s m tall, canyon arch at %s, %d spires, %d seracs  %.1f s" % (
        "%.0f" % drop if drop else "-", canyon_arch, spires, seracs, time.time() - t0))
    st.remove_generated(GENERATOR)
    cols = {"Landmarks": st.own_collection("Landmarks_Ice", "Landmarks", GENERATOR),
            "Rocks": st.own_collection("Landmarks_Seracs", "Rocks", GENERATOR)}
    st.instantiate(placer, cols, GENERATOR)
    bpy.ops.wm.save_as_mainfile(filepath=cc.MAP_FILE, relative_remap=True)
    print("landmarks generated in %.1f s" % (time.time() - t0))


if __name__ == "__main__":
    main()
