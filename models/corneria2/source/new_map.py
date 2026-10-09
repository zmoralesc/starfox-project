"""Creates corneria.blend, the map's master copy, empty: a flat terrain grid
under the sea, a collection per prop group, and the markers. Does nothing to an
existing corneria.blend except add what's missing (collections, markers), so
it is safe to re-run.

    blender --background --python new_map.py

What's in the map (see corneria_common.py for the names):
    Terrain     one grid mesh, SIZE x SIZE at CELL spacing (POINTS x POINTS
                vertices), Blender coordinates. Sculpt it freely: the export
                samples it from above at every grid point. Its "Paint" colour
                layer (vertex paint) marks paved ground (red) and ground under
                high lakes (blue); black is coloured by the game's own rules.
    Props/<group>  kit pieces as collection instances (Add > Collection
                Instance, or Alt+D an existing one), plus one-off meshes
                (lakes, roads). Instances of other collections that aren't kit
                pieces work as prefabs: their contents are exported.
    Markers     empties the game places things at: Start (the player; facing
                Blender +Y, north, when unrotated), IntroStart and
                IntroCameraSpot (the intro), Waterfall (the falls' lip, water
                flowing along its -Y), GreatFox.
    Preview     things only for looking at (the sea plane); not exported.

Scene custom property "high_water_level": the surface height of the lakes
marked blue in Paint (one level for the whole map).
"""

import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import corneria_common as cc  # noqa: E402

# Where the markers start (game coordinates), if they don't exist yet.
MARKER_START = {
    "Start": (0.0, 150.0, 7200.0),
    "IntroStart": (0.0, 150.0, 7500.0),
    "IntroCameraSpot": (30.0, 154.0, 7200.0),
    "Waterfall": (4000.0, 200.0, -4000.0),
    "GreatFox": (1000.0, 900.0, 9500.0),
}
SEA_FLOOR = -20.0


def ground_material():
    """Terrain preview: grass, plus the Paint layer's colour where painted."""
    m = bpy.data.materials.get("Corneria_Ground") or bpy.data.materials.new("Corneria_Ground")
    m.use_nodes = True
    nodes, links = m.node_tree.nodes, m.node_tree.links
    bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Roughness"].default_value = 0.9
    attr = next((n for n in nodes if n.type == "VERTEX_COLOR"), None) or nodes.new("ShaderNodeVertexColor")
    attr.layer_name = cc.PAINT_ATTRIBUTE
    add = next((n for n in nodes if n.type == "MIX"), None) or nodes.new("ShaderNodeMix")
    add.data_type = "RGBA"
    add.blend_type = "ADD"
    add.inputs["Factor"].default_value = 1.0
    add.inputs["A"].default_value = (*[cc.srgb_to_linear(c) for c in (0.42, 0.66, 0.3)], 1.0)
    links.new(attr.outputs["Color"], add.inputs["B"])
    links.new(add.outputs["Result"], bsdf.inputs["Base Color"])
    return m


def build_terrain(col):
    n = cc.POINTS
    verts = [cc.G(-cc.HALF + i * cc.CELL, SEA_FLOOR, -cc.HALF + j * cc.CELL) for j in range(n) for i in range(n)]
    faces = [(j * n + i, j * n + i + 1, (j + 1) * n + i + 1, (j + 1) * n + i)
             for j in range(n - 1) for i in range(n - 1)]
    me = bpy.data.meshes.new("Terrain")
    me.from_pydata(verts, [], faces)
    me.validate()
    if me.polygons[0].normal.z < 0:   # the game-to-Blender flip reverses the winding
        me.flip_normals()
    paint = me.color_attributes.new(cc.PAINT_ATTRIBUTE, "BYTE_COLOR", "POINT")
    for c in paint.data:
        c.color = (0.0, 0.0, 0.0, 1.0)
    me.materials.append(ground_material())
    o = bpy.data.objects.new("Terrain", me)
    col.objects.link(o)
    return o


def main():
    if os.path.exists(cc.MAP_FILE):
        bpy.ops.wm.open_mainfile(filepath=cc.MAP_FILE)
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.name = "Corneria"
    scene.unit_settings.system = "METRIC"
    if "high_water_level" not in scene:
        scene["high_water_level"] = 0.0
    # Views reach across the map.
    for screen in bpy.data.screens:
        for area in screen.areas:
            for space in area.spaces:
                if space.type == "VIEW_3D":
                    space.clip_end = 40000.0

    terrain = cc.collection("Terrain")
    if "Terrain" not in bpy.data.objects:
        build_terrain(terrain)
    props = cc.collection("Props")
    for group in cc.GROUPS:
        cc.collection(group, props)
    markers = cc.collection("Markers")
    for name in cc.MARKERS:
        if name not in bpy.data.objects:
            o = bpy.data.objects.new(name, None)
            o.empty_display_type = "ARROWS"
            o.empty_display_size = 60.0
            o.location = cc.G(*MARKER_START[name])
            markers.objects.link(o)
    preview = cc.collection("Preview")
    if "Sea" not in bpy.data.objects:
        me = bpy.data.meshes.new("Sea")
        s = cc.SIZE
        me.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
        me.materials.append(cc.material("Water"))
        o = bpy.data.objects.new("Sea", me)
        preview.objects.link(o)
    bpy.ops.wm.save_as_mainfile(filepath=cc.MAP_FILE, relative_remap=True)
    print("map ready:", cc.MAP_FILE)


main()
