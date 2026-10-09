"""Exports corneria.blend (the map's master copy) to the game. Reads whatever
is in the map; nothing has to be pasted by hand.

    blender --background corneria.blend --python export_corneria.py

Writes, into models/corneria2/:
    corneria_map.tres      the TerrainMap: the terrain sampled from above at
                           every grid point, per-cell paint (from the Paint
                           colour layer), the high-water level, and the
                           structure heights the AI flies over (measured from
                           the props' actual geometry)
    corneria_layout.tres   the PropLayout: every kit piece instance in Props
                           (with nested prefabs flattened), its group and its
                           transform
    corneria_kit.glb       one mesh per kit piece the layout uses, about its
                           origin (its collection's instance offset)
    corneria_props.glb     everything else in Props (one-off meshes, and kit
                           instances that are mirrored, which a MultiMesh
                           can't draw), one mesh per group per PROP_TILE
                           square, named "<group>__<i>_<j>"
    corneria_markers.tres  the Markers empties' transforms (MapMarkers)
"""

import math
import os
import sys
import time

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import corneria_common as cc  # noqa: E402

CELLS = cc.POINTS - 1
MISSING_GROUND = -20.0   # height where a ray finds no terrain
PAVED, HIGH_WATER = 1, 2  # TerrainMap.PAINT_*


def number(v, places=2):
    s = "%.*f" % (places, v)
    s = s.rstrip("0").rstrip(".") if "." in s else s
    return "0" if s == "-0" else s


def log(t0, what):
    print("  %-34s %6.1f s" % (what, time.time() - t0))


# --- Terrain ------------------------------------------------------------------
def terrain_samples():
    """Ground heights at every grid point and paint per cell (sampled from
    above: rays straight down onto the evaluated terrain, so sculpting,
    modifiers and moved vertices all count)."""
    obj = bpy.data.objects["Terrain"]
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    me = ev.to_mesh()
    mw = obj.matrix_world
    verts = [mw @ v.co for v in me.vertices]
    polys = [tuple(p.vertices) for p in me.polygons]
    bvh = BVHTree.FromPolygons(verts, polys)

    # Paint per polygon: the mean of its points' (or corners') colours.
    face_paint = [0] * len(polys)
    layer = me.color_attributes.get(cc.PAINT_ATTRIBUTE)
    if layer is not None:
        colors = np.empty(len(layer.data) * 4, dtype=np.float32)
        layer.data.foreach_get("color", colors)
        colors = colors.reshape(-1, 4)
        for k, p in enumerate(me.polygons):
            ids = list(p.vertices) if layer.domain == "POINT" else list(p.loop_indices)
            c = colors[ids].mean(axis=0)
            if c[0] > 0.5:
                face_paint[k] = PAVED
            elif c[2] > 0.5:
                face_paint[k] = HIGH_WATER
    ev.to_mesh_clear()

    down = Vector((0, 0, -1))
    top = 20000.0
    heights = np.empty(cc.POINTS * cc.POINTS, dtype=np.float64)
    misses = 0
    for j in range(cc.POINTS):
        gz = -cc.HALF + j * cc.CELL
        for i in range(cc.POINTS):
            gx = -cc.HALF + i * cc.CELL
            hit = bvh.ray_cast(Vector((gx, -gz, top)), down)
            if hit[0] is None:
                # Exactly on an edge (the map's border above all), the ray can
                # slip through: nudge it a centimetre towards the middle.
                nx = -0.01 if gx > 0 else 0.01
                ny = -0.013 if -gz > 0 else 0.013
                hit = bvh.ray_cast(Vector((gx + nx, -gz + ny, top)), down)
            if hit[0] is None:
                misses += 1
                heights[j * cc.POINTS + i] = MISSING_GROUND
            else:
                heights[j * cc.POINTS + i] = hit[0].z
    paint = np.zeros(CELLS * CELLS, dtype=np.uint8)
    for j in range(CELLS):
        gz = -cc.HALF + (j + 0.5) * cc.CELL
        for i in range(CELLS):
            gx = -cc.HALF + (i + 0.5) * cc.CELL
            hit = bvh.ray_cast(Vector((gx, -gz, top)), down)
            if hit[2] is not None:
                paint[j * CELLS + i] = face_paint[hit[2]]
    if misses:
        print("  warning: %d grid points have no terrain above or below them" % misses)
    return heights, paint


# --- Props ------------------------------------------------------------------
class Props:
    """Everything in the Props collection, flattened: kit instances (group,
    piece collection, Blender matrix of the piece's own space, where its
    origin is the collection's instance offset) and other meshes (group,
    object, Blender matrix of the object's mesh)."""

    def __init__(self):
        self.instances = []
        self.meshes = []
        props = bpy.data.collections["Props"]
        for group_col in props.children:
            if group_col.name not in cc.GROUPS:
                print("  warning: Props/%s is not a known group; skipped" % group_col.name)
                continue
            self.walk(group_col, Matrix.Identity(4), group_col.name, 0)

    def walk(self, col, parent, group, depth):
        if depth > 8:
            raise RuntimeError("prefabs nested too deep (an instance of itself?) in " + col.name)
        for o in col.objects:
            m = parent @ o.matrix_world
            if o.instance_type == "COLLECTION" and o.instance_collection is not None:
                c = o.instance_collection
                if c.name.startswith(cc.KIT_PREFIX):
                    self.instances.append((group, c, m))
                else:
                    # A prefab: its objects stand at instancer @ -offset @ their own matrix.
                    self.walk(c, m @ Matrix.Translation(-c.instance_offset), group, depth + 1)
            elif o.type == "MESH":
                self.meshes.append((group, o, m))
        for child in col.children:
            self.walk(child, parent, group, depth + 1)


def collection_objects(col):
    yield from col.objects
    for child in col.children:
        yield from collection_objects(child)


def evaluated(o):
    """A new mesh: object `o`'s geometry with its modifiers applied (in its own space)."""
    dg = bpy.context.evaluated_depsgraph_get()
    return bpy.data.meshes.new_from_object(o.evaluated_get(dg), preserve_all_data_layers=False, depsgraph=dg)


def joined(parts, name):
    """One new object (not linked anywhere) joining (mesh, Blender matrix)
    pairs, each transformed by its matrix (mirrored ones get their faces turned
    back out). The part meshes are removed."""
    bm = bmesh.new()
    materials = []
    for part, m in parts:
        part.transform(m)
        if m.determinant() < 0:
            part.flip_normals()
        # Remap material slots into the joined mesh's list.
        remap = []
        for mat in part.materials:
            if mat not in materials:
                materials.append(mat)
            remap.append(materials.index(mat))
        for p in part.polygons:
            p.material_index = remap[p.material_index] if remap else 0
        bm.from_mesh(part)
        bpy.data.meshes.remove(part)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for mat in materials:
        me.materials.append(mat)
    return bpy.data.objects.new(name, me)


def piece_parts(piece, m):
    """Kit piece `piece` (a collection) as (mesh, matrix) parts placed by `m`
    (a matrix of the piece's own space: its origin the instance offset)."""
    offset = Matrix.Translation(-piece.instance_offset)
    return [(evaluated(o), m @ offset @ o.matrix_world) for o in collection_objects(piece) if o.type == "MESH"]


def kit_mesh(piece):
    """Kit piece `piece` as one object about its origin."""
    return joined(piece_parts(piece, Matrix.Identity(4)), piece.name)


def tile_of(x, z):
    """The export tile of a game-space point."""
    return (int(math.floor((x + cc.HALF) / cc.PROP_TILE)), int(math.floor((z + cc.HALF) / cc.PROP_TILE)))


def split_by_tile(obj, group):
    """`obj` (world-space geometry) cut into one object per tile its faces'
    centres fall in, named "<group>__<i>_<j>"; `obj` is removed."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    by_tile = {}
    for f in bm.faces:
        c = f.calc_center_median()
        by_tile.setdefault(tile_of(c.x, -c.y), set()).add(f.index)
    out = []
    for (i, j), keep in by_tile.items():
        part = bm.copy()
        part.faces.ensure_lookup_table()
        bmesh.ops.delete(part, geom=[f for f in part.faces if f.index not in keep], context="FACES")
        me = bpy.data.meshes.new("%s__%d_%d" % (group, i, j))
        part.to_mesh(me)
        part.free()
        for mat in obj.data.materials:
            me.materials.append(mat)
        out.append(((group, i, j), me))
    bm.free()
    me = obj.data
    bpy.data.objects.remove(obj)
    bpy.data.meshes.remove(me)
    return out


def leftovers(props):
    """The one-off geometry and the mirrored instances, joined per group per
    tile: [object] (not linked anywhere yet)."""
    pieces = {}
    items = [(g, [(evaluated(o), m)]) for g, o, m in props.meshes if o.type == "MESH"]
    items += [(g, piece_parts(c, m)) for g, c, m in props.instances if m.determinant() < 0]
    for n, (group, parts) in enumerate(items):
        for key, me in split_by_tile(joined(parts, "part%d" % n), group):
            pieces.setdefault(key, []).append(me)
    return [joined([(me, Matrix.Identity(4)) for me in meshes], "%s__%d_%d" % key)
            for key, meshes in sorted(pieces.items())]


# --- Structure heights ----------------------------------------------------------
def triangles(obj):
    """An object's triangles as an (n, 3, 3) array (its mesh's own coordinates)."""
    me = obj.data
    me.calc_loop_triangles()
    co = np.empty(len(me.vertices) * 3, dtype=np.float64)
    me.vertices.foreach_get("co", co)
    tri = np.empty(len(me.loop_triangles) * 3, dtype=np.int64)
    me.loop_triangles.foreach_get("vertices", tri)
    return co.reshape(-1, 3)[tri.reshape(-1, 3)]


def raster(tops, tris):
    """Raises `tops` (CELLS x CELLS) to the top of every triangle (Blender
    world coordinates) over each cell its outline overlaps."""
    if len(tris) == 0:
        return
    gx = tris[:, :, 0]
    gz = -tris[:, :, 1]
    top = tris[:, :, 2].max(axis=1)
    i0 = np.clip(np.floor((gx.min(axis=1) + cc.HALF) / cc.CELL).astype(np.int64), 0, CELLS - 1)
    i1 = np.clip(np.floor((gx.max(axis=1) + cc.HALF) / cc.CELL).astype(np.int64), 0, CELLS - 1)
    j0 = np.clip(np.floor((gz.min(axis=1) + cc.HALF) / cc.CELL).astype(np.int64), 0, CELLS - 1)
    j1 = np.clip(np.floor((gz.max(axis=1) + cc.HALF) / cc.CELL).astype(np.int64), 0, CELLS - 1)
    flat = tops.reshape(-1)
    small = ((i1 - i0) <= 3) & ((j1 - j0) <= 3)
    for a in range(4):
        for b in range(4):
            m = small & (i0 + a <= i1) & (j0 + b <= j1)
            np.maximum.at(flat, (j0[m] + b) * CELLS + i0[m] + a, top[m])
    for k in np.nonzero(~small)[0]:
        sub = tops[j0[k]:j1[k] + 1, i0[k]:i1[k] + 1]
        np.maximum(sub, top[k], out=sub)


def structure_heights(props, kit_objects, leftover_objects):
    tops = np.zeros((CELLS, CELLS), dtype=np.float64)
    local = {name: triangles(o) for name, o in kit_objects.items()}
    for group, piece, m in props.instances:
        if not cc.GROUPS[group]["structure"] or m.determinant() < 0:
            continue
        t = local[piece.name]
        mat = np.array(m)
        raster(tops, t @ mat[:3, :3].T + mat[:3, 3])
    for o in leftover_objects:
        if cc.GROUPS[o.name.split("__")[0]]["structure"]:
            raster(tops, triangles(o))
    return tops


# --- Writing ------------------------------------------------------------------
def export_glb(objects, path):
    col = bpy.data.collections.new("ExportTemp")
    bpy.context.scene.collection.children.link(col)
    try:
        bpy.ops.object.select_all(action="DESELECT")
        for o in objects:
            col.objects.link(o)
            o.select_set(True)
        bpy.context.view_layer.objects.active = objects[0]
        bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, use_active_scene=True,
                                  export_apply=True, export_yup=True, export_materials="EXPORT",
                                  export_cameras=False, export_lights=False)
    finally:
        for o in objects:
            col.objects.unlink(o)
        bpy.data.collections.remove(col)


def write_map(heights, paint, tops):
    scene = bpy.context.scene
    with open(os.path.join(cc.OUT, "corneria_map.tres"), "w", newline="\n") as f:
        f.write('[gd_resource type="Resource" script_class="TerrainMap" format=3]\n\n')
        f.write('[ext_resource type="Script" path="res://world/terrain_map.gd" id="1_map"]\n\n')
        f.write('[resource]\nscript = ExtResource("1_map")\n')
        f.write("size = %s\npoints = %d\nhigh_water_level = %s\n" % (
            number(cc.SIZE), cc.POINTS, number(scene.get("high_water_level", 0.0))))
        f.write("heights = PackedFloat32Array(%s)\n" % ", ".join(number(h) for h in heights))
        f.write("paint = PackedByteArray(%s)\n" % ", ".join(str(p) for p in paint))
        f.write("structures = PackedFloat32Array(%s)\n" % ", ".join(number(t) for t in tops.reshape(-1)))


def write_layout(props):
    placed = [(g, c.name, m) for g, c, m in props.instances if m.determinant() > 0]
    pieces = sorted({p[1] for p in placed})
    groups = sorted({p[0] for p in placed})
    with open(os.path.join(cc.OUT, "corneria_layout.tres"), "w", newline="\n") as f:
        f.write('[gd_resource type="Resource" script_class="PropLayout" format=3]\n\n')
        f.write('[ext_resource type="Script" path="res://world/prop_layout.gd" id="1_layout"]\n\n')
        f.write('[resource]\nscript = ExtResource("1_layout")\n')
        f.write("pieces = PackedStringArray(%s)\n" % ", ".join('"%s"' % p for p in pieces))
        f.write("groups = PackedStringArray(%s)\n" % ", ".join('"%s"' % g for g in groups))
        f.write("piece = PackedInt32Array(%s)\n" % ", ".join(str(pieces.index(p[1])) for p in placed))
        f.write("group = PackedInt32Array(%s)\n" % ", ".join(str(groups.index(p[0])) for p in placed))
        values = []
        for _, _, m in placed:
            g = cc.game_matrix(m)
            # Basis columns x, y, z to 5 places, then the origin to the centimetre.
            values += [number(g[r][c], 5) for c in range(3) for r in range(3)]
            values += [number(g[r][3]) for r in range(3)]
        f.write("transforms = PackedFloat32Array(%s)\n" % ", ".join(values))
    return len(placed), pieces


def write_markers():
    lines = []
    for name in cc.MARKERS:
        o = bpy.data.objects.get(name)
        if o is None:
            print("  warning: no marker " + name)
            continue
        # Markers place things: their scale doesn't count.
        loc, rot, _ = o.matrix_world.decompose()
        m = cc.game_matrix(Matrix.LocRotScale(loc, rot, None))
        # Godot's Transform3D text: the basis row by row, then the origin.
        vals = [number(m[r][c], 6) for r in range(3) for c in range(3)] + [number(m[r][3]) for r in range(3)]
        lines.append('"%s": Transform3D(%s)' % (name, ", ".join(vals)))
    with open(os.path.join(cc.OUT, "corneria_markers.tres"), "w", newline="\n") as f:
        f.write('[gd_resource type="Resource" script_class="MapMarkers" format=3]\n\n')
        f.write('[ext_resource type="Script" path="res://world/map_markers.gd" id="1_markers"]\n\n')
        f.write('[resource]\nscript = ExtResource("1_markers")\n')
        f.write("markers = {\n%s\n}\n" % ",\n".join(lines))


def main():
    if os.path.normcase(bpy.data.filepath) != os.path.normcase(cc.MAP_FILE):
        bpy.ops.wm.open_mainfile(filepath=cc.MAP_FILE)
    t0 = time.time()
    print("exporting", cc.MAP_FILE)
    heights, paint = terrain_samples()
    log(t0, "terrain sampled")
    props = Props()
    # The kit meshes are exported under their pieces' names, which the map's
    # own objects may hold (a placed piece is named after it): those step
    # aside until the export is done.
    pieces_used = {c for _, c, _ in props.instances}
    renamed = []
    for c in pieces_used:
        holder = bpy.data.objects.get(c.name)
        if holder is not None and holder.library is None:
            renamed.append((holder, holder.name))
            holder.name = holder.name + "__placed"
    kit_objects = {c.name: kit_mesh(c) for c in pieces_used}
    for o in kit_objects.values():
        assert o.name in kit_objects, "kit mesh exported as %s" % o.name
    rest = leftovers(props)
    log(t0, "props gathered")
    tops = structure_heights(props, kit_objects, rest)
    log(t0, "structure heights")
    write_map(heights, paint, tops)
    count, pieces = write_layout(props)
    write_markers()
    if rest:
        export_glb(rest, os.path.join(cc.OUT, "corneria_props.glb"))
    else:
        print("  warning: nothing but kit instances: corneria_props.glb not written")
    used = [kit_objects[p] for p in pieces]
    if used:
        export_glb(used, os.path.join(cc.OUT, "corneria_kit.glb"))
    log(t0, "written")
    for o in list(kit_objects.values()) + rest:
        me = o.data
        bpy.data.objects.remove(o)
        bpy.data.meshes.remove(me)
    for holder, name in renamed:
        holder.name = name
    print("exported: %d kit instances of %d pieces, %d prop tiles, %d structure cells, %d paved, %d high water" % (
        count, len(pieces), len(rest), int((tops > 0).sum()), int((paint == PAVED).sum()),
        int((paint == HIGH_WATER).sum())))


main()
