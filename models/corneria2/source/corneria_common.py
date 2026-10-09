"""Shared by the Corneria map's Blender scripts: the map's size and grid, the
game/Blender coordinate conversion, the palette, the prop groups and the
helpers every script needs.

The map's master copy is corneria.blend (next to this file). The kit pieces
live in kit.blend, one collection per piece, linked into the map. Scripts:
    greybox_kit.py      placeholder kit pieces (never overwrites a real model)
    new_map.py          creates corneria.blend, empty, if it doesn't exist
    export_corneria.py  reads corneria.blend and writes the game's files

Game coordinates: Godot's, +X east, +Y up, -Z north, metres. Blender's: Z up,
+Y north. G() converts a game point to Blender; game_matrix() a Blender
transform to the game.
"""

import os

import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(HERE)          # models/corneria2: the exported files
MAP_FILE = os.path.join(HERE, "corneria.blend")
KIT_FILE = os.path.join(HERE, "kit.blend")

SIZE = 16000.0                        # the map: SIZE x SIZE metres, centred on the origin
HALF = SIZE / 2
CELL = 25.0                           # terrain grid spacing, as Terrain.cell_size
POINTS = int(SIZE / CELL) + 1         # grid points per side
PROP_TILE = 500.0                     # exported one-off geometry is cut into squares this size

# Prop groups: one collection each under "Props" in the map. solid: gets
# collision in the game (MapProps.solid_groups); structure: the AI flies over
# it (rasterised into the map's structure heights).
GROUPS = {
    "City": dict(solid=True, structure=True),
    "Town": dict(solid=True, structure=True),
    "Base": dict(solid=True, structure=True),
    "Landmarks": dict(solid=True, structure=True),   # arches, bridges, sea stacks, the spire...
    "Rocks": dict(solid=True, structure=True),
    "Water": dict(solid=True, structure=False),      # lakes and rivers above sea level (sheets)
    "Roads": dict(solid=False, structure=False),     # flat on the ground
    "Trees": dict(solid=False, structure=False),     # flown through
}
KIT_PREFIX = "Kit_"                   # a collection instance of one of these is a kit piece
PAINT_ATTRIBUTE = "Paint"             # the terrain's colour layer: red = paved, blue = high water
WATER_MATERIAL = "Corneria_Water"     # the game gives faces with it the level's water material
MARKERS = ("Start", "IntroStart", "IntroCameraSpot", "Waterfall", "GreatFox")

# Colours: sRGB, as they look in the game; material() converts them to linear
# for Blender and glTF. The light is bright: keep big surfaces off pure white.
# (sRGB colour, emission strength)
PALETTE = {
    "Tower": ((0.84, 0.86, 0.9), 0), "Glass": ((0.3, 0.55, 0.8), 0), "Concrete": ((0.72, 0.68, 0.6), 0),
    "RoofDark": ((0.36, 0.37, 0.42), 0), "Road": ((0.27, 0.27, 0.3), 0), "Stone": ((0.76, 0.68, 0.53), 0),
    "WarningLight": ((1.0, 0.2, 0.15), 6), "Wall": ((0.93, 0.91, 0.86), 0), "Roof": ((0.75, 0.38, 0.28), 0),
    "Lighthouse": ((0.82, 0.18, 0.14), 0), "Lamp": ((1.0, 0.9, 0.5), 8), "Military": ((0.45, 0.5, 0.42), 0),
    "Marking": ((0.95, 0.95, 0.9), 0), "Water": ((0.25, 0.5, 0.75), 0),
    "Tree": ((0.18, 0.4, 0.2), 0), "TreeLight": ((0.27, 0.5, 0.22), 0), "Trunk": ((0.4, 0.28, 0.18), 0),
    "Rock": ((0.55, 0.5, 0.46), 0), "Steel": ((0.6, 0.62, 0.66), 0), "BridgeRed": ((0.75, 0.25, 0.18), 0),
    "TaxiYellow": ((0.95, 0.8, 0.2), 0), "MilitaryDark": ((0.3, 0.34, 0.28), 0),
    "HazardBlack": ((0.12, 0.12, 0.14), 0), "CarBody": ((0.22, 0.52, 0.82), 0),
    "AwningBlue": ((0.2, 0.5, 0.85), 0), "Greybox": ((0.7, 0.7, 0.72), 0),
    "Pavement": ((0.66, 0.64, 0.6), 0), "Park": ((0.36, 0.58, 0.28), 0),
    "FieldWheat": ((0.86, 0.76, 0.42), 0), "FieldGreen": ((0.4, 0.6, 0.26), 0),
    "FieldBrown": ((0.58, 0.46, 0.3), 0), "FieldLight": ((0.62, 0.74, 0.34), 0),
    # The kit (models/corneria2/ASSETS.md): Cornerian architecture's warm
    # stone, dark glass bands, teal and orange accents, and light strips.
    "Cream": ((0.9, 0.85, 0.74), 0), "GlassDark": ((0.16, 0.3, 0.5), 0),
    "Teal": ((0.16, 0.58, 0.62), 0), "Orange": ((0.95, 0.55, 0.16), 0),
    "LightStrip": ((0.55, 0.85, 1.0), 3),
}

# Game (x, y, z) -> Blender (x, -z, y), as a matrix, and back.
TO_BLENDER = Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
TO_GAME = TO_BLENDER.inverted()


def G(x, y, z):
    """A game point in Blender coordinates."""
    return Vector((x, -z, y))


def game_point(v):
    """A Blender point in game coordinates."""
    return (v.x, v.z, -v.y)


def game_matrix(m):
    """A Blender transform (4x4) as the same transform in game coordinates."""
    return TO_GAME @ m @ TO_BLENDER


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def material(name):
    """The palette material `name` (as "Corneria_<name>"), made or updated."""
    srgb, emit = PALETTE[name]
    full = "Corneria_" + name
    m = bpy.data.materials.get(full) or bpy.data.materials.new(full)
    rgb = tuple(srgb_to_linear(c) for c in srgb)
    if not m.node_tree:
        m.use_nodes = True
    bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.8
    bsdf.inputs["Emission Strength"].default_value = emit
    if emit > 0:
        bsdf.inputs["Emission Color"].default_value = (*rgb, 1.0)
    m.diffuse_color = (*rgb, 1.0)
    return m


def collection(name, parent=None):
    """The collection `name`, made and linked under `parent` (default: the
    scene's) if it isn't there yet."""
    col = bpy.data.collections.get(name)
    if col is None or col.library is not None:
        col = bpy.data.collections.new(name)
    parent_children = (parent or bpy.context.scene.collection).children
    if col.name not in parent_children:
        parent_children.link(col)
    return col


def clear_collection(col):
    """Removes every object in `col` and its child collections (their meshes
    too, if nothing else uses them)."""
    for child in list(col.children):
        clear_collection(child)
        bpy.data.collections.remove(child)
    for o in list(col.objects):
        data = o.data
        bpy.data.objects.remove(o)
        if isinstance(data, bpy.types.Mesh) and data.users == 0:
            bpy.data.meshes.remove(data)


def kit_piece(name):
    """The kit collection `name`, linked from kit.blend into this file if
    needed (relative path, so the pair can move together)."""
    col = bpy.data.collections.get(name)
    if col is not None:
        return col
    with bpy.data.libraries.load(KIT_FILE, link=True, relative=True) as (src, dst):
        if name not in src.collections:
            raise KeyError("kit.blend has no collection " + name)
        dst.collections = [name]
    return dst.collections[0]


def place(name, game_xf, col):
    """An instance of kit piece `name` in `col`, at a game-space transform
    (a mathutils Matrix, 4x4: rotation, scale and position)."""
    piece = kit_piece(name)
    o = bpy.data.objects.new(name, None)
    o.instance_type = "COLLECTION"
    o.instance_collection = piece
    o.matrix_world = TO_BLENDER @ game_xf @ TO_GAME
    col.objects.link(o)
    return o


def game_transform(x, y, z, turn=0.0, scale=(1.0, 1.0, 1.0)):
    """A game-space transform: scaled (x, y, z), turned `turn` radians about +Y
    (anticlockwise seen from above), then moved to (x, y, z)."""
    sx, sy, sz = scale
    return (Matrix.Translation((x, y, z)) @ Matrix.Rotation(turn, 4, "Y")
            @ Matrix.Diagonal((sx, sy, sz, 1.0)))


def terrain_heights():
    """The Terrain grid's heights as a (POINTS, POINTS) numpy array, rows
    along game +z (south), read straight from its vertices (so sculpting
    counts, as long as the grid's vertices keep their order)."""
    import numpy as np
    me = bpy.data.objects["Terrain"].data
    if len(me.vertices) != POINTS * POINTS:
        raise RuntimeError("the Terrain mesh isn't the %d x %d grid new_map.py makes" % (POINTS, POINTS))
    co = np.empty(len(me.vertices) * 3, dtype=np.float64)
    me.vertices.foreach_get("co", co)
    return co.reshape(-1, 3)[:, 2].reshape(POINTS, POINTS)
