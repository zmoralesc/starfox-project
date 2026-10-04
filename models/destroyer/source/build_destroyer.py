"""Builds the destroyer model in Blender and exports it for the game.

Run inside Blender (Scripting tab, or through the Blender MCP):
    exec(open(r"<project>/models/destroyer/source/build_destroyer.py").read())
(set FORCE_EXPORT = True in the exec globals to export), or from the command line:
    blender --background --python build_destroyer.py -- --export

Everything is written in GAME coordinates (Godot: +X right, +Y up, -Z is the
bow), in metres, and converted to Blender's Z-up frame by G(). The glTF
exporter converts back, so positions here match enemies/destroyer.tscn.

Each destructible part is exported on its own, modelled around its own pivot
(the part node's position in destroyer.tscn), so the game can char or hide it
separately:
    destroyer_hull.glb         everything that isn't a part (pivot: ship origin)
    destroyer_bridge.glb       pivot BRIDGE_POS
    destroyer_thruster.glb     one thruster, used three times; nozzle faces +Z
    destroyer_hangar_door.glb  one door, for the left side (mirrored in Godot)

With --export (or EXPORT = True) it also writes collision.txt next to this
script: convex hull points for the hull, ready to paste into destroyer.tscn.
"""

import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

EXPORT = "--export" in sys.argv or globals().get("FORCE_EXPORT", False)
HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else \
    r"C:\Users\zemc7\OneDrive\Documentos\spaceship-project\models\destroyer\source"
OUT = os.path.dirname(HERE)

# ---------------------------------------------------------------- layout
# Part pivots (game coordinates). Keep in sync with destroyer.tscn.
BRIDGE_POS = (0.0, 75.0, 120.0)
THRUSTER_POS = {"L": (-51.0, 0.0, 190.0), "C": (0.0, 4.5, 190.0), "R": (51.0, 0.0, 190.0)}
HOUSING_X = 78.0          # hangar housing centre, each side
HANGAR_Z = 60.0
HOUSING_SIZE = (18.0, 24.0, 51.0)
DOOR_SIZE = (1.8, 18.0, 39.0)
DOOR_X = HOUSING_X + HOUSING_SIZE[0] / 2 + DOOR_SIZE[0] / 2

# Planform of the main hull (x, z), counter-clockwise seen from above: a wide
# armoured body splitting into two prongs with an open gap between them.
BODY = [(-75, 177), (-84, 90), (-45, -30), (-51, -187.5), (-24, -157.5), (-15, -45),
        (15, -45), (24, -157.5), (51, -187.5), (45, -30), (84, 90), (75, 177)]
# The same split into convex pieces, for collision.
BODY_AFT = [(-75, 177), (-84, 90), (-45, -30), (45, -30), (84, 90), (75, 177)]
PRONG_L = [(-45, -30), (-51, -187.5), (-24, -157.5), (-15, -45)]
PRONG_R = [(x * -1, z) for x, z in reversed(PRONG_L)]
HULL_Y = (-15.0, 12.0)
KEEL = [(-54, 165), (-36, -60), (36, -60), (54, 165)]
KEEL_Y = (-30.0, -15.0)
DECK = [(-45, 165), (-51, 90), (-18, -37.5), (18, -37.5), (51, 90), (45, 165)]
DECK_Y = (12.0, 24.0)
SUPER = [(-27, 150), (-21, 67.5), (21, 67.5), (27, 150)]
SUPER_Y = (24.0, 39.0)
TOWER = [(-12, 134), (-9, 106), (9, 106), (12, 134)]
TOWER_Y = (39.0, 62.0)
# Flared neck from the tower top into the underside of the bridge block, so the
# bridge grows out of the tower instead of sitting on it.
NECK_TOP = [(-16, 128.5), (-16, 111.5), (16, 111.5), (16, 128.5)]
NECK_Y = (TOWER_Y[1], 70.0)
TOWER_TOP_SCALE = 0.75
ENGINE_BLOCK = (150.0, 28.0, 20.0)   # size; centred at (0, 1, 172)

# ---------------------------------------------------------------- colours
# (sRGB colour, emission strength). The colours are the values the game ends up
# with (albedo / emission in Godot's inspector): Blender and glTF store linear
# values, so material() converts. The toon light is bright (the old destroyer's
# 0.46 grey rendered near-white), so the hull colours are deliberately dark.
COLORS = {
    "Hull": ((0.20, 0.22, 0.26), 0.0),
    "HullLight": ((0.32, 0.34, 0.39), 0.0),
    "Dark": ((0.07, 0.07, 0.09), 0.0),
    "Crimson": ((0.55, 0.04, 0.05), 0.0),
    "Window": ((1.0, 0.62, 0.2), 3.0),
    "Emitter": ((1.0, 0.55, 0.15), 4.0),
    "EngineGlow": ((1.0, 0.32, 0.1), 6.0),
}


def G(x, y, z):
    """Game (Y up, -Z forward) to Blender (Z up, +Y forward)."""
    return Vector((x, -z, y))


# ---------------------------------------------------------------- helpers
def material(name):
    full = "Destroyer_" + name
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
    m.diffuse_color = (*rgb, 1.0)
    return m


class Builder:
    def __init__(self, collection):
        self.c = collection
        self.groups = {}

    def _finish(self, name, me, mat, group, bevel):
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()
        o = bpy.data.objects.new(name, me)
        self.c.objects.link(o)
        me.materials.append(material(mat))
        if bevel > 0:
            md = o.modifiers.new("Bevel", "BEVEL")
            md.width = bevel
            md.segments = 1
            md.limit_method = "ANGLE"
        for p in me.polygons:
            p.use_smooth = False
        self.groups.setdefault(group, []).append(o)
        return o

    def prism(self, name, outline, y0, y1, mat="Hull", group="hull", bevel=0.0, top_scale=1.0):
        """Extrude a game-space outline (x, z) between heights y0 and y1."""
        return self.loft(name, outline, scaled(outline, top_scale), y0, y1, mat, group, bevel)

    def loft(self, name, bottom, top, y0, y1, mat="Hull", group="hull", bevel=0.0):
        """Join two outlines with the same number of points: `bottom` at y0, `top` at y1."""
        n = len(bottom)
        verts = [G(x, y0, z) for x, z in bottom] + [G(x, y1, z) for x, z in top]
        faces = [tuple(range(n)), tuple(range(n, 2 * n))]
        faces += [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
        me = bpy.data.meshes.new(name)
        me.from_pydata(verts, [], faces)
        return self._finish(name, me, mat, group, bevel)

    def box(self, name, size, center, mat="Hull", group="hull", bevel=0.0):
        sx, sy, sz = (s / 2 for s in size)
        x0, y0, z0 = center
        outline = [(x0 - sx, z0 + sz), (x0 - sx, z0 - sz), (x0 + sx, z0 - sz), (x0 + sx, z0 + sz)]
        return self.prism(name, outline, y0 - sy, y0 + sy, mat, group, bevel)

    def cylinder(self, name, r_front, r_back, length, center, mat="Hull", group="hull", axis="z", segments=20):
        """A cylinder/cone; along game Z (r_front at -Z) or game Y (r_front at the bottom)."""
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=segments, radius1=r_front, radius2=r_back, depth=length)
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        # create_cone runs along Blender Z, radius1 at -Z. Game Z = Blender -Y.
        if axis == "z":
            me.transform(Matrix.Rotation(math.radians(90), 4, "X"))
        me.transform(Matrix.Translation(G(*center)))
        o = self._finish(name, me, mat, group, 0.0)
        for p in me.polygons:
            p.use_smooth = len(p.vertices) == 4
        return o


def scaled(outline, factor):
    """An outline (game x/z) scaled about its centre."""
    n = len(outline)
    cx = sum(p[0] for p in outline) / n
    cz = sum(p[1] for p in outline) / n
    return [(cx + (x - cx) * factor, cz + (z - cz) * factor) for x, z in outline]


def offset(outline, d):
    """Shrink an outline (game x/z, either winding) by d metres, mitring the corners."""
    pts = [Vector((x, z)) for x, z in outline]
    n = len(pts)
    # Signed area tells the winding, and so which side of each edge is inside.
    area = sum(pts[i - 1].x * pts[i].y - pts[i].x * pts[i - 1].y for i in range(n)) / 2
    side = 1.0 if area > 0 else -1.0
    out = []
    for i in range(n):
        a, b, c = pts[i - 1], pts[i], pts[(i + 1) % n]
        e1 = (b - a).normalized()
        e2 = (c - b).normalized()
        n1 = Vector((-e1.y, e1.x)) * side  # inward normal of the edge into b
        n2 = Vector((-e2.y, e2.x)) * side  # ...and of the edge out of b
        bis = n1 + n2
        bis = n1 if bis.length < 1e-6 else bis.normalized()
        # Mitre: move along the bisector far enough to sit d from both edges
        # (capped so very sharp corners don't shoot off).
        out.append(b + bis * (d / max(bis.dot(n1), 0.3)))
    return [(p.x, p.y) for p in out]


# ---------------------------------------------------------------- build
def build():
    scene = bpy.data.scenes.get("Destroyer") or bpy.data.scenes.new("Destroyer")
    if bpy.context.window:
        bpy.context.window.scene = scene
    col = bpy.data.collections.get("Destroyer")
    if col is None:
        col = bpy.data.collections.new("Destroyer")
        scene.collection.children.link(col)
    for o in list(col.objects):
        bpy.data.objects.remove(o)
    # Drop meshes left over from earlier builds, so names stay clean.
    for me in list(bpy.data.meshes):
        if me.users == 0:
            bpy.data.meshes.remove(me)
    b = Builder(col)

    # --- Hull: armoured slab, an inset upper tier, keel underneath.
    b.prism("HullLower", BODY, HULL_Y[0], 3.0, "Hull", bevel=2.0)
    b.prism("HullUpper", offset(BODY, 4.0), 3.0, HULL_Y[1], "Hull", bevel=1.5)
    b.prism("Keel", KEEL, KEEL_Y[0], KEEL_Y[1], "Dark", bevel=1.5, top_scale=1.06)
    b.prism("Deck", DECK, DECK_Y[0], DECK_Y[1], "HullLight", bevel=1.5, top_scale=0.94)
    b.prism("Super", SUPER, SUPER_Y[0], SUPER_Y[1], "Hull", bevel=1.2, top_scale=0.86)
    b.prism("Tower", TOWER, TOWER_Y[0], TOWER_Y[1], "Hull", bevel=1.0, top_scale=TOWER_TOP_SCALE)
    b.loft("Neck", scaled(TOWER, TOWER_TOP_SCALE), NECK_TOP, NECK_Y[0], NECK_Y[1], "Hull", bevel=1.0)
    b.box("EngineBlock", ENGINE_BLOCK, (0.0, 1.0, 172.0), "Hull", bevel=2.0)
    b.box("EngineBlockTrim", (ENGINE_BLOCK[0] + 1, 3.0, ENGINE_BLOCK[2] + 1), (0.0, 9.0, 172.0), "Crimson")

    # Prow emitter between the prongs, in a dark collar.
    b.cylinder("EmitterCollar", 13.0, 13.0, 8.0, (0.0, 0.0, -38.0), "Dark", segments=16)
    b.cylinder("Emitter", 9.0, 10.5, 12.0, (0.0, 0.0, -46.0), "Emitter", segments=16)

    # Crimson bands: along each prong, and a chevron across the deck.
    for s, n in ((-1, "L"), (1, "R")):
        # A 4 m strip down the middle of each prong (a quad along the prong's slant).
        start, end = Vector((s * 31.5, -40.0)), Vector((s * 37.5, -165.0))
        d = (end - start).normalized()
        perp = Vector((d.y, -d.x)) * 2.0
        quad = [start + perp, end + perp, end - perp, start - perp]
        b.prism("ProngBand" + n, [(p.x, p.y) for p in quad], HULL_Y[1] - 0.2, HULL_Y[1] + 0.6, "Crimson")
    b.box("DeckChevron", (84.0, 0.8, 5.0), (0.0, DECK_Y[1] + 0.2, 128.0), "Crimson")
    b.box("DeckTrench", (8.0, 0.8, 90.0), (0.0, DECK_Y[1] + 0.2, 20.0), "Dark")

    # Vents along the aft body, outboard of the deck.
    for s, n in ((-1, "L"), (1, "R")):
        for i in range(7):
            z = 100.0 + i * 9.0
            b.box("Vent%s%d" % (n, i), (14.0, 1.0, 3.5), (s * 66.0, HULL_Y[1] + 0.3, z), "Dark")
        # Flank armour strip along the side of the body.
        b.box("FlankBand" + n, (1.2, 5.0, 70.0), (s * 82.0, -2.0, 130.0), "Crimson")

    # Hangar housings (the doors are parts, exported separately).
    for s, n in ((-1, "L"), (1, "R")):
        b.box("Housing" + n, HOUSING_SIZE, (s * HOUSING_X, 0.0, HANGAR_Z), "Hull", bevel=1.5)
        b.box("HousingTrim" + n, (HOUSING_SIZE[0] + 0.6, 2.0, HOUSING_SIZE[2] + 0.6),
              (s * HOUSING_X, HOUSING_SIZE[1] / 2 - 2.0, HANGAR_Z), "Crimson")

    # --- Bridge part (pivot BRIDGE_POS): command block, windows, sensor domes.
    bx, by, bz = BRIDGE_POS
    b.box("BridgeBlock", (39.0, 12.0, 18.0), (bx, by, bz), "Dark", "bridge", bevel=1.5)
    b.box("BridgeWindows", (33.0, 2.4, 0.6), (bx, by + 1.0, bz - 9.2), "Window", "bridge")
    b.box("BridgeRoof", (30.0, 2.0, 14.0), (bx, by + 7.0, bz + 1.0), "HullLight", "bridge", bevel=0.8)
    for s, n in ((-1, "L"), (1, "R")):
        b.cylinder("SensorDome" + n, 4.5, 3.0, 6.0, (bx + s * 7.0, by + 10.5, bz + 1.0), "Crimson", "bridge",
                   axis="y", segments=12)
    b.cylinder("Antenna", 0.6, 0.3, 16.0, (bx, by + 16.0, bz + 4.0), "Dark", "bridge", axis="y", segments=6)

    # --- Thruster part (pivot at the nozzle centre; exported once).
    b.cylinder("ThrusterHousing", 15.0, 13.5, 27.0, (0.0, 0.0, 0.0), "Dark", "thruster", segments=20)
    b.cylinder("ThrusterRing", 15.8, 15.8, 4.0, (0.0, 0.0, -4.0), "Crimson", "thruster", segments=20)
    b.cylinder("ThrusterGlow", 11.5, 11.5, 1.0, (0.0, 0.0, 13.6), "EngineGlow", "thruster", segments=20)

    # --- Hangar door part (left side; pivot at the door's centre).
    b.box("Door", DOOR_SIZE, (0.0, 0.0, 0.0), "Dark", "door", bevel=0.4)
    b.box("DoorStripe", (0.4, 2.5, DOOR_SIZE[2] - 4.0), (-DOOR_SIZE[0] / 2 - 0.2, 4.5, 0.0), "Crimson", "door")
    b.box("DoorStripe2", (0.4, 2.5, DOOR_SIZE[2] - 4.0), (-DOOR_SIZE[0] / 2 - 0.2, -4.5, 0.0), "Crimson", "door")

    # Preview placement: put the single thruster/door copies where they go,
    # plus extra copies, so the model looks complete in Blender.
    for o in b.groups["thruster"]:
        o.location = G(*THRUSTER_POS["C"])
    for key in ("L", "R"):
        for o in b.groups["thruster"]:
            dup = o.copy()
            dup.data = o.data
            dup.location = G(*THRUSTER_POS[key])
            col.objects.link(dup)
            b.groups.setdefault("preview", []).append(dup)
    for o in b.groups["door"]:
        o.location = G(-DOOR_X, 0.0, HANGAR_Z)
        dup = o.copy()
        dup.data = o.data
        dup.location = G(DOOR_X, 0.0, HANGAR_Z)
        dup.scale = (-1, 1, 1)
        col.objects.link(dup)
        b.groups.setdefault("preview", []).append(dup)
    return b


# ---------------------------------------------------------------- export
def export(b):
    pivots = {"hull": (0, 0, 0), "bridge": BRIDGE_POS, "thruster": THRUSTER_POS["C"],
              "door": (-DOOR_X, 0.0, HANGAR_Z)}
    files = {"hull": "destroyer_hull.glb", "bridge": "destroyer_bridge.glb",
             "thruster": "destroyer_thruster.glb", "door": "destroyer_hangar_door.glb"}
    for o in b.groups.get("preview", []):
        o.hide_set(True)
    for group, objs in b.groups.items():
        if group not in files:
            continue
        pivot = G(*pivots[group])
        saved = [(o, o.location.copy()) for o in objs]
        bpy.ops.object.select_all(action="DESELECT")
        for o in objs:
            o.location = o.location - pivot
            o.select_set(True)
        bpy.context.view_layer.objects.active = objs[0]
        bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, files[group]), export_format="GLB",
                                  use_selection=True, use_active_scene=True, export_apply=True, export_yup=True,
                                  export_materials="EXPORT", export_cameras=False, export_lights=False)
        for o, loc in saved:
            o.location = loc
    for o in b.groups.get("preview", []):
        o.hide_set(False)
    write_collision()


def _prism_points(outline, y0, y1, top_scale=1.0):
    n = len(outline)
    cx = sum(p[0] for p in outline) / n
    cz = sum(p[1] for p in outline) / n
    pts = [(x, y0, z) for x, z in outline]
    pts += [(cx + (x - cx) * top_scale, y1, cz + (z - cz) * top_scale) for x, z in outline]
    return pts


def write_collision():
    """Convex hull pieces in game coordinates, as Godot PackedVector3Array text."""
    pieces = {
        "Shape_body_aft": _prism_points(BODY_AFT, HULL_Y[0], HULL_Y[1]),
        "Shape_prong_l": _prism_points(PRONG_L, HULL_Y[0], HULL_Y[1]),
        "Shape_prong_r": _prism_points(PRONG_R, HULL_Y[0], HULL_Y[1]),
        "Shape_keel": _prism_points(KEEL, KEEL_Y[0], KEEL_Y[1], 1.06),
        "Shape_deck": _prism_points(DECK, DECK_Y[0], DECK_Y[1], 0.94),
        "Shape_super": _prism_points(SUPER, SUPER_Y[0], SUPER_Y[1], 0.86),
        "Shape_tower": _prism_points(TOWER, TOWER_Y[0], TOWER_Y[1], TOWER_TOP_SCALE),
        "Shape_neck": [(x, NECK_Y[0], z) for x, z in scaled(TOWER, TOWER_TOP_SCALE)]
                      + [(x, NECK_Y[1], z) for x, z in NECK_TOP],
    }
    lines = []
    for name, pts in pieces.items():
        flat = ", ".join("%g, %g, %g" % p for p in pts)
        lines.append('[sub_resource type="ConvexPolygonShape3D" id="%s"]\npoints = PackedVector3Array(%s)\n'
                     % (name, flat))
    with open(os.path.join(HERE, "collision.txt"), "w") as f:
        f.write("\n".join(lines))


builder = build()
if EXPORT:
    export(builder)
print("destroyer built:", {k: len(v) for k, v in builder.groups.items()}, "exported" if EXPORT else "")
