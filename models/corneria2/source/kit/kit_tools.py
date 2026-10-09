"""Shared by the kit build scripts (kit_*.py beside this file), which build
the real kit pieces into kit.blend (spec: models/corneria2/ASSETS.md).

    blender --background --python kit_city.py            builds into kit.blend
    KIT_OUT=<copy.blend> blender --background --python kit_city.py
                                                          ...into a copy instead
    KIT_PREVIEW=<dir>  also renders each piece built to <dir>/<piece>_front.png
                       and _back.png (front three-quarter / back three-quarter,
                       backface culling on, so a face pointing in shows as a hole)

A script calls begin(), builds each piece with piece() and a Builder, then
finish(). piece() replaces a collection only if it is missing, a placeholder
("greybox") or made by the same script (custom property "kit_script"): a
piece someone has edited by hand and unmarked is left alone.

Builder: geometry in the piece's own space (Blender metres, Z up, origin at
the centre of the footprint on the ground, front facing -Y). Vertices at the
same spot are merged, so pieces built side by side share edges; faces get
palette materials by name (corneria_common.PALETTE, without "Corneria_").
Surfaces split into cells (prism(), lathe(), grid()) can paint each cell its
own material: windows, bands and stripes that are part of the surface, so they
draw no ink line and nothing stands off it.

Two traps: two prisms stacked on the same outline in one Builder share their
rim edges (four faces on an edge: "non-manifold"), so use one prism with
`levels`, inset one, or build them in separate Builders. And caps take every
cut on their edge (closed, no T-junctions), so a finely cut side costs cap
triangles too.
"""

import math
import os
import shutil
import sys
from contextlib import contextmanager

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import corneria_common as cc  # noqa: E402

SMOOTH_ANGLE = math.radians(30.0)   # smooth-shaded faces meet at a crease (ink line) above this angle
MERGE = 1e-4                         # vertices closer than this are one
ROW_GAP = 400.0                      # each script's pieces stand in their own row in kit.blend, this far apart
PIECE_GAP = 30.0                     # ...this far apart along it

# Stack parts (ASSETS.md) are open where they join flush: a cap there ends
# exactly on the wall above or below it, so along the joint a few pixels show
# the hidden cap instead of the wall and the ink pass dots them. check()
# accepts open edges at these ends (the plug fills any crack behind).
JOINTS = {"Base": ("top",), "Shaft": ("bottom", "top"), "Crown": ("bottom",)}

_state = {}


# --- The kit file ------------------------------------------------------------------
def kit_file():
    return os.environ.get("KIT_OUT") or cc.KIT_FILE


def begin(script, row):
    """Opens the kit file (a KIT_OUT copy is first made from kit.blend if it
    doesn't exist). `script`: this script's name; `row`: its row in the file."""
    path = kit_file()
    if not os.path.exists(path):
        shutil.copyfile(cc.KIT_FILE, path)
    bpy.ops.wm.open_mainfile(filepath=path)
    _state.update(script=script, row=row, x=0.0, built=[], skipped=[])
    parent = bpy.data.collections.get("Built_" + script)
    if parent is None:
        parent = bpy.data.collections.new("Built_" + script)
        bpy.context.scene.collection.children.link(parent)
    _state["parent"] = parent


def piece(name, builders, width=None):
    """Makes collection `name` from `builders` [(object name suffix, Builder)]
    (one object each, "<name>" or "<name>_<suffix>"), standing at the next
    spot in this script's row. Returns the collection, or None if it was
    left alone (hand-made)."""
    col = bpy.data.collections.get(name)
    if col is not None and not col.get("greybox") and col.get("kit_script") != _state["script"]:
        print("  %s: hand-made (no kit_script mark), left alone" % name)
        _state["skipped"].append(name)
        return None
    if col is not None:
        cc.clear_collection(col)
        for parent in [c for c in bpy.data.collections if col.name in c.children]:
            parent.children.unlink(col)
        for scene in bpy.data.scenes:
            if col.name in scene.collection.children:
                scene.collection.children.unlink(col)
    else:
        col = bpy.data.collections.new(name)
    _state["parent"].children.link(col)
    if "greybox" in col:
        del col["greybox"]
    col["kit_script"] = _state["script"]
    objects = [b.object(name if not suffix else name + "_" + suffix) for suffix, b in builders]
    lo = min(min(v.co.x for v in o.data.vertices) for o in objects)
    hi = max(max(v.co.x for v in o.data.vertices) for o in objects)
    at = Vector((_state["x"] - lo, _state["row"] * ROW_GAP, 0.0))
    _state["x"] += (hi - lo) + PIECE_GAP
    for o in objects:
        o.location = at
        col.objects.link(o)
    col.instance_offset = at
    _state["built"].append(name)
    return col


def finish():
    """Saves the kit file, prints each piece's check, renders previews if asked."""
    bpy.ops.wm.save_as_mainfile(filepath=kit_file())
    print("\n%s: %d pieces built into %s" % (_state["script"], len(_state["built"]), kit_file()))
    problems = 0
    for name in _state["built"]:
        problems += check(bpy.data.collections[name])
    if _state["skipped"]:
        print("left alone (hand-made): " + ", ".join(_state["skipped"]))
    print("%d problem(s)" % problems)
    out = os.environ.get("KIT_PREVIEW")
    if out:
        os.makedirs(out, exist_ok=True)
        for name in _state["built"]:
            preview(bpy.data.collections[name], out)
        print("previews in " + out)


# --- Building ------------------------------------------------------------------------
class Builder:
    """One object's geometry. Points pass through the current transform
    (`with b.at(matrix):`), so a part can be built about its own origin and
    moved, turned or mirrored into place."""

    def __init__(self):
        self.verts = []
        self.index = {}
        self.faces = []        # (vertex indices, material name, smooth)
        self.xf = [Matrix.Identity(4)]

    @contextmanager
    def at(self, m):
        """Builds what follows through matrix `m` (on top of any current one)."""
        self.xf.append(self.xf[-1] @ m)
        try:
            yield self
        finally:
            self.xf.pop()

    def vert(self, p):
        v = self.xf[-1] @ Vector(p)
        key = (round(v.x / MERGE), round(v.y / MERGE), round(v.z / MERGE))
        if key not in self.index:
            self.index[key] = len(self.verts)
            self.verts.append(v)
        return self.index[key]

    def face(self, points, mat, smooth=False):
        """A face through `points` (anticlockwise seen from its front)."""
        idx = []
        for p in points:
            k = self.vert(p)
            if not idx or idx[-1] != k:
                idx.append(k)
        if len(idx) > 2 and idx[0] == idx[-1]:
            idx.pop()
        if len(idx) >= 3:
            if self.xf[-1].determinant() < 0:      # mirrored: keep the front out
                idx.reverse()
            self.faces.append((idx, mat, smooth))

    # -- Shapes ---------------------------------------------------------------------
    def prism(self, outline, z0, z1, mat, levels=(), columns=None, cell=None, top=True, bottom=True,
              top_mat=None, bottom_mat=None, smooth=False):
        """An upright prism: `outline` [(x, y)] anticlockwise seen from above,
        from z0 to z1. Its sides are cut at heights `levels` and, along each
        side, into `columns` (metres: cells about that wide; or a function
        (side index, side length) -> [cut fractions 0..1]). cell(side, column,
        row, (u0, u1) fractions, (za, zb)) -> a material name (None: `mat`)
        paints each cell. Caps take every cut on their edge, so the mesh stays
        closed."""
        zs = [z0] + sorted(z for z in levels if z0 < z < z1) + [z1]
        n = len(outline)
        top_ring, bottom_ring = [], []
        for s in range(n):
            a, b = Vector(outline[s]), Vector(outline[(s + 1) % n])
            length = (b - a).length
            if columns is None:
                cuts = []
            elif callable(columns):
                cuts = sorted(columns(s, length))
            else:
                k = max(1, round(length / columns))
                cuts = [i / k for i in range(1, k)]
            us = [0.0] + cuts + [1.0]
            for c in range(len(us) - 1):
                p0, p1 = a.lerp(b, us[c]), a.lerp(b, us[c + 1])
                for r in range(len(zs) - 1):
                    m = (cell(s, c, r, (us[c], us[c + 1]), (zs[r], zs[r + 1])) if cell else None) or mat
                    self.face([(p0.x, p0.y, zs[r]), (p1.x, p1.y, zs[r]), (p1.x, p1.y, zs[r + 1]),
                               (p0.x, p0.y, zs[r + 1])], m, smooth)
            for u in us[:-1]:
                p = a.lerp(b, u)
                top_ring.append((p.x, p.y, z1))
                bottom_ring.append((p.x, p.y, z0))
        if top:
            self.face(top_ring, top_mat or mat)
        if bottom:
            self.face(bottom_ring[::-1], bottom_mat or mat)

    def box(self, x0, y0, z0, x1, y1, z1, mat, **kw):
        """An axis-aligned box from corner to corner (prism() options apply)."""
        self.prism([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], z0, z1, mat, **kw)

    def lathe(self, profile, mat, segments=16, cell=None, smooth=True, cap_mat=None, turn=0.0):
        """A round shape about the Z axis: `profile` [(radius, z)] from bottom
        to top (radius 0 at an end closes it to a point; otherwise it gets a
        flat cap). cell(segment, row) -> material name (None: `mat`).
        Smooth-shaded: sharp profile corners still crease (SMOOTH_ANGLE)."""
        rings = []
        for r, z in profile:
            if r <= 0.0:
                rings.append([(0.0, 0.0, z)] * segments)
            else:
                rings.append([(r * math.cos(turn + 2 * math.pi * k / segments),
                               r * math.sin(turn + 2 * math.pi * k / segments), z) for k in range(segments)])
        for i in range(len(rings) - 1):
            for k in range(segments):
                k1 = (k + 1) % segments
                m = (cell(k, i) if cell else None) or mat
                self.face([rings[i][k], rings[i][k1], rings[i + 1][k1], rings[i + 1][k]], m, smooth)
        if profile[0][0] > 0.0:
            self.face(rings[0][::-1], cap_mat or mat)
        if profile[-1][0] > 0.0:
            self.face(rings[-1], cap_mat or mat)

    def extrude(self, outline, y0, y1, mat, cell=None, smooth=False, cap_mat=None):
        """A side profile `outline` [(x, z)] (anticlockwise seen from the
        front, -Y) pushed back from y0 to y1 (y0 < y1): gables, vaults,
        arches. cell(side index) -> material for each side strip."""
        n = len(outline)
        for s in range(n):
            (ax, az), (bx, bz) = outline[s], outline[(s + 1) % n]
            m = (cell(s) if cell else None) or mat
            self.face([(ax, y0, az), (ax, y1, az), (bx, y1, bz), (bx, y0, bz)], m, smooth)
        self.face([(x, y0, z) for x, z in outline], cap_mat or mat)
        self.face([(x, y1, z) for x, z in outline[::-1]], cap_mat or mat)

    def grid(self, origin, u, v, nu, nv, cell, mat):
        """A flat panel split nu x nv: origin + i/nu u + j/nv v; its front
        faces u x v. cell(i, j) -> material (None: `mat`). For painting a
        face of a shape built with face() by hand."""
        o, u, v = Vector(origin), Vector(u), Vector(v)
        for i in range(nu):
            for j in range(nv):
                p = lambda a, b: tuple(o + u * (a / nu) + v * (b / nv))
                self.face([p(i, j), p(i + 1, j), p(i + 1, j + 1), p(i, j + 1)], cell(i, j) or mat)

    # -- Into Blender ---------------------------------------------------------------
    def object(self, name):
        mats = []
        for _, m, _ in self.faces:
            if m not in mats:
                mats.append(m)
        me = bpy.data.meshes.new(name)
        me.from_pydata([tuple(v) for v in self.verts], [], [f for f, _, _ in self.faces])
        for m in mats:
            me.materials.append(cc.material(m))
        for p, (_, m, smooth) in zip(me.polygons, self.faces):
            p.material_index = mats.index(m)
            p.use_smooth = smooth
        me.validate()
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()
        if any(p.use_smooth for p in me.polygons):
            me.set_sharp_from_angle(angle=SMOOTH_ANGLE)
        return bpy.data.objects.new(name, me)


# --- Checks --------------------------------------------------------------------------
def check(col):
    """Prints a piece's triangles, size (game w x h x d), origin and
    problems: open edges, parts facing in, tiny faces, foreign materials.
    Returns the number of problems."""
    tris, problems, notes = 0, 0, []
    lo = Vector((math.inf,) * 3)
    hi = Vector((-math.inf,) * 3)
    mats = set()
    for o in col.all_objects:
        if o.type != "MESH":
            continue
        me = o.data
        me.calc_loop_triangles()
        tris += len(me.loop_triangles)
        m = Matrix.Translation(-col.instance_offset) @ o.matrix_world
        for v in me.vertices:
            p = m @ v.co
            lo = Vector(map(min, lo, p))
            hi = Vector(map(max, hi, p))
        mats |= {s.material.name for s in o.material_slots if s.material}
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.transform(m)
        # A stack part is left open where it joins the next one (see
        # JOINTS): edges at those heights don't count.
        joint_z = [z for z, which in ((min(v.co.z for v in bm.verts), "bottom"),
                                      (max(v.co.z for v in bm.verts), "top"))
                   if which in JOINTS.get(col.name.rsplit("_", 1)[-1], ()) and not o.name.endswith("_Plug")]
        open_edges = sum(1 for e in bm.edges if not e.is_manifold
                         and not any(all(abs(v.co.z - z) < 1e-3 for v in e.verts) for z in joint_z))
        if open_edges:
            problems += 1
            notes.append("%s: %d open/non-manifold edges" % (o.name, open_edges))
        tiny = sum(1 for f in bm.faces if f.calc_area() < 1e-6)
        if tiny:
            problems += 1
            notes.append("%s: %d zero-area faces" % (o.name, tiny))
        # Each closed part's signed volume: negative = built inside out.
        bm.faces.ensure_lookup_table()
        seen = set()
        for f in bm.faces:
            if f.index in seen:
                continue
            part, stack = [], [f]
            seen.add(f.index)
            while stack:
                g = stack.pop()
                part.append(g)
                for e in g.edges:
                    for h in e.link_faces:
                        if h.index not in seen:
                            seen.add(h.index)
                            stack.append(h)
            vol = 0.0
            for g in part:
                vs = [l.vert.co for l in g.loops]
                for i in range(1, len(vs) - 1):
                    vol += vs[0].dot(vs[i].cross(vs[i + 1])) / 6.0
            if vol < 0:
                problems += 1
                notes.append("%s: a part of %d faces faces inward (volume %.1f)" % (o.name, len(part), vol))
        bm.free()
    foreign = [m for m in mats if not (m.startswith("Corneria_") and m[9:] in cc.PALETTE)]
    if foreign:
        problems += 1
        notes.append("materials not in the palette: " + ", ".join(sorted(foreign)))
    print("  %-28s %6d tris  %6.1f x %5.1f x %5.1f m  base z %+.2f  centre (%+.1f, %+.1f)  %s" % (
        col.name, tris, hi.x - lo.x, hi.z - lo.z, hi.y - lo.y, lo.z, (lo.x + hi.x) / 2, (lo.y + hi.y) / 2,
        ", ".join(sorted(m[9:] for m in mats))))
    for n in notes:
        print("      ! " + n)
    return problems


# --- Previews ---------------------------------------------------------------------------
def preview(col, out, size=640):
    """Renders `col` front and back three-quarter (Workbench, flat palette
    colours, outlines, backface culling) to <out>/<name>_front/_back.png."""
    scene = bpy.data.scenes.new("Preview")
    inst = bpy.data.objects.new("Preview", None)
    inst.instance_type = "COLLECTION"
    inst.instance_collection = col
    scene.collection.objects.link(inst)
    lo = Vector((math.inf,) * 3)
    hi = Vector((-math.inf,) * 3)
    for o in col.all_objects:
        if o.type == "MESH":
            for c in o.bound_box:
                p = o.matrix_world @ Vector(c) - col.instance_offset
                lo = Vector(map(min, lo, p))
                hi = Vector(map(max, hi, p))
    centre = (lo + hi) / 2
    radius = (hi - lo).length / 2
    cam_data = bpy.data.cameras.new("PreviewCam")
    cam_data.lens = 50
    cam = bpy.data.objects.new("PreviewCam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    try:
        scene.render.engine = "BLENDER_WORKBENCH"
    except TypeError:
        pass
    shading = scene.display.shading
    shading.light = "STUDIO"
    shading.color_type = "MATERIAL"
    shading.show_backface_culling = True
    shading.show_object_outline = True
    shading.show_cavity = False
    scene.render.resolution_x = scene.render.resolution_y = size
    scene.render.film_transparent = False
    world = bpy.data.worlds.new("PreviewWorld")
    world.color = (0.55, 0.65, 0.8)
    scene.world = world
    distance = radius / math.tan(math.radians(18)) * 1.05
    for side, direction in (("front", Vector((0.75, -1.0, 0.45))), ("back", Vector((-0.75, 1.0, 0.45)))):
        d = direction.normalized()
        cam.location = centre + d * distance
        cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
        cam_data.clip_end = distance * 4
        scene.render.filepath = os.path.join(out, "%s_%s.png" % (col.name, side))
        bpy.ops.render.render(write_still=True, scene=scene.name)
    bpy.data.objects.remove(cam)
    bpy.data.cameras.remove(cam_data)
    bpy.data.objects.remove(inst)
    bpy.data.worlds.remove(world)
    bpy.data.scenes.remove(scene)
