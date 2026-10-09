"""Landmarks generator for corneria.blend: the stone arches along the bay,
the sea stacks, the natural arch on the big island.

    blender --background corneria.blend --python gen_landmarks.py

Re-running it REPLACES what it made before (objects and collections with
generator = "landmarks"); anything else is left alone. It reads the terrain
and the Start marker, so run it after gen_terrain.py and after moving Start.
Set LANDMARKS_PLAN=<file.png> for a plan instead (a dry run).

    arches      the approach: the bay's centreline (found in the terrain: the
                middle of its widest stretch of water, row by row) carried on
                out to sea towards the Start marker. An arch stands across it
                at each of ARCH_SPOTS, on the bed, its opening along the path,
                each turned and sized a little differently.
    stacks      clusters of rock pillars in shallow water (STACK_CLUSTERS and
                round each island), kept clear of the approach.
    rock arch   a natural arch on the big island's south shore, its opening
                along the shore.
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
from gen_terrain import ISLANDS  # noqa: E402

GENERATOR = "landmarks"
SEED = 41

# --- The approach's arches -------------------------------------------------------------
BAY_ROWS = (1500.0, 3300.0, 50.0)        # z rows the bay's centreline is found on: first, last, step
BAY_SEARCH = (-1800.0, 600.0)            # ...looking for water between these x
BAY_DEEP = -2.0                          # the bay's water counts where the bed is under this
ARCH_SPOTS = [1700.0, 2250.0, 2800.0, 3350.0, 3900.0]   # z of each arch along the approach
ARCH_SCALE = (0.9, 1.1)                  # each arch's size, at random in this range
ARCH_TURN = 0.15                         # ...and its turn off square to the path (radians, either way)
ARCH_SINK = 2.0                          # its feet go this far into the bed
ARCH_CLEARANCE = 75.0                    # its opening's top stands at least this high above the water
ARCH_OPENING = 0.72                      # the opening's height as a share of the arch's (Kit_Landmark_Arch)

# --- Sea stacks ---------------------------------------------------------------------------
# Clusters: x, z, radius, how many (each stack in water STACK_DEPTH deep).
STACK_CLUSTERS = [(-2100.0, 3500.0, 450.0, 6), (500.0, 3550.0, 350.0, 5), (-3600.0, 3550.0, 500.0, 6),
                  (2900.0, 3450.0, 300.0, 4), (6900.0, 1950.0, 400.0, 5)]
ISLAND_STACKS = 3                        # round each island, besides
STACK_DEPTH = (-30.0, -3.0)              # the bed under a stack lies between these
STACK_SIZE = dict(width=(18.0, 34.0), height=(30.0, 90.0))
STACK_GAP = 60.0                         # stacks stand at least this far apart
APPROACH_CLEAR = 250.0                   # ...and this far from the approach's path

PIECES = dict(arch="Kit_Landmark_Arch", stack="Kit_Rock_Stack", rock_arch="Kit_Rock_Arch")


def approach_path(ground):
    """The bay's centreline, then on out to the Start marker: a polyline of
    game (x, z), north to south."""
    pts = []
    xs = np.arange(BAY_SEARCH[0], BAY_SEARCH[1], 5.0)
    for z in np.arange(*BAY_ROWS):
        wet = ground.height(xs, np.full(xs.shape, z)) < BAY_DEEP
        # The widest run of water in the row.
        best, run_start = None, None
        for k, w in enumerate(np.append(wet, False)):
            if w and run_start is None:
                run_start = k
            elif not w and run_start is not None:
                if best is None or k - run_start > best[1] - best[0]:
                    best = (run_start, k)
                run_start = None
        if best is not None:
            pts.append(((xs[best[0]] + xs[best[1] - 1]) / 2, float(z)))
    # Smooth out the row-to-row jitter (a running mean over 5 rows).
    xs_s = np.convolve([p[0] for p in pts], np.ones(5) / 5, mode="same")
    pts = [(float(x), z) for x, (_, z) in zip(xs_s, pts)][2:-2]
    start = bpy.data.objects.get("Start")
    if start is not None:
        sx, _, sz = cc.game_point(start.matrix_world.translation)
        pts.append((sx, sz))
    return st.densify(pts, 20.0)


def point_on(path, z):
    """The path's point at row z (it runs north to south) and its direction there."""
    for a, b in zip(path, path[1:]):
        if a[1] <= z <= b[1]:
            t = (z - a[1]) / (b[1] - a[1])
            d = (b[0] - a[0], b[1] - a[1])
            n = math.hypot(*d)
            return (a[0] + (b[0] - a[0]) * t, z), (d[0] / n, d[1] / n)
    return None, None


def place_arches(path, ground, placer, rng):
    w, h, d = placer.size("arch")
    count = 0
    for z in ARCH_SPOTS:
        p, f = point_on(path, z)
        if p is None:
            print("  warning: the approach doesn't reach z = %.0f" % z)
            continue
        s = rng.uniform(*ARCH_SCALE)
        turn = math.atan2(f[0], f[1]) + rng.uniform(-ARCH_TURN, ARCH_TURN)   # local z (through the opening) along the path
        # Standing on the lowest ground under its feet.
        ax, az = math.cos(turn), -math.sin(turn)          # its span (local x) in game x, z
        feet = [(p[0] + side * ax * w * s * 0.42, p[1] + side * az * w * s * 0.42) for side in (-1, 0, 1)]
        y = float(ground.height(np.array([q[0] for q in feet]), np.array([q[1] for q in feet])).min()) - ARCH_SINK
        tall = max(h * s, (ARCH_CLEARANCE - y) / ARCH_OPENING)    # deeper water: a taller arch
        placer.put("arch", p[0], y, p[1], turn, (w * s, tall, d * s), "Landmarks")
        count += 1
    return count


def path_distance(path, x, z):
    return min(math.hypot(x - px, z - pz) for px, pz in path)


def place_stacks(path, ground, placer, rng):
    clusters = list(STACK_CLUSTERS) + [(ix, iz, r * 1.4, ISLAND_STACKS) for ix, iz, r, _ in ISLANDS]
    w0, h0, _ = placer.size("stack")
    placed = []
    for cx, cz, r, count in clusters:
        made = 0
        for _ in range(count * 40):
            if made == count:
                break
            a, rr = rng.uniform(0, 2 * math.pi), r * math.sqrt(rng.random())
            x, z = cx + rr * math.cos(a), cz + rr * math.sin(a)
            bed = float(ground.height([x], [z])[0])
            if not STACK_DEPTH[0] <= bed <= STACK_DEPTH[1]:
                continue
            if any(math.hypot(x - px, z - pz) < STACK_GAP for px, pz in placed):
                continue
            if path_distance(path, x, z) < APPROACH_CLEAR:
                continue
            width = rng.uniform(*STACK_SIZE["width"])
            height = rng.uniform(*STACK_SIZE["height"]) - bed       # its height above the water, plus the depth
            placer.put("stack", x, bed - 1.0, z, rng.uniform(0, 2 * math.pi), (width, height, width), "Rocks")
            placed.append((x, z))
            made += 1
    return len(placed)


def place_rock_arch(ground, placer):
    """On the big island's south shore, the opening along the shore."""
    ix, iz, r, _ = max(ISLANDS, key=lambda i: i[2])
    zs = np.arange(iz, iz + r * 2, 5.0)
    h = ground.height(np.full(zs.shape, ix), zs)
    wet = np.nonzero(h < 0.5)[0]
    if not len(wet):
        print("  warning: no shore found south of the big island")
        return 0
    z = float(zs[wet[0]])
    w, _, _ = placer.size("rock_arch")
    feet = ground.height(np.full(3, ix), np.array([z - w * 0.42, z, z + w * 0.42]))   # its feet: north and south
    # Turned a quarter: its span runs north-south, so the opening faces along the shore (east-west).
    placer.put("rock_arch", ix, float(feet.min()) - ARCH_SINK, z, math.pi / 2, None, "Rocks")
    return 1


def main():
    if os.path.normcase(bpy.data.filepath) != os.path.normcase(cc.MAP_FILE):
        bpy.ops.wm.open_mainfile(filepath=cc.MAP_FILE)
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    ground = st.Ground()
    placer = st.Placer(PIECES)
    path = approach_path(ground)
    arches = place_arches(path, ground, placer, rng)
    stacks = place_stacks(path, ground, placer, rng)
    rock_arch = place_rock_arch(ground, placer)
    print("  approach %d points, %d arches, %d stacks, %d rock arch  %.1f s" % (
        len(path), arches, stacks, rock_arch, time.time() - t0))

    plan = os.environ.get("LANDMARKS_PLAN")
    if plan:
        st.save_plan(plan, ground, (-5000.0, 1200.0, 7600.0, 7000.0), res=6.0,
                     lines=[(path, 6.0, (0.9, 0.3, 0.2))], placer=placer,
                     colours={"Kit_Rock_Stack": (0.55, 0.5, 0.46), "Kit_Rock_Arch": (0.45, 0.4, 0.36),
                              "Kit_Landmark_Arch": (0.95, 0.9, 0.7)})
        print("plan saved to %s (dry run: map not changed)" % plan)
        return

    st.remove_generated(GENERATOR)
    cols = {"Landmarks": st.own_collection("Landmarks_Arches", "Landmarks", GENERATOR),
            "Rocks": st.own_collection("Landmarks_Rocks", "Rocks", GENERATOR)}
    st.instantiate(placer, cols, GENERATOR)
    bpy.ops.wm.save_as_mainfile(filepath=cc.MAP_FILE, relative_remap=True)
    print("landmarks generated in %.1f s" % (time.time() - t0))


if __name__ == "__main__":
    main()
