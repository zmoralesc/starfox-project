"""Builds the destroyer model in Blender and exports it for the game.

Run inside Blender (Scripting tab, or through the Blender MCP):
    exec(open(r"<project>/models/destroyer/source/build_destroyer.py").read())
(set FORCE_EXPORT = True in the exec globals to export), or from the command line:
    blender --background --python build_destroyer.py -- --export

Everything is written in GAME coordinates (Godot: +X right, +Y up, -Z is the
bow) before scaling: G() converts to Blender's Z-up frame and multiplies by
SCALE, so the ship in the game (and in enemies/destroyer.tscn) is SCALE times
every number here. The glTF exporter converts back. Surface detail (windows,
plates) is sized in real metres instead, so it doesn't grow with the hull: a
bigger ship gets more windows, not bigger ones.

Each destructible part is exported on its own, modelled around its own pivot
(the part node's position in destroyer.tscn), so the game can char or hide it
separately:
    destroyer_hull.glb         everything that isn't a part (pivot: ship origin)
    destroyer_bridge.glb       pivot BRIDGE_POS
    destroyer_thruster.glb     one thruster, used three times; nozzle faces +Z
    destroyer_hangar_door.glb  one door, for the left side (mirrored in Godot)

With --export (or EXPORT = True) it also writes collision.txt next to this
script: convex hull points for the hull, ready to paste into destroyer.tscn.
And proxies.txt: the extra_proxies line for destroyer.tscn (AI avoidance
spheres for the superstructure, housings, deck and keel).
"""

import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

EXPORT = "--export" in sys.argv or globals().get("FORCE_EXPORT", False)
HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else \
    r"C:\Users\zemc7\OneDrive\Documentos\spaceship-project\models\destroyer\source"
OUT = os.path.dirname(HERE)

# ---------------------------------------------------------------- layout
# Size of the ship in the game relative to the numbers below. Changing it
# means scaling everything in destroyer.tscn too (part positions, radii,
# collision, hull_outline, extra_proxies, turret mounts...).
SCALE = 2.0
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
# A narrower second tier under the keel (outline at its top; it tapers to
# KEEL_LOWER_TAPER at the bottom), so the underside steps down instead of
# being one flat slab.
KEEL_LOWER = [(-33, 145), (-22, -40), (22, -40), (33, 145)]
KEEL_LOWER_Y = (-37.0, KEEL_Y[0])
KEEL_LOWER_TAPER = 0.92
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
    "HullDark": ((0.14, 0.15, 0.18), 0.0),       # armour plate variation
    "PanelLine": ((0.05, 0.05, 0.065), 0.0),    # shows in the gaps between plates
    "Dark": ((0.07, 0.07, 0.09), 0.0),
    "Crimson": ((0.55, 0.04, 0.05), 0.0),
    "Window": ((1.0, 0.62, 0.2), 3.0),
    "RunningLight": ((1.0, 0.12, 0.08), 5.0),
    "Emitter": ((1.0, 0.55, 0.15), 4.0),
    "EngineGlow": ((1.0, 0.32, 0.1), 6.0),
}


def G(x, y, z):
    """Game (Y up, -Z forward) to Blender (Z up, +Y forward), scaled by SCALE."""
    return Vector((x, -z, y)) * SCALE


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
            md.width = bevel * SCALE
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
        me.transform(Matrix.Scale(SCALE, 4))
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


# ---------------------------------------------------------------- detail helpers
class Batch:
    """Collects many small pieces and turns them into one object per material,
    so hundreds of plates and windows don't become hundreds of nodes in Godot."""

    def __init__(self):
        self.parts = {}  # material -> (verts, faces)

    def prism(self, outline, y0, y1, mat, top_scale=1.0):
        verts, faces = self.parts.setdefault(mat, ([], []))
        n = len(outline)
        start = len(verts)
        verts += [G(x, y0, z) for x, z in outline] + [G(x, y1, z) for x, z in scaled(outline, top_scale)]
        faces.append(tuple(start + i for i in range(n)))
        faces.append(tuple(start + n + i for i in range(n)))
        faces += [(start + i, start + (i + 1) % n, start + n + (i + 1) % n, start + n + i) for i in range(n)]

    def box(self, size, center, mat):
        sx, sy, sz = (s / 2 for s in size)
        x0, y0, z0 = center
        self.prism([(x0 - sx, z0 + sz), (x0 - sx, z0 - sz), (x0 + sx, z0 - sz), (x0 + sx, z0 + sz)],
                   y0 - sy, y0 + sy, mat)

    def oriented_box(self, center, along, length, depth, y0, y1, mat):
        """A box standing on the x/z plane, `length` along the 2D direction
        `along` and `depth` across it, from height y0 to y1."""
        a = along.normalized() * (length / 2)
        c = Vector((-along.y, along.x)).normalized() * (depth / 2)
        pts = [center + a + c, center - a + c, center - a - c, center + a - c]
        self.prism([(p.x, p.y) for p in pts], y0, y1, mat)

    def flush(self, b, name, group="hull"):
        for mat, (verts, faces) in self.parts.items():
            me = bpy.data.meshes.new(name + mat)
            me.from_pydata(verts, [], faces)
            b._finish(name + mat, me, mat, group, 0.0)
        self.parts = {}


def inside(p, outline):
    """Point (x, z) inside a polygon (game x/z), by ray casting."""
    x, z = p
    hit = False
    n = len(outline)
    for i in range(n):
        (x1, z1), (x2, z2) = outline[i - 1], outline[i]
        if (z1 > z) != (z2 > z) and x < x1 + (z - z1) * (x2 - x1) / (z2 - z1):
            hit = not hit
    return hit


def rect(center_x, center_z, size_x, size_z):
    """An axis-aligned rectangle outline (game x/z)."""
    hx, hz = size_x / 2, size_z / 2
    return [(center_x - hx, center_z + hz), (center_x - hx, center_z - hz),
            (center_x + hx, center_z - hz), (center_x + hx, center_z + hz)]


def plate_field(batch, rng, region, y, along, cell_w, cell_l, palette, keep_out=(), circles=(), down=False):
    """Armour plates over a flat surface at height y (a top, or with `down` an
    underside), in a staggered brick
    pattern (columns `cell_w` wide across `along`, plates 1-2 `cell_l` long),
    each on a dark underlay the size of its whole cell, so the thin gaps between
    neighbouring plates show as panel lines (and spots with no plate show the
    plain hull, not a black hole). Plates are kept only if they lie
    fully inside `region` and clear of the `keep_out` outlines and (x, z, r)
    `circles` (turrets and other parts). `palette`: [(material, weight), ...].
    Plate sizes and gaps are real metres (see SCALE)."""
    gap = 0.7 / SCALE
    cell_w, cell_l = cell_w / SCALE, cell_l / SCALE
    # `down`: the surface faces down (the underside), so plates hang below y.
    s = -1.0 if down else 1.0
    plate_top = y + s * 0.45 / SCALE
    along = Vector(along).normalized()
    across = Vector((-along.y, along.x))
    us = [Vector(p).dot(across) for p in region]
    vs = [Vector(p).dot(along) for p in region]
    mats = [m for m, _ in palette]
    weights = [w for _, w in palette]
    u = min(us)
    while u < max(us):
        v = min(vs) - rng.uniform(0, cell_l)
        while v < max(vs):
            length = cell_l * rng.choice((1.0, 1.0, 1.5, 2.0))
            corners = [across * (u + du) + along * (v + dv)
                       for du, dv in ((gap / 2, gap / 2), (cell_w - gap / 2, gap / 2),
                                      (cell_w - gap / 2, length - gap / 2), (gap / 2, length - gap / 2))]
            pts = [(c.x, c.y) for c in corners]
            mid = sum(corners, Vector((0, 0))) / 4
            ok = all(inside(p, region) for p in pts)
            ok = ok and not any(inside(p, k) for k in keep_out for p in pts + [(mid.x, mid.y)])
            ok = ok and not any(any((Vector(p) - Vector((cx, cz))).length < r for p in pts + [(mid.x, mid.y)])
                                for cx, cz, r in circles)
            if ok:
                cell = [across * (u + du) + along * (v + dv)
                        for du, dv in ((0, 0), (cell_w, 0), (cell_w, length), (0, length))]
                batch.prism([(c.x, c.y) for c in cell], y, y + s * 0.08 / SCALE, "PanelLine")
                batch.prism(pts, y + s * 0.08 / SCALE, plate_top, rng.choices(mats, weights)[0])
            v += length
        u += cell_w


def window_row(batch, rng, outline, y, spacing, mat="Window", size=(1.8, 0.9), skip=0.0,
               keep_out=(), min_edge=12.0, max_abs_z=999.0):
    """Small lit windows along the outside of a vertical-sided outline at
    height y: one every `spacing` metres along each edge longer than
    `min_edge`, a random `skip` fraction left dark, none inside `keep_out`
    outlines or beyond |z| > max_abs_z. Sizes and spacing are real metres (see SCALE)."""
    spacing /= SCALE
    size = (size[0] / SCALE, size[1] / SCALE)
    pts = [Vector(p) for p in outline]
    n = len(pts)
    area = sum(pts[i - 1].x * pts[i].y - pts[i].x * pts[i - 1].y for i in range(n)) / 2
    side = 1.0 if area > 0 else -1.0
    for i in range(n):
        a, c = pts[i - 1], pts[i]
        edge = c - a
        if edge.length < min_edge:
            continue
        d = edge.normalized()
        out = -Vector((-d.y, d.x)) * side  # outward normal
        count = int((edge.length - spacing) // spacing)
        for k in range(count):
            p = a + d * (spacing * (k + 1)) + out * (0.15 / SCALE)
            if abs(p.y) > max_abs_z or rng.random() < skip:
                continue
            if any(inside((p.x, p.y), ko) for ko in keep_out):
                continue
            batch.oriented_box(p, d, size[0], 0.4 / SCALE, y - size[1] / 2, y + size[1] / 2, mat)


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
    b.prism("Keel", KEEL, KEEL_Y[0], KEEL_Y[1], "Hull", bevel=1.5, top_scale=1.06)
    b.loft("KeelLower", scaled(KEEL_LOWER, KEEL_LOWER_TAPER), KEEL_LOWER, KEEL_LOWER_Y[0], KEEL_LOWER_Y[1],
           "Dark", bevel=1.2)
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

    add_detail(b)

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


# ---------------------------------------------------------------- detail
# Turret mounts (x, z) on the hull top, from destroyer.tscn: detail keeps clear.
TURRETS = [(sx * x, z) for x, z in ((37.5, -150), (33, -75), (42, 15), (54, 105)) for sx in (-1, 1)]
TURRET_CLEARANCE = 9.0
# Height of the armour plates' top above the surface they sit on (plates are
# 0.45 m thick in the game, see plate_field), where greebles stand.
PLATE_TOP = 0.45 / SCALE


def add_detail(b):
    """Surface detail, all decoration (no collision, no gameplay parts touched):
    armour plates with panel lines on the flat tops, rows of lit windows and red
    running lights, and greebles (conduits, machinery, antennas). Seeded, so a
    rebuild gives the same ship."""
    rng = random.Random(7)
    hull = Batch()
    bridge = Batch()
    turrets = [(x, z, TURRET_CLEARANCE) for x, z in TURRETS]
    housings = [rect(s * HOUSING_X, HANGAR_Z, HOUSING_SIZE[0] + 6, HOUSING_SIZE[2] + 6) for s in (-1, 1)]
    plain = [("Hull", 0.45), ("HullLight", 0.3), ("HullDark", 0.25)]

    # --- Armour plates.
    deck_top = scaled(DECK, 0.94)
    plate_field(hull, rng, offset(deck_top, 2.5), DECK_Y[1], (0, 1), 9.0, 11.0,
                [("HullLight", 0.6), ("Hull", 0.4)],
                keep_out=[offset(SUPER, -1.5), rect(0, 20, 10, 92), rect(0, 128, 86, 7)])
    plate_field(hull, rng, offset(scaled(SUPER, 0.86), 1.5), SUPER_Y[1], (0, 1), 6.0, 8.0,
                [("Hull", 0.5), ("HullLight", 0.3), ("HullDark", 0.2)], keep_out=[offset(TOWER, -1.5)])
    for s, prong in ((-1, PRONG_L), (1, PRONG_R)):
        start, end = Vector((s * 31.5, -40.0)), Vector((s * 37.5, -165.0))
        d = (end - start).normalized()
        perp = Vector((d.y, -d.x)) * 3.5
        band = [start + perp - d * 3, end + perp + d * 3, end - perp + d * 3, start - perp - d * 3]
        plate_field(hull, rng, offset(prong, 4.5), HULL_Y[1], d, 4.0, 8.0, plain,
                    keep_out=[[(p.x, p.y) for p in band]], circles=turrets)
    plate_field(hull, rng, offset(BODY_AFT, 5.5), HULL_Y[1], (0, 1), 8.0, 10.0, plain,
                keep_out=[offset(DECK, -1.5), rect(-66, 127, 18, 62), rect(66, 127, 18, 62),
                          rect(0, 172, 152, 22)] + housings,
                circles=turrets + [(0.0, -38.0, 15.0)])

    # --- Lit windows: two rows along the hull sides, more on the superstructure
    # and tower (their sides slope in, so each row follows the outline at its height).
    hangars = [rect(s * HOUSING_X, HANGAR_Z, 30, 60) for s in (-1, 1)]
    window_row(hull, rng, offset(BODY, 4.0), 8.0, 5.0, skip=0.15, keep_out=hangars, max_abs_z=170)
    window_row(hull, rng, BODY, -5.0, 7.0, skip=0.4, keep_out=hangars, max_abs_z=170)
    for y in (31.0, 35.5):
        t = (y - SUPER_Y[0]) / (SUPER_Y[1] - SUPER_Y[0])
        window_row(hull, rng, scaled(SUPER, 1 - 0.14 * t), y, 4.0, skip=0.1, min_edge=10)
    for y in (47.0, 55.0):
        t = (y - TOWER_Y[0]) / (TOWER_Y[1] - TOWER_Y[0])
        window_row(hull, rng, scaled(TOWER, 1 - (1 - TOWER_TOP_SCALE) * t), y, 3.5, size=(1.5, 1.0),
                   skip=0.1, min_edge=8)
    # Under each hangar door: a row of bay lights.
    for s in (-1, 1):
        x = s * (HOUSING_X + HOUSING_SIZE[0] / 2 + 0.2)
        for k in range(6):
            hull.oriented_box(Vector((x, HANGAR_Z - 16 + k * 6.4)), Vector((0, 1)), 1.6, 0.4, -11.0, -10.0, "Window")

    # --- Red running lights: prong tips, the widest point of the hull, the
    # engine block's outer corners, and the top of the bridge antenna.
    for s in (-1, 1):
        for center in ((s * 48.0, 13.0, -182.0), (s * 25.5, 13.0, -156.0), (s * 84.7, 0.0, 90.0),
                       (s * 74.0, 15.5, 181.0)):
            hull.box((1.4, 1.4, 1.4), center, "RunningLight")
    bx, by, bz = BRIDGE_POS
    bridge.box((1.2, 1.2, 1.2), (bx, by + 24.4, bz + 4.0), "RunningLight")

    # --- Greebles.
    # Conduits along each prong, either side of the crimson band, broken into
    # runs with junction boxes and kept clear of the turrets.
    for s in (-1, 1):
        start, end = Vector((s * 31.5, -40.0)), Vector((s * 37.5, -165.0))
        d = (end - start).normalized()
        perp = Vector((d.y, -d.x))
        length = (end - start).length
        for side in (-5.5, 5.5):
            pos = 4.0
            while pos < length - 6.0:
                run = rng.uniform(9.0, 16.0)
                mid = start + d * (pos + run / 2) + perp * side
                if all((mid - Vector((tx, tz))).length > TURRET_CLEARANCE + run / 2 for tx, tz in TURRETS):
                    hull.oriented_box(mid, d, run, 1.1, HULL_Y[1] + PLATE_TOP, HULL_Y[1] + PLATE_TOP + 0.9, "Dark")
                    hull.oriented_box(start + d * (pos + run) + perp * side, d, 2.2, 2.2,
                                      HULL_Y[1] + PLATE_TOP, HULL_Y[1] + 2.0, "HullDark")
                pos += run + rng.uniform(2.0, 6.0)
    # Ribs across the deck trench.
    for k in range(10):
        hull.box((11.0, 0.8, 1.2), (0.0, DECK_Y[1] + 0.9, -22.0 + k * 9.5), "HullLight")
    # Machinery on the superstructure roof, the aft deck and the engine block.
    def machinery(region, base_y, count, avoid=(), max_size=5.0):
        placed = 0
        for _ in range(count * 12):
            if placed >= count:
                break
            sx, sz = rng.uniform(2.0, max_size), rng.uniform(2.0, max_size + 1.0)
            cx = rng.uniform(min(p[0] for p in region), max(p[0] for p in region))
            cz = rng.uniform(min(p[1] for p in region), max(p[1] for p in region))
            r = rect(cx, cz, sx, sz)
            if not all(inside(p, region) for p in r) or any(inside(p, a) for a in avoid for p in r + [(cx, cz)]):
                continue
            h = rng.uniform(1.0, 2.8)
            hull.box((sx, h, sz), (cx, base_y + h / 2, cz), rng.choice(("Dark", "HullDark", "HullLight")))
            placed += 1
    machinery(offset(scaled(SUPER, 0.86), 2.0), SUPER_Y[1] + PLATE_TOP, 10, avoid=[offset(TOWER, -2.0)])
    machinery(rect(0, 157, 70, 10), DECK_Y[1] + PLATE_TOP, 6)
    machinery(rect(0, 172, 140, 16), ENGINE_BLOCK[1] / 2 + 1.0, 9, max_size=6.0)

    # Bridge: two more antenna masts and a dish on the roof, equipment pods on
    # the block's flanks (all part of the bridge, so they char with it).
    roof = by + 8.0
    bridge.box((0.5, 8.0, 0.5), (bx - 13.0, roof + 4.0, bz + 5.0), "Dark")
    bridge.box((0.4, 11.0, 0.4), (bx - 11.0, roof + 5.5, bz - 4.0), "Dark")
    for s in (-1, 1):
        bridge.box((2.0, 5.0, 8.0), (bx + s * 20.5, by - 1.0, bz + 2.0), "HullDark")
    b.cylinder("BridgeDish", 0.8, 3.6, 1.6, (bx + 11.0, roof + 0.8, bz + 5.0), "HullLight", "bridge",
               axis="y", segments=12)

    add_underside(b, hull)
    hull.flush(b, "Detail")
    bridge.flush(b, "BridgeDetail", "bridge")


def add_underside(b, hull):
    """Underside detail, seen when diving under the ship (at the thrusters).
    The sun is overhead, so everything here sits in the shadow band: small
    colour differences vanish, and what reads is shape (the stepped keel, big
    plates whose edges get ink outlines, radiator fins) and light (windows,
    floodlights, the ventral bay's glow). Its own seed, so the top detail is
    unchanged by edits here."""
    rng = random.Random(11)
    housings = [rect(s * HOUSING_X, HANGAR_Z, HOUSING_SIZE[0] + 6, HOUSING_SIZE[2] + 6) for s in (-1, 1)]
    keel_top = scaled(KEEL, 1.06)
    lower_bottom = scaled(KEEL_LOWER, KEEL_LOWER_TAPER)
    shade = [("Hull", 0.4), ("HullLight", 0.4), ("HullDark", 0.2)]
    bay = rect(0.0, 35.0, 16.0, 26.0)
    spine = rect(0.0, 53.0, 3.0, 164.0)
    radiators = [rect(s * 66.0, 158.0, 20.0, 22.0) for s in (-1, 1)]

    # --- Large plates: the hull's bottom around the keel and under the prongs,
    # the step between the keel tiers, and the lower tier's bottom.
    plate_field(hull, rng, offset(BODY_AFT, 4.0), HULL_Y[0], (0, 1), 7.0, 14.0, shade,
                keep_out=[offset(keel_top, -2.0)] + housings + radiators, down=True)
    for prong in (PRONG_L, PRONG_R):
        d = Vector(prong[1]) - Vector(prong[0])
        plate_field(hull, rng, offset(prong, 4.0), HULL_Y[0], d, 6.0, 12.0, shade, down=True)
    plate_field(hull, rng, offset(KEEL, 2.0), KEEL_Y[0], (0, 1), 5.0, 12.0, shade,
                keep_out=[offset(KEEL_LOWER, -2.0)], circles=[(s * 22.0, -50.0, 6.0) for s in (-1, 1)], down=True)
    plate_field(hull, rng, offset(lower_bottom, 2.0), KEEL_LOWER_Y[0], (0, 1), 10.0, 14.0, shade,
                keep_out=[offset(bay, -2.0), offset(spine, -1.0)], down=True)

    # --- Crimson spine down the lower tier, lined with floodlights.
    y = KEEL_LOWER_Y[0]
    hull.prism(spine, y, y - 0.6, "Crimson")
    for k in range(14):
        z = -24.0 + k * 12.0
        if not inside((0.0, z), offset(bay, -3.0)):
            for s in (-1, 1):
                hull.box((1.2, 0.5, 1.2), (s * 3.2, y - 0.4, z), "Window")

    # --- Ventral bay: a glowing grating in a dark frame.
    bx, bz = 0.0, 35.0
    hull.box((16.0, 1.2, 26.0), (bx, y - 0.6, bz), "Dark")
    hull.box((12.0, 0.2, 22.0), (bx, y - 1.25, bz), "Emitter")
    for k in range(5):
        hull.box((12.0, 0.6, 1.0), (bx, y - 1.5, bz - 8.8 + k * 4.4), "Dark")
    hull.box((1.0, 0.6, 22.0), (bx, y - 1.5, bz), "Dark")

    # --- Lit windows along both keel tiers' sides (their sides slope, so each
    # row follows the outline at its height).
    for y, spacing, skip in ((-19.0, 5.0, 0.2), (-25.0, 6.0, 0.35)):
        t = (y - KEEL_Y[0]) / (KEEL_Y[1] - KEEL_Y[0])
        window_row(hull, rng, scaled(KEEL, 1 + 0.06 * t), y, spacing, skip=skip)
    y = (KEEL_LOWER_Y[0] + KEEL_LOWER_Y[1]) / 2
    window_row(hull, rng, scaled(KEEL_LOWER, (1 + KEEL_LOWER_TAPER) / 2), y, 8.0, skip=0.4)

    # --- Radiator fins under the aft hull, outboard of the keel.
    for s in (-1, 1):
        for k in range(8):
            hull.box((0.8, 3.5, 18.0), (s * (58.0 + k * 2.4), HULL_Y[0] - 1.75, 158.0), "HullDark")

    # --- Sensor blisters under the keel's bow corners, and red running lights
    # on the keel tiers' corners.
    for s, n in ((-1, "L"), (1, "R")):
        b.cylinder("SensorBlister" + n, 2.5, 4.5, 3.0, (s * 22.0, KEEL_Y[0] - 1.5, -50.0), "Crimson",
                   axis="y", segments=12)
    for x, z in lower_bottom:
        hull.box((1.4, 1.4, 1.4), (x, KEEL_LOWER_Y[0] - 0.4, z), "RunningLight")
    for x, z in KEEL:
        hull.box((1.4, 1.4, 1.4), (x, KEEL_Y[0] - 0.4, z), "RunningLight")


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
    print("AI proxies written:", write_proxies())


def _prism_points(outline, y0, y1, top_scale=1.0):
    n = len(outline)
    cx = sum(p[0] for p in outline) / n
    cz = sum(p[1] for p in outline) / n
    pts = [(x, y0, z) for x, z in outline]
    pts += [(cx + (x - cx) * top_scale, y1, cz + (z - cz) * top_scale) for x, z in outline]
    return pts


# Hand-placed AI avoidance spheres (x, y, z, radius; before SCALE): the
# superstructure, the tower and bridge, and the hangar housings.
EXTRA_PROXIES = [(0, 55, 120, 28), (0, 30, 85, 20), (0, 30, 135, 22), (-78, 0, 60, 18), (78, 0, 60, 18)]


def proxy_layer(outline, y0, y1, r):
    """AI avoidance spheres of radius r filling a prism (outline between y0 and
    y1): a grid 2r apart, at mid-height, inside the outline."""
    y = (y0 + y1) / 2
    xs = [p[0] for p in outline]
    zs = [p[1] for p in outline]
    out = []
    z = min(zs) + r
    while z < max(zs):
        x = 0.0
        while x < max(abs(v) for v in xs):
            for side in ([1] if x == 0 else [1, -1]):
                if inside((x * side, z), outline):
                    out.append((x * side, y, z, r))
            x += 2 * r
        z += 2 * r
    return out


def write_proxies():
    """The destroyer's extra_proxies (destroyer.tscn), in game coordinates: the
    hand-placed ones plus layers covering the raised deck and the keel. The
    hull_outline grid destroyer.gd builds only covers the main hull's height,
    and at this size the AI otherwise flew into the deck and keel on attack runs."""
    spheres = list(EXTRA_PROXIES)
    spheres += proxy_layer(DECK, DECK_Y[0], DECK_Y[1], 14.0)
    # One layer for both keel tiers: centred lower, the spheres reach the
    # lower tier's bottom and still the keel's top.
    spheres += proxy_layer(KEEL, KEEL_LOWER_Y[0], KEEL_Y[1], 12.0)
    text = ", ".join("Vector4(%g, %g, %g, %g)" % tuple(c * SCALE for c in s) for s in spheres)
    with open(os.path.join(HERE, "proxies.txt"), "w") as f:
        f.write("extra_proxies = Array[Vector4]([%s])\n" % text)
    return len(spheres)


def write_collision():
    """Convex hull pieces in game coordinates, as Godot PackedVector3Array text."""
    pieces = {
        "Shape_body_aft": _prism_points(BODY_AFT, HULL_Y[0], HULL_Y[1]),
        "Shape_prong_l": _prism_points(PRONG_L, HULL_Y[0], HULL_Y[1]),
        "Shape_prong_r": _prism_points(PRONG_R, HULL_Y[0], HULL_Y[1]),
        "Shape_keel": _prism_points(KEEL, KEEL_Y[0], KEEL_Y[1], 1.06),
        "Shape_keel_lower": [(x, KEEL_LOWER_Y[0], z) for x, z in scaled(KEEL_LOWER, KEEL_LOWER_TAPER)]
                            + [(x, KEEL_LOWER_Y[1], z) for x, z in KEEL_LOWER],
        "Shape_deck": _prism_points(DECK, DECK_Y[0], DECK_Y[1], 0.94),
        "Shape_super": _prism_points(SUPER, SUPER_Y[0], SUPER_Y[1], 0.86),
        "Shape_tower": _prism_points(TOWER, TOWER_Y[0], TOWER_Y[1], TOWER_TOP_SCALE),
        "Shape_neck": [(x, NECK_Y[0], z) for x, z in scaled(TOWER, TOWER_TOP_SCALE)]
                      + [(x, NECK_Y[1], z) for x, z in NECK_TOP],
    }
    lines = []
    for name, pts in pieces.items():
        flat = ", ".join("%g, %g, %g" % tuple(c * SCALE for c in p) for p in pts)
        lines.append('[sub_resource type="ConvexPolygonShape3D" id="%s"]\npoints = PackedVector3Array(%s)\n'
                     % (name, flat))
    with open(os.path.join(HERE, "collision.txt"), "w") as f:
        f.write("\n".join(lines))


builder = build()
if EXPORT:
    export(builder)
print("destroyer built:", {k: len(v) for k, v in builder.groups.items()}, "exported" if EXPORT else "")
