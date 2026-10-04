"""Builds the Venomian enemy fighter (the "Mantis") in Blender and exports it.

Run inside Blender (Scripting tab, or through the Blender MCP):
    exec(open(r"<project>/models/enemy_fighter/source/build_enemy_fighter.py").read())
(set FORCE_EXPORT = True in the exec globals to export), or from the command line:
    blender --background --python build_enemy_fighter.py -- --export

Like build_destroyer.py, everything is in GAME coordinates (Godot: +X right,
+Y up, -Z is the nose), in metres, converted to Blender's Z-up frame by G().
The origin is the ship's centre (the node origin in enemy_fighter.tscn).

Materials are named so the game can recolour them per fighter type
(FighterModel, enemies/fighter_model.gd):
    Fighter_Accent   painted markings (pincer tips and bands, wing stripes, tip plates, fin)
    Fighter_Lights   glowing eye and running lights (pincer tips, wing edges, tip plates)
The engine glow is not part of the model: it's the Model/Glow node in the
scene, which Fighter scales with speed.

Exports enemy_fighter.glb next to the source folder.
"""

import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

EXPORT = "--export" in sys.argv or globals().get("FORCE_EXPORT", False)
HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else \
    r"C:\Users\zemc7\OneDrive\Documentos\spaceship-project\models\enemy_fighter\source"
OUT = os.path.dirname(HERE)

# (sRGB colour as the game shows it, emission strength). Accent and Lights are
# the elite's colours; the light fighter's are set in its scene.
COLORS = {
    "Hull": ((0.36, 0.40, 0.30), 0.0),
    "Dark": ((0.10, 0.11, 0.10), 0.0),
    "Canopy": ((0.16, 0.10, 0.20), 0.0),
    "Accent": ((0.50, 0.16, 0.46), 0.0),
    "Lights": ((1.0, 0.15, 0.1), 10.0),
}

# Gun barrels under the forelegs; MuzzleL/R in the scene sit at their tips.
GUN_X = 0.95
GUN_Y = -0.42
GUN_Z = (-0.4, -2.1)


def G(x, y, z):
    """Game (Y up, -Z forward) to Blender (Z up, +Y forward)."""
    return Vector((x, -z, y))


def material(name):
    full = "Fighter_" + name
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
        self.objects = []

    def _finish(self, name, me, mat, mirror=False, bevel=0.0, smooth=False):
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()
        o = bpy.data.objects.new(name, me)
        self.c.objects.link(o)
        me.materials.append(material(mat))
        if mirror:
            md = o.modifiers.new("Mirror", "MIRROR")
            md.use_axis[0] = True
            md.use_clip = True
        if bevel > 0:
            md = o.modifiers.new("Bevel", "BEVEL")
            md.width = bevel
            md.segments = 1
            md.limit_method = "ANGLE"
        for p in me.polygons:
            p.use_smooth = smooth
        self.objects.append(o)
        return o

    def loft(self, name, bottom, top, mat="Hull", mirror=False, bevel=0.0):
        """Join two rings of game-space (x, y, z) points with the same count."""
        n = len(bottom)
        verts = [G(*p) for p in bottom] + [G(*p) for p in top]
        faces = [tuple(range(n)), tuple(range(n, 2 * n))]
        faces += [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
        me = bpy.data.meshes.new(name)
        me.from_pydata(verts, [], faces)
        return self._finish(name, me, mat, mirror, bevel)

    def slab(self, name, outline, y0, y1, mat="Hull", mirror=False, bevel=0.0, top_scale=1.0):
        """Extrude a game-space outline (x, z) between heights y0 and y1."""
        n = len(outline)
        cx = sum(p[0] for p in outline) / n
        cz = sum(p[1] for p in outline) / n
        bottom = [(x, y0, z) for x, z in outline]
        top = [(cx + (x - cx) * top_scale, y1, cz + (z - cz) * top_scale) for x, z in outline]
        return self.loft(name, bottom, top, mat, mirror, bevel)

    def strip(self, name, a, b, width, y0, y1, mat, mirror=True):
        """A thin strip from a to b (game x, z), e.g. a light along a wing edge."""
        pa, pb = Vector(a), Vector(b)
        d = (pb - pa).normalized()
        p = Vector((d.y, -d.x)) * (width / 2)
        quad = [pa + p, pb + p, pb - p, pa - p]
        return self.slab(name, [(q.x, q.y) for q in quad], y0, y1, mat, mirror)

    def ellipsoid(self, name, radii, center, mat="Hull", segments=20):
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=segments, v_segments=segments // 2, radius=1.0)
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        me.transform(Matrix.Diagonal((radii[0], radii[2], radii[1], 1.0)))
        me.transform(Matrix.Translation(G(*center)))
        return self._finish(name, me, mat, smooth=True)

    def cylinder(self, name, r_front, r_back, z0, z1, x, y, mat="Dark", mirror=False, segments=10):
        """A cylinder/cone along game Z from z0 (r_front) to z1 (r_back), at (x, y)."""
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=segments, radius1=r_front, radius2=r_back,
                              depth=abs(z1 - z0))
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        me.transform(Matrix.Rotation(math.radians(90), 4, "X"))  # Blender Z -> -Y (radius1 at game -Z)
        me.transform(Matrix.Translation(G(x, y, (z0 + z1) / 2)))
        o = self._finish(name, me, mat, mirror)
        for p in me.polygons:
            p.use_smooth = len(p.vertices) == 4
        return o


def build():
    scene = bpy.data.scenes.get("EnemyFighter") or bpy.data.scenes.new("EnemyFighter")
    if bpy.context.window:
        bpy.context.window.scene = scene
    col = bpy.data.collections.get("EnemyFighter")
    if col is None:
        col = bpy.data.collections.new("EnemyFighter")
        scene.collection.children.link(col)
    for o in list(col.objects):
        bpy.data.objects.remove(o)
    for me in list(bpy.data.meshes):
        if me.users == 0:
            bpy.data.meshes.remove(me)
    b = Builder(col)

    # --- Body: a tapered wedge, a dark keel underneath, a canopy on top.
    b.loft("Body", [(-0.9, -0.4, 2.0), (-0.6, -0.4, -1.2), (0.6, -0.4, -1.2), (0.9, -0.4, 2.0)],
           [(-0.5, 0.45, 1.8), (-0.3, 0.3, -0.9), (0.3, 0.3, -0.9), (0.5, 0.45, 1.8)], "Hull", bevel=0.08)
    b.loft("Keel", [(-0.35, -0.62, 1.7), (-0.2, -0.5, -0.9), (0.2, -0.5, -0.9), (0.35, -0.62, 1.7)],
           [(-0.6, -0.38, 1.9), (-0.45, -0.38, -1.1), (0.45, -0.38, -1.1), (0.6, -0.38, 1.9)], "Dark")
    b.ellipsoid("Canopy", (0.3, 0.2, 0.5), (0.0, 0.42, 0.7), "Canopy", segments=16)
    # Dark ribs across the back, like an insect's segments.
    for i, z in enumerate((1.4, 1.68)):
        w = 0.48 + i * 0.04
        b.loft("Rib%d" % i, [(-w - 0.36, -0.38, z - 0.06), (w + 0.36, -0.38, z - 0.06),
                             (w + 0.36, -0.38, z + 0.06), (-w - 0.36, -0.38, z + 0.06)],
               [(-w, 0.47, z - 0.06), (w, 0.47, z - 0.06), (w, 0.47, z + 0.06), (-w, 0.47, z + 0.06)], "Dark")

    # The head: one big glowing compound eye on the forebody, under a dark crest.
    b.ellipsoid("Eye", (0.35, 0.28, 0.45), (0.0, 0.4, -0.55), "Lights", segments=16)
    b.loft("Crest", [(-0.38, 0.36, -0.05), (0.38, 0.36, -0.05), (0.2, 0.36, 0.25), (-0.2, 0.36, 0.25)],
           [(-0.12, 0.72, -0.15), (0.12, 0.72, -0.15), (0.06, 0.6, 0.25), (-0.06, 0.6, 0.25)], "Dark")

    # --- Pincers: two forelegs reaching past the nose, accent tips with glowing points.
    b.loft("Prong", [(0.6, -0.3, 0.2), (0.75, -0.3, -2.4), (0.55, -0.3, -3.3), (0.95, -0.3, -2.5), (1.3, -0.3, 0.3)],
           [(0.62, 0.15, 0.03), (0.76, 0.15, -2.31), (0.58, 0.15, -3.12), (0.94, 0.15, -2.4), (1.25, 0.15, 0.12)],
           "Dark", mirror=True)
    b.slab("ProngTip", [(0.62, -2.9), (0.55, -3.3), (0.82, -2.95)], -0.25, 0.12, "Accent", mirror=True)
    # On the front of each tip, so it faces whoever the fighter is coming at.
    b.slab("ProngLight", [(0.53, -3.36), (0.66, -3.1), (0.6, -3.0), (0.5, -3.22)], -0.2, 0.08, "Lights",
           mirror=True)
    # A painted band round each foreleg.
    b.slab("ProngBand", [(0.7, -1.2), (0.7, -1.5), (1.06, -1.4), (1.1, -1.1)], -0.33, 0.18, "Accent", mirror=True)

    # --- Wings: swept back from the rear of the body, with upright tip plates.
    wing = [(0.85, 0.2), (3.0, 1.6), (3.1, 2.3), (0.85, 1.9)]
    b.slab("Wing", wing, -0.08, 0.08, "Hull", mirror=True)
    b.slab("WingStripe", [(1.3, 0.75), (2.7, 1.65), (2.75, 1.95), (1.3, 1.25)], 0.08, 0.11, "Accent", mirror=True)
    # Wrapped round the leading edge (top to bottom) so it faces forward: lying on
    # top of the wing, a light is edge-on to anyone ahead.
    b.strip("WingLight", (0.88, 0.15), (2.98, 1.53), 0.16, -0.11, 0.12, "Lights")
    b.loft("WingTip", [(2.75, -0.6, 1.4), (3.0, -0.6, 1.6), (3.1, -0.6, 2.3), (2.85, -0.6, 2.2)],
           [(2.8, 0.6, 1.54), (2.98, 0.6, 1.68), (3.05, 0.6, 2.17), (2.87, 0.6, 2.1)], "Accent", mirror=True)
    # A light bar down the front edge of each tip plate.
    b.slab("TipLight", [(2.7, 1.33), (2.86, 1.36), (2.92, 1.5), (2.76, 1.47)], -0.66, 0.66, "Lights", mirror=True)

    # Guns slung under the forelegs.
    b.cylinder("Gun", 0.07, 0.11, GUN_Z[1], GUN_Z[0], GUN_X, GUN_Y, "Dark", mirror=True)
    b.cylinder("GunMount", 0.16, 0.16, GUN_Z[0] - 0.1, GUN_Z[0] + 0.5, GUN_X, GUN_Y, "Dark", mirror=True)

    # --- Tail: a dorsal fin and twin engine nozzles.
    b.slab("Fin", [(-0.06, 2.0), (-0.06, 0.6), (0.06, 0.6), (0.06, 2.0)], 0.4, 1.4, "Accent", top_scale=0.5)
    b.cylinder("Nozzle", 0.28, 0.24, 1.9, 2.25, 0.32, 0.0, "Dark", mirror=True, segments=14)
    return b


def export(b):
    bpy.ops.object.select_all(action="DESELECT")
    for o in b.objects:
        o.select_set(True)
    bpy.context.view_layer.objects.active = b.objects[0]
    bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "enemy_fighter.glb"), export_format="GLB",
                              use_selection=True, use_active_scene=True, export_apply=True, export_yup=True,
                              export_materials="EXPORT", export_cameras=False, export_lights=False)


builder = build()
if EXPORT:
    export(builder)
print("enemy fighter built:", len(builder.objects), "objects", "exported" if EXPORT else "")
