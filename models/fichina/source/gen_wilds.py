"""Wilds generator for fichina.blend: snow-laden pine forests and rocks on the
land nothing else uses. Corneria's wilds generator
(models/corneria/source/gen_wilds.py) with Fichina's forests: only snow
pines, dense in the south-west taiga and thinning out up the slopes far below
Corneria's treeline, none on the glacier.

    blender --background fichina.blend --python gen_wilds.py

Run it LAST: it keeps off whatever the map already holds (the paving, water,
the glacier, every mesh's vertices and every kit piece's footprint in Props),
so run it again after changing the colony, the outposts or the landmarks.
Re-running it REPLACES what it made before (generator = "wilds").
"""

import importlib.util
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
from fields import fbm, smoothstep  # noqa: E402

# Corneria's generator, loaded under its own name (this file shares its name).
_spec = importlib.util.spec_from_file_location("corneria_wilds", os.path.join(cc.CORNERIA_SOURCE, "gen_wilds.py"))
cw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cw)

GENERATOR = "wilds"
SEED = 53
cw.GENERATOR = GENERATOR

# --- Forests -----------------------------------------------------------------------------
TREE_SPACING = 18.0
TREE_JITTER = 0.4
FOREST_PATCHES = (900.0, 0.1, 0.24)      # noise size, and the noise values over which a patch fades in
LONE_TREES = 0.015
TAIGA_DENSITY = (0.75, 500.0)            # in the taiga (gen_terrain.TAIGA): this density, fading out over this far
VALLEY_FLOORS = (0.55, 160.0, (0.25, 0.4))   # low valley floors (under this height) get clumps of this density
                                         # (where noise is over the first value, full over the second)
TREELINE = (240.0, 400.0)                # trees thin out between these heights
TREE_GROUND = dict(min_height=4.0, max_slope=0.6)
TREE_SCALE = (1.1, 2.1)

PIECES = dict(pine="Kit_Tree_SnowPine", boulder="Kit_Rock_Boulder", outcrop="Kit_Rock_Outcrop")
cw.PIECES = PIECES


def glacier_cells():
    """Cells on the glacier (the terrain's Paint: green)."""
    me = bpy.data.objects["Terrain"].data
    layer = me.color_attributes[cc.PAINT_ATTRIBUTE]
    colors = np.empty(len(layer.data) * 4, dtype=np.float32)
    layer.data.foreach_get("color", colors)
    green = colors.reshape(cc.POINTS, cc.POINTS, 4)[..., 1] > 0.5
    return green[:-1, :-1] | green[1:, :-1] | green[:-1, 1:] | green[1:, 1:]


def plant_forests(ground, taken, placer, rng):
    x, z = cw.jittered_grid(TREE_SPACING, TREE_JITTER, rng)
    h = ground.height(x, z)
    slope = ground.steepness(x, z)
    density = np.maximum(smoothstep(FOREST_PATCHES[1], FOREST_PATCHES[2], fbm(x, z, FOREST_PATCHES[0], 4, 71)) * 0.6,
                         LONE_TREES)
    taiga = smoothstep(TAIGA_DENSITY[1], 0.0, gt.ellipse_dist(x, z, *gt.TAIGA))
    density = np.maximum(density, TAIGA_DENSITY[0] * taiga * (0.6 + 0.4 * smoothstep(-0.2, 0.2, fbm(x, z, 400, 2, 72))))
    density = np.maximum(density, VALLEY_FLOORS[0] * (h < VALLEY_FLOORS[1]) * smoothstep(*VALLEY_FLOORS[2], fbm(x, z, 600, 2, 73)))
    density = density * smoothstep(TREELINE[1], TREELINE[0], h)
    keep = ((rng.random(x.shape) < density) & (h >= TREE_GROUND["min_height"])
            & (slope <= TREE_GROUND["max_slope"]) & cw.is_free(taken, x, z))
    x, z, slope = x[keep], z[keep], slope[keep]
    scales = rng.uniform(*TREE_SCALE, x.shape)
    turns = rng.uniform(0, 2 * math.pi, x.shape)
    ground_y = ground.surface(x, z)
    w = placer.size("pine")[0]
    for k in range(len(x)):
        s = float(scales[k])
        y = float(ground_y[k]) - 0.3 - float(slope[k]) * w * s * 0.1
        placer.put("pine", float(x[k]), y, float(z[k]), float(turns[k]), None, "Trees", scale=(s, s * rng.uniform(0.9, 1.1), s))
    return int(len(x))


def main():
    if os.path.normcase(bpy.data.filepath) != os.path.normcase(cc.MAP_FILE):
        bpy.ops.wm.open_mainfile(filepath=cc.MAP_FILE)
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    ground = st.Ground()
    taken = cw.taken_cells(ground) | glacier_cells()
    print("  %d of %d cells taken  %.1f s" % (int(taken.sum()), taken.size, time.time() - t0))
    placer = st.Placer(PIECES)
    trees = plant_forests(ground, taken, placer, rng)
    boulders, outcrops = cw.place_rocks(ground, taken, placer, rng)
    print("  %d pines, %d boulders, %d outcrops  %.1f s" % (trees, boulders, outcrops, time.time() - t0))
    st.remove_generated(GENERATOR)
    cols = {"Trees": st.own_collection("Wilds_Forests", "Trees", GENERATOR),
            "Rocks": st.own_collection("Wilds_Rocks", "Rocks", GENERATOR)}
    st.instantiate(placer, cols, GENERATOR)
    bpy.ops.wm.save_as_mainfile(filepath=cc.MAP_FILE, relative_remap=True)
    print("wilds generated in %.1f s" % (time.time() - t0))


if __name__ == "__main__":
    main()
