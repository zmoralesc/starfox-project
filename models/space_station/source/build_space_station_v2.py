"""Builds the Cornerian space station, second design ("the Drum"), in Blender
and exports it.

Run from the command line:
    blender --background --python build_space_station_v2.py -- --export
(add --no-render to skip the preview renders, --no-checks to skip the
geometry checks). Inside Blender (Scripting tab) exec() the file; set
FORCE_EXPORT = True in the exec globals to export.

Like build_space_station.py, everything is in GAME coordinates (Godot: +X
right, +Y up, -Z forward: the bow), in metres, converted to Blender's Z-up
frame by G(). The origin is the station's centre, on its axis, halfway
between the two wheels.

Layout: a spine along Z (bow at -Z) carrying two wheels, 1600 m across, at
z = -250 and z = +250, each joined to its hub drum by three spokes (at 90,
210 and 330 degrees: a Y). Three long tower blocks on the outside of the
rims tie the wheels together at the spoke angles, so the whole reads as an
open drum. The three sectors between the spokes are clear tunnels bow to
stern, and the drum is open sideways between the towers: the fly-through
openings (OPENINGS, verified by ray casts). A hangar block at the bow with a
lit 150 x 84 m bay (BAY_SIZE), docking arms in the harbour between the wheels, three
solar arms and a dish at the stern.

Surface detail is painted flush (coplanar faces in another material: no ink
lines): window rows, Cornerian blue stripes, hazard yellow at docks and the
hangar, panel plates, vents. Raised pieces (spoke frames, radiators, docking
clamps, nav lights) are few and grouped. Curved hulls are smooth-shaded
(SMOOTH_ANGLE), corners hard. Finer detail is printed: tiling textures the
script generates (plating seams and hatches on the hull greys and the blue
stripes, hazard stripes on the yellow trim, cells on the solar panels, lit
and dim windows), packed into the .glb and multiplied over the material
colours (TEXTURES, add_station_uvs()).

Each component is one mesh object, modelled round its own pivot (PIVOTS,
game coordinates: its attachment point), named Station_<Component>.

Writes space_station_v2.blend (here), exports ../space_station_v2.glb (one
node per component) and writes proxies_v2.txt (the `proxies` line for
world/space_station.tscn: AI avoidance spheres, game coordinates). Preview
renders go to preview_v2/.
"""

import math
import os
import random
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
EXPORT = "--export" in ARGS or globals().get("FORCE_EXPORT", False)
RENDER = "--no-render" not in ARGS
CHECKS = "--no-checks" not in ARGS
HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else \
    r"C:\dev\spaceship-project\models\space_station\source"
OUT = os.path.dirname(HERE)
PREVIEW_DIR = os.path.join(HERE, "preview_v2")

# ---------------------------------------------------------------- layout
# Wheels: a chamfered box cross-section (radius RING_IN..RING_OUT, +-RING_HALF
# along Z), one at z = -RING_Z (fore) and one at +RING_Z (aft).
RING_IN = 710.0
RING_OUT = 800.0
RING_HALF = 35.0
RING_CHAMFER = 10.0
RING_Z = 250.0
RING_SEGMENTS = 96                       # 3.75 degrees, 49 m chords
SPOKE_ANGLES = [90.0, 210.0, 330.0]      # degrees round Z, from +X towards +Y
MID_ANGLES = [30.0, 150.0, 270.0]        # the sectors' centres
# Habitat modules and radiator clusters on the rims: on the wheel's AI
# spheres (48 per wheel, 7.5 degrees apart), so those enclose them.
MODULE_ANGLES = [15.0 + 30.0 * k for k in range(12) if min(abs((15.0 + 30.0 * k - a + 180.0) % 360.0 - 180.0) for a in (90.0, 210.0, 330.0)) > 20.0]
MODULE_SIZE = (30.0, 60.0, 56.0)          # radial (6 m of it sunk), tangent, along Z
RADIATOR_ANGLES = [45.0, 165.0, 285.0]
SPOKE_SIZE = (50.0, 40.0)                # across (tangent), deep (along Z)
SPOKE_R0 = 138.0                         # sunk 12 m into the hub drum (radius 150)
SPOKE_R1 = RING_IN + 12.0                # sunk 12 m into the wheel
# Towers: blocks outside the rims at the spoke angles, tying the wheels together.
TOWER_R = (760.0, 846.0)                 # radial extent (sunk 40 m into the wheel)
TOWER_WIDTH = 120.0                      # tangent
TOWER_Z = 276.0                          # half-length along Z
TOWER_BLOCK = (862.0, 136.0, 130.0)      # command block on the outside: outer radius, width, half-length
# The spine, bow to stern, as (z, radius) profile sections with a material.
HUB_R = 150.0
WAIST_R = 100.0
NECK_R = 64.0
SPINE_SECTIONS = [
    ([(-392, NECK_R), (-345, NECK_R)], "Hull"),
    ([(-345, NECK_R), (-315, HUB_R)], "HullLight"),
    ([(-315, HUB_R), (-185, HUB_R)], "Hull"),           # fore hub drum (windows)
    ([(-185, HUB_R), (-165, WAIST_R)], "HullLight"),
    ([(-165, WAIST_R), (165, WAIST_R)], "Hull"),        # the harbour waist
    ([(165, WAIST_R), (185, HUB_R)], "HullLight"),
    ([(185, HUB_R), (315, HUB_R)], "Hull"),             # aft hub drum (windows)
    ([(315, HUB_R), (345, NECK_R)], "HullLight"),
    ([(345, NECK_R), (422, NECK_R)], "Hull"),
]
SPINE_PROFILE = [pt for profile, _ in SPINE_SECTIONS for pt in profile]
SPINE_SEGMENTS = 48
# Docking arms in the harbour, at the sector centres.
DOCK_Z = 0.0
DOCK_R = (90.0, 160.0)                   # arm from the waist to the clamp
DOCK_CLAMP = (40.0, 48.0, 60.0)          # clamp block: radial, tangent, along Z
# The hangar block at the bow.
HANGAR_Z = (-560.0, -380.0)              # bow face, aft face (joins the spine neck)
HANGAR_SIZE = (320.0, 200.0)             # X, Y: wider than the hub drum, the bow "head"
HANGAR_CHAMFER = 18.0
BAY_SIZE = (150.0, 84.0)                 # the lit opening on the bow face
BAY_DEPTH = 60.0
BAY_Y = -10.0                            # bay centre, below the block's middle (bridge above)
APRON = (160.0, 10.0, 70.0)              # deck under the mouth: X, Y, length forward
PIER_SIZE = (26.0, 100.0, 44.0)          # harbour piers either side of the mouth: X, Y, length forward
PIER_GAP = 9.0                           # from the mouth's edge to a pier
# Stern: the dish and three solar arms.
DISH_Z = 422.0
SOLAR_Z = 360.0
SOLAR_R = (60.0, 496.0)                  # beam from the neck to just past the last panel
SOLAR_PANEL = (84.0, 70.0)               # radial, along Z, per panel
SOLAR_PANELS = 4
# Faces meeting at less than this stay smoothly shaded (curved hulls); sharper
# edges (box corners, chamfers) stay hard.
SMOOTH_ANGLE = 30.0

PIVOTS = {
    "Core": (0.0, 0.0, 0.0),
    "RingFore": (0.0, 0.0, -RING_Z),
    "RingAft": (0.0, 0.0, RING_Z),
    "Hangar": (0.0, 0.0, HANGAR_Z[1]),
    "Dish": (0.0, 0.0, DISH_Z),
}
for _i, _a in enumerate(SPOKE_ANGLES):
    _d = (math.cos(math.radians(_a)), math.sin(math.radians(_a)))
    PIVOTS["SpokeF%d" % _i] = (HUB_R * _d[0], HUB_R * _d[1], -RING_Z)
    PIVOTS["SpokeA%d" % _i] = (HUB_R * _d[0], HUB_R * _d[1], RING_Z)
    PIVOTS["Tower%d" % _i] = (RING_OUT * _d[0], RING_OUT * _d[1], 0.0)
    PIVOTS["Solar%d" % _i] = (NECK_R * _d[0], NECK_R * _d[1], SOLAR_Z)
for _i, _a in enumerate(MID_ANGLES):
    _d = (math.cos(math.radians(_a)), math.sin(math.radians(_a)))
    PIVOTS["Dock%d" % _i] = (WAIST_R * _d[0], WAIST_R * _d[1], DOCK_Z)

# The fly-through openings (game coordinates), each a box the formation can
# cross on a straight line: (name, centre, size, flight axis). Checked by
# casting rays along the axis through a grid over the box's cross-section.
OPENINGS = []
for _a in MID_ANGLES:
    _d = (math.cos(math.radians(_a)), math.sin(math.radians(_a)))
    OPENINGS.append(("sector %g" % _a, (430.0 * _d[0], 430.0 * _d[1], 0.0), (300.0, 300.0, 1300.0), "z"))
OPENINGS.append(("side above", (0.0, 340.0, 0.0), (1700.0, 300.0, 300.0), "x"))
OPENINGS.append(("side right", (340.0, 0.0, 0.0), (300.0, 1700.0, 300.0), "y"))
OPENINGS.append(("side left", (-340.0, 0.0, 0.0), (300.0, 1700.0, 300.0), "y"))

# ---------------------------------------------------------------- colours
# (sRGB colour as the game shows it, emission strength); material() converts
# to linear. The toon light is bright, so even the "white" hull is a mid grey.
# Materials ending in Window/Glow or starting with Nav are left out of the
# game's collision (world/space_station.gd), so they only ever paint flush
# detail or small lights. HangarInterior glows but is solid: it's the bay's
# walls, which the player can crash into.
COLORS = {
    "Hull": ((0.30, 0.32, 0.35), 0.0),
    "HullLight": ((0.40, 0.42, 0.45), 0.0),
    "HullDark": ((0.22, 0.235, 0.26), 0.0),    # plates, frames, machinery
    "Dark": ((0.08, 0.09, 0.11), 0.0),         # recesses, vents
    "Accent": ((0.08, 0.20, 0.50), 0.0),       # Cornerian blue
    "Trim": ((0.80, 0.58, 0.12), 0.0),         # hazard yellow at docks and the hangar
    "Solar": ((0.05, 0.08, 0.22), 0.0),
    "HangarInterior": ((0.40, 0.66, 0.90), 2.5),   # solid, lit bay walls
    "Window": ((0.62, 0.85, 1.0), 3.0),
    "HangarGlow": ((0.45, 0.75, 1.0), 4.0),
    "NavRed": ((1.0, 0.12, 0.08), 6.0),
    "NavGreen": ((0.15, 1.0, 0.3), 6.0),
    "NavWhite": ((1.0, 1.0, 1.0), 6.0),
}
NON_SOLID = {"Window", "HangarGlow", "NavRed", "NavGreen", "NavWhite"}

X = Vector((1.0, 0.0, 0.0))
Y = Vector((0.0, 1.0, 0.0))
Z = Vector((0.0, 0.0, 1.0))
TAU = 2.0 * math.pi


def G(v):
    """Game (Y up, -Z forward) to Blender (Z up, +Y forward)."""
    return Vector((v[0], -v[2], v[1]))


def material(name):
    full = "Station_" + name
    m = bpy.data.materials.get(full) or bpy.data.materials.new(full)
    srgb, emit = COLORS[name]
    rgb = tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb)
    m.use_nodes = True
    bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.6
    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["Emission Strength"].default_value = emit
    if emit > 0:
        bsdf.inputs["Emission Color"].default_value = (*rgb, 1.0)
    # Workbench previews use the viewport colour; lit materials show bright.
    m.diffuse_color = (*rgb, 1.0) if emit == 0 else (*(min(1.0, c * 1.6) for c in rgb), 1.0)
    if name in TEXTURES:
        add_colour_texture(m, bsdf, rgb, TEXTURES[name])
    if name in EMISSION_TEXTURES:
        add_emission_texture(m, bsdf, EMISSION_TEXTURES[name])
    return m


# ---------------------------------------------------------------- textures
# Printed surface detail: tiling images the script generates, packed into the
# .glb and multiplied over the material colour (a glTF base colour texture
# times factor, which the game's ToonMaterial keeps; normal and roughness
# maps would be dropped, so everything is colour). Every mesh gets one UV
# layer in metres / TEX_TILE laid out round the station's axis
# (add_station_uvs), so one tile size serves every texture, and a texture's
# pixels per metre is its size / TEX_TILE. The player sees the station from
# 50 m to 3 km: the detail is coarse (seams 20 cm wide, plates 12-36 m) so it
# reads at a few hundred metres and nothing fine enough to shimmer.
TEX_TILE = 96.0                       # metres per texture repeat (one UV unit)
TEXTURES = {                          # material -> colour texture (multiplied over its colour)
    "Hull": "Plating", "HullLight": "Plating", "HullDark": "Plating", "Accent": "Plating",
    "Trim": "Hazard",
    "Solar": "Solar",
}
EMISSION_TEXTURES = {"Window": "Windows"}   # material -> emission texture (its glow colour)
TEX_SIZES = {"Plating": 2048, "Hazard": 1024, "Solar": 1024, "Windows": 512}   # pixels per side
# Plating: brightness multipliers in linear light (what the shader multiplies by).
PLATE_SCALE = 3.0                     # the plate layout in build_plating_pixels is in metres x this (rows 9-18 m,
                                      # plates 12-36 m: smaller read as brickwork on a 1.8 km station); seams don't scale
PLATE_TONES = (0.80, 0.97)            # each plate picks one: the large-scale variation
SEAM_TONE = 0.42                      # panel seams
SEAM_M = 0.22                         # seam width, metres
LIP_GAIN = 1.06                       # the lit lip just inside each seam (capped at 1)
DETAIL_TONE = 0.55                    # hatch outlines, grille slats, conduits, stencils
GRIME = (0.90, 0.75)                  # shading under each plate's top seam: depth, metres
TONE_NOISE = 0.04                     # smooth +- tone variation over the tile (3 cells)
# Hazard stripes on the trim: a dark stripe every HAZARD_PERIOD metres at 45 degrees.
HAZARD_PERIOD = 2.0
HAZARD_DARK = 0.22
HAZARD_FRACTION = 0.45
# Solar panels: a grid of SOLAR_CELL metre cells with dark dividers.
SOLAR_CELL = 4.0
SOLAR_LINE_M = 0.2
SOLAR_LINE_TONE = 0.5
SOLAR_CELL_TONES = (0.86, 1.0)
# Windows: 4 m patches lit fully, dimmed or nearly dark (weights), so rows of
# windows don't all glow the same.
WINDOW_LEVELS = ((1.0, 0.70), (0.72, 0.20), (0.40, 0.10))
WINDOW_PATCH = 4.0

_images = {}


def _tile_image(name, S, dtype=np.float32):
    """An (S, S) array of ones and helpers that paint it with wrap-around."""
    img = np.ones((S, S), dtype=dtype)

    def fill(u0, v0, w, h, val):
        us = np.arange(int(u0), int(u0) + int(w)) % S
        vs = np.arange(int(v0), int(v0) + int(h)) % S
        img[np.ix_(vs, us)] = val

    def scale(u0, v0, w, h, k):
        us = np.arange(int(u0), int(u0) + int(w)) % S
        vs = np.arange(int(v0), int(v0) + int(h)) % S
        img[np.ix_(vs, us)] *= k

    def shade(u0, v0, w, h, k0, k1):
        """Multiplies by a vertical gradient k0 (top) to k1 (bottom)."""
        us = np.arange(int(u0), int(u0) + int(w)) % S
        vs = np.arange(int(v0), int(v0) + int(h)) % S
        g = np.linspace(k0, k1, len(vs), dtype=dtype)
        img[np.ix_(vs, us)] *= g[:, None]

    return img, fill, scale, shade


def smooth_tile(grid, S):
    """A periodic grid of values resampled to S x S with cosine
    interpolation: tiling low-frequency noise (grid[v][u])."""
    n = grid.shape[0]
    x = np.arange(S) * n / S
    i0 = np.floor(x).astype(int)
    f = x - i0
    f = 0.5 - 0.5 * np.cos(np.pi * f)
    i0 %= n
    i1 = (i0 + 1) % n
    a, b = grid[np.ix_(i0, i0)], grid[np.ix_(i0, i1)]
    c, d = grid[np.ix_(i1, i0)], grid[np.ix_(i1, i1)]
    fx, fy = f[None, :], f[:, None]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def noise_grid(n, rng):
    return np.array([[rng.uniform(-1.0, 1.0) for _ in range(n)] for _ in range(n)], dtype=np.float32)


def build_plating_pixels(seed=19):
    """The hull plating tile as an (S, S) array of linear multipliers: rows
    of 9-18 m plates 12-36 m long (layout sizes x PLATE_SCALE), staggered,
    each a little different in tone,
    with 22 cm seams, a lit lip inside them, grime shading under the top seam
    and at most one feature (hatch, grille, conduit pair, stencil, inset
    strip) per plate. Tiles seamlessly: rows split v exactly and plates wrap
    round u."""
    S = TEX_SIZES["Plating"]
    px = S / TEX_TILE                      # pixels per metre: seams, lips, grime
    pm = px * PLATE_SCALE                  # pixels per layout metre: plates and their features
    seam = max(2, int(round(SEAM_M * px)))
    rng = random.Random(seed)
    img, fill, scale, shade = _tile_image("Plating", S)

    def plate_detail(u0, v0, w, h, tone):
        dark = tone * DETAIL_TONE
        # Bolts in the corners, then at most one feature.
        b = int(0.25 * pm)
        dot = max(2, int(0.1 * pm))
        for cu, cv in ((u0 + b, v0 + b), (u0 + w - b - dot, v0 + b),
                       (u0 + b, v0 + h - b - dot), (u0 + w - b - dot, v0 + h - b - dot)):
            fill(cu, cv, dot, dot, dark)
        roll = rng.random()
        line = max(2, int(0.08 * pm))
        if roll < 0.20 and w > 3.0 * pm and h > 2.4 * pm:
            # Access hatch: an outlined, slightly darker rectangle.
            hw = int(rng.uniform(1.2, 2.4) * pm)
            hh = int(rng.uniform(1.0, min(1.6, h / pm - 1.0)) * pm)
            hu = u0 + rng.randint(int(0.5 * pm), w - hw - int(0.5 * pm))
            hv = v0 + (h - hh) // 2
            scale(hu, hv, hw, hh, 0.92)
            for (a, c, ww, hh2) in ((hu, hv, hw, line), (hu, hv + hh - line, hw, line),
                                    (hu, hv, line, hh), (hu + hw - line, hv, line, hh)):
                fill(a, c, ww, hh2, dark)
        elif roll < 0.34 and w > 3.5 * pm and h > 2.0 * pm:
            # Vent grille: parallel dark slats.
            gw = int(rng.uniform(1.6, 3.0) * pm)
            gh = int(rng.uniform(0.6, min(1.2, h / pm - 0.8)) * pm)
            gu = u0 + rng.randint(int(0.5 * pm), w - gw - int(0.5 * pm))
            gv = v0 + (h - gh) // 2
            step = max(4, int(0.22 * pm))
            for s in range(gu, gu + gw - line, step):
                fill(s, gv, line, gh, dark)
        elif roll < 0.42 and w > 2.5 * pm:
            # A pair of conduits along the plate.
            cv = v0 + int(h * rng.uniform(0.3, 0.7))
            cu = u0 + int(0.4 * pm)
            cw = w - int(0.8 * pm)
            fill(cu, cv, cw, line, dark)
            fill(cu, cv + int(0.3 * pm), cw, line, dark)
        elif roll < 0.50 and w > 3.0 * pm and h > 1.5 * pm:
            # A stencilled marking: a bar and a few squares under it.
            mu = u0 + rng.randint(int(0.5 * pm), w - int(1.8 * pm))
            mv = v0 + rng.randint(int(0.4 * pm), h - int(0.9 * pm))
            fill(mu, mv, int(1.0 * pm), int(0.22 * pm), dark)
            for k in range(rng.randint(2, 4)):
                fill(mu + k * int(0.3 * pm), mv + int(0.32 * pm), int(0.2 * pm), int(0.2 * pm), dark)
        elif roll < 0.60 and h > 2.0 * pm:
            # Inset strip along the plate.
            sh = int(0.35 * pm)
            scale(u0 + int(0.5 * pm), v0 + (h - sh) // 2, w - int(1.0 * pm), sh, 0.88)

    # Rows: 3-6 m bands summing exactly to the tile.
    rows, v = [], 0
    while v < S:
        h = int(rng.choice((3.0, 4.0, 4.0, 5.0, 6.0)) * pm)
        if S - (v + h) < 3 * pm:
            h = S - v
        rows.append((v, h))
        v += h
    for v0, h in rows:
        # Plates 4-12 m long from a random stagger, wrapping in u.
        u, start = 0, rng.randint(0, S - 1)
        while u < S:
            w = int(rng.uniform(4.0, 12.0) * pm)
            if S - (u + w) < 4 * pm:
                w = S - u
            # Some plates split in two across the row.
            parts = [(v0, h)]
            if h >= 5 * pm and rng.random() < 0.3:
                cut = int(h * rng.uniform(0.4, 0.6))
                parts = [(v0, cut), (v0 + cut, h - cut)]
            for pv, ph in parts:
                tone = rng.uniform(*PLATE_TONES)
                fill(start + u, pv, w, ph, tone)
                plate_detail(start + u, pv, w, ph, tone)
                # Seam on the plate's low edges (the neighbours draw the other
                # two), a lit lip just inside, grime fading down from the top.
                fill(start + u, pv, w, seam, SEAM_TONE)
                fill(start + u, pv, seam, ph, SEAM_TONE)
                lip = max(1, int(0.06 * px))
                fill(start + u + seam, pv + seam, w - seam, lip, min(1.0, tone * LIP_GAIN))
                fill(start + u + seam, pv + seam, lip, ph - seam, min(1.0, tone * LIP_GAIN))
                depth = int(GRIME[1] * px)
                shade(start + u + seam + lip, pv + seam + lip, w - seam - lip, min(depth, ph - seam - lip),
                      GRIME[0], 1.0)
            u += w
    # Smooth tone variation over the whole tile, so big flat faces aren't
    # uniform from a distance.
    img *= 1.0 + TONE_NOISE * smooth_tile(noise_grid(3, rng), S)
    return np.clip(img, 0.0, 1.0)


def build_hazard_pixels(seed=7):
    """Hazard stripes for the trim: dark diagonal stripes over the yellow,
    edges softened over a pixel so they don't crawl."""
    S = TEX_SIZES["Hazard"]
    px = S / TEX_TILE
    period = HAZARD_PERIOD * px
    u, v = np.meshgrid(np.arange(S) + 0.5, np.arange(S) + 0.5)
    phase = ((u + v) / period) % 1.0
    inside = phase < HAZARD_FRACTION
    dist = np.minimum(np.minimum(np.abs(phase), np.abs(phase - HAZARD_FRACTION)), np.abs(phase - 1.0))
    sdf = np.where(inside, dist, -dist) * period      # pixels to the stripe edge, positive inside
    coverage = np.clip(sdf / 1.5 + 0.5, 0.0, 1.0)
    img = (1.0 - (1.0 - HAZARD_DARK) * coverage).astype(np.float32)
    rng = random.Random(seed)
    img *= 1.0 + 0.05 * smooth_tile(noise_grid(3, rng), S)
    return np.clip(img, 0.0, 1.0)


def build_solar_pixels(seed=5):
    """Solar panel cells: a grid of SOLAR_CELL m cells with dark divider
    lines, each cell a slightly different tone with a soft sheen across it."""
    S = TEX_SIZES["Solar"]
    px = S / TEX_TILE
    cell = int(SOLAR_CELL * px)
    n = max(1, S // cell)
    cell = S // n                      # cells divide the tile exactly, so it tiles
    line = max(1, int(SOLAR_LINE_M * px))
    rng = random.Random(seed)
    img, fill, scale, shade = _tile_image("Solar", S)
    ramp = np.linspace(1.0, 0.9, cell, dtype=np.float32)
    sheen = (ramp[:, None] + ramp[None, :]) / 2
    for i in range(n):
        for j in range(n):
            tone = rng.uniform(*SOLAR_CELL_TONES)
            img[j * cell:(j + 1) * cell, i * cell:(i + 1) * cell] = tone * sheen
            fill(i * cell, j * cell, cell, line, SOLAR_LINE_TONE)
            fill(i * cell, j * cell, line, cell, SOLAR_LINE_TONE)
    return np.clip(img, 0.0, 1.0)


def build_window_pixels(seed=3):
    """The windows' glow as an (S, S, 3) linear colour: the Window colour at
    full brightness, dimmed or nearly dark in WINDOW_PATCH m patches."""
    S = TEX_SIZES["Windows"]
    px = S / TEX_TILE
    patch = max(1, int(WINDOW_PATCH * px))
    n = max(1, S // patch)
    patch = S // n
    rng = random.Random(seed)
    levels = [lv for lv, _ in WINDOW_LEVELS]
    weights = [wt for _, wt in WINDOW_LEVELS]
    lum = np.ones((S, S), dtype=np.float32)
    for i in range(n):
        for j in range(n):
            lum[j * patch:(j + 1) * patch, i * patch:(i + 1) * patch] = rng.choices(levels, weights)[0]
    srgb = COLORS["Window"][0]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]
    return np.stack([lum * c for c in lin], axis=-1)


TEX_BUILDERS = {"Plating": build_plating_pixels, "Hazard": build_hazard_pixels,
                "Solar": build_solar_pixels, "Windows": build_window_pixels}


def texture_image(name):
    """The Blender image for texture `name` (built once per run from its
    linear pixels, saved to the preview folder as tex_<name>.png and packed,
    so the glTF export embeds it)."""
    if name in _images:
        return _images[name]
    lin = TEX_BUILDERS[name]()
    S = TEX_SIZES[name]
    if lin.ndim == 2:
        lin = np.repeat(lin[..., None], 3, axis=-1)
    srgb = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(np.maximum(lin, 0.0), 1.0 / 2.4) - 0.055)
    rgba = np.ones((S, S, 4), dtype=np.float32)
    rgba[..., :3] = srgb
    full = "Station_" + name
    old = bpy.data.images.get(full)
    if old:
        bpy.data.images.remove(old)
    img = bpy.data.images.new(full, S, S, alpha=False)
    img.pixels.foreach_set(rgba.ravel())
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    img.filepath_raw = os.path.join(PREVIEW_DIR, "tex_%s.png" % name.lower())
    img.file_format = 'PNG'
    img.save()
    img.pack()
    _images[name] = img
    return img


def _image_node(mat, image):
    nodes = mat.node_tree.nodes
    tex = next((n for n in nodes if n.type == 'TEX_IMAGE' and n.image == image), None)
    if tex is None:
        tex = nodes.new('ShaderNodeTexImage')
        tex.image = image
    return tex


def add_colour_texture(mat, bsdf, rgb, name):
    """Base colour = texture x the material's colour (a Multiply mix, which
    the glTF exporter writes as a base colour texture plus factor)."""
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    tex = _image_node(mat, texture_image(name))
    mix = next((n for n in nodes if n.type == 'MIX' and n.blend_type == 'MULTIPLY'), None)
    if mix is None:
        mix = nodes.new('ShaderNodeMix')
        mix.data_type = 'RGBA'
        mix.blend_type = 'MULTIPLY'
    mix.inputs['Factor'].default_value = 1.0
    a = next(s for s in mix.inputs if s.identifier == 'A_Color')
    b = next(s for s in mix.inputs if s.identifier == 'B_Color')
    out = next(s for s in mix.outputs if s.identifier == 'Result_Color')
    b.default_value = (*rgb, 1.0)
    links.new(tex.outputs['Color'], a)
    links.new(out, bsdf.inputs['Base Color'])


def add_emission_texture(mat, bsdf, name):
    """The glow colour comes from the texture (already in the material's
    colour); the strength stays on the BSDF (KHR_materials_emissive_strength)."""
    links = mat.node_tree.links
    tex = _image_node(mat, texture_image(name))
    links.new(tex.outputs['Color'], bsdf.inputs['Emission Color'])


# Per-projection offsets (in tiles) so opposite faces and the different
# frames don't show the same stretch of texture.
_UV_OFFSETS = {
    ("a", 1): (0.00, 0.00), ("a", -1): (0.37, 0.61),      # axial faces (looking along the axis)
    ("r", 1): (0.13, 0.29), ("r", -1): (0.71, 0.08),      # radial faces (rims, drums, outer walls)
    ("t", 1): (0.52, 0.44), ("t", -1): (0.23, 0.83),      # tangential faces (spoke and tower sides)
    (0, 1): (0.05, 0.47), (0, -1): (0.66, 0.19),          # box faces (the hangar), by axis
    (1, 1): (0.31, 0.72), (1, -1): (0.88, 0.35),
    (2, 1): (0.44, 0.06), (2, -1): (0.17, 0.58),
}
UV_BOX_PARTS = {"Hangar"}             # axis-aligned parts on the station's axis: box projection
UV_AXIS_RADIUS = 48.0                 # faces centred closer to the axis (neck end caps) are box-projected


def add_station_uvs(me, name, pivot):
    """One UV layer in metres / TEX_TILE, laid out round the station's axis
    so the textures follow the structure without seams. Each face is mapped
    by its normal (game coordinates, the axis along z): faces looking along
    the axis (ring sides, spoke and tower ends) get u round the axis (arc
    length at the face's radius) and v the radius; radial faces (rims, the
    drums, the towers' outer walls) u round the axis and v along z; faces
    whose normal is tangential (spoke and tower sides) u along z and v the
    radius. Arc length uses a radius rounded to a whole number of tiles per
    turn, so a band is seamless all the way round. Faces near the axis (the
    neck end caps) and the hangar (a box on the axis) are box-projected along
    their main axis instead, like the Juggernaut's plating."""
    uv = me.uv_layers[0] if me.uv_layers else me.uv_layers.new(name="UVMap")
    origin = G(Vector(pivot))
    box_part = name in UV_BOX_PARTS
    rng = random.Random(name)
    part_offset = (rng.random(), rng.random())    # the two wheels must not plate alike
    for poly in me.polygons:
        n = to_game(poly.normal)
        if n.length < 0.5:
            continue
        loops = list(poly.loop_indices)
        pts = [to_game(origin + me.vertices[me.loops[li].vertex_index].co) for li in loops]
        c = sum(pts, Vector()) / len(pts)
        rc = math.hypot(c.x, c.y)
        if box_part or rc < UV_AXIS_RADIUS:
            ax = max(range(3), key=lambda i: abs(n[i]))
            ou, ov = _UV_OFFSETS[(ax, 1 if n[ax] >= 0 else -1)]
            for li, p in zip(loops, pts):
                if ax == 0:
                    u, v = p.z, p.y
                elif ax == 1:
                    u, v = p.z, p.x
                else:
                    u, v = p.x, p.y
                uv.data[li].uv = (u / TEX_TILE + ou + part_offset[0], v / TEX_TILE + ov + part_offset[1])
            continue
        d = Vector((c.x / rc, c.y / rc, 0.0))
        t = Vector((-d.y, d.x, 0.0))
        comps = {"a": n.z, "r": n.dot(d), "t": n.dot(t)}
        kind = max(comps, key=lambda k: abs(comps[k]))
        ou, ov = _UV_OFFSETS[(kind, 1 if comps[kind] >= 0 else -1)]
        if kind == "t":
            for li, p in zip(loops, pts):
                uv.data[li].uv = (p.z / TEX_TILE + ou + part_offset[0], p.dot(d) / TEX_TILE + ov + part_offset[1])
            continue
        # Arc length round the axis at the face's mean radius, rounded so a
        # whole number of tiles goes round; angles unwrapped about the
        # face's centre so no face straddles the seam.
        radii = [math.hypot(p.x, p.y) for p in pts]
        r_mean = sum(radii) / len(radii)
        r_eff = max(1.0, round(TAU * r_mean / TEX_TILE)) * TEX_TILE / TAU
        a_c = math.atan2(c.y, c.x)
        for li, p, r in zip(loops, pts, radii):
            a = a_c + (math.atan2(p.y, p.x) - a_c + math.pi) % TAU - math.pi
            u = a * r_eff
            v = r if kind == "a" else p.z
            uv.data[li].uv = (u / TEX_TILE + ou + part_offset[0], v / TEX_TILE + ov + part_offset[1])


def radial(deg):
    a = math.radians(deg)
    return Vector((math.cos(a), math.sin(a), 0.0))


def tangent(deg):
    a = math.radians(deg)
    return Vector((-math.sin(a), math.cos(a), 0.0))


def near_angle(deg, angles, span):
    return any(abs((deg - a + 180.0) % 360.0 - 180.0) < span for a in angles)


# ---------------------------------------------------------------- primitives
# Each returns (verts, faces, mats) in game coordinates: faces as vertex index
# tuples, mats one material name per face. Part.add() collects them.
def box(center, size, axes=(X, Y, Z), mat="Hull"):
    """A box of `size` along the three `axes` (unit vectors), about `center`."""
    c = Vector(center)
    hx, hy, hz = (s / 2 for s in size)
    ex, ey, ez = axes
    verts = [c + ex * (sx * hx) + ey * (sy * hy) + ez * (sz * hz)
             for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    return verts, faces, [mat] * 6


def beam(a, b, width, height, up=Y, mat="Hull"):
    """A box from a to b: `width` across, `height` towards `up`."""
    a, b = Vector(a), Vector(b)
    ez = (b - a).normalized()
    ex = up.cross(ez)
    if ex.length < 1e-6:
        ex = X.cross(ez)
    ex.normalize()
    ey = ez.cross(ex)
    return box((a + b) / 2, (width, height, (b - a).length), (ex, ey, ez), mat)


def cells(w, h, rects, base):
    """Partitions a w x h rectangle (local u 0..w, v 0..h) into cells, one
    material each: `rects` are (u0, v0, u1, v1, mat) painted over `base`
    (later ones on top; mat None cuts a hole). Returns (us, vs, grid) with
    grid[i][j] the material of cell i, j. Same-material cells merge again when
    the mesh is finished (Part.build), so paint costs only its outline."""
    us = sorted({0.0, w} | {max(0.0, min(w, r[k])) for r in rects for k in (0, 2)})
    vs = sorted({0.0, h} | {max(0.0, min(h, r[k])) for r in rects for k in (1, 3)})
    us = [u for i, u in enumerate(us) if i == 0 or u - us[i - 1] > 1e-6]
    vs = [v for i, v in enumerate(vs) if i == 0 or v - vs[i - 1] > 1e-6]
    grid = []
    for i in range(len(us) - 1):
        cu = (us[i] + us[i + 1]) / 2
        row = []
        for j in range(len(vs) - 1):
            cv = (vs[j] + vs[j + 1]) / 2
            m = base
            for u0, v0, u1, v1, rm in rects:
                if u0 < cu < u1 and v0 < cv < v1:
                    m = rm
            row.append(m)
        grid.append(row)
    return us, vs, grid


def plane_face(origin, u_axis, v_axis, normal, w, h, rects=(), base="Hull"):
    """A flat w x h rectangle with its (0, 0) corner at `origin`, spanning
    u_axis and v_axis, wound to face `normal`, painted with `rects` (see
    cells())."""
    us, vs, grid = cells(w, h, rects, base)
    verts, faces, mats = [], [], []
    index = {}

    def vid(i, j):
        key = (i, j)
        if key not in index:
            index[key] = len(verts)
            verts.append(Vector(origin) + u_axis * us[i] + v_axis * vs[j])
        return index[key]

    flip = u_axis.cross(v_axis).dot(normal) < 0.0
    for i in range(len(us) - 1):
        for j in range(len(vs) - 1):
            m = grid[i][j]
            if m is None:
                continue
            f = (vid(i, j), vid(i + 1, j), vid(i + 1, j + 1), vid(i, j + 1))
            faces.append(tuple(reversed(f)) if flip else f)
            mats.append(m)
    return verts, faces, mats


def face_frame(axes, key):
    """For a box face `key` ('+x'...'-z' in the box's local axes): its outward
    normal and the (u, v) axes its paint rectangles use. u and v are the other
    two axes in cyclic order (x: u=y v=z; y: u=z v=x; z: u=x v=y), origin at
    the corner where both are at their minimum."""
    ex, ey, ez = axes
    k = "xyz".index(key[1])
    sign = 1.0 if key[0] == "+" else -1.0
    n = axes[k] * sign
    return n, axes[(k + 1) % 3], axes[(k + 2) % 3], k


def painted_box(center, size, axes=(X, Y, Z), base="Hull", paint=None, chamfer=0.0):
    """A box like box(), each face painted with paint[key] rectangles (see
    face_frame() for the u, v frame; sizes in metres from the face's corner).
    With `chamfer`, the edges and corners are cut at 45 degrees and the main
    faces shrink by it (paint coordinates then start at the chamfered corner)."""
    c = Vector(center)
    half = [s / 2 for s in size]
    paint = paint or {}
    verts, faces, mats = [], [], []

    def add(piece):
        v, f, m = piece
        start = len(verts)
        verts.extend(v)
        faces.extend(tuple(start + i for i in face) for face in f)
        mats.extend(m)

    for key in ("+x", "-x", "+y", "-y", "+z", "-z"):
        n, ua, va, k = face_frame(axes, key)
        ku, kv = (k + 1) % 3, (k + 2) % 3
        w, h = size[ku] - 2 * chamfer, size[kv] - 2 * chamfer
        origin = c + n * half[k] - ua * (w / 2) - va * (h / 2)
        add(plane_face(origin, ua, va, n, w, h, paint.get(key, ()), base))
    if chamfer > 0.0:
        hx, hy, hz = half
        ch = chamfer
        ex, ey, ez = axes

        def corner_pts(sx, sy, sz):
            return [c + ex * (sx * (hx - ch)) + ey * (sy * (hy - ch)) + ez * (sz * hz),
                    c + ex * (sx * (hx - ch)) + ey * (sy * hy) + ez * (sz * (hz - ch)),
                    c + ex * (sx * hx) + ey * (sy * (hy - ch)) + ez * (sz * (hz - ch))]

        for sx in (-1, 1):
            for sy in (-1, 1):
                for sz in (-1, 1):
                    pts = corner_pts(sx, sy, sz)
                    start = len(verts)
                    verts.extend(pts)
                    tri = (start, start + 1, start + 2)
                    centre = sum(pts, Vector()) / 3
                    out = (centre - c)
                    nrm = (pts[1] - pts[0]).cross(pts[2] - pts[0])
                    faces.append(tri if nrm.dot(out) > 0 else tuple(reversed(tri)))
                    mats.append(base)
        # Edge chamfers: along each axis, the four edges around it.
        for k in range(3):
            ku, kv = (k + 1) % 3, (k + 2) % 3
            for su in (-1, 1):
                for sv in (-1, 1):
                    pts = []
                    for sk in (-1, 1):
                        p_u = c + axes[k] * (sk * (half[k] - ch)) + axes[ku] * (su * half[ku]) + axes[kv] * (sv * (half[kv] - ch))
                        p_v = c + axes[k] * (sk * (half[k] - ch)) + axes[ku] * (su * (half[ku] - ch)) + axes[kv] * (sv * half[kv])
                        pts.append((p_u, p_v))
                    quad = [pts[0][0], pts[0][1], pts[1][1], pts[1][0]]
                    start = len(verts)
                    verts.extend(quad)
                    f = (start, start + 1, start + 2, start + 3)
                    nrm = (quad[1] - quad[0]).cross(quad[2] - quad[0])
                    out = sum(quad, Vector()) / 4 - c
                    faces.append(f if nrm.dot(out) > 0 else tuple(reversed(f)))
                    mats.append(base)
    return verts, faces, mats


def lathe(profile, segments, rows=None, closed=False, a0=0.0, a1=TAU, origin=(0, 0, 0), axis=Z, ref=X,
          base="Hull"):
    """Revolves a profile of (along-axis, radius) points round `axis` through
    `origin`, from angle a0 to a1 (measured from `ref`). An open profile (a
    spindle) gets end caps; a closed one (a ring's cross-section) is capped at
    the ends of a partial sweep.

    `rows` paints the bands between profile points: one entry per profile
    edge, a material name or a callable pattern(j, n, deg) -> [(t0, t1, mat)]
    giving painted sub-cells along the chord of segment j (t in 0..1, the
    rest of the cell stays in `base`; a (material, pattern) tuple fills the
    rest with that material instead). Sub-cell vertices lie on the chord, so
    every face stays flat."""
    o = Vector(origin)
    w = Vector(axis).normalized()
    u = (Vector(ref) - w * Vector(ref).dot(w)).normalized()
    v = w.cross(u)
    full = abs(a1 - a0 - TAU) < 1e-6
    n_ang = segments if full else segments + 1
    m = len(profile)
    verts = []
    for j in range(n_ang):
        a = a0 + (a1 - a0) * j / segments
        d = u * math.cos(a) + v * math.sin(a)
        verts += [o + w * t + d * r for t, r in profile]
    faces, mats = [], []
    n_rows = m if closed else m - 1
    for j in range(segments):
        j2 = (j + 1) % n_ang
        deg = math.degrees(a0 + (a1 - a0) * (j + 0.5) / segments) % 360.0
        for i in range(n_rows):
            i2 = (i + 1) % m
            row = rows[i] if rows else base
            quad = (j * m + i, j * m + i2, j2 * m + i2, j2 * m + i)
            fill = base
            if isinstance(row, tuple):
                fill, row = row       # (fill material, pattern): paint over another base
            if not callable(row):
                faces.append(quad)
                mats.append(row)
                continue
            # Painted: split the cell along the chord at the pattern's cuts.
            cuts = sorted(row(j, segments, deg), key=lambda c: c[0])
            ts, paint = [0.0], []
            for t0, t1, mat in cuts:
                t0, t1 = max(0.0, min(1.0, t0)), max(0.0, min(1.0, t1))
                if t1 - t0 < 1e-4 or t0 < ts[-1] - 1e-4:
                    continue   # empty, or overlapping the previous cut
                if t0 > ts[-1] + 1e-4:
                    ts.append(t0)
                    paint.append(fill)
                ts.append(t1)
                paint.append(mat)
            if ts[-1] < 1.0 - 1e-4:
                ts.append(1.0)
                paint.append(fill)
            a_lo, a_hi = verts[j * m + i], verts[j2 * m + i]
            b_lo, b_hi = verts[j * m + i2], verts[j2 * m + i2]
            ids_a, ids_b = [], []
            for t in ts:
                if t <= 0.0:
                    ids_a.append(j * m + i)
                    ids_b.append(j * m + i2)
                elif t >= 1.0:
                    ids_a.append(j2 * m + i)
                    ids_b.append(j2 * m + i2)
                else:
                    ids_a.append(len(verts))
                    verts.append(a_lo.lerp(a_hi, t))
                    ids_b.append(len(verts))
                    verts.append(b_lo.lerp(b_hi, t))
            for k in range(len(ts) - 1):
                faces.append((ids_a[k], ids_b[k], ids_b[k + 1], ids_a[k + 1]))
                mats.append(paint[k])
    if full and not closed:
        if profile[0][1] > 0:
            faces.append(tuple(j * m for j in range(n_ang)))
            mats.append(base)
        if profile[-1][1] > 0:
            faces.append(tuple(j * m + m - 1 for j in range(n_ang)))
            mats.append(base)
    if not full and closed:
        faces.append(tuple(range(m)))
        faces.append(tuple((n_ang - 1) * m + i for i in range(m)))
        mats += [base, base]
    return verts, faces, mats


def window_row(count, width, margin=0.0, skip=None, cond=None, mat="Window"):
    """A lathe row pattern: `count` windows per segment, each `width` of the
    chord (t units), evenly spaced inside `margin`; `skip(j, k)` leaves one
    out, `cond(j, deg)` leaves the whole segment plain."""
    def pattern(j, n, deg):
        if cond and not cond(j, deg):
            return []
        span = 1.0 - 2.0 * margin
        pitch = span / count
        out = []
        for k in range(count):
            if skip and skip(j, k):
                continue
            c = margin + pitch * (k + 0.5)
            out.append((c - width / 2, c + width / 2, mat))
        return out
    return pattern


def plain_row(mat, cond):
    """A lathe row pattern painting the whole cell `mat` where cond(j, deg)."""
    return lambda j, n, deg: [(0.0, 1.0, mat)] if cond(j, deg) else []


def inset_row(mat, inset, cond=None):
    """A lathe row pattern painting the cell `mat` with `inset` (t units)
    left plain at both ends, where cond(j, deg)."""
    return lambda j, n, deg: [(inset, 1.0 - inset, mat)] if (cond is None or cond(j, deg)) else []


# ---------------------------------------------------------------- parts
class Part:
    """One exported node: all its pieces in one mesh, one material slot per
    colour. build() welds shared vertices, closes T-junctions (so every shell
    is a closed manifold), merges coplanar same-material faces (painted cells
    back into one face) and smooth-shades curved surfaces."""

    def __init__(self, name):
        self.name = name
        self.pivot = Vector(PIVOTS[name])
        self.verts = []
        self.faces = []
        self.mats = []

    def add(self, piece, mat=None):
        verts, faces, mats = piece
        start = len(self.verts)
        self.verts += [Vector(p) for p in verts]
        for f, m in zip(faces, mats):
            self.faces.append(tuple(start + i for i in f))
            self.mats.append(mat or m)

    def build(self, collection):
        me = bpy.data.meshes.new("Station_" + self.name)
        me.from_pydata([G(p - self.pivot) for p in self.verts], [], self.faces)
        names = sorted(set(self.mats))
        for n in names:
            me.materials.append(material(n))
        for poly, mat in zip(me.polygons, self.mats):
            poly.material_index = names.index(mat)
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.002)
        close_t_junctions(bm)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        # Painted cells of one material in one plane merge back into a single
        # face (the angle is tiny so faces only merge when truly coplanar);
        # the merge removes vertices along straight edges, so close the
        # T-junctions that leaves.
        bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(0.001), use_dissolve_boundaries=False,
                                 verts=bm.verts[:], edges=bm.edges[:], delimit={'MATERIAL'})
        close_t_junctions(bm)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        bm.to_mesh(me)
        bm.free()
        for poly in me.polygons:
            poly.use_smooth = True
        me.set_sharp_from_angle(angle=math.radians(SMOOTH_ANGLE))
        me.update()
        add_station_uvs(me, self.name, self.pivot)
        o = bpy.data.objects.new("Station_" + self.name, me)
        o.location = G(self.pivot)
        collection.objects.link(o)
        return o


def close_t_junctions(bm, eps=0.003):
    """Splits every edge at each vertex that lies on it (a painted cell's
    corner on a neighbouring face's edge) and welds the two, so faces share
    their edges and the shells are true manifolds."""
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    vlist = list(bm.verts)   # splitting adds vertices, which invalidates index lookups
    kd = KDTree(len(vlist))
    for i, v in enumerate(vlist):
        kd.insert(v.co, i)
    kd.balance()
    targets = {}
    for e in list(bm.edges):
        a, b = e.verts[0].co.copy(), e.verts[1].co.copy()
        ab = b - a
        length = ab.length
        if length < 2 * eps:
            continue
        hits = []
        for co, idx, _ in kd.find_range((a + b) / 2, length / 2 + eps):
            v = vlist[idx]
            if v is e.verts[0] or v is e.verts[1]:
                continue
            t = (co - a).dot(ab) / (length * length)
            if t <= eps / length or t >= 1.0 - eps / length:
                continue
            if ((co - a) - ab * t).length > eps:
                continue
            hits.append((t, v))
        if not hits:
            continue
        hits.sort(key=lambda h: h[0])
        edge = e
        start = e.verts[0]
        prev_t = 0.0
        for t, v in hits:
            frac = (t - prev_t) / (1.0 - prev_t)
            # edge_split(edge, vert, fac) returns (new_edge, new_vert): the
            # new edge runs start..new_vert; `edge` goes on to the far end.
            _, new_vert = bmesh.utils.edge_split(edge, start, frac)
            targets[new_vert] = v
            start = new_vert
            prev_t = t
    if targets:
        bmesh.ops.weld_verts(bm, targetmap=targets)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()


# ---------------------------------------------------------------- paint helpers
# Rectangles for painted_box faces: (u0, v0, u1, v1, material).
def window_run(a0, a1, b, h=2.0, w=3.0, pitch=6.0, run=8, pause=3, rng=None, skip=0.12, along="u"):
    """A row of windows spaced along one face axis (`along`: "u" or "v")
    between a0 and a1, at position b on the other axis: each w wide (along the
    row), h tall, `pitch` apart, in runs of `run` with `pause` gaps; a few
    left out at random."""
    out, k = [], 0
    a = a0 + pitch / 2
    while a + w / 2 <= a1:
        if k % (run + pause) < run and not (rng and rng.random() < skip):
            if along == "u":
                out.append((a - w / 2, b, a + w / 2, b + h, "Window"))
            else:
                out.append((b, a - w / 2, b + h, a + w / 2, "Window"))
        a += pitch
        k += 1
    return out


def plates(u0, u1, v0, v1, cw, cl, mats=("HullLight", "HullDark"), rng=None, skip=0.3, gap=1.5):
    """A loose grid of painted panel plates cw x cl over u0..u1, v0..v1, some
    cells left bare, in a random tone from `mats`."""
    out = []
    nu, nv = max(1, int((u1 - u0) // cw)), max(1, int((v1 - v0) // cl))
    w, l = (u1 - u0) / nu, (v1 - v0) / nv
    for i in range(nu):
        for j in range(nv):
            if rng and rng.random() < skip:
                continue
            m = rng.choice(mats) if rng else mats[0]
            out.append((u0 + i * w + gap, v0 + j * l + gap, u0 + (i + 1) * w - gap, v0 + (j + 1) * l - gap, m))
    return out


def vents(u0, u1, v, h=4.0, w=10.0, pitch=14.0, mat="Dark"):
    """A row of dark vent rectangles along u at height v."""
    out = []
    u = u0
    while u + w <= u1 + 1e-6:
        out.append((u, v, u + w, v + h, mat))
        u += pitch
    return out


def habitat(deg):
    """True where the wheels carry habitat bays (windows): every other 30
    degree bay, clear of the towers."""
    return int(deg // 30.0) % 2 == 0 and not near_angle(deg, SPOKE_ANGLES, 7.0)


def service(deg):
    return not habitat(deg) and not near_angle(deg, SPOKE_ANGLES, 7.0)


# ---------------------------------------------------------------- components
def build_core(rng):
    """The spine: bow neck, fore hub drum, harbour waist, aft hub drum, stern
    neck. Windows on the drums and waist, blue collars at the wheel planes."""
    p = Part("Core")
    n = SPINE_SEGMENTS
    win3 = window_row(3, 0.16, margin=0.1, skip=lambda j, k: rng.random() < 0.15)
    win2 = window_row(2, 0.2, margin=0.14, skip=lambda j, k: rng.random() < 0.15)
    # One lathe bow to stern (separate sections would double up their end
    # caps where they meet): the profile is the sections joined, with paint
    # rows cut into the drums and the waist.
    entries = []   # (point, paint row of the edge starting at it)

    def seg(pt, row):
        if entries and abs(entries[-1][0][0] - pt[0]) < 1e-6 and abs(entries[-1][0][1] - pt[1]) < 1e-6:
            entries[-1] = (pt, row)   # the last section's end point: this section's row applies
        else:
            entries.append((pt, row))

    for profile, mat in SPINE_SECTIONS:
        (z0, r0), (z1, r1) = profile
        if r0 == HUB_R and r1 == HUB_R:
            # A drum: two window bands, a painted light band between them.
            band = [(z0, "Hull"), (z0 + 14, win3), (z0 + 18, plain_row("HullLight", lambda j, d: j % 4 != 3)),
                    (z0 + 40, inset_row("HullLight", 0.05, lambda j, d: j % 2 == 0)),
                    (z1 - 40, plain_row("HullLight", lambda j, d: j % 4 != 1)), (z1 - 18, win3),
                    (z1 - 14, "Hull"), (z1, None)]
        elif r0 == WAIST_R and r1 == WAIST_R:
            # The harbour waist: window bands near the ends, dark vents between.
            vent = inset_row("Dark", 0.2, lambda j, d: j % 3 == 0 and not near_angle(d, MID_ANGLES, 12.0))
            band = [(z0, "Hull"), (z0 + 30, win2), (z0 + 33, "Hull"), (z0 + 60, vent), (z0 + 66, "HullDark"),
                    (z1 - 66, vent), (z1 - 60, "Hull"), (z1 - 33, win2), (z1 - 30, "Hull"), (z1, None)]
        else:
            band = [(z0, mat), (z1, None)]
        # Each entry paints the edge that starts at it (None: the section's
        # last point, whose row the next section supplies).
        for k, (z, row) in enumerate(band):
            seg((z, r1 if k == len(band) - 1 else r0), row if row is not None else mat)
    pts = [e[0] for e in entries]
    rows = [e[1] for e in entries[:-1]]
    p.add(lathe(pts, n, rows=rows, base="Hull"))
    # Blue collars at the wheel planes (where the spokes meet the drums) and
    # round the necks, a little proud.
    for z0, z1, r in ((-RING_Z - 8, -RING_Z + 8, HUB_R + 0.8), (RING_Z - 8, RING_Z + 8, HUB_R + 0.8),
                      (-378, -366, NECK_R + 0.8), (380, 392, NECK_R + 0.8)):
        p.add(lathe([(z0, r), (z1, r)], n, base="Accent"), "Accent")
    # Nav lights on the drums' sides, between the spokes.
    for z in (-RING_Z, RING_Z):
        for deg in MID_ANGLES:
            d = radial(deg)
            p.add(box(d * (HUB_R + 0.8) + Z * z, (2.4, 2.4, 2.4), (d, tangent(deg), Z), "NavWhite"))
    return p


def ring_profile():
    """The wheel's cross-section as a closed (z, r) loop with one paint row
    per edge: a lit rail on the inner face, window bands and light panels on
    both sides (habitat bays), a blue stripe and plates round the rim."""
    c, h, ri, ro = RING_CHAMFER, RING_HALF, RING_IN, RING_OUT
    rng = random.Random(4471)
    panel = inset_row("HullLight", 0.04, lambda j, d: habitat(d))
    windows = window_row(6, 0.07, margin=0.05, skip=lambda j, k: rng.random() < 0.12, cond=lambda j, d: habitat(d))
    # The rim is off-white (HullLight): a dark vent pair every third segment
    # of the service bays, mid-grey plates on the habitat bays' segments.
    svc_vent = ("HullLight", window_row(2, 0.25, margin=0.12, mat="Dark",
                                        cond=lambda j, d: service(d) and j % 3 == 1))
    rim_plate = ("HullLight", inset_row("Hull", 0.05, lambda j, d: habitat(d) and (j // 2) % 2 == 0))
    stripe = ("HullLight", plain_row("Accent", lambda j, d: not near_angle(d, SPOKE_ANGLES, 6.0)))
    pts, rows = [], []

    def seg(pt, row):
        pts.append(pt)
        rows.append(row)

    w1, w2 = ri + 30.0, ri + 54.0                    # the two window bands' radii
    seg((-(h - c), ri), "HullLight")                 # inner face: two blue guide stripes
    seg((-16.0, ri), "Accent")
    seg((-12.0, ri), "HullLight")
    seg((-0.8, ri), "Window")                        # the lit rail
    seg((0.8, ri), "HullLight")
    seg((12.0, ri), "Accent")
    seg((16.0, ri), "HullLight")
    seg((h - c, ri), "HullLight")                    # chamfer
    seg((h, ri + c), "Hull")                         # aft side, from the inner edge out
    seg((h, ri + c + 4), panel)
    seg((h, w1), windows)
    seg((h, w1 + 3), panel)
    seg((h, w2), windows)
    seg((h, w2 + 3), panel)
    seg((h, ro - c - 4), "Hull")
    seg((h, ro - c), "HullLight")                    # chamfer
    seg((h - c, ro), rim_plate)                      # rim: plates, blue stripe, vents
    seg((7, ro), stripe)
    seg((-7, ro), svc_vent)
    seg((-(h - c), ro), "HullLight")                 # chamfer
    seg((-h, ro - c), "Hull")                        # fore side, from the rim in
    seg((-h, ro - c - 4), panel)
    seg((-h, w2 + 3), windows)
    seg((-h, w2), panel)
    seg((-h, w1 + 3), windows)
    seg((-h, w1), panel)
    seg((-h, ri + c + 4), "Hull")
    seg((-h, ri + c), "Hull")                        # chamfer back to the start
    return pts, rows


def build_ring(name, z, rng):
    p = Part(name)
    pts, rows = ring_profile()
    p.add(lathe(pts, RING_SEGMENTS, rows=rows, closed=True, origin=(0, 0, z), base="Hull"))
    # Radiator clusters on the rim at the service bays: a dark bed and four
    # light fins, which break up the wheel's silhouette.
    for deg in RADIATOR_ANGLES:
        d, t = radial(deg), tangent(deg)
        p.add(box(d * (RING_OUT + 0.5) + Z * z, (3.0, 48.0, 30.0), (d, t, Z), "HullDark"))
        for k in range(4):
            p.add(box(d * (RING_OUT + 8.0) + t * ((k - 1.5) * 11.0) + Z * z, (14.0, 1.6, 26.0), (d, t, Z),
                      "HullLight"))
    # Habitat modules on the rim at the habitat bay centres, sunk into the
    # wheel: a lit block (window rows on the faces seen from the bow and
    # stern) with a blue band, and a navigation light on top: red on the
    # left (-X) half, green on the right.
    for deg in MODULE_ANGLES:
        d, t = radial(deg), tangent(deg)
        mr, mw, mz = MODULE_SIZE
        c = d * (RING_OUT - 6.0 + mr / 2) + Z * z
        # Faces (local d, t, Z): +-z are the bow/stern faces (u along d, v
        # along t), +x the outer face (u along t, v along Z).
        ends = window_run(4.0, mw - 4.0, mr - 10.0, h=2.2, w=3.0, pitch=5.0, run=20, pause=0, rng=rng, along="u")
        ends += window_run(4.0, mw - 4.0, mr - 16.0, h=2.2, w=3.0, pitch=5.0, run=20, pause=0, rng=rng, along="u")
        ends = [(v, u, v2, u2, m) for (u, v, u2, v2, m) in ends]   # windows run along t (v), at radial u
        outer = [(6.0, mz / 2 - 4.0, mw - 6.0, mz / 2 + 4.0, "Accent")]
        outer += window_run(8.0, mw - 8.0, mz / 2 + 10.0, h=2.2, w=3.0, pitch=5.0, run=20, pause=0, rng=rng)
        outer += window_run(8.0, mw - 8.0, mz / 2 - 12.0, h=2.2, w=3.0, pitch=5.0, run=20, pause=0, rng=rng)
        p.add(painted_box(c, (mr, mw, mz), (d, t, Z), "HullLight", {"+z": ends, "-z": ends, "+x": outer}, chamfer=3.0))
        p.add(box(d * (RING_OUT - 6.0 + mr + 0.7) + Z * z, (2.4, 2.4, 2.4), (d, t, Z),
                  "NavRed" if d.x < 0 else "NavGreen"))
    return p


def build_spoke(name, deg, z, rng):
    """A spoke from the hub drum to the wheel: a blue stripe and window run
    down each side, plates fore and aft, frames every 80 m."""
    p = Part(name)
    d, t = radial(deg), tangent(deg)
    w, h = SPOKE_SIZE
    length = SPOKE_R1 - SPOKE_R0
    centre = d * ((SPOKE_R0 + SPOKE_R1) / 2) + Z * z
    # Faces in the box's local axes (d, t, Z): +-y are the sides seen from the
    # sectors (u along Z, v along the spoke), +-z the fore and aft faces
    # (u along the spoke, v across).
    side = [(h / 2 - 3.0, 30.0, h / 2 + 3.0, length - 30.0, "Accent")]
    side += window_run(40.0, length - 40.0, h / 2 + 8.0, rng=rng, along="v")
    end = plates(30.0, length - 30.0, 3.0, w - 3.0, 50.0, w, rng=rng, skip=0.35)
    p.add(painted_box(centre, (length, w, h), (d, t, Z), "Hull",
                      {"+y": side, "-y": side, "+z": end, "-z": end}))
    # Frames round the spoke, standing a little proud, clear of the windows.
    for k in range(7):
        r = SPOKE_R0 + 90.0 + 80.0 * k
        p.add(box(d * r + Z * z, (3.0, w + 3.0, h + 3.0), (d, t, Z), "HullLight"))
    # White strobes where the spoke meets the wheel.
    for sz in (-1, 1):
        p.add(box(d * (SPOKE_R1 - 30.0) + Z * (z + sz * (h / 2 + 0.7)), (2.4, 2.4, 2.4), (d, t, Z), "NavWhite"))
    return p


def build_tower(name, deg, rng):
    """A long block outside the rim tying the two wheels together, with a
    command block on its outer face: the station's main window areas."""
    p = Part(name)
    d, t = radial(deg), tangent(deg)
    r0, r1 = TOWER_R
    depth = r1 - r0
    length = 2 * TOWER_Z
    centre = d * ((r0 + r1) / 2)
    ch = 6.0
    bw, bh = TOWER_WIDTH - 2 * ch, length - 2 * ch
    # Outer face (+x: u along t, v along Z): two blue stripes down its length,
    # window bands near each wheel; the command block covers the middle.
    outer = [(10.0, 20.0, 18.0, bh - 20.0, "Accent"), (bw - 18.0, 20.0, bw - 10.0, bh - 20.0, "Accent")]
    for v in (bh / 2 - TOWER_Z + 30.0, bh / 2 + TOWER_Z - 44.0):
        for row in range(3):
            outer += window_run(24.0, bw - 24.0, v + row * 5.0, pitch=5.0, run=6, pause=2, rng=rng)
    # Side faces (+-y: u along Z, v across the depth): plates and a window row.
    sides = plates(20.0, bh - 20.0, 4.0, depth - 2 * ch - 4.0, 60.0, depth, mats=("Hull", "HullDark"), rng=rng,
                   skip=0.3)
    sides += window_run(30.0, bh - 30.0, depth / 2 - ch - 1.0, rng=rng)
    # Ends (+-z): a dark vent panel.
    ends = [(8.0, 8.0, depth - 2 * ch - 8.0, bw - 8.0, "Dark")]
    p.add(painted_box(centre, (depth, TOWER_WIDTH, length), (d, t, Z), "HullLight",
                      {"+x": outer, "+y": sides, "-y": sides, "+z": ends, "-z": ends}, chamfer=ch))
    # Command block: sunk 2 m into the outer face.
    bo, bwid, bhalf = TOWER_BLOCK
    bdepth = bo - (r1 - 2.0)
    bc = d * ((r1 - 2.0 + bo) / 2)
    cb = 4.0
    fw, fh = bwid - 2 * cb, 2 * bhalf - 2 * cb
    face = [(6.0, 6.0, fw - 6.0, fh - 6.0, "Hull")]
    for row in range(5):
        face += window_run(16.0, fw - 16.0, 20.0 + row * 7.0, h=2.5, w=3.5, pitch=6.0, run=10, pause=2, rng=rng)
    for row in range(5):
        face += window_run(16.0, fw - 16.0, fh - 36.0 + row * 7.0, h=2.5, w=3.5, pitch=6.0, run=10, pause=2,
                           rng=rng)
    face += [(fw / 2 - 30.0, fh / 2 - 14.0, fw / 2 + 30.0, fh / 2 + 14.0, "Accent"),
             (fw / 2 - 26.0, fh / 2 - 10.0, fw / 2 + 26.0, fh / 2 + 10.0, "HullLight")]
    bsides = window_run(20.0, fh - 20.0, bdepth / 2 - cb - 1.0, rng=rng)
    p.add(painted_box(bc, (bdepth, bwid, 2 * bhalf), (d, t, Z), "HullLight",
                      {"+x": face, "+y": bsides, "-y": bsides}, chamfer=cb))
    # Nav lights at the block's corners, white strobes at the tower's ends.
    nav = "NavRed" if d.x < -0.1 else ("NavGreen" if d.x > 0.1 else "NavWhite")
    for sz in (-1, 1):
        for st in (-1, 1):
            p.add(box(d * (bo + 0.7) + t * (st * (bwid / 2 - 10.0)) + Z * (sz * (bhalf - 10.0)),
                      (2.4, 2.4, 2.4), (d, t, Z), nav))
        p.add(box(d * ((r0 + r1) / 2) + Z * (sz * (TOWER_Z + 0.7)), (2.4, 2.4, 2.4), (d, t, Z), "NavWhite"))
    return p


def build_hangar(rng):
    """The bow block: a lit bay 136 x 76 m on its bow face framed in hazard
    yellow, an apron with approach lights under it, a bridge on top."""
    p = Part("Hangar")
    z0, z1 = HANGAR_Z
    sx, sy = HANGAR_SIZE
    ch = HANGAR_CHAMFER
    centre = Vector((0.0, 0.0, (z0 + z1) / 2))
    length = z1 - z0
    fw, fh = sx - 2 * ch, sy - 2 * ch          # bow face after the chamfer
    bw, bh = BAY_SIZE
    bu0, bv0 = fw / 2 - bw / 2, fh / 2 + BAY_Y - bh / 2
    bu1, bv1 = bu0 + bw, bv0 + bh
    bow = [(bu0 - 6.0, bv0 - 6.0, bu1 + 6.0, bv1 + 6.0, "Trim"), (bu0, bv0, bu1, bv1, None)]
    # A window row above the mouth.
    bow += window_run(bu0 - 4.0, bu1 + 4.0, bv1 + 12.0, pitch=5.0, run=10, pause=2, rng=rng)
    bow += plates(4.0, fw - 4.0, bv1 + 20.0, fh - 4.0, 40.0, 24.0, mats=("Hull", "HullDark"), rng=rng, skip=0.3)
    # Side faces (+-x: u along Y, v along Z): a blue band, two window rows, plates.
    sw, sh = fh, length - 2 * ch
    side = [(sw / 2 + 12.0, 12.0, sw / 2 + 22.0, sh - 12.0, "Accent")]
    side += window_run(16.0, sh - 16.0, sw / 2 - 4.0, rng=rng, along="v")
    side += window_run(16.0, sh - 16.0, sw / 2 + 2.0, rng=rng, along="v")
    greys = ("Hull", "HullDark")
    side += plates(10.0, sh - 10.0, 6.0, sw / 2 - 14.0, 44.0, 20.0, mats=greys, rng=rng, skip=0.35)
    # Top (+y: u along Z, v along X) and bottom (-y) plates; aft face plates.
    top = plates(10.0, sh - 10.0, 6.0, fw - 6.0, 44.0, 36.0, mats=greys, rng=rng, skip=0.4)
    bottom = plates(10.0, sh - 10.0, 6.0, fw - 6.0, 44.0, 36.0, mats=greys, rng=rng, skip=0.4)
    bottom += vents(20.0, sh - 20.0, fw / 2 - 2.0, h=4.0, w=12.0, pitch=18.0)
    aft = plates(6.0, fw - 6.0, 6.0, fh - 6.0, 40.0, 30.0, mats=greys, rng=rng, skip=0.3)
    p.add(painted_box(centre, (sx, sy, length), (X, Y, Z), "HullLight",
                      {"-z": bow, "+x": side, "-x": side, "+y": top, "-y": bottom, "+z": aft}, chamfer=ch))
    # The bay: four walls and a back wall, lit (solid HangarInterior) with
    # glow bars painted along the floor and ceiling and across the back.
    x0, x1 = -bw / 2, bw / 2
    y0, y1 = BAY_Y - bh / 2, BAY_Y + bh / 2
    zf, zb = z0, z0 + BAY_DEPTH
    bars = []
    for k in range(4):
        u = 12.0 + k * (bw - 24.0) / 3.0
        bars.append((u - 1.0, 4.0, u + 1.0, BAY_DEPTH - 4.0, "HangarGlow"))
    walls = [(0.0, 8.0, BAY_DEPTH, 11.0, "HangarGlow"), (0.0, bh - 11.0, BAY_DEPTH, bh - 8.0, "HangarGlow")]
    p.add(plane_face(Vector((x0, y0, zf)), X, Z, Y, bw, BAY_DEPTH, bars, "HangarInterior"))      # floor
    p.add(plane_face(Vector((x0, y1, zf)), X, Z, -Y, bw, BAY_DEPTH, bars, "HangarInterior"))     # ceiling
    p.add(plane_face(Vector((x0, y0, zf)), Z, Y, X, BAY_DEPTH, bh, walls, "HangarInterior"))     # left wall
    p.add(plane_face(Vector((x1, y0, zf)), Z, Y, -X, BAY_DEPTH, bh, walls, "HangarInterior"))    # right wall
    back = [(10.0, 6.0, bw - 10.0, bh - 14.0, "Dark"), (bw / 2 - 20.0, 8.0, bw / 2 + 20.0, 34.0, "HullDark"),
            (0.0, bh - 8.0, bw, bh - 5.0, "HangarGlow")]
    p.add(plane_face(Vector((x0, y0, zb)), X, Y, -Z, bw, bh, back, "HangarInterior"))            # back wall
    # Apron: a deck under the mouth, sunk into the bow face, with approach
    # lights painted along it and a hazard stripe across its front.
    aw, ah, al = APRON
    atop = y0 - 0.6
    ac = Vector((0.0, atop - ah / 2, z0 + 4.0 - (al + 4.0) / 2))
    # Its top face: u along Z (from the front edge), v along X.
    deck = [(6.0, aw / 2 - 1.0, al - 2.0, aw / 2 + 1.0, "HangarGlow")]
    for k in range(4):
        u = 10.0 + k * 16.0
        deck += [(u, 14.0, u + 1.6, 24.0, "HangarGlow"), (u, aw - 24.0, u + 1.6, aw - 14.0, "HangarGlow")]
    deck.append((0.0, 4.0, 3.0, aw - 4.0, "Trim"))
    p.add(painted_box(ac, (aw, ah, al + 4.0), (X, Y, Z), "HullLight", {"+y": deck, "-z": [(0.0, 0.0, aw, ah, "Trim")]}))
    # Harbour piers flanking the mouth: blocks standing forward of the bow
    # face (sunk 4 m into it) with approach light bars down their inner
    # faces, hazard stripes and a red (left) or green (right) light.
    pw_, ph_, pl_ = PIER_SIZE
    for sx_ in (-1, 1):
        pc = Vector((sx_ * (bw / 2 + PIER_GAP + pw_ / 2), BAY_Y + 4.0, z0 + 4.0 - pl_ / 2))
        inner = "-x" if sx_ > 0 else "+x"
        # +-x faces: u along Y, v along Z (from the aft end).
        bars = [(u, 4.0, u + 2.0, pl_ - 10.0, "HangarGlow") for u in (ph_ / 2 - 30.0, ph_ / 2 - 10.0, ph_ / 2 + 10.0)]
        bars += [(ph_ / 2 - 40.0, 0.0, ph_ / 2 + 20.0, 3.0, "Trim")]
        front = [(0.0, 0.0, pw_, 4.0, "Trim"), (0.0, ph_ - 4.0, pw_, ph_, "Trim"), (0.0, 4.0, 3.0, ph_ - 4.0, "Trim"),
                 (pw_ - 3.0, 4.0, pw_, ph_ - 4.0, "Trim")]
        top = [(0.0, 0.0, 4.0, pw_, "Trim")]
        p.add(painted_box(pc, (pw_, ph_, pl_), (X, Y, Z), "HullLight", {inner: bars, "-z": front, "+y": top}))
        p.add(box((pc.x, pc.y + ph_ / 2 + 0.7, pc.z - pl_ / 2 + 8.0), (2.4, 2.4, 2.4),
                  mat="NavRed" if sx_ < 0 else "NavGreen"))
    # Bridge on top: a smaller chamfered block with window rows, an antenna
    # mast with a red light, white strobes.
    bc = Vector((0.0, sy / 2 + 12.0, (z0 + z1) / 2 + 10.0))
    bsz = (84.0, 26.0, 90.0)
    bfront = window_run(6.0, bsz[0] - 6.0 - 2 * 3.0, 12.0, h=2.5, w=3.5, pitch=5.0, run=12, pause=2, rng=rng)
    bside = window_run(6.0, bsz[2] - 6.0 - 6.0, 12.0, h=2.5, w=3.5, pitch=5.0, run=12, pause=2, rng=rng, along="v")
    p.add(painted_box(bc, bsz, (X, Y, Z), "HullLight", {"-z": bfront, "+x": bside, "-x": bside,
                                                         "+y": [(10.0, 10.0, 60.0, 48.0, "Accent")]}, chamfer=3.0))
    top_y = bc.y + bsz[1] / 2
    p.add(beam((0.0, top_y - 2.0, bc.z), (0.0, top_y + 34.0, bc.z), 1.8, 1.8, up=X, mat="HullLight"))
    p.add(box((0.0, top_y + 35.0, bc.z), (2.6, 2.6, 2.6), mat="NavRed"))
    for sx_ in (-1, 1):
        p.add(box((sx_ * (bsz[0] / 2 - 6.0), top_y + 0.7, bc.z - bsz[2] / 2 + 8.0), (2.4, 2.4, 2.4), mat="NavWhite"))
    return p


def build_dock(name, deg, rng):
    """A docking arm in the harbour: a beam from the waist to a clamp block
    striped in hazard yellow, a white light on its end."""
    p = Part(name)
    d, t = radial(deg), tangent(deg)
    r0, r1 = DOCK_R
    p.add(beam(d * r0 + Z * DOCK_Z, d * (r1 + 2.0) + Z * DOCK_Z, 14.0, 14.0, up=Z, mat="HullLight"))
    cr, ct, cz = DOCK_CLAMP
    cc = d * (r1 + cr / 2) + Z * DOCK_Z
    # Clamp faces (local axes d, t, Z): stripes round it, dark pads on the
    # faces that look along Z (where a ship would berth).
    stripe_t = [(2.0, 0.0, 6.0, ct, "Trim"), (cz - 6.0, 0.0, cz - 2.0, ct, "Trim")]       # +-y: u along Z, v along t
    stripe_x = [(0.0, 2.0, ct, 6.0, "Trim"), (0.0, cz - 6.0, ct, cz - 2.0, "Trim")]       # +x: u along t, v along Z
    pad = [(4.0, 4.0, cr - 4.0, ct - 4.0, "Dark"), (2.0, 0.0, cr - 2.0, 2.5, "Trim"), (2.0, ct - 2.5, cr - 2.0, ct, "Trim")]
    p.add(painted_box(cc, (cr, ct, cz), (d, t, Z), "HullLight",
                      {"+y": stripe_t, "-y": stripe_t, "+x": stripe_x, "+z": pad, "-z": pad}))
    p.add(box(cc + d * (cr / 2 + 0.7), (2.4, 2.4, 2.4), (d, t, Z), "NavWhite"))
    return p


def build_solar(name, deg, rng):
    """A solar arm at the stern: a beam out from the neck carrying four
    panels in the plane of the arm and the axis (edge-on from the bow)."""
    p = Part(name)
    d, t = radial(deg), tangent(deg)
    r0, r1 = SOLAR_R
    p.add(beam(d * (r0 - 8.0) + Z * SOLAR_Z, d * r1 + Z * SOLAR_Z, 12.0, 12.0, up=Z, mat="HullLight"))
    pw, pz = SOLAR_PANEL
    r = r0 + 50.0
    for k in range(SOLAR_PANELS):
        c = d * (r + pw / 2) + Z * SOLAR_Z
        # Cells painted on both faces (u along Z, v along the arm): a frame
        # line and dividers in the hull tone.
        grid = [(1.5, 1.5, pz - 1.5, pw - 1.5, "Solar")]
        grid += [(pz / 2 - 0.5, 1.5, pz / 2 + 0.5, pw - 1.5, "HullLight")]
        grid += [(1.5, pw * q - 0.5, pz - 1.5, pw * q + 0.5, "HullLight") for q in (0.25, 0.5, 0.75)]
        p.add(painted_box(c, (pw, 1.6, pz), (d, t, Z), "HullLight", {"+y": grid, "-y": grid}))
        r += pw + 10.0
    tip = "NavRed" if d.x < -0.1 else ("NavGreen" if d.x > 0.1 else "NavWhite")
    p.add(box(d * (r1 + 0.7) + Z * SOLAR_Z, (2.6, 2.6, 2.6), (d, t, Z), tip))
    return p


def build_dish(rng):
    """The comms dish at the stern: a mast off the neck, a parabolic dish
    facing aft, a feed horn on three struts."""
    p = Part("Dish")
    n = 32
    # The mast runs on through the dish's centre hole (inner radius 12), so
    # the dish is held by it rather than touching its end.
    p.add(lathe([(DISH_Z - 6, 44.0), (DISH_Z + 20, 30.0), (DISH_Z + 62, 20.0)], n, base="HullLight"), "HullLight")
    base = DISH_Z + 46.0
    depth, rim, inner, thick = 30.0, 110.0, 12.0, 4.0
    front = [(base + 6 + depth * (r / rim) ** 2, r) for r in [inner + (rim - inner) * k / 10 for k in range(11)]]
    back = [(z - thick, r) for z, r in reversed(front)]
    p.add(lathe(front + back, n, closed=True, base="HullLight"), "HullLight")
    z0, z1 = front[-1][0] - thick - 0.5, front[-1][0] + 0.5
    p.add(lathe([(z0, rim - 3), (z0, rim + 0.8), (z1, rim + 0.8), (z1, rim - 3)], n, closed=True, base="Accent"),
          "Accent")
    focus = base + 6 + rim * rim / (4 * depth)
    for k in range(3):
        a = TAU * k / 3 + math.pi / 2
        # Each strut starts 3 m under the dish's surface at its foot.
        foot_r = rim * 0.94
        foot_z = base + 6 + depth * (foot_r / rim) ** 2 - 3.0
        rim_pt = Vector((math.cos(a) * foot_r, math.sin(a) * foot_r, foot_z))
        p.add(beam(rim_pt, (0, 0, focus - 6), 1.8, 1.8, up=Z, mat="HullLight"))
    p.add(lathe([(focus - 9, 7.0), (focus + 2, 4.0)], 12, base="Dark"), "Dark")
    p.add(box((0, 0, focus + 3), (2.6, 2.6, 2.6), mat="NavWhite"))
    return p


def build():
    """Builds every component into the SpaceStationV2 collection of the
    current scene (removing an earlier build) and returns the objects."""
    scene = bpy.context.scene
    col = bpy.data.collections.get("SpaceStationV2")
    if col is None:
        col = bpy.data.collections.new("SpaceStationV2")
        scene.collection.children.link(col)
    for o in list(col.objects):
        bpy.data.objects.remove(o)
    for me in list(bpy.data.meshes):
        if me.users == 0:
            bpy.data.meshes.remove(me)
    rng = random.Random(2077)   # seeded: re-running gives the same windows
    parts = [build_core(rng), build_ring("RingFore", -RING_Z, rng), build_ring("RingAft", RING_Z, rng)]
    for i, a in enumerate(SPOKE_ANGLES):
        parts.append(build_spoke("SpokeF%d" % i, a, -RING_Z, rng))
        parts.append(build_spoke("SpokeA%d" % i, a, RING_Z, rng))
    parts += [build_tower("Tower%d" % i, a, rng) for i, a in enumerate(SPOKE_ANGLES)]
    parts.append(build_hangar(rng))
    parts += [build_dock("Dock%d" % i, a, rng) for i, a in enumerate(MID_ANGLES)]
    parts += [build_solar("Solar%d" % i, a, rng) for i, a in enumerate(SPOKE_ANGLES)]
    parts.append(build_dish(rng))
    return [part.build(col) for part in parts]


# ---------------------------------------------------------------- AI proxies
def spine_radius(z):
    """The spine's radius at z (0 beyond its ends)."""
    for (z0, r0), (z1, r1) in zip(SPINE_PROFILE, SPINE_PROFILE[1:]):
        if z0 <= z <= z1:
            if z1 == z0:
                return max(r0, r1)
            return r0 + (r1 - r0) * (z - z0) / (z1 - z0)
    return 0.0


def proxies():
    """AI avoidance spheres (x, y, z, radius), game coordinates. Each sphere
    encloses the slice of the part it covers (checked by check_proxies()):
    chains round both wheels, rows down the spokes and towers, slices of the
    spine, the hangar block, docking arms, solar panels and the dish. The AI
    pads each by 1.3x plus a margin, so the openings stay open."""
    spheres = []
    # Wheels: 48 spheres of 80 m each (7.5 degrees, 99 m apart), which also
    # enclose the modules and radiators on the rim (MODULE_ANGLES).
    ring_mid = (RING_IN + RING_OUT) / 2
    n = 48
    for z in (-RING_Z, RING_Z):
        for k in range(n):
            a = TAU * k / n
            spheres.append((ring_mid * math.cos(a), ring_mid * math.sin(a), z, 80.0))
    # Spokes: section 50 x 40 (frames 53 x 43), spheres of 46 every 58 m.
    w, h = SPOKE_SIZE
    sp_half = math.hypot(w / 2 + 1.5, h / 2 + 1.5)
    sp_radius = 46.0
    sp_step = 2.0 * math.sqrt(sp_radius ** 2 - sp_half ** 2) * 0.95
    for deg in SPOKE_ANGLES:
        d = radial(deg)
        for z in (-RING_Z, RING_Z):
            r = HUB_R + 12.0
            while r < SPOKE_R1 - 12.0:
                p = d * r
                spheres.append((p.x, p.y, z, sp_radius))
                r += sp_step
        # Towers: the bar plus its command block, spheres of 94 every 76 m.
        tr = (TOWER_R[0] + TOWER_BLOCK[0]) / 2
        tw_radius = 94.0
        tw_step = 76.0
        count = math.ceil((2 * TOWER_Z - 60.0) / tw_step) + 1
        for k in range(count):
            z = -TOWER_Z + 30.0 + (2 * TOWER_Z - 60.0) * k / (count - 1)
            p = d * tr
            spheres.append((p.x, p.y, z, tw_radius))
        # Solar arms: the inner beam, then one sphere per panel.
        p = d * (SOLAR_R[0] + 24.0)
        spheres.append((p.x, p.y, SOLAR_Z, 30.0))
        pw, pz = SOLAR_PANEL
        r = SOLAR_R[0] + 50.0
        for k in range(SOLAR_PANELS):
            p = d * (r + pw / 2)
            spheres.append((p.x, p.y, SOLAR_Z, round(math.hypot(pw / 2 + 1.0, pz / 2 + 1.0) + 1.0)))
            r += pw + 10.0
        p = d * (SOLAR_R[1] - 6.0)
        spheres.append((p.x, p.y, SOLAR_Z, 14.0))
    # Spine: a sphere per 50 m slice, enclosing the widest part of it.
    slice_ = 50.0
    z = SPINE_PROFILE[0][0] + slice_ / 2
    while z < SPINE_PROFILE[-1][0]:
        half = slice_ / 2
        widest = max(spine_radius(z + t * half / 4) for t in range(-4, 5)) + 1.0
        spheres.append((0.0, 0.0, z, round(math.hypot(widest, half) + 2.0)))
        z += slice_
    # Docking arms: three along the beam, one on the clamp.
    for deg in MID_ANGLES:
        d = radial(deg)
        for r in (112.0, 140.0):
            spheres.append((d.x * r, d.y * r, DOCK_Z, 24.0))
        r = DOCK_R[1] + DOCK_CLAMP[0] / 2
        spheres.append((d.x * r, d.y * r, DOCK_Z, 46.0))
    # The hangar block (eight), its bridge, the apron (two), the piers (two).
    z0, z1 = HANGAR_Z
    for x in (-80.0, 80.0):
        for y in (-50.0, 50.0):
            for z in (z0 + 45.0, z1 - 45.0):
                spheres.append((x, y, z, 108.0))
    spheres.append((0.0, HANGAR_SIZE[1] / 2 + 16.0, (z0 + z1) / 2 + 10.0, 54.0))
    for x in (-40.0, 40.0):
        spheres.append((x, BAY_Y - BAY_SIZE[1] / 2 - 5.0, z0 - 40.0, 56.0))
    for x in (-1.0, 1.0):
        spheres.append((x * (BAY_SIZE[0] / 2 + PIER_GAP + PIER_SIZE[0] / 2), BAY_Y + 4.0, z0 + 4.0 - PIER_SIZE[2] / 2, 60.0))
    # The dish: mast and dish.
    spheres.append((0.0, 0.0, DISH_Z + 22.0, 46.0))
    spheres.append((0.0, 0.0, DISH_Z + 76.0, 114.0))
    return spheres


def write_proxies(spheres):
    text = ", ".join("Vector4(%g, %g, %g, %g)" % tuple(round(c, 1) for c in s) for s in spheres)
    with open(os.path.join(HERE, "proxies_v2.txt"), "w") as f:
        f.write("proxies = Array[Vector4]([%s])\n" % text)
    return len(spheres)


# ---------------------------------------------------------------- checks
def to_game(v):
    """Blender (Z up) to game (Y up, -Z forward)."""
    return Vector((v.x, v.z, -v.y))


def is_solid(mat):
    name = mat.name[len("Station_"):] if mat.name.startswith("Station_") else mat.name
    return name not in NON_SOLID


def islands(obj):
    """The object's connected shells: a list of dicts with the island's
    polygon indices, its vertices (game coordinates), triangles and whether
    it's solid (any face in a solid material)."""
    me = obj.data
    me.calc_loop_triangles()
    parent = list(range(len(me.vertices)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for poly in me.polygons:
        vs = poly.vertices
        for k in range(1, len(vs)):
            a, b = find(vs[0]), find(vs[k])
            if a != b:
                parent[a] = b
    groups = {}
    for poly in me.polygons:
        groups.setdefault(find(poly.vertices[0]), []).append(poly.index)
    verts = [to_game(obj.location + v.co) for v in me.vertices]
    tris_by_poly = {}
    for t in me.loop_triangles:
        tris_by_poly.setdefault(t.polygon_index, []).append(tuple(t.vertices))
    out = []
    for polys in groups.values():
        tris = [tv for pi in polys for tv in tris_by_poly[pi]]
        solid = any(is_solid(me.materials[me.polygons[pi].material_index]) for pi in polys)
        used = sorted({i for tv in tris for i in tv})
        lo = Vector((min(verts[i].x for i in used), min(verts[i].y for i in used), min(verts[i].z for i in used)))
        hi = Vector((max(verts[i].x for i in used), max(verts[i].y for i in used), max(verts[i].z for i in used)))
        out.append({"obj": obj.name, "polys": polys, "tris": tris, "verts": verts, "solid": solid,
                    "lo": lo, "hi": hi, "mesh": me})
    return out


def check_outward(all_islands):
    """Normals point outwards: every closed shell's signed volume is positive
    (the game draws front faces only)."""
    bad = []
    for isl in all_islands:
        verts = isl["verts"]
        volume = sum(verts[a].dot(verts[b].cross(verts[c])) for a, b, c in isl["tris"]) / 6.0
        if volume <= 0.0:
            bad.append((isl["obj"], volume, isl["lo"]))
    print("CHECK outward normals: %d of %d shells inside out" % (len(bad), len(all_islands)))
    for name, volume, lo in bad[:10]:
        print("   INSIDE OUT %s shell at %s (volume %.1f)" % (name, tuple(round(c) for c in lo), volume))
    return not bad


def boxes_touch(a, b, pad=0.05):
    return all(a["lo"][k] - pad <= b["hi"][k] and b["lo"][k] - pad <= a["hi"][k] for k in range(3))


def check_attached(all_islands):
    """Nothing floats: every shell must overlap another, and every shell must
    be reachable from the Core's spine through overlaps."""
    bvhs = [BVHTree.FromPolygons(isl["verts"], isl["tris"]) for isl in all_islands]
    n = len(all_islands)
    adj = [set() for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if boxes_touch(all_islands[i], all_islands[j]) and bvhs[i].overlap(bvhs[j]):
                adj[i].add(j)
                adj[j].add(i)
    core = max((i for i in range(n) if all_islands[i]["obj"] == "Station_Core"),
               key=lambda i: len(all_islands[i]["tris"]))
    seen, stack = {core}, [core]
    while stack:
        i = stack.pop()
        for j in adj[i]:
            if j not in seen:
                seen.add(j)
                stack.append(j)
    loose = [i for i in range(n) if i not in seen]
    print("CHECK attached: %d shells, %d not reachable from the spine" % (n, len(loose)))
    for i in loose[:20]:
        isl = all_islands[i]
        print("   FLOATING %s shell of %d tris at %s..%s (%s)" % (
            isl["obj"], len(isl["tris"]), tuple(round(c) for c in isl["lo"]), tuple(round(c) for c in isl["hi"]),
            "solid" if isl["solid"] else "light"))
    return not loose


def check_closed(objects):
    """Every shell closed: no edge with other than two faces."""
    ok = True
    for o in objects:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bad = [e for e in bm.edges if len(e.link_faces) != 2]
        if bad:
            ok = False
            e = bad[0]
            print("   OPEN %s: %d non-manifold edges, e.g. at %s" % (
                o.name, len(bad), tuple(round(c, 1) for c in to_game(o.location + e.verts[0].co))))
        bm.free()
    print("CHECK closed meshes:", "all closed" if ok else "FAILED")
    return ok


def poly_overlap_2d(a, b, eps=0.03):
    """True if two simple 2D polygons share interior area (not just an edge
    or a corner): an edge pair crosses properly, or a vertex of one lies
    inside the other, clear of its boundary."""
    def cross(o, p, q):
        return (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])

    def crosses(p0, p1, q0, q1):
        d1, d2 = cross(q0, q1, p0), cross(q0, q1, p1)
        d3, d4 = cross(p0, p1, q0), cross(p0, p1, q1)
        if abs(d1) < 1e-9 or abs(d2) < 1e-9 or abs(d3) < 1e-9 or abs(d4) < 1e-9:
            return False
        return (d1 > 0) != (d2 > 0) and (d3 > 0) != (d4 > 0)

    def inside(pt, poly):
        x, y = pt
        hit = False
        n = len(poly)
        for i in range(n):
            (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % n]
            # Distance to the edge: on the boundary doesn't count.
            dx, dy = x1 - x0, y1 - y0
            ln = math.hypot(dx, dy)
            if ln > 1e-9:
                t = max(0.0, min(1.0, ((x - x0) * dx + (y - y0) * dy) / (ln * ln)))
                if math.hypot(x - (x0 + t * dx), y - (y0 + t * dy)) < eps:
                    return False
            if (y0 > y) != (y1 > y):
                xi = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
                if xi > x:
                    hit = not hit
        return hit

    na, nb = len(a), len(b)
    for i in range(na):
        for j in range(nb):
            if crosses(a[i], a[(i + 1) % na], b[j], b[(j + 1) % nb]):
                return True
    return any(inside(p, b) for p in a) or any(inside(p, a) for p in b)


def check_shared_planes(all_islands):
    """No two faces of different shells lie in one plane where they overlap."""
    buckets = {}
    for idx, isl in enumerate(all_islands):
        me, verts = isl["mesh"], isl["verts"]
        for pi in isl["polys"]:
            poly = me.polygons[pi]
            n = to_game(poly.normal)
            if n.length < 0.5:
                continue
            c = sum((verts[i] for i in poly.vertices), Vector()) / len(poly.vertices)
            off = n.dot(c)
            key = (round(n.x, 2), round(n.y, 2), round(n.z, 2), round(off / 0.5))
            buckets.setdefault(key, []).append((idx, pi))
    bad = []
    for key, faces in buckets.items():
        if len({f[0] for f in faces}) < 2:
            continue
        n = Vector(key[:3]).normalized()
        u = (X if abs(n.x) < 0.9 else Y).cross(n).normalized()
        v = n.cross(u)
        polys2d = []
        for idx, pi in faces:
            isl = all_islands[idx]
            pts = [isl["verts"][i] for i in isl["mesh"].polygons[pi].vertices]
            polys2d.append((idx, pi, [(p.dot(u), p.dot(v)) for p in pts], pts[0].dot(n)))
        for a in range(len(polys2d)):
            for b in range(a + 1, len(polys2d)):
                ia, pa, qa, oa = polys2d[a]
                ib, pb, qb, ob = polys2d[b]
                if ia == ib or abs(oa - ob) > 0.02:
                    continue
                if poly_overlap_2d(qa, qb):
                    bad.append((all_islands[ia]["obj"], all_islands[ib]["obj"], qa[0], n))
    print("CHECK shared planes: %d overlapping coplanar face pairs" % len(bad))
    for oa, ob, q, n in bad[:15]:
        print("   SHARED %s / %s, normal %s" % (oa, ob, tuple(round(c, 2) for c in n)))
    return not bad


def solid_bvh(all_islands):
    verts, tris = [], []
    for isl in all_islands:
        if not isl["solid"]:
            continue
        base = len(verts)
        verts += isl["verts"]
        tris += [tuple(base + i for i in t) for t in isl["tris"]]
    return BVHTree.FromPolygons(verts, tris), verts, tris


def check_openings(bvh):
    """Rays along each opening's axis over a 10 m grid of its cross-section
    must cross the whole box without hitting anything solid."""
    ok = True
    for name, centre, size, axis in OPENINGS:
        k = "xyz".index(axis)
        ku, kv = (k + 1) % 3, (k + 2) % 3
        d = Vector((0, 0, 0))
        d[k] = 1.0
        hits, total = 0, 0
        nu, nv = int(size[ku] // 10), int(size[kv] // 10)
        first = None
        for i in range(nu + 1):
            for j in range(nv + 1):
                o = Vector(centre)
                o[ku] = centre[ku] - size[ku] / 2 + i * size[ku] / nu
                o[kv] = centre[kv] - size[kv] / 2 + j * size[kv] / nv
                o[k] = centre[k] - size[k] / 2
                hit = bvh.ray_cast(o, d, size[k])
                total += 1
                if hit[0] is not None:
                    hits += 1
                    first = first or hit[0]
        print("CHECK opening %-12s %d x %d m: %d of %d rays blocked%s" % (
            name, size[ku], size[kv], hits, total, "" if not first else ", first at %s" % (tuple(round(c) for c in first),)))
        ok = ok and hits == 0
    return ok


def check_proxies(spheres, all_islands):
    """Every solid surface inside some sphere: sampled at every vertex, face
    centre and a grid over large triangles."""
    kd = KDTree(len(spheres))
    for i, s in enumerate(spheres):
        kd.insert(Vector(s[:3]), i)
    kd.balance()
    max_r = max(s[3] for s in spheres)

    def covered(p):
        for co, i, dist in kd.find_range(p, max_r):
            if dist <= spheres[i][3]:
                return True
        return False

    samples, missed = 0, []
    for isl in all_islands:
        if not isl["solid"]:
            continue
        verts = isl["verts"]
        for t in isl["tris"]:
            a, b, c = (verts[i] for i in t)
            longest = max((a - b).length, (b - c).length, (c - a).length)
            n = max(1, min(40, int(longest / 12.0)))
            for i in range(n + 1):
                for j in range(n + 1 - i):
                    k = n - i - j
                    p = (a * i + b * j + c * k) / n
                    samples += 1
                    if not covered(p):
                        missed.append((isl["obj"], p))
    print("CHECK proxies: %d spheres, %d of %d samples uncovered" % (len(spheres), len(missed), samples))
    by_obj = {}
    for name, p in missed:
        by_obj.setdefault(name, []).append(p)
    for name, pts in by_obj.items():
        print("   UNCOVERED %s: %d, e.g. %s" % (name, len(pts), tuple(round(c) for c in pts[0])))
    return not missed


def report_counts(objects):
    total_solid, total_light, reach = 0, 0, 0.0
    print("--- triangles per component (solid + non-solid) ---")
    for o in objects:
        me = o.data
        solid = light = 0
        for poly in me.polygons:
            n = len(poly.vertices) - 2
            if is_solid(me.materials[poly.material_index]):
                solid += n
            else:
                light += n
        for v in me.vertices:
            reach = max(reach, (o.location + v.co).length)
        total_solid += solid
        total_light += light
        print("  %-18s %6d + %5d" % (o.name, solid, light))
    print("  TOTAL %d solid + %d non-solid = %d triangles; bounding radius %.1f m" % (
        total_solid, total_light, total_solid + total_light, reach))
    return total_solid + total_light, reach


def run_checks(objects, spheres):
    results = {}
    results["closed"] = check_closed(objects)
    all_islands = [isl for o in objects for isl in islands(o)]
    results["outward"] = check_outward(all_islands)
    results["attached"] = check_attached(all_islands)
    results["planes"] = check_shared_planes(all_islands)
    bvh, _, _ = solid_bvh(all_islands)
    results["openings"] = check_openings(bvh)
    results["proxies"] = check_proxies(spheres, all_islands)
    print("CHECK summary:", ", ".join("%s %s" % (k, "ok" if v else "FAILED") for k, v in results.items()))
    return results


# ---------------------------------------------------------------- previews
def preview_marker(collection, pos, name):
    """A 6 m fighter-sized wedge (orange) for scale in the previews; not exported."""
    me = bpy.data.meshes.new(name)
    v, f, _ = box((0, 0, 0), (6.0, 1.6, 6.0))
    me.from_pydata([G(p) for p in v], [], f)
    m = bpy.data.materials.get("PreviewMarker") or bpy.data.materials.new("PreviewMarker")
    m.diffuse_color = (1.0, 0.35, 0.05, 1.0)
    me.materials.append(m)
    o = bpy.data.objects.new(name, me)
    o.location = G(Vector(pos))
    collection.objects.link(o)
    return o


def render_views(objects):
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_WORKBENCH'
    shading = scene.display.shading
    shading.light = 'STUDIO'
    shading.color_type = 'MATERIAL'
    shading.show_object_outline = True
    shading.object_outline_color = (0.0, 0.0, 0.0)
    shading.show_cavity = True
    shading.cavity_type = 'BOTH'
    shading.show_shadows = False
    scene.display.render_aa = '8'
    scene.render.film_transparent = False
    world = bpy.data.worlds.get("PreviewWorld") or bpy.data.worlds.new("PreviewWorld")
    world.color = (0.09, 0.10, 0.12)
    scene.world = world
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100

    col = bpy.data.collections.get("PreviewV2")
    if col is None:
        col = bpy.data.collections.new("PreviewV2")
        scene.collection.children.link(col)
    for o in list(col.objects):
        bpy.data.objects.remove(o)
    cam_data = bpy.data.cameras.new("PreviewCamera")
    cam = bpy.data.objects.new("PreviewCamera", cam_data)
    col.objects.link(cam)
    scene.camera = cam
    cam_data.clip_end = 12000.0
    # Scale markers: a fighter beside the hangar apron and one off a tower.
    preview_marker(col, (30.0, -30.0, -640.0), "Marker_Hangar")
    preview_marker(col, (40.0, 880.0, -60.0), "Marker_Tower")
    preview_marker(col, (700.0, 180.0, -300.0), "Marker_Ring")

    def shoot(name, loc, target, lens=35.0, ortho=None):
        cam.location = G(Vector(loc))
        direction = (G(Vector(target)) - cam.location).normalized()
        cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
        if ortho:
            cam_data.type = 'ORTHO'
            cam_data.ortho_scale = ortho
        else:
            cam_data.type = 'PERSP'
            cam_data.lens = lens
        scene.render.filepath = os.path.join(PREVIEW_DIR, name + ".png")
        bpy.ops.render.render(write_still=True)
        print("rendered", name)

    shoot("hero", (1500.0, 900.0, -1900.0), (0.0, 0.0, -60.0), lens=32.0)
    shoot("front", (0.0, 0.0, -4000.0), (0.0, 0.0, 0.0), ortho=1900.0)
    shoot("side", (4000.0, 0.0, 0.0), (0.0, 0.0, 0.0), ortho=1900.0)
    shoot("top", (0.0, 4000.0, 0.0), (0.0, 0.0, 1.0), ortho=1900.0)
    shoot("rear", (-1400.0, 800.0, 2000.0), (0.0, 0.0, 100.0), lens=32.0)
    shoot("hangar", (160.0, -30.0, -760.0), (0.0, -8.0, -560.0), lens=35.0)
    shoot("strafe_tower", (90.0, 900.0, -150.0), (-20.0, 846.0, 60.0), lens=28.0)
    shoot("strafe_ring", (640.0, 260.0, -345.0), (753.0, 106.0, -258.0), lens=28.0)
    shoot("strafe_spoke", (40.0, 430.0, -300.0), (-40.0, 560.0, -250.0), lens=28.0)
    for name, centre, size, axis in OPENINGS:
        k = "xyz".index(axis)
        loc = Vector(centre)
        loc[k] -= 1500.0
        if axis == "z":
            loc[k] = -1600.0
        shoot("opening_" + name.replace(" ", "_"), tuple(loc), tuple(centre), lens=28.0)
    render_textured(col, shoot)


def render_textured(col, shoot):
    """Close-ups in EEVEE (Workbench shows flat colours only): the textures
    and the glow under one sun, as tex_*.png."""
    scene = bpy.context.scene
    try:
        scene.render.engine = 'BLENDER_EEVEE'
    except TypeError:
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
    scene.eevee.taa_render_samples = 16
    scene.view_settings.view_transform = 'Standard'
    world = scene.world
    world.use_nodes = True
    bg = next((n for n in world.node_tree.nodes if n.type == 'BACKGROUND'), None)
    if bg:
        bg.inputs[0].default_value = (0.09, 0.10, 0.12, 1.0)
        bg.inputs[1].default_value = 1.0
    sun = bpy.data.lights.get("PreviewSun") or bpy.data.lights.new("PreviewSun", 'SUN')
    sun.energy = 3.0
    sun_obj = bpy.data.objects.new("PreviewSun", sun)
    col.objects.link(sun_obj)
    # From above and the bow, the side the hero view looks from.
    sun_obj.rotation_euler = G(Vector((-0.5, -0.8, 0.45))).normalized().to_track_quat('-Z', 'Y').to_euler()
    shoot("tex_hero", (1500.0, 900.0, -1900.0), (0.0, 0.0, -60.0), lens=32.0)
    shoot("tex_hangar", (160.0, -30.0, -760.0), (0.0, -8.0, -560.0), lens=35.0)
    shoot("tex_tower", (90.0, 900.0, -150.0), (-20.0, 846.0, 60.0), lens=28.0)
    shoot("tex_ring", (640.0, 260.0, -345.0), (753.0, 106.0, -258.0), lens=28.0)
    shoot("tex_drum", (260.0, 120.0, -330.0), (60.0, 30.0, -250.0), lens=35.0)
    shoot("tex_dock", (250.0, 60.0, -150.0), (156.0, 90.0, 0.0), lens=35.0)
    shoot("tex_solar", (420.0, 250.0, 200.0), (0.0, 300.0, 370.0), lens=35.0)
    shoot("tex_far", (2600.0, 1400.0, -2800.0), (0.0, 0.0, 0.0), lens=40.0)


# ---------------------------------------------------------------- export
def export(objects):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objects:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "space_station_v2.glb"), export_format="GLB",
                              use_selection=True, use_active_scene=True, export_apply=True, export_yup=True,
                              export_materials="EXPORT", export_cameras=False, export_lights=False)
    print("exported space_station_v2.glb")


def main():
    if bpy.app.background:
        # Our own session: start from an empty scene.
        for o in list(bpy.data.objects):
            bpy.data.objects.remove(o)
    scene = bpy.context.scene
    scene.name = "SpaceStationV2"
    station = build()
    print("space station v2 built:", len(station), "objects")
    total, reach = report_counts(station)
    spheres = proxies()
    print("AI proxies written:", write_proxies(spheres))
    if CHECKS:
        run_checks(station, spheres)
    if RENDER:
        render_views(station)
    if EXPORT:
        export(station)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "space_station_v2.blend"))
    print("saved space_station_v2.blend")


main()
