"""Wilds generator for corneria.blend: forests and rocks on the land nothing
else uses.

    blender --background corneria.blend --python gen_wilds.py

Run it LAST: it keeps off whatever the map already holds (the paving, water,
every mesh's vertices and every kit piece's footprint in Props, hand-placed
ones included), so run it again after changing the settlements or the
landmarks. Re-running it REPLACES what it made before (objects and
collections with generator = "wilds"). Set WILDS_PLAN=<file.png> for a plan
instead (a dry run).

    forests     trees on a jittered grid (TREE_SPACING), kept where a
                density field says: noise patches (FOREST_PATCHES), more on
                hillsides (HILLSIDE), thinning out below the snow (TREELINE),
                none on cliffs, beaches or taken ground. Broadleaf low down,
                pines higher up (PINES).
    rocks       boulders scattered on steep ground and in the mountains,
                outcrops on the steepest high ground, sunk into it.
"""

import math
import os
import sys
import time

import bpy
import numpy as np
from mathutils import Matrix

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import corneria_common as cc  # noqa: E402
import settlement as st  # noqa: E402
from fields import fbm, smoothstep  # noqa: E402

GENERATOR = "wilds"
SEED = 53

# --- Forests -----------------------------------------------------------------------------
TREE_SPACING = 20.0                      # the grid trees are picked from, metres
TREE_JITTER = 0.4                        # ...each moved up to this share of it
FOREST_PATCHES = (1100.0, 0.12, 0.24)    # noise size, and the noise values over which a patch fades in
LONE_TREES = 0.03                        # outside the patches, this share of spots still get a tree
HILLSIDE = (0.12, 0.45, 0.35)            # slopes from, to, and how much denser forest gets there
TREELINE = (380.0, 470.0)                # trees thin out between these heights (snow from 480)
TREE_GROUND = dict(min_height=4.0, max_slope=0.8)   # none on beaches or cliffs
PINES = (100.0, 300.0, 0.1, 0.95)        # pines grow from 10 % of trees at the first height to 95 % at the second
TREE_SCALE = (1.3, 2.3)                  # forest trees are big: their crowns close up
TAKEN_MARGIN = 1                         # cells round anything taken stay clear too

# --- Rocks ------------------------------------------------------------------------------
BOULDERS = dict(spacing=60.0, slope=(0.3, 1.2), high=(150.0, 0.25), chance=0.25, size=(4.0, 12.0))
OUTCROPS = dict(spacing=140.0, slope=0.55, height=200.0, chance=0.5, width=(20.0, 45.0), tall=(10.0, 30.0))
ROCK_SINK = 0.3                          # rocks stand this share of their height in the ground

PIECES = dict(broadleaf="Kit_Tree_Broadleaf", pine="Kit_Tree_Pine",
              boulder="Kit_Rock_Boulder", outcrop="Kit_Rock_Outcrop")


# --- What's taken ------------------------------------------------------------------------
def _walk(col, parent, out_meshes, out_instances, depth=0):
    for o in col.objects:
        if o.get("generator") == GENERATOR:
            continue
        m = parent @ o.matrix_world
        if o.instance_type == "COLLECTION" and o.instance_collection is not None:
            c = o.instance_collection
            if c.name.startswith(cc.KIT_PREFIX):
                out_instances.append((c, m))
            elif depth < 8:
                _walk(c, m @ Matrix.Translation(-c.instance_offset), out_meshes, out_instances, depth + 1)
        elif o.type == "MESH":
            out_meshes.append((o, m))
    for child in col.children:
        if child.get("generator") != GENERATOR:
            _walk(child, parent, out_meshes, out_instances, depth + 1)


def taken_cells(ground):
    """Cells (CELLS x CELLS, rows along +z) something already uses: water,
    paving, any mesh's vertex in Props, any kit piece's footprint; grown by
    TAKEN_MARGIN."""
    cells = cc.POINTS - 1
    taken = np.zeros((cells, cells), dtype=bool)

    def mark(x, z, r=0.0):
        """Every cell within r of the points (arrays of game x, z)."""
        x, z = np.asarray(x, float), np.asarray(z, float)
        reach = int(math.ceil(r / cc.CELL))
        i = np.floor((x + cc.HALF) / cc.CELL).astype(int)
        j = np.floor((z + cc.HALF) / cc.CELL).astype(int)
        for di in range(-reach, reach + 1):
            for dj in range(-reach, reach + 1):
                ii, jj = np.clip(i + di, 0, cells - 1), np.clip(j + dj, 0, cells - 1)
                taken[jj, ii] = True

    # Water and paving.
    h = ground.h
    corners = np.minimum.reduce([h[:-1, :-1], h[1:, :-1], h[:-1, 1:], h[1:, 1:]])
    taken |= corners < st.WATER_BELOW
    me = bpy.data.objects["Terrain"].data
    layer = me.color_attributes.get(cc.PAINT_ATTRIBUTE)
    if layer is not None and layer.domain == "POINT":
        colors = np.empty(len(layer.data) * 4, dtype=np.float32)
        layer.data.foreach_get("color", colors)
        colors = colors.reshape(cc.POINTS, cc.POINTS, 4)
        red = colors[..., 0] > 0.5
        blue = colors[..., 2] > 0.5
        any_red = red[:-1, :-1] | red[1:, :-1] | red[:-1, 1:] | red[1:, 1:]
        any_blue = blue[:-1, :-1] | blue[1:, :-1] | blue[:-1, 1:] | blue[1:, 1:]
        taken |= any_red | any_blue
    # Everything in Props.
    meshes, instances = [], []
    _walk(bpy.data.collections["Props"], Matrix.Identity(4), meshes, instances)
    for o, m in meshes:
        co = np.empty(len(o.data.vertices) * 3, dtype=np.float64)
        o.data.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3) @ np.array(m)[:3, :3].T + np.array(m)[:3, 3]
        mark(co[:, 0], -co[:, 1])
        # Faces' middles too, for big faces (lot slabs) whose corners are far apart.
        for p in o.data.polygons:
            if p.area > cc.CELL * cc.CELL:
                c = m @ p.center
                mark([c.x], [-c.y], math.sqrt(p.area) / 2)
    sizes = st.Kit({c.name for c, _ in instances}).size if instances else {}
    by_radius = {}
    for c, m in instances:
        w, _, d = sizes[c.name]
        sx, _, sz = m.to_scale()
        r = math.hypot(w * sx, d * sz) / 2
        by_radius.setdefault(round(r / cc.CELL), []).append((m.translation.x, -m.translation.y))
    for reach, pts in by_radius.items():
        pts = np.array(pts)
        mark(pts[:, 0], pts[:, 1], reach * cc.CELL)
    for _ in range(TAKEN_MARGIN):
        grown = taken.copy()
        grown[1:, :] |= taken[:-1, :]
        grown[:-1, :] |= taken[1:, :]
        grown[:, 1:] |= taken[:, :-1]
        grown[:, :-1] |= taken[:, 1:]
        taken = grown
    return taken


def is_free(taken, x, z):
    cells = cc.POINTS - 1
    i = np.clip(np.floor((x + cc.HALF) / cc.CELL).astype(int), 0, cells - 1)
    j = np.clip(np.floor((z + cc.HALF) / cc.CELL).astype(int), 0, cells - 1)
    return ~taken[j, i]


def jittered_grid(spacing, jitter, rng, margin=40.0):
    k = np.arange(-cc.HALF + margin, cc.HALF - margin, spacing)
    X, Z = np.meshgrid(k, k)
    X = X + rng.uniform(-1, 1, X.shape) * spacing * jitter
    Z = Z + rng.uniform(-1, 1, Z.shape) * spacing * jitter
    return X.ravel(), Z.ravel()


# --- Forests ----------------------------------------------------------------------------
def plant_forests(ground, taken, placer, rng):
    x, z = jittered_grid(TREE_SPACING, TREE_JITTER, rng)
    h = ground.height(x, z)
    slope = ground.steepness(x, z)
    density = np.maximum(smoothstep(FOREST_PATCHES[1], FOREST_PATCHES[2], fbm(x, z, FOREST_PATCHES[0], 4, 71)), LONE_TREES)
    density = density + HILLSIDE[2] * smoothstep(HILLSIDE[0], HILLSIDE[1], slope)
    density = density * smoothstep(TREELINE[1], TREELINE[0], h)
    keep = ((rng.random(x.shape) < density) & (h >= TREE_GROUND["min_height"])
            & (slope <= TREE_GROUND["max_slope"]) & is_free(taken, x, z))
    x, z, h, slope = x[keep], z[keep], h[keep], slope[keep]
    pine_share = np.clip(PINES[2] + (PINES[3] - PINES[2]) * (h - PINES[0]) / (PINES[1] - PINES[0]), PINES[2], PINES[3])
    pines = rng.random(x.shape) < pine_share
    scales = rng.uniform(*TREE_SCALE, x.shape)
    turns = rng.uniform(0, 2 * math.pi, x.shape)
    ground_y = ground.surface(x, z)
    for k in range(len(x)):
        key = "pine" if pines[k] else "broadleaf"
        w = placer.size(key)[0]
        s = float(scales[k])
        # Sunk by the slope across its trunk, so no side floats.
        y = float(ground_y[k]) - 0.3 - float(slope[k]) * w * s * 0.1
        placer.put(key, float(x[k]), y, float(z[k]), float(turns[k]), None, "Trees", scale=(s, s, s))
    return int(len(x)), int(pines.sum())


# --- Rocks -------------------------------------------------------------------------------
def place_rocks(ground, taken, placer, rng):
    b = BOULDERS
    x, z = jittered_grid(b["spacing"], 0.45, rng)
    h, slope = ground.height(x, z), ground.steepness(x, z)
    want = (((slope >= b["slope"][0]) & (slope <= b["slope"][1])) | ((h > b["high"][0]) & (rng.random(x.shape) < b["high"][1])))
    keep = want & (rng.random(x.shape) < b["chance"]) & (h > 2.0) & is_free(taken, x, z)
    boulders = 0
    for bx, bz in zip(x[keep], z[keep]):
        size = rng.uniform(*b["size"])
        _, bh, _ = placer.size("boulder")
        tall = size * rng.uniform(0.5, 0.8)
        y = float(ground.surface([bx], [bz])[0]) - tall * ROCK_SINK
        placer.put("boulder", float(bx), y, float(bz), rng.uniform(0, 2 * math.pi), (size, tall, size * rng.uniform(0.7, 1.0)), "Rocks")
        boulders += 1
    o = OUTCROPS
    x, z = jittered_grid(o["spacing"], 0.45, rng)
    h, slope = ground.height(x, z), ground.steepness(x, z)
    keep = (slope >= o["slope"]) & (h > o["height"]) & (rng.random(x.shape) < o["chance"]) & is_free(taken, x, z)
    outcrops = 0
    for ox, oz in zip(x[keep], z[keep]):
        width, tall = rng.uniform(*o["width"]), rng.uniform(*o["tall"])
        y = float(ground.surface([ox], [oz])[0]) - tall * ROCK_SINK
        placer.put("outcrop", float(ox), y, float(oz), rng.uniform(0, 2 * math.pi), (width, tall, width * rng.uniform(0.6, 1.0)), "Rocks")
        outcrops += 1
    return boulders, outcrops


def main():
    if os.path.normcase(bpy.data.filepath) != os.path.normcase(cc.MAP_FILE):
        bpy.ops.wm.open_mainfile(filepath=cc.MAP_FILE)
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    ground = st.Ground()
    taken = taken_cells(ground)
    print("  %d of %d cells taken  %.1f s" % (int(taken.sum()), taken.size, time.time() - t0))
    placer = st.Placer(PIECES)
    trees, pines = plant_forests(ground, taken, placer, rng)
    boulders, outcrops = place_rocks(ground, taken, placer, rng)
    print("  %d trees (%d pines), %d boulders, %d outcrops  %.1f s" % (trees, pines, boulders, outcrops, time.time() - t0))

    plan = os.environ.get("WILDS_PLAN")
    if plan:
        # The whole map, coarse; taken cells shaded.
        cells = cc.POINTS - 1
        jj, ii = np.nonzero(taken[::4, ::4])
        polys = [([(-cc.HALF + i * 100.0, -cc.HALF + j * 100.0), (-cc.HALF + i * 100.0 + 100.0, -cc.HALF + j * 100.0),
                   (-cc.HALF + i * 100.0 + 100.0, -cc.HALF + j * 100.0 + 100.0), (-cc.HALF + i * 100.0, -cc.HALF + j * 100.0 + 100.0)],
                  (0.75, 0.72, 0.68)) for i, j in zip(ii, jj)]
        st.save_plan(plan, ground, (-cc.HALF, -cc.HALF, cc.HALF, cc.HALF), res=10.0, polygons=polys, placer=placer,
                     colours={"Kit_Tree_Broadleaf": (0.2, 0.45, 0.18), "Kit_Tree_Pine": (0.1, 0.28, 0.14),
                              "Kit_Rock_Boulder": (0.4, 0.37, 0.34), "Kit_Rock_Outcrop": (0.35, 0.32, 0.3)})
        print("plan saved to %s (dry run: map not changed)" % plan)
        return

    st.remove_generated(GENERATOR)
    cols = {"Trees": st.own_collection("Wilds_Forests", "Trees", GENERATOR),
            "Rocks": st.own_collection("Wilds_Rocks", "Rocks", GENERATOR)}
    st.instantiate(placer, cols, GENERATOR)
    bpy.ops.wm.save_as_mainfile(filepath=cc.MAP_FILE, relative_remap=True)
    print("wilds generated in %.1f s" % (time.time() - t0))


if __name__ == "__main__":
    main()
