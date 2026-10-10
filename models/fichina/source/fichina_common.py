"""Shared by the Fichina map's Blender scripts: the map's size and grid, the
game/Blender coordinate conversion, the palette, the prop groups and the
helpers every script needs.

The helpers are Corneria's (models/corneria/source/corneria_common.py), run
here with Fichina's values: this file executes that one, then sets its own
paths, palette, groups and markers. It also registers itself as
"corneria_common" and puts Corneria's source folders on the path, so the
shared scripts (settlement.py, fields.py, kit/kit_tools.py, export_corneria.py
and greybox_kit.py) work on Fichina when a Fichina script imports this module
first. Import it before any of them.

The map's master copy is fichina.blend (next to this file). The kit pieces
live in kit.blend, one collection per piece, linked into the map. Scripts:
    greybox.py          placeholder kit pieces (never overwrites a real model)
    new_map.py          creates fichina.blend, empty, if it doesn't exist
    gen_*.py            the generators (terrain, colony, outposts, landmarks, wilds)
    export_fichina.py   reads fichina.blend and writes the game's files

Game coordinates: Godot's, +X east, +Y up, -Z north, metres. Blender's: Z up,
+Y north. G() converts a game point to Blender; game_matrix() a Blender
transform to the game.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CORNERIA_SOURCE = os.path.join(os.path.dirname(os.path.dirname(HERE)), "corneria", "source")

# Corneria's helpers, defined in this module's namespace: they read the
# constants below when called, so they work on Fichina's.
_base = os.path.join(CORNERIA_SOURCE, "corneria_common.py")
with open(_base, encoding="utf-8") as _f:
    exec(compile(_f.read(), _base, "exec"))

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(HERE)          # models/fichina: the exported files
MAP_FILE = os.path.join(HERE, "fichina.blend")
KIT_FILE = os.path.join(HERE, "kit.blend")
NAME = "fichina"
MATERIAL_PREFIX = "Fichina_"

SIZE = 16000.0                        # the map: SIZE x SIZE metres, centred on the origin
HALF = SIZE / 2
CELL = 25.0                           # terrain grid spacing, as Terrain.cell_size
POINTS = int(SIZE / CELL) + 1         # grid points per side
PROP_TILE = 500.0                     # exported one-off geometry is cut into squares this size

# Prop groups: one collection each under "Props" in the map. solid: gets
# collision in the game (MapProps.solid_groups); structure: the AI flies over
# it (rasterised into the map's structure heights).
GROUPS = {
    "Colony": dict(solid=True, structure=True),      # the colony round the Climate Control Center
    "Outposts": dict(solid=True, structure=True),    # the spaceport, research and mining outposts, masts
    "Landmarks": dict(solid=True, structure=True),   # ice spires, the ice arches, the frozen falls
    "Rocks": dict(solid=True, structure=True),       # boulders, outcrops, seracs
    "Water": dict(solid=True, structure=False),      # frozen lakes above the sea-level plane (sheets)
    "Roads": dict(solid=False, structure=False),     # flat on the ground
    "Trees": dict(solid=False, structure=False),     # flown through
}
WATER_MATERIAL = "Fichina_Water"      # the game gives faces with it the level's water (ice) material
MARKERS = ("Start", "IntroStart", "IntroCameraSpot", "GreatFox", "ClimateCenter")

# Colours: sRGB, as they look in the game; material() converts them to linear
# for Blender and glTF. (sRGB colour, emission strength.) Art direction in
# ../ASSETS.md: white and pale-grey insulated panels, dark metal, blue glass,
# Antarctic-station signal orange, warm lit windows for the polar dusk, ice
# blues, cold dark rock, dark snow-laden pines.
PALETTE = {
    # Buildings.
    "Panel": ((0.85, 0.87, 0.9), 0), "PanelGrey": ((0.6, 0.63, 0.68), 0),
    "Steel": ((0.6, 0.62, 0.66), 0), "DarkMetal": ((0.28, 0.3, 0.35), 0),
    "Concrete": ((0.64, 0.64, 0.66), 0), "RoofDark": ((0.34, 0.36, 0.41), 0),
    "Glass": ((0.3, 0.55, 0.8), 0), "GlassDark": ((0.16, 0.3, 0.5), 0),
    "WindowLit": ((1.0, 0.78, 0.45), 2.5), "Greenhouse": ((0.62, 0.95, 0.55), 2.0),
    "Signal": ((0.9, 0.32, 0.14), 0), "SignalYellow": ((0.95, 0.78, 0.2), 0),
    "HazardBlack": ((0.12, 0.12, 0.14), 0), "Marking": ((0.95, 0.95, 0.9), 0),
    "LightStrip": ((0.55, 0.85, 1.0), 3), "WarningLight": ((1.0, 0.2, 0.15), 6),
    "Lamp": ((1.0, 0.9, 0.5), 8), "CoreGlow": ((0.45, 0.95, 1.0), 6),
    # Snow and ice.
    "Snow": ((0.93, 0.95, 0.98), 0), "Ice": ((0.62, 0.82, 0.95), 0), "IceDeep": ((0.35, 0.6, 0.85), 0),
    "Rock": ((0.42, 0.42, 0.48), 0), "RockLight": ((0.58, 0.58, 0.63), 0),
    # Foliage (drawn without ink lines: FOLIAGE).
    "Pine": ((0.12, 0.28, 0.22), 0), "PineLight": ((0.2, 0.38, 0.28), 0),
    "PineSnow": ((0.9, 0.93, 0.97), 0), "Trunk": ((0.35, 0.25, 0.18), 0),
    # Ground and placeholders.
    "Pavement": ((0.42, 0.43, 0.47), 0), "Road": ((0.25, 0.26, 0.3), 0),
    "Water": ((0.62, 0.8, 0.92), 0), "Greybox": ((0.7, 0.7, 0.72), 0),
}
FOLIAGE = ("Pine", "PineLight", "PineSnow", "Trunk")

# The shared scripts import "corneria_common": make that this module, and
# give them their folders.
sys.modules["corneria_common"] = sys.modules[__name__]
for _p in (CORNERIA_SOURCE, os.path.join(CORNERIA_SOURCE, "kit")):
    if _p not in sys.path:
        sys.path.append(_p)
