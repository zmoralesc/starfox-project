"""Adds placeholder ("greybox") kit pieces to kit.blend: plain boxes, cylinders
and cones at a piece's final name and size, so the map can be laid out before
the real models exist.

    blender --background --python greybox_kit.py

Creates kit.blend if it doesn't exist. A piece's collection is (re)built only
if it is missing or still a placeholder (custom property "greybox"): a real
model made under the same name is never touched. Replace a placeholder by
deleting its collection's objects, modelling the piece in it, and clearing the
"greybox" property; every map instance then shows the real model.

The real pieces are built by kit/kit_*.py (spec: ../ASSETS.md), as variants
(Kit_X_A, _B...) that settlement.Placer prefers over the placeholder Kit_X.

Kit rules (see ../ASSETS.md): one collection per piece, named
Kit_*, its origin (the collection's instance offset) on the ground at the
piece's centre, front facing Blender -Y (the game's +Z, south); materials from
the palette (corneria_common.PALETTE, named Corneria_*).
"""

import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import corneria_common as cc  # noqa: E402

# name: (shape, size in game metres (width x, height y, depth z), palette colour)
# shape "box", "cylinder" (width = diameter), "cone" (a tree: trunk + cone).
PIECES = {
    "Kit_Grey_Box": ("box", (10.0, 10.0, 10.0), "Greybox"),
    "Kit_Grey_Tower": ("cylinder", (30.0, 100.0, 30.0), "Tower"),
    "Kit_Grey_Tree": ("cone", (8.0, 15.0, 8.0), "Tree"),
    # Corneria City (gen_city.py scales them to fit their lots: the sizes are
    # what a piece is at scale 1, which the real models should keep).
    "Kit_City_House": ("box", (11.0, 7.0, 13.0), "Wall"),
    "Kit_City_Shop": ("box", (12.0, 13.0, 16.0), "Stone"),
    "Kit_City_Apartment": ("box", (24.0, 24.0, 24.0), "Concrete"),
    "Kit_City_Office": ("box", (30.0, 45.0, 30.0), "Tower"),
    "Kit_City_Tower": ("box", (36.0, 150.0, 36.0), "Glass"),
    "Kit_City_RoundTower": ("cylinder", (36.0, 130.0, 36.0), "Glass"),
    "Kit_City_Spire": ("cylinder", (44.0, 340.0, 44.0), "Tower"),
    "Kit_City_Warehouse": ("box", (50.0, 14.0, 30.0), "RoofDark"),
    "Kit_City_Tank": ("cylinder", (24.0, 16.0, 24.0), "Steel"),
    "Kit_City_Crane": ("box", (10.0, 50.0, 30.0), "TaxiYellow"),
    "Kit_City_Bridge": ("box", (24.0, 4.0, 100.0), "Concrete"),   # a deck: length along z
    "Kit_City_Pier": ("box", (8.0, 20.0, 8.0), "Concrete"),
    "Kit_Tree_Broadleaf": ("cone", (10.0, 14.0, 10.0), "TreeLight"),
    # The harbour town, villages and farms (gen_town.py).
    "Kit_Town_House": ("box", (10.0, 8.0, 12.0), "Wall"),
    "Kit_Town_Hall": ("box", (18.0, 16.0, 26.0), "Stone"),
    "Kit_Town_Shed": ("box", (30.0, 10.0, 20.0), "RoofDark"),
    "Kit_Town_Lighthouse": ("cylinder", (10.0, 36.0, 10.0), "Lighthouse"),
    "Kit_Town_Jetty": ("box", (6.0, 2.0, 60.0), "Trunk"),      # a deck: length along z
    "Kit_Town_Boat": ("box", (5.0, 3.0, 14.0), "AwningBlue"),
    "Kit_Town_Post": ("box", (0.8, 4.0, 0.8), "Trunk"),        # a pier's leg
    # The military base (gen_base.py).
    "Kit_Base_Hangar": ("box", (60.0, 22.0, 50.0), "MilitaryDark"),   # doors at the front (+z)
    "Kit_Base_ControlTower": ("box", (14.0, 40.0, 14.0), "Concrete"),
    "Kit_Base_HQ": ("box", (70.0, 24.0, 40.0), "Concrete"),
    "Kit_Base_Barracks": ("box", (40.0, 10.0, 14.0), "Military"),
    "Kit_Base_Shed": ("box", (30.0, 8.0, 20.0), "Military"),
    "Kit_Base_Radar": ("cylinder", (18.0, 22.0, 18.0), "Steel"),
    "Kit_Base_Bunker": ("box", (10.0, 4.0, 10.0), "MilitaryDark"),
    "Kit_Farm_Barn": ("box", (16.0, 10.0, 26.0), "Roof"),
    "Kit_Farm_Silo": ("cylinder", (7.0, 18.0, 7.0), "Steel"),
    # Landmarks (gen_landmarks.py) and the wilds (gen_wilds.py).
    "Kit_Landmark_Arch": ("arch", (170.0, 120.0, 26.0), "Stone"),    # the bay's arches; opening 119 x 86 m
    "Kit_Rock_Arch": ("arch", (110.0, 70.0, 22.0), "Rock"),          # a natural arch
    "Kit_Rock_Stack": ("frustum", (24.0, 60.0, 24.0), "Rock"),       # sea stacks
    "Kit_Rock_Boulder": ("frustum", (8.0, 5.0, 8.0), "Rock"),
    "Kit_Rock_Outcrop": ("frustum", (30.0, 18.0, 30.0), "Rock"),
    "Kit_Tree_Pine": ("cone", (7.0, 16.0, 7.0), "Tree"),
}
SPACING = 120.0   # placeholders stand in a row along Blender +X, this far apart


def outward(me):
    """Every face of a closed mesh pointing out (the game draws only fronts)."""
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    return me


def box(name, w, h, d, mat):
    me = bpy.data.meshes.new(name)
    x, y = w / 2, d / 2
    verts = [(sx * x, sy * y, z) for z in (0, h) for sy in (-1, 1) for sx in (-1, 1)]
    faces = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    me.from_pydata(verts, [], faces)
    me.materials.append(mat)
    me.validate()
    outward(me)
    return me


def cylinder(name, r0, r1, h, mat, segments=16, z0=0.0):
    """A cylinder (or a cone, with r1 0: one apex point) standing on z0."""
    me = bpy.data.meshes.new(name)
    n = segments
    ring = lambda z, r: [(r * math.cos(2 * math.pi * k / n), r * math.sin(2 * math.pi * k / n), z) for k in range(n)]
    verts = ring(z0, r0)
    faces = [tuple(range(n - 1, -1, -1))]
    if r1 > 0:
        verts += ring(z0 + h, r1)
        faces += [(k, (k + 1) % n, n + (k + 1) % n, n + k) for k in range(n)] + [tuple(range(n, 2 * n))]
    else:
        verts.append((0.0, 0.0, z0 + h))
        faces += [(k, (k + 1) % n, n) for k in range(n)]
    me.from_pydata(verts, [], faces)
    me.materials.append(mat)
    me.validate()
    outward(me)
    for p in me.polygons[1:n + 1]:   # the sides (the bottom cap is first)
        p.use_smooth = True
    return me


def add(col, name, me, at):
    o = bpy.data.objects.new(name, me)
    o.location = at
    col.objects.link(o)
    return o


def arch(name, w, h, d, mat, n=32):
    """An arch: w wide, h high, d deep (along Blender y), its opening 0.7 w
    wide and 0.72 h high with a round top. A slab bent round the opening:
    its outline and the opening's are sampled at the same n + 1 points along
    their lengths, and joined front, back, outside, inside and at the feet."""
    r = w * 0.35
    rise = h * 0.72 - r                       # the opening's straight sides
    inner_len = 2 * rise + math.pi * r
    outer_len = 2 * h + w

    def inner(t):
        s = t * inner_len
        if s < rise:
            return (-r, s)
        if s < rise + math.pi * r:
            a = math.pi - (s - rise) / r
            return (r * math.cos(a), rise + r * math.sin(a))
        return (r, inner_len - s)

    def outer(t):
        s = t * outer_len
        if s < h:
            return (-w / 2, s)
        if s < h + w:
            return (-w / 2 + (s - h), h)
        return (w / 2, outer_len - s)

    ts = [k / n for k in range(n + 1)]
    ring = [outer(t) for t in ts] + [inner(t) for t in ts]   # outer 0..n, inner n+1..2n+1
    verts = [(x, -d / 2, z) for x, z in ring] + [(x, d / 2, z) for x, z in ring]
    m = len(ring)
    faces = []
    for k in range(n):
        o0, o1, i0, i1 = k, k + 1, n + 1 + k, n + 2 + k
        faces.append((o0, o1, i1, i0))                       # front
        faces.append((m + o0, m + i0, m + i1, m + o1))       # back
        faces.append((o0, m + o0, m + o1, o1))               # outside
        faces.append((i0, i1, m + i1, m + i0))               # inside
    for o, i in ((0, n + 1), (n, 2 * n + 1)):                # the feet
        faces.append((o, i, m + i, m + o))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.materials.append(mat)
    me.validate()
    return outward(me)


def build_piece(col, shape, size, colour, at):
    w, h, d = size
    mat = cc.material(colour)
    if shape == "box":
        add(col, col.name, box(col.name, w, h, d, mat), at)
    elif shape == "cylinder":
        add(col, col.name, cylinder(col.name, w / 2, w / 2, h, mat), at)
    elif shape == "cone":
        trunk_h = h * 0.25
        add(col, col.name + "_Trunk", cylinder(col.name + "_Trunk", w * 0.08, w * 0.08, trunk_h,
                                               cc.material("Trunk"), 8), at)
        add(col, col.name + "_Crown", cylinder(col.name + "_Crown", w / 2, 0.0, h - trunk_h, mat, 12, trunk_h), at)
    elif shape == "frustum":
        # A rock: seven flat sides narrowing to 55 % at the top.
        me = cylinder(col.name, w / 2, w * 0.275, h, mat, 7)
        for p in me.polygons:
            p.use_smooth = False
        add(col, col.name, me, at)
    elif shape == "arch":
        add(col, col.name, arch(col.name, w, h, d, mat), at)
    else:
        raise ValueError(shape)


def main():
    if os.path.exists(cc.KIT_FILE):
        bpy.ops.wm.open_mainfile(filepath=cc.KIT_FILE)
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.name = "Kit"
    made = kept = 0
    for k, (name, (shape, size, colour)) in enumerate(PIECES.items()):
        col = bpy.data.collections.get(name)
        if col is not None and not col.get("greybox"):
            kept += 1
            continue
        if col is None:
            col = cc.collection(name)
        else:
            cc.clear_collection(col)
        col["greybox"] = True
        at = Vector((k * SPACING, 0.0, 0.0))
        col.instance_offset = at
        build_piece(col, shape, size, colour, at)
        made += 1
    bpy.ops.wm.save_as_mainfile(filepath=cc.KIT_FILE)
    print("greybox kit: %d placeholders built, %d real pieces kept" % (made, kept))


main()
