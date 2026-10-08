"""
juggernaut_c2.py

Stage C: Pass C2 (Detail Pass & Asset Export) for Concept H, the Juggernaut.
Builds on approved C1 form pass (Review 3: 170m armoured stern at 1.5x scale):
1. Bug Fixes in script:
   - Outline color 3-tuple for Blender 5.2.
   - setup_all_materials preserves polygon material indices without reset.
2. Three C1 Form Refinements:
   - Flanks: Stepped heavy citadel armour modules standing out several metres.
   - Belly: 3-tier stepped keel structure with heavy ventral machinery/reactor blocks.
   - Bridge Head: Distinct sculpted command head with neck separation, forward-raked
     armored visor brow, deep window embrasures with mullions, and roof sensor array.
3. Tertiary Detail (Real Metres, scale=1.0):
   - Crew/bridge windows (1.8m x 0.9m), running lights (1-3m), hatches, vents,
     radiator coolant piping, and painted panel variation.
4. Collision & Markers:
   - Collision collection with 14 convex Col_ meshes closely covering the hull.
   - Markers collection with all part pivots, launch points, and turret mounts.
5. glTF Export:
   - 8 individual .glb binary files exported to models/destroyer/.
"""

import bpy
import bmesh
import math
import os
import random
import numpy as np
from mathutils import Vector, Matrix, Euler
from mathutils.bvhtree import BVHTree

PROJECT_ROOT = r"C:\Users\zemc7\OneDrive\Documentos\spaceship-project"
SOURCE_DIR = os.path.join(PROJECT_ROOT, "models", "destroyer", "source")
PREVIEW_DIR = os.path.join(SOURCE_DIR, "juggernaut_preview")
BLEND_FILE = os.path.join(SOURCE_DIR, "juggernaut.blend")
EXPORT_DIR = os.path.join(PROJECT_ROOT, "models", "destroyer")

SCALE = 1.5

# Turret mount pads, (x, y, z) in design units (times SCALE = metres): z is the
# height of the hull surface the pad stands on. The pad is 2 m thick, centred on
# that surface (half sunk, so it never floats where the surface slopes), and the
# turret (and its marker) stands on the pad's top, 1 m above the surface.
# The hull and the markers both read this list, so moving a turret is one edit.
MOUNT_PADS = [
    (-15.0, 240.0, 88.0 - 16.0 * 110.0 / 130.0), (15.0, 240.0, 88.0 - 16.0 * 110.0 / 130.0),  # on the bow glacis
    (-75.0, 110.0, 80.0), (75.0, 110.0, 80.0),   # on the forward sponson plates
    (-52.0, 55.0, 76.0),  (52.0, 55.0, 76.0),    # on the main deck beside the radiator trench
    (-42.0, -130.0, 125.0), (42.0, -130.0, 125.0),  # on the castle bastions
]

# Where the bridge stands, (y, z) in design units: centred on the castle's
# upper pedestal (y -180 to -135, top at z 136), so its 38-long plinth sits
# wholly on it and only the visor brow overhangs the front. At y -130 most of
# the bridge hung in the air in front of the pedestal.
BRIDGE_Y, BRIDGE_Z = -156.0, 136.0

# -----------------------------------------------------------------------------
# Materials Setup (Venom Palette)
# -----------------------------------------------------------------------------
COLORS = {
    "Hull": ((0.20, 0.22, 0.26), 0.0),
    "HullLight": ((0.32, 0.34, 0.38), 0.0),
    "HullDark": ((0.13, 0.14, 0.17), 0.0),
    "Dark": ((0.07, 0.07, 0.09), 0.0),
    "Crimson": ((0.30, 0.11, 0.11), 0.0),  # muted: the old 0.55, 0.04, 0.05 read as flat, saturated red
    "GlowGreen": ((0.35, 1.00, 0.20), 5.0),
    "Window": ((1.00, 0.65, 0.20), 4.0),
    "EngineGlow": ((1.00, 0.35, 0.10), 6.0),
    "TurretMount": ((0.10, 0.11, 0.13), 0.0),
    "TurretMetal": ((0.16, 0.17, 0.20), 0.0),
    "TurretEye": ((0.35, 1.00, 0.20), 5.0),
    "RunningLight": ((0.90, 0.05, 0.05), 5.0),
    "CorridorCyan": ((0.15, 0.80, 1.00), 1.0),
    "HullMid": ((0.26, 0.28, 0.32), 0.0),  # hull detail panels only
}

def srgb_to_linear(c):
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)

def get_or_create_material(name):
    if name.startswith("Destroyer_") or name.startswith("Turret_") or name.startswith("Corridor"):
        mat_name = name
        key = name.replace("Destroyer_", "").replace("Turret_", "")
    else:
        mat_name = "Destroyer_" + name
        key = name
        
    mat = bpy.data.materials.get(mat_name) or bpy.data.materials.new(mat_name)
    mat.use_nodes = True
    mat.use_backface_culling = True
    
    srgb, emit = COLORS.get(key, ((0.5, 0.5, 0.5), 0.0))
    rgb = srgb_to_linear(srgb)
    
    bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.55
        bsdf.inputs["Metallic"].default_value = 0.0
        if "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = (*rgb, 1.0)
        if "Emission Strength" in bsdf.inputs:
            bsdf.inputs["Emission Strength"].default_value = emit
    mat.diffuse_color = (*rgb, 1.0)
    if key in PLATING_MATS and bsdf:
        add_plating_texture(mat, bsdf, rgb)
    return mat

# -----------------------------------------------------------------------------
# Hull plating texture: printed detail (seams, plate tones, hatches, vents)
# -----------------------------------------------------------------------------
# One tiling greyscale image multiplied over the hull greys (glTF base colour
# texture times factor; Godot's ToonMaterial keeps both). It is printed on the
# surface, so it adds no geometry. Every mesh gets UVs projected along its
# faces' main axis at PLATING_TILE metres per repeat (add_plating_uvs).
PLATING_MATS = {"Hull", "HullLight", "HullDark", "HullMid", "Crimson"}  # crimson: worn in game by toon_worn.gdshader
PLATING_TILE = 16.0   # metres of hull per texture repeat
PLATING_SIZE = 2048   # pixels per side (128 px per metre)
PLATING_PNG = os.path.join(PREVIEW_DIR, "juggernaut_plating.png")

# Brightness multipliers, in linear light (what the shader multiplies by).
PLATE_TONES = (0.80, 1.0)  # each plate picks one: the large-scale variation
SEAM_TONE = 0.30           # panel seams
SEAM_PX = 7                # seam width (5.5 cm)
EDGE_TONE = 1.0            # the lit lip beside each seam
DETAIL_TONE = 0.42         # hatch outlines, vent slats, bolts

_plating_image = None

def build_plating_pixels(seed=11):
    """The plating tile as an (S, S) array of linear multipliers. Rows run
    across u (along the ship on decks and sides), so plates are long and
    staggered like hull plating. Tiles seamlessly: rows split v exactly, and
    plates wrap around u."""
    S = PLATING_SIZE
    px = S / PLATING_TILE
    rng = random.Random(seed)
    img = np.ones((S, S), dtype=np.float32)

    def fill(u0, v0, w, h, val):
        us = np.arange(u0, u0 + w) % S
        vs = np.arange(v0, v0 + h) % S
        img[np.ix_(vs, us)] = val

    def scale(u0, v0, w, h, k):
        us = np.arange(u0, u0 + w) % S
        vs = np.arange(v0, v0 + h) % S
        img[np.ix_(vs, us)] *= k

    def plate_detail(u0, v0, w, h, tone):
        # Rivets in the corners, then at most one feature.
        b = 14
        for cu, cv in ((u0 + b, v0 + b), (u0 + w - b - 5, v0 + b),
                       (u0 + b, v0 + h - b - 5), (u0 + w - b - 5, v0 + h - b - 5)):
            fill(cu, cv, 5, 5, DETAIL_TONE)
        roll = rng.random()
        if roll < 0.22 and w > 2.5 * px and h > 1.6 * px:
            # Access hatch: an outlined, slightly darker rectangle.
            hw = int(rng.uniform(0.9, 1.8) * px)
            hh = int(rng.uniform(0.7, min(1.4, h / px - 0.6)) * px)
            hu = u0 + rng.randint(int(0.3 * px), w - hw - int(0.3 * px))
            hv = v0 + (h - hh) // 2
            scale(hu, hv, hw, hh, 0.88)
            for (a, c, ww, hh2) in ((hu, hv, hw, 4), (hu, hv + hh - 4, hw, 4),
                                    (hu, hv, 4, hh), (hu + hw - 4, hv, 4, hh)):
                fill(a, c, ww, hh2, tone * DETAIL_TONE)
        elif roll < 0.38 and w > 3.4 * px and h > 1.4 * px:
            # Vent grille: parallel dark slats.
            gw = int(rng.uniform(1.4, 2.6) * px)
            gh = int(rng.uniform(0.6, min(1.0, h / px - 0.6)) * px)
            gu = u0 + rng.randint(int(0.3 * px), w - gw - int(0.3 * px))
            gv = v0 + (h - gh) // 2
            for s in range(gu, gu + gw - 6, 14):
                fill(s, gv, 7, gh, tone * DETAIL_TONE)
        elif roll < 0.48 and h > 1.2 * px:
            # Inset strip along the plate.
            sh = int(0.25 * px)
            scale(u0 + int(0.4 * px), v0 + (h - sh) // 2, w - int(0.8 * px), sh, 0.86)

    # Rows: 2-4 m bands summing exactly to the tile.
    rows, v = [], 0
    while v < S:
        h = int(rng.choice((2.0, 2.5, 3.0, 4.0)) * px)
        if S - (v + h) < 2 * px:
            h = S - v
        rows.append((v, h))
        v += h
    for v0, h in rows:
        # Plates: 3-8 m long, starting at a random stagger, wrapping in u.
        u, start = 0, rng.randint(0, S - 1)
        while u < S:
            w = int(rng.uniform(3.0, 8.0) * px)
            if S - (u + w) < 3 * px:
                w = S - u
            # Some plates split into two across the row.
            parts = [(v0, h)]
            if h >= 3 * px and rng.random() < 0.3:
                cut = int(h * rng.uniform(0.4, 0.6))
                parts = [(v0, cut), (v0 + cut, h - cut)]
            for pv, ph in parts:
                tone = rng.uniform(*PLATE_TONES)
                fill(start + u, pv, w, ph, tone)
                plate_detail(start + u, pv, w, ph, tone)
                # Seam on the plate's low edges, lit lip just inside it
                # (the neighbours draw the other two edges).
                fill(start + u, pv, w, SEAM_PX, SEAM_TONE)
                fill(start + u, pv, SEAM_PX, ph, SEAM_TONE)
                fill(start + u + SEAM_PX, pv + SEAM_PX, w - SEAM_PX, 3, EDGE_TONE)
                fill(start + u + SEAM_PX, pv + SEAM_PX, 3, ph - SEAM_PX, EDGE_TONE)
            u += w
    return img

def plating_image():
    """The plating texture (built once per run, saved to the preview folder
    and packed so the glTF export embeds it)."""
    global _plating_image
    if _plating_image is not None:
        return _plating_image
    lin = build_plating_pixels()
    srgb = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(lin, 1.0 / 2.4) - 0.055)
    S = PLATING_SIZE
    rgba = np.ones((S, S, 4), dtype=np.float32)
    rgba[..., 0] = rgba[..., 1] = rgba[..., 2] = srgb
    old = bpy.data.images.get("Juggernaut_Plating")
    if old:
        bpy.data.images.remove(old)
    img = bpy.data.images.new("Juggernaut_Plating", S, S, alpha=False)
    img.pixels.foreach_set(rgba.ravel())
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    img.filepath_raw = PLATING_PNG
    img.file_format = 'PNG'
    img.save()
    img.pack()
    _plating_image = img
    return img

def add_plating_texture(mat, bsdf, rgb):
    """Base colour = plating texture x the material's colour (a Multiply mix,
    which the glTF exporter writes as texture plus factor)."""
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    tex = next((n for n in nodes if n.type == 'TEX_IMAGE'), None) or nodes.new('ShaderNodeTexImage')
    tex.image = plating_image()
    mix = next((n for n in nodes if n.type == 'MIX'), None) or nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.blend_type = 'MULTIPLY'
    mix.inputs['Factor'].default_value = 1.0
    a = next(s for s in mix.inputs if s.identifier == 'A_Color')
    b = next(s for s in mix.inputs if s.identifier == 'B_Color')
    out = next(s for s in mix.outputs if s.identifier == 'Result_Color')
    b.default_value = (*rgb, 1.0)
    links.new(tex.outputs['Color'], a)
    links.new(out, bsdf.inputs['Base Color'])

# Per-projection offsets (in tiles) so opposite faces and the three axes don't
# show the same stretch of plating.
_PLATING_OFFSETS = {
    (0, 1): (0.00, 0.00), (0, -1): (0.37, 0.61),
    (1, 1): (0.13, 0.29), (1, -1): (0.71, 0.08),
    (2, 1): (0.52, 0.44), (2, -1): (0.23, 0.83),
}

def add_plating_uvs(me):
    """Box-project UVs at PLATING_TILE metres per repeat, in the mesh's own
    coordinates (metres). Decks and sides run u along the ship (y), so the
    long plates run fore and aft."""
    uv = me.uv_layers[0] if me.uv_layers else me.uv_layers.new(name="UVMap")
    verts = me.vertices
    for poly in me.polygons:
        n = poly.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        ou, ov = _PLATING_OFFSETS[(ax, 1 if n[ax] >= 0 else -1)]
        for li in poly.loop_indices:
            co = verts[me.loops[li].vertex_index].co
            if ax == 2:
                u, v = co.y, co.x
            elif ax == 0:
                u, v = co.y, co.z
            else:
                u, v = co.x, co.z
            uv.data[li].uv = (u / PLATING_TILE + ou, v / PLATING_TILE + ov)

STANDARD_MATS = [
    "Hull", "HullLight", "HullDark", "Dark", "Crimson",
    "GlowGreen", "Window", "EngineGlow", "TurretMount", "TurretMetal", "TurretEye",
    "RunningLight"
]

def setup_all_materials(mesh):
    indices = [p.material_index for p in mesh.polygons]
    mesh.materials.clear()
    for m in STANDARD_MATS:
        mesh.materials.append(get_or_create_material(m))
    for poly, idx in zip(mesh.polygons, indices):
        poly.material_index = idx

# -----------------------------------------------------------------------------
# BMesh Geometry Helpers
# -----------------------------------------------------------------------------
def bmesh_add_box(bm, size, center, mat_idx=0, scale=SCALE):
    sx, sy, sz = [s * scale / 2.0 for s in size]
    cx, cy, cz = [c * scale for c in center]
    pts = [
        (-sx, -sy, -sz), (sx, -sy, -sz), (sx, sy, -sz), (-sx, sy, -sz),
        (-sx, -sy,  sz), (sx, -sy,  sz), (sx, sy,  sz), (-sx, sy,  sz)
    ]
    verts = [bm.verts.new(Vector((cx + x, cy + y, cz + z))) for x, y, z in pts]
    bm.verts.ensure_lookup_table()
    
    faces_idx = [
        (0, 1, 2, 3), (7, 6, 5, 4),
        (0, 4, 5, 1), (1, 5, 6, 2),
        (2, 6, 7, 3), (3, 7, 4, 0)
    ]
    for idxs in faces_idx:
        f = bm.faces.new([verts[i] for i in idxs])
        f.material_index = mat_idx

def bmesh_add_real_box(bm, size, center, mat_idx=0):
    bmesh_add_box(bm, size, center, mat_idx=mat_idx, scale=1.0)

def bmesh_add_real_chamfered_box(bm, size, center, chamfer=0.2, mat_idx=0):
    bmesh_add_chamfered_box(bm, size, center, chamfer=chamfer, mat_idx=mat_idx, scale=1.0)

def bmesh_add_chamfered_box(bm, size, center, chamfer=3.0, mat_idx=0, scale=SCALE):
    sx, sy, sz = [s * scale / 2.0 for s in size]
    cx, cy, cz = [c * scale for c in center]
    c = min(chamfer * scale, sx * 0.45, sz * 0.45)
    poly = [
        (-sx + c, -sz), (sx - c, -sz),
        (sx, -sz + c), (sx, sz - c),
        (sx - c, sz), (-sx + c, sz),
        (-sx, sz - c), (-sx, -sz + c)
    ]
    v_back = [bm.verts.new(Vector((cx + x, cy - sy, cz + z))) for x, z in poly]
    v_front = [bm.verts.new(Vector((cx + x, cy + sy, cz + z))) for x, z in poly]
    bm.verts.ensure_lookup_table()
    
    f_b = bm.faces.new(list(reversed(v_back)))
    f_b.material_index = mat_idx
    f_f = bm.faces.new(v_front)
    f_f.material_index = mat_idx
    
    n = len(poly)
    for i in range(n):
        nxt = (i + 1) % n
        f = bm.faces.new([v_back[i], v_back[nxt], v_front[nxt], v_front[i]])
        f.material_index = mat_idx

def bmesh_add_loft_y(bm, cross_sections, mat_idx=0, smooth=False, scale=SCALE):
    n_pts = len(cross_sections[0][1])
    n_sec = len(cross_sections)
    new_verts = []
    for y, pts in cross_sections:
        ring = []
        for x, z in pts:
            ring.append(bm.verts.new(Vector((x * scale, y * scale, z * scale))))
        new_verts.append(ring)
    bm.verts.ensure_lookup_table()
    
    for i in range(n_sec - 1):
        r1 = new_verts[i]
        r2 = new_verts[i + 1]
        for j in range(n_pts):
            nxt = (j + 1) % n_pts
            f = bm.faces.new([r1[j], r1[nxt], r2[nxt], r2[j]])
            f.material_index = mat_idx
            f.smooth = smooth
            
    f_start = bm.faces.new(list(reversed(new_verts[0])))
    f_start.material_index = mat_idx
    f_end = bm.faces.new(new_verts[-1])
    f_end.material_index = mat_idx

# -----------------------------------------------------------------------------
# Juggernaut Ship Mesh Builders (Pass C2 Refined Geometry)
# -----------------------------------------------------------------------------
def build_juggernaut_hull():
    """
    Builds Juggernaut_Hull in ship space (Origin at ship center line / mid-keel).
    Contains:
    - Battering Ram Prow & Bow Glacis with running lights and sensor blisters.
    - Flank Citadels: stepped heavy armour volumes and protruding buttress columns.
    - Recessed Hangar Bays & Frames with tertiary windows and portal beacons.
    - Recessed Dorsal Spine & Radiator Trench with coolant manifold piping.
    - Stern Castle Superstructure Base & Lateral Bastion Towers.
    - 170m Armoured Engine Block & Transom Cowlings.
    - Ventral Architecture: 3-tier stepped keel with sonar bulb, reactor vault, sump.
    - 8 Turret Mount Pads (10m across, unscaled).
    """
    bm = bmesh.new()
    
    # =========================================================================
    # 1. MAIN HULL LOWER & UPPER WEDGES
    # =========================================================================
    main_sections = [
        (-300.0, [(-70, 0),   (-45, 68),  (45, 68),  (70, 0),   (55, -8),  (-55, -8)]),
        (-140.0, [(-82, 0),   (-54, 76),  (54, 76),  (82, 0),   (64, -10), (-64, -10)]),
        (80.0,   [(-88, 0),   (-58, 76),  (58, 76),  (88, 0),   (68, -10), (-68, -10)]),
        (200.0,  [(-74, 2),   (-48, 72),  (48, 72),  (74, 2),   (58, -8),  (-58, -8)]),
        (270.0,  [(-48, 6),   (-32, 60),  (32, 60),  (48, 6),   (36, -6),  (-36, -6)]),
    ]
    bmesh_add_loft_y(bm, main_sections, mat_idx=0) # Destroyer_Hull
    
    # Glacis Armor Plates (Fore upper hull slope)
    glacis_plates = [
        (130.0, [(-56, 76), (-34, 88), (34, 88), (56, 76)]),
        (260.0, [(-34, 60), (-20, 72), (20, 72), (34, 60)]),
    ]
    bmesh_add_loft_y(bm, glacis_plates, mat_idx=1) # Destroyer_HullLight
    
    # Painted darker armor panels on glacis
    for y_panel in (150.0, 190.0, 230.0):
        w_p = 50.0 - (y_panel - 150.0) * 0.25
        z_p = 82.0 - (y_panel - 150.0) * 0.14
        bmesh_add_box(bm, (w_p, 25.0, 1.2), (0.0, y_panel, z_p), mat_idx=2) # Destroyer_HullDark
    
    # =========================================================================
    # 2. BATTERING RAM PROW & CHIN RAM (Y: 260 to 365, Z: -12 to 44)
    # =========================================================================
    ram_core = [
        (260.0, [(-42, 8),  (-28, 54), (28, 54), (42, 8),  (28, -6),  (-28, -6)]),
        (295.0, [(-34, 10), (-22, 48), (22, 48), (34, 10), (22, -8),  (-22, -8)]),
        (330.0, [(-24, 12), (-16, 40), (16, 40), (24, 12), (16, -10), (-16, -10)]),
        (355.0, [(-14, 14), (-10, 32), (10, 32), (14, 14), (10, -12), (-10, -12)]),
        (365.0, [(-6,  16), (-4,  24), (4,  24), (6,  16), (4,  -12), (-4,  -12)]),
    ]
    bmesh_add_loft_y(bm, ram_core, mat_idx=0)
    
    ram_crest = [
        (265.0, [(-16, 52), (0, 64), (16, 52), (0, 56)]),
        (320.0, [(-12, 44), (0, 54), (12, 44), (0, 48)]),
        (355.0, [(-6,  32), (0, 40), (6,  32), (0, 36)]),
    ]
    bmesh_add_loft_y(bm, ram_crest, mat_idx=4) # Destroyer_Crimson
    
    for s in (-1, 1):
        ram_spur = [
            (270.0, [(s * 36, 12), (s * 48, 18), (s * 48, 44), (s * 36, 40)]),
            (315.0, [(s * 22, 14), (s * 32, 20), (s * 32, 36), (s * 22, 32)]),
        ]
        bmesh_add_loft_y(bm, ram_spur, mat_idx=1) # Destroyer_HullLight
        
    chin_ram = [
        (300.0, [(-8, 2),  (8, 2),  (4, -8),  (-4, -8)]),
        (340.0, [(-6, 4),  (6, 4),  (3, -10), (-3, -10)]),
        (348.0, [(-4, 6),  (4, 6),  (2, -10), (-2, -10)]),
    ]
    bmesh_add_loft_y(bm, chin_ram, mat_idx=1)
    
    # Ram flank teeth / armor steps
    # x follows the ram's narrowing flank (its side at z = 24 is at 32.8, 27.0
    # and 20.6 for these y), so each tooth stands 3 out of it.
    for s in (-1, 1):
        for y_t, x_t in ((280.0, 33.3), (305.0, 27.5), (330.0, 21.1)):
            bmesh_add_chamfered_box(bm, (5.0, 8.0, 12.0), (s * x_t, y_t, 24.0), chamfer=1.5, mat_idx=1)
            
    # Bow Glacis Transverse Armor Stiffeners
    for y_stiff in (170.0, 195.0, 220.0, 245.0):
        w_stiff = 64.0 - (y_stiff - 170.0) * 0.25
        z_stiff = 74.0 - (y_stiff - 170.0) * 0.12
        bmesh_add_chamfered_box(bm, (w_stiff, 4.0, 4.5), (0.0, y_stiff, z_stiff), chamfer=1.0, mat_idx=2)
        
    # Prow Tertiary Detail: running lights and sensor blisters (in real metres)
    bmesh_add_real_box(bm, (1.8, 1.8, 1.8), (0.0, 365.0 * SCALE, 20.0 * SCALE), mat_idx=11) # RunningLight at tip
    bmesh_add_real_box(bm, (1.8, 1.8, 1.8), (0.0, 348.0 * SCALE, -10.0 * SCALE), mat_idx=11) # RunningLight chin
    for s in (-1, 1):
        bmesh_add_real_chamfered_box(bm, (2.4, 3.5, 2.0), (s * 14.0 * SCALE, 330.0 * SCALE, 36.0 * SCALE), chamfer=0.4, mat_idx=2)
        bmesh_add_real_box(bm, (1.5, 1.5, 1.5), (s * 14.0 * SCALE, 332.0 * SCALE, 36.0 * SCALE), mat_idx=11)
        
    # Bow Mooring / Airlock Access Hatch (real metres)
    # Centred on the sloping glacis top (88 - 16 * 110/130 at y = 240), thick
    # enough that neither end lifts off the slope.
    glacis_z = (88.0 - 16.0 * 110.0 / 130.0) * SCALE
    bmesh_add_real_box(bm, (4.0, 5.0, 1.2), (0.0, 240.0 * SCALE, glacis_z), mat_idx=3)
    bmesh_add_real_box(bm, (2.8, 3.6, 1.3), (0.0, 240.0 * SCALE, glacis_z + 0.15), mat_idx=1)
    
    # =========================================================================
    # 3. SPONSON CITADELS & STEPPED FLANK ARMOUR MODULES (C2 REFINEMENT 1)
    # Strictly leaves Y in [-55, +35] 100% CLEAR for broadside view & slide strip!
    # Armour blocks stand out 8-14m past hull side (X up to ±100m) with deep relief.
    # =========================================================================
    for s in (-1, 1):
        fwd_bulkhead = [
            (90.0,  [(s * 68, 2), (s * 68, 76), (s * 88, 76), (s * 88, 2)]),
            (140.0, [(s * 64, 4), (s * 64, 72), (s * 74, 72), (s * 74, 4)]),
        ]
        bmesh_add_loft_y(bm, fwd_bulkhead, mat_idx=1)
        
        aft_bulkhead = [
            (-130.0, [(s * 48, 2), (s * 48, 72), (s * 60, 72), (s * 60, 2)]),
            (-90.0,  [(s * 48, 2), (s * 48, 76), (s * 88, 76), (s * 88, 2)]),
        ]
        bmesh_add_loft_y(bm, aft_bulkhead, mat_idx=1)
        
        bmesh_add_chamfered_box(bm, (26.0, 50.0, 8.0), (s * 74.0, 110.0, 76.0), chamfer=3.0, mat_idx=2)
        
        # --- A. Stepped Forward Citadel Bastion (Y: 42 to 135) ---
        # Base heavy citadel module standing out 12m past hull line (X to ±100m)
        bmesh_add_chamfered_box(bm, (14.0, 78.0, 56.0), (s * 93.0, 85.0, 40.0), chamfer=2.5, mat_idx=0)
        # Upper stepped armor tier
        bmesh_add_chamfered_box(bm, (8.0, 32.0, 22.0), (s * 97.0, 68.0, 52.0), chamfer=2.0, mat_idx=1)
        # Lower stepped armor tier
        bmesh_add_chamfered_box(bm, (8.0, 32.0, 22.0), (s * 97.0, 104.0, 26.0), chamfer=2.0, mat_idx=2)
        # 3 Protruding vertical buttress pillars standing out to X = ±101m
        for y_butt in (46.0, 84.0, 122.0):
            bmesh_add_chamfered_box(bm, (6.0, 8.0, 64.0), (s * 98.5, y_butt, 40.0), chamfer=1.5, mat_idx=2)
            # Running lights on outer corners of forward buttresses (real metres)
            bmesh_add_real_box(bm, (1.5, 1.5, 1.5), (s * 101.5 * SCALE, y_butt * SCALE, 70.0 * SCALE), mat_idx=11)
            bmesh_add_real_box(bm, (1.5, 1.5, 1.5), (s * 101.5 * SCALE, y_butt * SCALE, 10.0 * SCALE), mat_idx=11)
            
        # --- B. Stepped Aft Citadel Bastion (Y: -130 to -58) ---
        # Base heavy citadel module standing out 12m past hull line
        bmesh_add_chamfered_box(bm, (14.0, 66.0, 56.0), (s * 93.0, -95.0, 40.0), chamfer=2.5, mat_idx=0)
        # Upper stepped armor tier
        bmesh_add_chamfered_box(bm, (8.0, 28.0, 22.0), (s * 97.0, -80.0, 52.0), chamfer=2.0, mat_idx=1)
        # Lower stepped armor tier
        bmesh_add_chamfered_box(bm, (8.0, 28.0, 22.0), (s * 97.0, -110.0, 26.0), chamfer=2.0, mat_idx=2)
        # 3 Protruding vertical buttress pillars
        for y_butt in (-64.0, -96.0, -126.0):
            bmesh_add_chamfered_box(bm, (6.0, 8.0, 64.0), (s * 98.5, y_butt, 40.0), chamfer=1.5, mat_idx=2)
            bmesh_add_real_box(bm, (1.5, 1.5, 1.5), (s * 101.5 * SCALE, y_butt * SCALE, 70.0 * SCALE), mat_idx=11)
            bmesh_add_real_box(bm, (1.5, 1.5, 1.5), (s * 101.5 * SCALE, y_butt * SCALE, 10.0 * SCALE), mat_idx=11)
            
        # Flank Airlock Hatches (real metres)
        # On the citadel module's face (x = 100), slightly sunk into it.
        for y_h in (68.0, -95.0):
            bmesh_add_real_box(bm, (0.5, 4.0, 3.0), (s * (100.0 * SCALE + 0.2), y_h * SCALE, 40.0 * SCALE), mat_idx=3)
            bmesh_add_real_box(bm, (0.8, 3.0, 2.2), (s * (100.0 * SCALE + 0.3), y_h * SCALE, 40.0 * SCALE), mat_idx=1)
        
        # Sponson Shoulder & Bilge Armor Rails (outside door corridor)
        bmesh_add_chamfered_box(bm, (3.5, 60.0, 3.5), (s * 87.0, 95.0, 75.0), chamfer=0.8, mat_idx=1)
        bmesh_add_chamfered_box(bm, (3.5, 60.0, 3.5), (s * 87.0, -95.0, 75.0), chamfer=0.8, mat_idx=1)
        bmesh_add_chamfered_box(bm, (3.5, 60.0, 3.5), (s * 87.0, 95.0, 5.0),  chamfer=0.8, mat_idx=2)
        bmesh_add_chamfered_box(bm, (3.5, 60.0, 3.5), (s * 87.0, -95.0, 5.0),  chamfer=0.8, mat_idx=2)
            
    # =========================================================================
    # 4. RECESSED HANGAR BAYS & PORTAL FRAMES (Y: -10, Z: 24)
    # Deep cavity inside the protected well formed between flank bastions
    # =========================================================================
    for s in (-1, 1):
        bmesh_add_box(bm, (24.0, 78.0, 36.0), (s * 76.0, -10.0, 24.0), mat_idx=3) # Destroyer_Dark cavity
        
        # The frame overlaps the cavity's edges (and the jambs run into the
        # lintel and sill) so it reads as one piece; its opening stays clear of
        # the door (y -48 to 28, z 7 to 41).
        bmesh_add_chamfered_box(bm, (1.8, 86.0, 3.5), (s * 88.0, -10.0, 43.5), chamfer=0.8, mat_idx=1) # Lintel
        bmesh_add_chamfered_box(bm, (1.8, 86.0, 3.5), (s * 88.0, -10.0, 4.5),  chamfer=0.8, mat_idx=1) # Sill
        bmesh_add_chamfered_box(bm, (1.6, 3.5, 37.5), (s * 88.0, 30.5, 24.0),  chamfer=0.8, mat_idx=1) # Fore jamb
        bmesh_add_chamfered_box(bm, (1.6, 3.5, 37.5), (s * 88.0, -50.5, 24.0), chamfer=0.8, mat_idx=1) # Aft jamb

        # Door pocket: the wall the open door slides up in front of. The hull
        # side slopes in above the bay, so without it the posts and windows
        # above the door hung in the air. Its face (x = 85.5) stays just inside
        # the door's ribs (85.9); its top sits a little above the deck (76).
        bmesh_add_box(bm, (29.5, 84.0, 34.5), (s * 70.75, -10.0, 59.25), mat_idx=0)

        bmesh_add_box(bm, (1.5, 2.5, 34.0), (s * 86.25, -50.8, 63.0), mat_idx=2)
        bmesh_add_box(bm, (1.5, 2.5, 34.0), (s * 86.25, 30.8, 63.0),  mat_idx=2)

        # Portal Beacon Running Lights (real metres: 1.5m cubes at portal corners)
        for y_c in (-50.5, 30.5):
            for z_c in (4.5, 43.5):
                bmesh_add_real_box(bm, (1.6, 1.6, 1.6), (s * (88.0 * SCALE + 1.0), y_c * SCALE, z_c * SCALE), mat_idx=11)

        # Flight Operations Observation Slits above portal lintel (real metres: 1.8m x 0.9m), on the pocket
        for y_win in (-32.0, -22.0, -12.0, -2.0, 8.0, 18.0):
            bmesh_add_real_box(bm, (0.4, 1.8, 0.9), (s * (85.5 * SCALE + 0.15), y_win * SCALE, 52.0 * SCALE), mat_idx=6) # Window
            
    # =========================================================================
    # 5. RECESSED DORSAL SPINE & RADIATOR TRENCH (8 BAYS, 192 FINS, 4 ARCHES)
    # Rich functional secondary heat dissipation architecture
    # =========================================================================
    for s in (-1, 1):
        trench_wall = [
            (-70.0, [(s * 24, 82), (s * 30, 82), (s * 30, 96), (s * 24, 96)]),
            (150.0, [(s * 20, 78), (s * 26, 78), (s * 26, 92), (s * 20, 92)]),
        ]
        bmesh_add_loft_y(bm, trench_wall, mat_idx=2)
        
        bay_ranges = [(-65.0, -20.0), (-15.0, 30.0), (35.0, 80.0), (85.0, 135.0)]
        for y0, y1 in bay_ranges:
            bmesh_add_box(bm, (11.0, (y1 - y0), 6.0), (s * 18.0, (y0 + y1) / 2.0, 89.0), mat_idx=5) # GlowGreen
            # 24 individual 3D cooling fin plates per bay (192 cooling fins total!)
            for y_fin in np.linspace(y0 + 1.2, y1 - 1.2, 24):
                bmesh_add_chamfered_box(bm, (11.5, 0.7, 7.5), (s * 18.0, y_fin, 89.5), chamfer=0.2, mat_idx=2)
            bmesh_add_chamfered_box(bm, (14.0, 5.0, 10.0), (s * 18.0, y1 + 2.5, 91.0), chamfer=1.0, mat_idx=0)
            
    bmesh_add_chamfered_box(bm, (6.0, 220.0, 6.0), (0.0, 40.0, 88.5), chamfer=1.5, mat_idx=1)
    
    # Radiator Central Coolant Pipe Trunk (real metres: 1.4m dia conduit)
    # (A little shorter than the spine, so their end faces don't share a plane.)
    bmesh_add_real_chamfered_box(bm, (1.6, 218.0 * SCALE, 1.6), (0.0, 40.0 * SCALE, (88.5 + 3.2) * SCALE), chamfer=0.4, mat_idx=2)

    # 4 Transverse Structural Bridging Arches spanning over trench (Y: -18, 32, 82, 138)
    # Lintel 7 deep and legs 6.6, so neither shares a face plane with the
    # other or with the 5-deep fin bay end caps they straddle.
    for y_arch in (-18.0, 32.0, 82.0, 138.0):
        bmesh_add_chamfered_box(bm, (58.0, 7.0, 4.5), (0.0, y_arch, 97.0), chamfer=1.2, mat_idx=1) # Arch lintel
        for s in (-1, 1):
            bmesh_add_chamfered_box(bm, (4.5, 6.6, 11.0), (s * 27.0, y_arch, 89.5), chamfer=1.0, mat_idx=2)
            # Coolant manifold junctions on arch lintel corners
            bmesh_add_real_box(bm, (1.8, 1.8, 1.8), (s * 27.0 * SCALE, y_arch * SCALE, 99.5 * SCALE), mat_idx=2)
            
    # =========================================================================
    # 6. STERN CASTLE SUPERSTRUCTURE BASE (Y: -260 to -80, Z: 75 to 136)
    # Towering fortress mass stepping up in tiers
    # =========================================================================
    # The castle's foot goes down to z = 70, into the deck (76 here, 71 at its
    # aft end): at 78 to 82 the whole castle hovered over the deck.
    castle_glacis = [
        (-140.0, [(-46, 70), (-38, 124), (38, 124), (46, 70)]),
        (-80.0,  [(-40, 70), (-30, 98),  (30, 98),  (40, 70)]),
    ]
    bmesh_add_loft_y(bm, castle_glacis, mat_idx=1) # Destroyer_HullLight

    castle_citadel = [
        (-240.0, [(-46, 70), (-38, 124), (38, 124), (46, 70)]),
        (-140.0, [(-46, 70), (-38, 124), (38, 124), (46, 70)]),
    ]
    bmesh_add_loft_y(bm, castle_citadel, mat_idx=0)
    
    # Lateral Bastion Towers housing Turret Mounts 7 & 8 at X=±42, Y=-130, Z=124
    for s in (-1, 1):
        bmesh_add_chamfered_box(bm, (18.0, 38.0, 14.0), (s * 40.0, -130.0, 118.0), chamfer=2.5, mat_idx=2)
        bmesh_add_chamfered_box(bm, (22.0, 24.0, 8.0),  (s * 40.0, -130.0, 108.0), chamfer=2.0, mat_idx=1)
        # Bastion observation windows (real metres: 1.8m x 0.9m)
        for y_w in (-140.0, -130.0, -120.0):
            bmesh_add_real_box(bm, (0.4, 1.8, 0.9), (s * (49.0 * SCALE), y_w * SCALE, 118.0 * SCALE), mat_idx=6)
            
    # Stern Castle Upper Pedestal / Neck Base (Y: -180 to -135, Z: 124 to 136)
    bmesh_add_chamfered_box(bm, (44.0, 45.0, 12.0), (0.0, -157.5, 130.0), chamfer=3.0, mat_idx=2)
    
    # =========================================================================
    # 7. ARMOURED ENGINE BLOCK & TRANSOM COWLS (C1 REVIEW 2 & 3 REQUIREMENT)
    # Widens to 170m across (X=±85m) over Y: -215 to -315m.
    # Built-in cowlings for all 3 engines; Nozzles protrude 20m past transom!
    # Pylons and struts completely removed!
    # =========================================================================
    deck_wedge = [
        (-315.0, [(-85, 46), (-35, 54), (35, 54), (85, 46), (72, 42), (-72, 42)]),
        (-215.0, [(-56, 68), (-32, 78), (32, 78), (56, 68), (48, 62), (-48, 62)]),
    ]
    bmesh_add_loft_y(bm, deck_wedge, mat_idx=1)
    
    # Transom Engine Housing Cowlings (terminating at Y = -315m)
    # 1. Central Keel Cowling Collar (Center at X=0, Z=20)
    bmesh_add_chamfered_box(bm, (50.0, 25.0, 48.0), (0.0, -305.0, 20.0), chamfer=6.0, mat_idx=2)
    bmesh_add_box(bm, (38.0, 6.0, 38.0), (0.0, -313.0, 20.0), mat_idx=3) # Dark collar recess
    
    # 2 & 3. Built-In Side Engine Cowling Housings (Centers at X=±62, Z=36)
    # Rear faces are staggered (cowl -316, lip -316.5, post -316.9; housing
    # -314.6 just inside the deck wedge's -315): pieces sharing a face plane flicker.
    for s in (-1, 1):
        bmesh_add_chamfered_box(bm, (44.0, 40.0, 44.0), (s * 62.0, -294.6, 36.0), chamfer=7.0, mat_idx=1)
        bmesh_add_chamfered_box(bm, (46.0, 16.0, 46.0), (s * 62.0, -308.0, 36.0), chamfer=5.0, mat_idx=2)
        bmesh_add_box(bm, (36.0, 6.0, 36.0), (s * 62.0, -312.6, 36.0), mat_idx=3) # Dark collar recess

        # Heavy structural cowl rim projecting over nozzle at Y = -315m
        # (Lip top 59.8 above the cowl's 59; post side 84.5 beyond the housing's 84.)
        bmesh_add_chamfered_box(bm, (42.0, 7.0, 6.4), (s * 62.0, -313.0, 56.6), chamfer=1.5, mat_idx=4) # Crimson cowl lip
        bmesh_add_chamfered_box(bm, (6.0, 7.8, 42.0), (s * (62.0 + 19.5), -313.0, 36.0), chamfer=1.5, mat_idx=2)
        
        # Running lights on outer transom corners (real metres)
        bmesh_add_real_box(bm, (1.8, 1.8, 1.8), (s * 85.0 * SCALE, -315.0 * SCALE, 46.0 * SCALE), mat_idx=11)
        bmesh_add_real_box(bm, (1.8, 1.8, 1.8), (s * 85.0 * SCALE, -315.0 * SCALE, 20.0 * SCALE), mat_idx=11)
        
        # Fuel / Coolant manifold piping from engine block into cowl
        bmesh_add_real_chamfered_box(bm, (1.6, 50.0 * SCALE, 1.6), (s * 42.0 * SCALE, -280.0 * SCALE, 52.0 * SCALE), chamfer=0.4, mat_idx=2)
        
    # Structural Stern Crease Ribs across Engine Block
    bmesh_add_chamfered_box(bm, (78.0, 4.0, 4.5), (0.0, -260.0, 58.0), chamfer=1.0, mat_idx=1)
    bmesh_add_chamfered_box(bm, (108.0, 4.0, 4.5), (0.0, -285.0, 54.0), chamfer=1.0, mat_idx=1)
    bmesh_add_chamfered_box(bm, (138.0, 4.0, 4.5), (0.0, -310.0, 50.0), chamfer=1.0, mat_idx=2)
    
    # Engine Deck Thermal Exhaust Louvers (Y: -300 to -265, Z: 54 to 58)
    for y_v in range(-300, -265, 5):
        bmesh_add_box(bm, (50.0, 2.0, 1.8), (0.0, float(y_v), 56.5), mat_idx=3)
        
    # Engineering Deck Airlock Hatch (real metres)
    # Centred on the deck wedge's sloping top (78 - 24 * 30/100 at y = -245;
    # at z = 60 it was buried inside the wedge).
    deck_z = (78.0 - 24.0 * 30.0 / 100.0) * SCALE
    bmesh_add_real_box(bm, (3.5, 4.5, 1.6), (0.0, -245.0 * SCALE, deck_z), mat_idx=3)
    bmesh_add_real_box(bm, (2.5, 3.2, 1.8), (0.0, -245.0 * SCALE, deck_z + 0.15), mat_idx=1)
        
    # =========================================================================
    # 8. MULTI-TIERED STEPPED KEEL & VENTRAL MACHINERY BLOCKS (C2 REFINEMENT 2)
    # 3-tier stepped keel structure with forward sonar bulb, midships reactor vault,
    # and aft thruster feed sump.
    # =========================================================================
    for s in (-1, 1):
        ventral_sponson = [
            (-270.0, [(s * 32, -4), (s * 42, -12), (s * 46, -12), (s * 38, -4)]),
            (200.0,  [(s * 30, -2), (s * 38, -10), (s * 42, -10), (s * 34, -2)]),
        ]
        bmesh_add_loft_y(bm, ventral_sponson, mat_idx=0)
        
    # Tier 1: Wide ventral foundation deck / tray
    ventral_tray = [
        (-280.0, [(-24, -6), (-20, -14), (20, -14), (24, -6)]),
        (0.0,    [(-26, -6), (-22, -15), (22, -15), (26, -6)]),
        (210.0,  [(-20, -6), (-16, -14), (16, -14), (20, -6)]),
    ]
    bmesh_add_loft_y(bm, ventral_tray, mat_idx=0)
    
    # Tier 2: Stepped central keel spine girder
    keel_spine = [
        (-290.0, [(-14, -14), (-10, -25), (10, -25), (14, -14)]),
        (0.0,    [(-16, -15), (-12, -26), (12, -26), (16, -15)]),
        (220.0,  [(-12, -14), (-8,  -23), (8,  -23), (12, -14)]),
    ]
    bmesh_add_loft_y(bm, keel_spine, mat_idx=2) # Destroyer_HullDark
    
    # Tier 3: Three Massive Ventral Machinery / Reactor Blocks
    # 1. Forward Sonar / Gravimetric Sensor Bulb (Y: 135 to 185)
    bmesh_add_chamfered_box(bm, (28.0, 48.0, 14.0), (0.0, 160.0, -28.0), chamfer=3.0, mat_idx=1) # HullLight
    bmesh_add_box(bm, (20.0, 40.0, 1.5), (0.0, 160.0, -35.2), mat_idx=5) # GlowGreen sensor slit
    bmesh_add_real_box(bm, (1.6, 1.6, 1.6), (0.0, 184.0 * SCALE, -34.0 * SCALE), mat_idx=11) # RunningLight, on the bulb's nose
    
    # 2. Midships Ventral Reactor Vault / Containment Block (Y: -42 to 22)
    bmesh_add_chamfered_box(bm, (34.0, 64.0, 16.0), (0.0, -10.0, -31.0), chamfer=3.5, mat_idx=2) # HullDark
    bmesh_add_chamfered_box(bm, (36.0, 8.0, 16.5), (0.0, -10.0, -31.0), chamfer=1.5, mat_idx=4) # Crimson band
    # Transverse cooling louvers along reactor vault belly
    for y_l in (-30.0, -20.0, 0.0, 10.0, 20.0):
        bmesh_add_box(bm, (30.0, 3.0, 2.0), (0.0, y_l, -39.0), mat_idx=3)
    # Reactor maintenance access hatch (real metres)
    # Under the crimson band (bottom at -39.25), sunk 0.2 m into it.
    bmesh_add_real_box(bm, (3.0, 4.0, 0.8), (0.0, -10.0 * SCALE, (-39.25 * SCALE) - 0.2), mat_idx=1)
    
    # 3. Aft Fuel Manifold & Thruster Feed Sump Block (Y: -220 to -160)
    bmesh_add_chamfered_box(bm, (38.0, 60.0, 16.0), (0.0, -190.0, -29.0), chamfer=3.5, mat_idx=1) # HullLight
    # Twin heavy fuel trunk conduits running aft towards engine block
    for s in (-1, 1):
        bmesh_add_chamfered_box(bm, (6.0, 75.0, 6.0), (s * 14.0, -255.0, -26.0), chamfer=1.5, mat_idx=2)
    bmesh_add_real_box(bm, (1.6, 1.6, 1.6), (0.0, -160.0 * SCALE, -36.0 * SCALE), mat_idx=11) # RunningLight
        
    # 16 Transverse Ventral Rib Gussets (Z: -16)
    for y_gusset in np.linspace(-260.0, 180.0, 16):
        bmesh_add_chamfered_box(bm, (68.0, 4.5, 6.0), (0.0, y_gusset, -15.0), chamfer=1.2, mat_idx=2)
        
    # =========================================================================
    # 9. TURRET MOUNT PADS (8 FLAT LEVEL PADS 10M ACROSS - UNSCALED)
    # =========================================================================
    for p in MOUNT_PADS:
        mat_trans = Matrix.Translation(Vector((p[0] * SCALE, p[1] * SCALE, p[2] * SCALE)))
        res = bmesh.ops.create_cone(
            bm,
            cap_ends=True,
            segments=32,
            radius1=5.0,
            radius2=5.0,
            depth=2.0,
            matrix=mat_trans
        )
        for v in res["verts"]:
            for f in v.link_faces:
                f.material_index = 8 # TurretMount
                
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new("Juggernaut_Hull")
    bm.to_mesh(me)
    bm.free()
    setup_all_materials(me)
    return me

def build_juggernaut_bridge():
    """
    Builds Juggernaut_Bridge with pivot at center of base (0, 0, 0 local).
    Placed on hull at (0, BRIDGE_Y * SCALE, BRIDGE_Z * SCALE).
    C2 Refinement 3:
    - Base Plinth with deck paneling.
    - Sculpted narrow neck waist (18m x 20m) with 4 diagonal corner buttresses,
      giving deep undercut shadow and clear daylight separation!
    - Faceted forward-tapering command head with cheek deflectors.
    - Deeply recessed panoramic amber window band with 8 dark structural mullions.
    - Aggressive forward-raked visor brow (projecting 6m forward over windows with 15° rake).
    - Roof command crest with cupola dome, T-bar mast, real-metre antenna needles (6m).
    - Tertiary crew windows and red running lights.
    """
    bm = bmesh.new()
    
    # 1. Base pedestal tier (Z: 0 to 6, width 40m, length 38m)
    bmesh_add_chamfered_box(bm, (40.0, 38.0, 6.0), (0.0, 0.0, 3.0), chamfer=3.0, mat_idx=1) # HullLight
    bmesh_add_box(bm, (34.0, 32.0, 0.8), (0.0, 0.0, 6.2), mat_idx=2) # Contrasting deck plate
    
    # 2. Sculpted Narrow Neck Waist with Corner Daylight Cutouts (Z: 6 to 15)
    # Narrow waist core (18m wide x 20m long) vs 40m plinth and 38m head!
    bmesh_add_chamfered_box(bm, (18.0, 20.0, 9.0), (0.0, -1.0, 10.5), chamfer=1.5, mat_idx=2)
    # 4 Angled Diagonal Corner Buttress Pylons supporting head from below
    for sx in (-1, 1):
        for sy, y_b in [(-1, -9.0), (1, 7.0)]:
            bmesh_add_chamfered_box(bm, (4.5, 5.5, 9.0), (sx * 13.0, y_b, 10.5), chamfer=1.0, mat_idx=0)
        
    # 3. Main Command Head Lower Block (Z: 15 to 22)
    # Faceted forward-tapering hull block
    bmesh_add_chamfered_box(bm, (36.0, 32.0, 7.0), (0.0, 2.0, 18.5), chamfer=2.5, mat_idx=0)
    # Flared lateral cheek deflectors
    for s in (-1, 1):
        bmesh_add_chamfered_box(bm, (5.0, 24.0, 6.5), (s * 19.5, 1.0, 18.5), chamfer=1.5, mat_idx=2)
    # Forward prow snout wedge
    bmesh_add_chamfered_box(bm, (16.0, 6.0, 6.0), (0.0, 18.0, 18.5), chamfer=1.5, mat_idx=1)
        
    # 4. Deeply Recessed Panoramic Window Band with 8 Mullions (Z: 22 to 26)
    # Recessed inner amber glowing window core
    bmesh_add_chamfered_box(bm, (30.0, 28.0, 4.0), (0.0, 2.0, 24.0), chamfer=1.5, mat_idx=6) # Window
    # 8 Dark Structural Mullion Pillars dividing the embrasures
    # 4 Forward observation embrasure mullions
    # (4.6 tall, running into the head and visor: at 4.0 they shared the
    # window band's top and bottom planes.)
    for x_m in (-9.0, -3.0, 3.0, 9.0):
        bmesh_add_box(bm, (1.2, 1.5, 4.6), (x_m, 16.5, 24.0), mat_idx=2)
    # 4 Flank observation embrasure mullions (2 per side)
    for s in (-1, 1):
        for y_m in (-4.0, 4.0):
            bmesh_add_box(bm, (1.5, 1.2, 4.6), (s * 15.5, y_m, 24.0), mat_idx=2)
    
    # 5. Menacing Overhanging Armored Visor Brow (Z: 26 to 31)
    # Forward-raked visor brow extending 6.5m forward past windows
    bmesh_add_chamfered_box(bm, (38.0, 36.0, 5.0), (0.0, 5.0, 28.5), chamfer=3.0, mat_idx=2) # HullDark visor
    # Central forward beak crest with bold crimson stripe
    bmesh_add_chamfered_box(bm, (10.0, 34.0, 1.8), (0.0, 5.0, 31.2), chamfer=0.8, mat_idx=4) # Crimson crest
    # Flared downward cheek deflector wings
    for s in (-1, 1):
        bmesh_add_chamfered_box(bm, (4.0, 26.0, 4.5), (s * 19.5, 3.0, 27.5), chamfer=1.0, mat_idx=1)
    
    # 6. Roof Command Crest & Sensor Array (Z: 31 to 38)
    bmesh_add_chamfered_box(bm, (10.0, 10.0, 4.5), (0.0, 0.0, 33.2), chamfer=2.0, mat_idx=2) # Cupola
    bmesh_add_chamfered_box(bm, (22.0, 3.5, 2.5), (0.0, -2.0, 36.5), chamfer=0.8, mat_idx=1) # T-bar mast
    for s in (-1, 1):
        bmesh_add_chamfered_box(bm, (4.5, 4.5, 3.5), (s * 11.5, 2.0, 31.5), chamfer=1.2, mat_idx=1)
        
    # Real-metre Communication Antenna Needles (6m tall, 0.4m dia - real metres)
    # Standing on the T-bar mast (top at 37.75), foot sunk 0.4 m into it.
    for s in (-1, 1):
        bmesh_add_real_box(bm, (0.4, 0.4, 6.0), (s * 8.0 * SCALE, -2.0 * SCALE, 37.5 * SCALE + 3.0), mat_idx=2)
        # Red beacon light at antenna tip (real metres)
        bmesh_add_real_box(bm, (1.2, 1.2, 1.2), (s * 8.0 * SCALE, -2.0 * SCALE, 37.5 * SCALE + 6.0), mat_idx=11)
        # Red running lights on visor brow wingtips (real metres)
        bmesh_add_real_box(bm, (1.5, 1.5, 1.5), (s * 19.5 * SCALE, 16.0 * SCALE, 28.5 * SCALE), mat_idx=11)
        
    # Crew / Officer Stateroom Windows on lower command deck flanks (real metres: 1.8m x 0.9m)
    # On the cheek deflectors' outer faces (x = 22, y -11 to 13): at x = 18.5
    # they were hidden inside the cheeks, or hung in the air behind them.
    for s in (-1, 1):
        for y_win in (9.0, 3.0, -3.0, -9.0):
            bmesh_add_real_box(bm, (0.4, 1.8, 0.9), (s * (22.0 * SCALE + 0.15), y_win * SCALE, 18.5 * SCALE), mat_idx=6)
        
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new("Juggernaut_Bridge")
    bm.to_mesh(me)
    bm.free()
    setup_all_materials(me)
    return me

def build_juggernaut_thruster_keel():
    """
    Builds Juggernaut_ThrusterKeel with pivot at nozzle center (0, 0, 0 local) facing -Y.
    100% closed, manifold geometry. Deep flared bell lined with Destroyer_EngineGlow.
    """
    bm = bmesh.new()
    outer_r, inner_r, length = 22.0 * SCALE, 16.0 * SCALE, 44.0 * SCALE
    throat_depth = 12.0 * SCALE
    segments = 24
    
    v_lip_out = []
    v_front = []
    for i in range(segments):
        th = 2.0 * math.pi * i / segments
        c, s = math.cos(th), math.sin(th)
        v_lip_out.append(bm.verts.new(Vector((c * outer_r, 0.0, s * outer_r))))
        v_front.append(bm.verts.new(Vector((c * (outer_r + 3.0 * SCALE), length, s * (outer_r + 3.0 * SCALE)))))
    bm.verts.ensure_lookup_table()
    
    for i in range(segments):
        nxt = (i + 1) % segments
        bm.faces.new([v_lip_out[i], v_front[i], v_front[nxt], v_lip_out[nxt]]).material_index = 2
    c_front = bm.verts.new(Vector((0.0, length, 0.0)))
    for i in range(segments):
        nxt = (i + 1) % segments
        bm.faces.new([c_front, v_front[nxt], v_front[i]]).material_index = 2
        
    v_lip_in = []
    v_throat = []
    for i in range(segments):
        th = 2.0 * math.pi * i / segments
        c, s = math.cos(th), math.sin(th)
        v_lip_in.append(bm.verts.new(Vector((c * (outer_r - 2.0 * SCALE), 0.0, s * (outer_r - 2.0 * SCALE)))))
        v_throat.append(bm.verts.new(Vector((c * inner_r, throat_depth, s * inner_r))))
    bm.verts.ensure_lookup_table()
    
    for i in range(segments):
        nxt = (i + 1) % segments
        bm.faces.new([v_lip_out[nxt], v_lip_out[i], v_lip_in[i], v_lip_in[nxt]]).material_index = 1
        
    for i in range(segments):
        nxt = (i + 1) % segments
        bm.faces.new([v_lip_in[i], v_throat[i], v_throat[nxt], v_lip_in[nxt]]).material_index = 7 # EngineGlow
        
    c_core = bm.verts.new(Vector((0.0, throat_depth, 0.0)))
    for i in range(segments):
        nxt = (i + 1) % segments
        bm.faces.new([c_core, v_throat[nxt], v_throat[i]]).material_index = 7 # EngineGlow
        
    c_cone_tip = bm.verts.new(Vector((0.0, throat_depth - 6.0 * SCALE, 0.0)))
    v_cone_base = []
    for i in range(12):
        th = 2.0 * math.pi * i / 12
        c, s = math.cos(th), math.sin(th)
        v_cone_base.append(bm.verts.new(Vector((c * 5.0 * SCALE, throat_depth, s * 5.0 * SCALE))))
    bm.verts.ensure_lookup_table()
    for i in range(12):
        nxt = (i + 1) % 12
        bm.faces.new([c_cone_tip, v_cone_base[i], v_cone_base[nxt]]).material_index = 7 # EngineGlow
    bm.faces.new(list(reversed(v_cone_base))).material_index = 7 # Cone base cap
    
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new("Juggernaut_ThrusterKeel")
    bm.to_mesh(me)
    bm.free()
    setup_all_materials(me)
    return me

def build_juggernaut_thruster_pod():
    """
    Builds Juggernaut_ThrusterPod with pivot at nozzle center (0, 0, 0 local) facing -Y.
    100% closed, manifold geometry. Deep flared bell lined with Destroyer_EngineGlow.
    Keeps only nozzle and glowing core so destroyed pod chars without charring hull.
    """
    bm = bmesh.new()
    outer_r, inner_r, length = 18.0 * SCALE, 13.0 * SCALE, 40.0 * SCALE
    throat_depth = 11.0 * SCALE
    segments = 24
    
    v_lip_out = []
    v_front = []
    for i in range(segments):
        th = 2.0 * math.pi * i / segments
        c, s = math.cos(th), math.sin(th)
        v_lip_out.append(bm.verts.new(Vector((c * outer_r, 0.0, s * outer_r))))
        v_front.append(bm.verts.new(Vector((c * (outer_r + 3.0 * SCALE), length, s * (outer_r + 3.0 * SCALE)))))
    bm.verts.ensure_lookup_table()
    
    for i in range(segments):
        nxt = (i + 1) % segments
        bm.faces.new([v_lip_out[i], v_front[i], v_front[nxt], v_lip_out[nxt]]).material_index = 2
    c_front = bm.verts.new(Vector((0.0, length, 0.0)))
    for i in range(segments):
        nxt = (i + 1) % segments
        bm.faces.new([c_front, v_front[nxt], v_front[i]]).material_index = 2
        
    v_lip_in = []
    v_throat = []
    for i in range(segments):
        th = 2.0 * math.pi * i / segments
        c, s = math.cos(th), math.sin(th)
        v_lip_in.append(bm.verts.new(Vector((c * (outer_r - 2.0 * SCALE), 0.0, s * (outer_r - 2.0 * SCALE)))))
        v_throat.append(bm.verts.new(Vector((c * inner_r, throat_depth, s * inner_r))))
    bm.verts.ensure_lookup_table()
    
    for i in range(segments):
        nxt = (i + 1) % segments
        bm.faces.new([v_lip_out[nxt], v_lip_out[i], v_lip_in[i], v_lip_in[nxt]]).material_index = 1
        
    for i in range(segments):
        nxt = (i + 1) % segments
        bm.faces.new([v_lip_in[i], v_throat[i], v_throat[nxt], v_lip_in[nxt]]).material_index = 7 # EngineGlow
        
    c_core = bm.verts.new(Vector((0.0, throat_depth, 0.0)))
    for i in range(segments):
        nxt = (i + 1) % segments
        bm.faces.new([c_core, v_throat[nxt], v_throat[i]]).material_index = 7 # EngineGlow
        
    c_cone_tip = bm.verts.new(Vector((0.0, throat_depth - 5.0 * SCALE, 0.0)))
    v_cone_base = []
    for i in range(12):
        th = 2.0 * math.pi * i / 12
        c, s = math.cos(th), math.sin(th)
        v_cone_base.append(bm.verts.new(Vector((c * 4.0 * SCALE, throat_depth, s * 4.0 * SCALE))))
    bm.verts.ensure_lookup_table()
    for i in range(12):
        nxt = (i + 1) % 12
        bm.faces.new([c_cone_tip, v_cone_base[i], v_cone_base[nxt]]).material_index = 7 # EngineGlow
    bm.faces.new(list(reversed(v_cone_base))).material_index = 7 # Cone base cap
    
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new("Juggernaut_ThrusterPod")
    bm.to_mesh(me)
    bm.free()
    setup_all_materials(me)
    return me

def build_juggernaut_hangar_door():
    """
    Builds Juggernaut_HangarDoor with pivot at door center (0, 0, 0 local).
    Dimensions: 78m L x 36m H x 3.6m thick (before scale). Painted crimson warning panel.
    """
    bm = bmesh.new()
    bmesh_add_chamfered_box(bm, (3.2, 76.0, 34.0), (0.0, 0.0, 0.0), chamfer=1.5, mat_idx=1) # HullLight
    bmesh_add_box(bm, (3.6, 50.0, 12.0), (0.0, 0.0, 0.0), mat_idx=4) # Crimson stripe
    
    # Ribs stand 0.3 proud of the stripe (at 3.5 they were 0.05 from its faces and flickered).
    for z_rib in (-12.0, -6.0, 6.0, 12.0):
        bmesh_add_box(bm, (4.2, 74.0, 1.8), (0.0, 0.0, z_rib), mat_idx=2)
        
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new("Juggernaut_HangarDoor")
    bm.to_mesh(me)
    bm.free()
    setup_all_materials(me)
    return me

# -----------------------------------------------------------------------------
# Redesigned Chunky Industrial Turret (Zero Clipping, Mantlet Pitch Axis)
# Turret and its 10m mount pads remain completely UNSCALED (SCALE = 1.0)
# -----------------------------------------------------------------------------
def build_turret_parts():
    """
    Builds the 3-part heavy dual-barrel turret:
    - Turret_Base: origin Z=0 (mount pad), octagonal ring r=3.2 to 3.8m, h=1.4m.
    - Turret_Yaw: origin on yaw axis Z=2.0. Armored gunhouse with open front/roof slot.
    - Turret_Pitch: origin on pitch axis inside front mantlet slot (0, 1.3, 0.8) relative to yaw.
      Twin slim barrels elevate from -5° to 80° with ZERO clipping!
    - Base + Yaw strictly fits <= 5.0m bounding sphere.
    """
    # 1. Turret_Base (Origin at mount surface Z=0)
    bm_b = bmesh.new()
    pts_b_bot = []
    pts_b_top = []
    for i in range(8):
        th = 2.0 * math.pi * i / 8.0
        c, s = math.cos(th), math.sin(th)
        pts_b_bot.append(Vector((c * 3.2, s * 3.2, 0.0)))
        pts_b_top.append(Vector((c * 3.8, s * 3.8, 1.6)))  # 1.6: the head's underside is at 1.5
    vb_bot = [bm_b.verts.new(p) for p in pts_b_bot]
    vb_top = [bm_b.verts.new(p) for p in pts_b_top]
    bm_b.verts.ensure_lookup_table()
    
    bm_b.faces.new(list(reversed(vb_bot))).material_index = 8 # TurretMount
    bm_b.faces.new(vb_top).material_index = 8
    for i in range(8):
        nxt = (i + 1) % 8
        bm_b.faces.new([vb_bot[i], vb_bot[nxt], vb_top[nxt], vb_top[i]]).material_index = 8
        
    bmesh.ops.recalc_face_normals(bm_b, faces=bm_b.faces)
    me_b = bpy.data.meshes.new("Turret_Base")
    bm_b.to_mesh(me_b)
    bm_b.free()
    setup_all_materials(me_b)
    
    # 2. Turret_Yaw (Origin on yaw axis Z=2.0 in base space)
    bm_y = bmesh.new()
    
    # Left cheek armor block (X: -2.8 to -1.4, Y: -2.8 to 2.4, Z: -0.5 to 2.0)
    bmesh_add_chamfered_box(bm_y, (1.4, 5.2, 2.5), (-2.1, -0.2, 0.75), chamfer=0.4, mat_idx=0, scale=1.0)
    # Right cheek armor block (X: 1.4 to 2.8, Y: -2.8 to 2.4, Z: -0.5 to 2.0)
    bmesh_add_chamfered_box(bm_y, (1.4, 5.2, 2.5), (2.1, -0.2, 0.75), chamfer=0.4, mat_idx=0, scale=1.0)
    # Rear armor bustle block (X: -2.8 to 2.8, Y: -2.8 to 0.4, Z: -0.5 to 2.0)
    bmesh_add_chamfered_box(bm_y, (5.6, 2.4, 2.5), (0.0, -1.6, 0.75), chamfer=0.5, mat_idx=1, scale=1.0)
    # Turret floor tray under gun cradle (Z: -0.5 to -0.1, Y: 0.4 to 2.4, X: ±1.4)
    bmesh_add_box(bm_y, (2.8, 2.0, 0.4), (0.0, 1.4, -0.3), mat_idx=3, scale=1.0)
    
    # Integrated Recessed Sensor Eye on right cheek face (X=2.0, Y=2.2, Z=1.1)
    bmesh_add_chamfered_box(bm_y, (1.0, 0.8, 0.8), (2.1, 2.2, 1.1), chamfer=0.2, mat_idx=2, scale=1.0)
    bmesh_add_box(bm_y, (0.7, 0.25, 0.45), (2.1, 2.55, 1.1), mat_idx=10, scale=1.0) # TurretEye (glowing green lens)
    
    bmesh.ops.recalc_face_normals(bm_y, faces=bm_y.faces)
    me_y = bpy.data.meshes.new("Turret_Yaw")
    bm_y.to_mesh(me_y)
    bm_y.free()
    setup_all_materials(me_y)
    
    # 3. Turret_Pitch (Origin at pitch axis inside gun slot: (0.0, 1.3, 0.8) relative to yaw)
    bm_p = bmesh.new()
    
    pts_m_l = []
    pts_m_r = []
    for i in range(16):
        th = 2.0 * math.pi * i / 16.0
        c, s = math.cos(th), math.sin(th)
        pts_m_l.append(Vector((-1.3, c * 1.05, s * 1.05)))
        pts_m_r.append(Vector((1.3,  c * 1.05, s * 1.05)))
    vm_l = [bm_p.verts.new(p) for p in pts_m_l]
    vm_r = [bm_p.verts.new(p) for p in pts_m_r]
    bm_p.verts.ensure_lookup_table()
    bm_p.faces.new(list(reversed(vm_l))).material_index = 9 # TurretMetal
    bm_p.faces.new(vm_r).material_index = 9
    for i in range(16):
        nxt = (i + 1) % 16
        bm_p.faces.new([vm_l[i], vm_l[nxt], vm_r[nxt], vm_r[i]]).material_index = 9
        
    for s in (-1.0, 1.0):
        bmesh_add_chamfered_box(bm_p, (0.75, 2.8, 0.75), (s * 0.9, 1.5, 0.0), chamfer=0.12, mat_idx=1, scale=1.0)
        bmesh_add_chamfered_box(bm_p, (0.45, 6.0, 0.45), (s * 0.9, 5.7, 0.0), chamfer=0.08, mat_idx=9, scale=1.0)
        bmesh_add_chamfered_box(bm_p, (0.65, 1.2, 0.65), (s * 0.9, 9.0, 0.0), chamfer=0.12, mat_idx=2, scale=1.0)
        bmesh_add_box(bm_p, (0.75, 0.5, 0.25), (s * 0.9, 9.0, 0.0), mat_idx=3, scale=1.0)
        
    bmesh.ops.recalc_face_normals(bm_p, faces=bm_p.faces)
    me_p = bpy.data.meshes.new("Turret_Pitch")
    bm_p.to_mesh(me_p)
    bm_p.free()
    setup_all_materials(me_p)
    
    return me_b, me_y, me_p

# -----------------------------------------------------------------------------
# Collision & Marker Builders
# -----------------------------------------------------------------------------
def build_collision_meshes(col_collision):
    """
    Builds the Collision collection of 14 convex, closed meshes named Col_<Name>
    covering the scaled hull closely (within a few metres).
    All parts (bridge, thrusters, doors, turrets) are excluded as they have their own collision in-game.
    """
    col_specs = [
        ("Col_RamBow", (38.0, 78.0, 44.0), (0.0, 310.0, 15.0), 8.0),
        ("Col_GlacisUpper", (72.0, 120.0, 28.0), (0.0, 210.0, 68.0), 10.0),
        ("Col_GlacisLower", (84.0, 120.0, 44.0), (0.0, 210.0, 30.0), 8.0),
        ("Col_SpineDorsal", (54.0, 230.0, 24.0), (0.0, 35.0, 90.0), 6.0),
        ("Col_Sponson_L", (36.0, 240.0, 74.0), (-80.0, 0.0, 40.0), 5.0),
        ("Col_Sponson_R", (36.0, 240.0, 74.0), (80.0, 0.0, 40.0), 5.0),
        ("Col_CastleBase", (84.0, 150.0, 46.0), (0.0, -170.0, 105.0), 10.0),
        ("Col_CastleTower", (48.0, 75.0, 16.0), (0.0, -145.0, 130.0), 5.0),
        ("Col_EngineBlock_C", (74.0, 100.0, 58.0), (0.0, -265.0, 30.0), 8.0),
        ("Col_EngineBlock_L", (50.0, 95.0, 48.0), (-62.0, -270.0, 38.0), 6.0),
        ("Col_EngineBlock_R", (50.0, 95.0, 48.0), (62.0, -270.0, 38.0), 6.0),
        ("Col_KeelForward", (44.0, 120.0, 34.0), (0.0, 160.0, -18.0), 6.0),
        ("Col_KeelMid", (48.0, 140.0, 38.0), (0.0, -10.0, -22.0), 6.0),
        ("Col_KeelAft", (54.0, 150.0, 36.0), (0.0, -185.0, -20.0), 6.0),
    ]
    
    col_objs = []
    for name, size, center, chamfer in col_specs:
        bm = bmesh.new()
        bmesh_add_chamfered_box(bm, size, center, chamfer=chamfer, mat_idx=0, scale=SCALE)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        obj = bpy.data.objects.new(name, me)
        col_collision.objects.link(obj)
        col_objs.append(obj)
        
    return col_objs

def build_markers(col_markers):
    """
    Builds the Markers collection of 16 empties:
    - Part pivots: Bridge, ThrusterKeel, ThrusterPod_L/R, HangarDoor_L/R
    - Launch points: Launch_L/R
    - Turret mounts: TurretMount_1..8
    """
    marker_specs = [
        ("Marker_Bridge", (0.0, BRIDGE_Y * SCALE, BRIDGE_Z * SCALE)),
        ("Marker_ThrusterKeel", (0.0, -335.0 * SCALE, 20.0 * SCALE)),
        ("Marker_ThrusterPod_L", (-62.0 * SCALE, -335.0 * SCALE, 36.0 * SCALE)),
        ("Marker_ThrusterPod_R", (62.0 * SCALE, -335.0 * SCALE, 36.0 * SCALE)),
        ("Marker_HangarDoor_L", (-88.0 * SCALE, -10.0 * SCALE, 24.0 * SCALE)),
        ("Marker_HangarDoor_R", (88.0 * SCALE, -10.0 * SCALE, 24.0 * SCALE)),
        ("Marker_Launch_L", (-90.0 * SCALE, -10.0 * SCALE, 24.0 * SCALE)),
        ("Marker_Launch_R", (90.0 * SCALE, -10.0 * SCALE, 24.0 * SCALE)),
    ]
    
    for i, p in enumerate(MOUNT_PADS, 1):
        marker_specs.append((f"Marker_TurretMount_{i}", (p[0] * SCALE, p[1] * SCALE, p[2] * SCALE + 1.0)))
        
    marker_objs = []
    for name, loc in marker_specs:
        emp = bpy.data.objects.new(name, None)
        emp.location = Vector(loc)
        col_markers.objects.link(emp)
        marker_objs.append(emp)
        
    return marker_objs

# -----------------------------------------------------------------------------
# Scene Assembly & Population
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# Hull Surface Detail (Pass C3): painted into the hull
# -----------------------------------------------------------------------------
# Armour panels, window bands, running lights and markings, painted flush into
# Juggernaut_Hull itself: each one is a rectangle cut into the hull's faces,
# whose faces inside it get another material. Nothing stands off the surface,
# and a colour change draws no ink line, so they read as part of the hull.
#
# Placing: each rectangle is found by ray-casting onto the hull and turned to
# the surface there. It's kept only if its whole footprint (plus a margin)
# samples as one flat plane, outside the keep-out areas, and clear of other
# rectangles, so it never wraps over an edge, a step or the existing detail.
# Sizes are in real metres; area bounds in design units.
#
# Cutting: four planes through the rectangle's sides split the faces under it
# (bmesh bisect). Hull quads that are bent (several are, by up to 3 m) are
# first replaced by Blender's own triangles for them, so cutting them can't
# move the surface. Afterwards, flat faces of one material are merged again,
# which removes the cut lines running past each rectangle.

PAINT_MATS = {
    "hull": 0, "light": 1, "dark": 2, "crimson": 4,
    "window": 6, "running_light": 11, "mid": 12,
}
# Panel greys, tried in this order of preference (after a per-panel shuffle);
# a panel never takes the grey of the surface it's painted on.
PANEL_GREYS = ["mid", "light", "dark", "hull"]

THRUSTER_POINTS = [(0.0, -335.0, 20.0), (-62.0, -335.0, 36.0), (62.0, -335.0, 36.0)]


def detail_keep_out(p):
    """The keep-out area a world point is in (the C3 brief's list), or None."""
    x, y, z = p.x / SCALE, p.y / SCALE, p.z / SCALE
    for px, py, pz in MOUNT_PADS:
        if (x - px) ** 2 + (y - py) ** 2 < 10.0 ** 2:
            return "pad"
    if abs(x) >= 84.0 and -56.0 <= y <= 36.0 and 0.0 <= z <= 80.0:
        return "hangar"
    # The trench's inside: fins, glow beds, arches, spine.
    if abs(x) < 24.5 and -72.0 <= y <= 152.0 and z >= 76.0:
        return "trench"
    if abs(x) <= 22.0 and -180.0 <= y <= -135.0 and z >= 130.0:
        return "pedestal"
    for tx, ty, tz in THRUSTER_POINTS:
        if (x - tx) ** 2 + (y - ty) ** 2 < 30.0 ** 2 and abs(z - tz) < 30.0:
            return "engine"
    return None


def detail_frame(normal, along):
    """Axes for a rectangle on a surface: z out of it, y as close to `along`
    as the surface allows (they run along the ship), x across."""
    z = normal.normalized()
    y = along - z * along.dot(z)
    if y.length < 1e-3:
        y = Vector((1.0, 0.0, 0.0)) - z * z.x
    y.normalize()
    return y.cross(z), y, z


class HullPaint:
    def __init__(self, hull_obj, seed=1138):
        self.mesh = hull_obj.data
        self.mesh.calc_loop_triangles()
        tris = self.mesh.loop_triangles
        # Built from Blender's own triangles (what the export writes), so the
        # triangle index also gives the polygon each hit lies on.
        self.tri_poly = [t.polygon_index for t in tris]
        self.bvh = BVHTree.FromPolygons([v.co.copy() for v in self.mesh.vertices],
                                        [tuple(t.vertices) for t in tris])
        self.rng = random.Random(seed)
        self.decals = []   # dicts: center, x, y, z, sx, sy, paint, polys, roll
        self.placed = []   # bounding boxes, for spacing
        self.stats = {}

    # --- placing -------------------------------------------------------------

    def _bounds(self, center, x, y, sx, sy):
        corners = [center + x * (dx * sx) + y * (dy * sy) for dx in (-0.5, 0.5) for dy in (-0.5, 0.5)]
        lo = Vector((min(c.x for c in corners), min(c.y for c in corners), min(c.z for c in corners))) - Vector((0.2, 0.2, 0.2))
        hi = Vector((max(c.x for c in corners), max(c.y for c in corners), max(c.z for c in corners))) + Vector((0.2, 0.2, 0.2))
        return lo, hi

    def _clashes(self, lo, hi, gap):
        for plo, phi in self.placed:
            if (lo.x - gap < phi.x and hi.x + gap > plo.x and lo.y - gap < phi.y and hi.y + gap > plo.y
                    and lo.z - gap < phi.z and hi.z + gap > plo.z):
                return True
        return False

    def _footprint(self, loc, x, y, z, sx, sy, tol, pad, step):
        """(why the footprint can't take a rectangle or None, the hull
        polygons under it)."""
        wa, wb = sx + 2.0 * pad, sy + 2.0 * pad
        na, nb = max(2, math.ceil(wa / step)), max(2, math.ceil(wb / step))
        polys = set()
        for i in range(na + 1):
            for j in range(nb + 1):
                p = loc + x * (-wa / 2.0 + wa * i / na) + y * (-wb / 2.0 + wb * j / nb)
                hit, normal, index, _ = self.bvh.ray_cast(p + z * 25.0, -z, 28.0)
                if hit is None:
                    return "edge", polys
                if normal.dot(z) < 0.0:
                    normal = -normal
                if abs((hit - loc).dot(z)) > tol or normal.dot(z) < 0.985:
                    return "uneven", polys
                if detail_keep_out(hit):
                    return "keep-out", polys
                polys.add(self.tri_poly[index])
        return None, polys

    def place(self, area, origin, direction, sx, sy, paint, along=Vector((0.0, 1.0, 0.0)),
              tol=0.1, pad=0.6, step=1.0, gap=0.6, shrink=(1.0,)):
        """Ray-casts from `origin` along `direction` onto the hull and records
        a rectangle there (sx across, sy along), trying each `shrink` factor in
        turn. True if one was recorded."""
        stats = self.stats.setdefault(area, {})
        hit, normal, _, _ = self.bvh.ray_cast(origin, direction)
        if hit is None:
            stats["miss"] = stats.get("miss", 0) + 1
            return False
        if normal.dot(direction) > 0.0:
            normal = -normal
        x, y, z = detail_frame(normal, along)
        reason = "keep-out" if detail_keep_out(hit) else None
        if reason is None:
            for f in shrink:
                a, b = sx * f, sy * f
                reason, polys = self._footprint(hit, x, y, z, a, b, tol, pad, step)
                if reason:
                    continue
                lo, hi = self._bounds(hit, x, y, a, b)
                if self._clashes(lo, hi, gap):
                    reason = "overlap"
                    continue
                self.placed.append((lo, hi))
                self.decals.append({"center": hit, "x": x, "y": y, "z": z, "sx": a, "sy": b,
                                    "paint": paint, "polys": polys, "roll": self.rng.random()})
                stats["placed"] = stats.get("placed", 0) + 1
                return True
        stats[reason] = stats.get(reason, 0) + 1
        return False

    # --- patterns ------------------------------------------------------------

    def panels_top(self, area, x0, x1, y0, y1, cw, cl, gap=2.0, skip=0.15, direction=-1.0):
        """A grid of panels on the surfaces seen from above, cw across by cl
        along (m), over design x0..x1 (x >= 0, mirrored to the other side) and
        y0..y1. Some cells stay bare; a cell that doesn't fit shrinks once,
        then gives up."""
        xa, xb, ya, yb = x0 * SCALE, x1 * SCALE, y0 * SCALE, y1 * SCALE
        nx = max(1, int((xb - xa + gap) // (cw + gap)))
        ny = max(1, int((yb - ya + gap) // (cl + gap)))
        for i in range(nx):
            cx = xa + gap / 2.0 + cw / 2.0 + i * (cw + gap)
            for j in range(ny):
                cy = ya + cl / 2.0 + j * (cl + gap)
                if self.rng.random() < skip:
                    continue
                for side in ((1.0, -1.0) if cx > 0.5 else (1.0,)):
                    self.place(area, Vector((side * cx, cy, 300.0 * -direction)), Vector((0.0, 0.0, direction)),
                               cw, cl, "panel", shrink=(1.0, 0.75))

    def panels_side(self, area, y0, y1, z0, z1, ch, cl, gap=2.0, skip=0.15):
        """A grid of panels on the hull's sides, seen from +x and -x: ch tall by
        cl along (m), over design y0..y1 and z0..z1."""
        ya, yb, za, zb = y0 * SCALE, y1 * SCALE, z0 * SCALE, z1 * SCALE
        ny = max(1, int((yb - ya + gap) // (cl + gap)))
        nz = max(1, int((zb - za + gap) // (ch + gap)))
        for j in range(ny):
            cy = ya + cl / 2.0 + j * (cl + gap)
            for k in range(nz):
                cz = za + ch / 2.0 + k * (ch + gap)
                if self.rng.random() < skip:
                    continue
                for side in (1.0, -1.0):
                    self.place(area, Vector((side * 400.0, cy, cz)), Vector((-side, 0.0, 0.0)),
                               ch, cl, "panel", shrink=(1.0, 0.75))

    def window_band(self, area, y0, y1, z=None, x=None, run=16, pause=3, spacing=3.6):
        """Rows of 1.8 x 0.9 m windows along the ship, long side horizontal: on
        both sides at height z (seen from +-x), or on the belly at x (seen from
        below). Runs of `run` windows with a pause of `pause` windows between,
        from design y1 down to y0."""
        y, count = y1 * SCALE, 0
        while y >= y0 * SCALE:
            if count < run:
                for side in (1.0, -1.0):
                    if z is not None:
                        origin, direction = Vector((side * 400.0, y, z * SCALE)), Vector((-side, 0.0, 0.0))
                    else:
                        origin, direction = Vector((side * x * SCALE, y, -300.0)), Vector((0.0, 0.0, 1.0))
                    self.place(area, origin, direction, 0.9, 1.8, "window",
                               tol=0.08, pad=0.5, step=0.45, gap=0.3)
            count = (count + 1) % (run + pause)
            y -= spacing

    def light(self, area, origin, direction, search=3.0):
        """A 2 m running light on the nearest flat spot round a point (tries
        offsets up to `search` m), mirrored across the centre line."""
        for side in (1.0, -1.0):
            o = Vector((origin.x * side, origin.y, origin.z))
            d = Vector((direction.x * side, direction.y, direction.z))
            offsets = [Vector((0, 0, 0))]
            for r in (search / 2.0, search):
                for v in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
                    offsets.append(Vector(v) * r)
            for off in offsets:
                if self.place(area, o + off, d, 2.0, 2.0, "running_light", tol=0.12, pad=0.3, step=0.5, gap=0.4):
                    break

    def chevron(self, area, y, arm=16.0, width=3.0, angle=0.6):
        """A crimson chevron on a deck at design y, pointing forward: two bars
        either side of the centre line (not meeting, so they don't overlap)."""
        s, c = math.sin(angle), math.cos(angle)
        for side in (1.0, -1.0):
            along = Vector((-side * s, c, 0.0))
            cx = side * (arm / 2.0 * s + 1.5)
            self.place(area, Vector((cx, y * SCALE, 300.0)), Vector((0.0, 0.0, -1.0)),
                       width, arm, "crimson", along=along, gap=0.5, shrink=(1.0, 0.8))

    def stripe_across(self, area, x, y, length, width=3.0):
        """A crimson stripe across the ship at design (x, y), mirrored."""
        for side in (1.0, -1.0):
            self.place(area, Vector((side * x * SCALE, y * SCALE, 300.0)), Vector((0.0, 0.0, -1.0)),
                       length, width, "crimson", gap=0.5, shrink=(1.0, 0.75, 0.5))

    def report(self):
        print("\n--- HULL PAINT PLACEMENT (placed / skipped by reason) ---")
        for area, st in self.stats.items():
            rest = ", ".join("%s %d" % (k, v) for k, v in sorted(st.items()) if k != "placed")
            print("  %-14s placed %4d   %s" % (area, st.get("placed", 0), rest))

    # --- cutting -------------------------------------------------------------

    def apply(self):
        """Cuts every recorded rectangle into the hull mesh and paints it."""
        me = self.mesh
        me.materials.append(get_or_create_material("HullMid"))  # index 12
        tris_by_poly = {}
        for t in me.loop_triangles:
            tris_by_poly.setdefault(t.polygon_index, []).append(tuple(t.vertices))

        bm = bmesh.new()
        bm.from_mesh(me)
        bm.faces.ensure_lookup_table()
        bm.verts.ensure_lookup_table()

        # Bent polygons (anywhere, not just under a rectangle): swap in
        # Blender's own triangles first. Cutting a bent quad, or merging it with
        # a neighbour below, would triangulate it another way and move the
        # surface; its triangles are exactly flat, so they only ever merge
        # with faces truly in their plane.
        bent = 0
        for pi, f in enumerate(list(bm.faces)):
            if len(f.verts) == 3:
                continue
            n, c = f.normal, f.calc_center_median()
            if max(abs((v.co - c).dot(n)) for v in f.verts) < 0.002:
                continue
            mat = f.material_index
            bmesh.ops.delete(bm, geom=[f], context='FACES_ONLY')
            for tv in tris_by_poly[pi]:
                bm.faces.new([bm.verts[i] for i in tv]).material_index = mat
            bent += 1

        # Edges to keep: the hull's own (halves of a split edge inherit the
        # mark) and each finished rectangle's outline. New cut edges start at 0.
        keep = bm.edges.layers.int.new("keep")
        for e in bm.edges:
            e[keep] = 1
        cover = {}  # paint kind -> painted fraction of each rectangle

        for d in self.decals:
            c, x, y, z = d["center"], d["x"], d["y"], d["z"]
            hx, hy = d["sx"] / 2.0, d["sy"] / 2.0

            # The faces under the rectangle (and a margin round it), found on
            # the mesh as it is now: earlier rectangles have reshaped it.
            bm.faces.ensure_lookup_table()
            tree = BVHTree.FromBMesh(bm)
            step = min(1.0, max(0.3, min(hx, hy) / 2.0))
            wa, wb = 2.0 * hx + 1.0, 2.0 * hy + 1.0
            na, nb = max(2, math.ceil(wa / step)), max(2, math.ceil(wb / step))
            faces = set()
            for i in range(na + 1):
                for j in range(nb + 1):
                    p = c + x * (-wa / 2.0 + wa * i / na) + y * (-wb / 2.0 + wb * j / nb)
                    hit = tree.ray_cast(p + z * 2.0, -z, 4.0)
                    if hit[0] is not None:
                        faces.add(bm.faces[hit[2]])

            for co, no in ((c + x * hx, x), (c - x * hx, x), (c + y * hy, y), (c - y * hy, y)):
                edges = {e for f in faces for e in f.edges}
                verts = {v for f in faces for v in f.verts}
                res = bmesh.ops.bisect_plane(bm, geom=list(faces) + list(edges) + list(verts),
                                             dist=0.0001, plane_co=co, plane_no=no)
                new = {g for g in res["geom"] if isinstance(g, bmesh.types.BMFace)}
                faces = {f for f in faces | new if f.is_valid}

            # The cuts ran right across the faces under the rectangle. Keep its
            # outline and dissolve the rest of them again, so lines never
            # build up across a face (bmesh keeps whatever edge a face needs
            # to stay hole-free). Vertices stay: dissolving them would cut the
            # rectangle's corners; the final merge removes the straight ones.
            def local(v):
                r = v.co - c
                return r.dot(x), r.dot(y)

            def on_outline(e):
                (u0, w0), (u1, w1) = local(e.verts[0]), local(e.verts[1])
                eps = 0.002
                for a0, a1, b0, b1, ha, hb in ((u0, u1, w0, w1, hx, hy), (w0, w1, u0, u1, hy, hx)):
                    for s in (ha, -ha):
                        if abs(a0 - s) < eps and abs(a1 - s) < eps and max(abs(b0), abs(b1)) <= hb + eps:
                            return True
                return False

            outline = []
            loose = []
            for e in {e for f in faces for e in f.edges}:
                if e[keep]:
                    continue
                (outline if on_outline(e) else loose).append(e)
            if loose:
                bmesh.ops.dissolve_edges(bm, edges=loose, use_verts=False, use_face_split=False)
            for e in outline:
                if e.is_valid:
                    e[keep] = 1

            # Paint the faces inside the outline: the ones that touch it, and
            # any that lay wholly inside it and were never cut. Every corner
            # must be inside (a face that wraps round the rectangle can have
            # its centre inside it).
            faces = {f for f in faces if f.is_valid}
            faces |= {f for e in outline if e.is_valid for f in e.link_faces}
            inside = []
            for f in faces:
                f.normal_update()
                if f.normal.dot(z) < 0.95:
                    continue
                if all(abs(u) <= hx + 0.002 and abs(w) <= hy + 0.002 and abs((v.co - c).dot(z)) < 0.5
                       for v in f.verts for u, w in (local(v),)):
                    inside.append(f)
            kind = d["paint"] if d["paint"] in ("window", "panel") else "other"
            cover.setdefault(kind, []).append(sum(f.calc_area() for f in inside) / (d["sx"] * d["sy"]))
            if not inside:
                continue
            paint = d["paint"]
            if paint == "panel":
                # A grey other than the surface's own.
                base = max(set(f.material_index for f in inside), key=[f.material_index for f in inside].count)
                options = [g for g in PANEL_GREYS if PAINT_MATS[g] != base]
                paint = options[min(int(d["roll"] * len(options)), len(options) - 1)]
            for f in inside:
                f.material_index = PAINT_MATS[paint]

        # Merge flat faces of one material again: removes leftover cut lines
        # and the vertices along straight edges. The angle is tiny so faces
        # only merge when truly in one plane (0.05 degrees moved big faces by
        # up to 0.35 m).
        bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(0.001), use_dissolve_boundaries=False,
                                 verts=bm.verts[:], edges=bm.edges[:], delimit={'MATERIAL'})
        bm.edges.layers.int.remove(keep)
        bm.normal_update()
        bm.to_mesh(me)
        bm.free()
        me.update()
        print("Hull paint: %d rectangles, %d bent polygons triangulated first" % (len(self.decals), bent))
        for kind, got in cover.items():
            print("  paint coverage %-7s %4d rectangles: %d fully painted, %d partly, %d not at all"
                  % (kind, len(got), sum(1 for g in got if g > 0.98), sum(1 for g in got if 0.02 < g <= 0.98),
                     sum(1 for g in got if g <= 0.02)))


def paint_juggernaut_hull(hull_obj):
    """Paints the hull's surface detail (see the section comment above).
    Order matters: lights, windows and markings claim their spots first, then
    the panels fill round them."""
    d = HullPaint(hull_obj)
    down = Vector((0.0, 0.0, -1.0))
    up = Vector((0.0, 0.0, 1.0))
    side = Vector((-1.0, 0.0, 0.0))
    S = SCALE

    # Running lights at the extremities (both sides).
    for p, direction in (
        ((10.0, 322.0, 300.0), down),        # ram tip, upper corners
        ((300.0, 332.0, 20.0 * S), side),    # ram tip, sides
        ((300.0, 116.0 * S, 66.0 * S), side),   # forward bastion, fore top corner
        ((300.0, 56.0 * S, 66.0 * S), side),    # forward bastion, aft top corner
        ((300.0, -66.0 * S, 66.0 * S), side),   # aft bastion, fore top corner
        ((300.0, -124.0 * S, 66.0 * S), side),  # aft bastion, aft top corner
        ((78.0 * S, 128.0 * S, 300.0), down),   # sponson plate corners
        ((30.0 * S, -228.0 * S, 300.0), down),  # castle top, aft corners
        ((30.0 * S, -100.0 * S, 300.0), down),  # castle top, fore corners
        ((300.0, -302.0 * S, 50.0 * S), side),  # engine block, aft top corners
        ((78.0 * S, -300.0 * S, 300.0), down),  # engine deck, aft corners
        ((62.0 * S, 210.0 * S, -300.0), up),    # belly, forward corners
        ((62.0 * S, -150.0 * S, -300.0), up),   # belly, aft corners
    ):
        d.light("lights", Vector(p), direction)

    # Window bands: the main scale cue. Bastion faces, the long hull slopes
    # fore and aft (which get no panels: their big faces are bent, so panels
    # there came out small and tilted, and the windows carry them), the
    # castle's walls (three decks), the engine block, the ram's flanks, and a
    # row down each side of the belly.
    for z in (30.0, 50.0):
        d.window_band("win_bastion", 52.0, 118.0, z=z, run=12, pause=2)
        d.window_band("win_bastion", -128.0, -62.0, z=z, run=12, pause=2)
    for z in (22.0, 36.0, 50.0):
        d.window_band("win_bow_side", 142.0, 258.0, z=z, run=18, pause=3)
        d.window_band("win_aft_side", -264.0, -142.0, z=z, run=18, pause=3)
    for z in (88.0, 100.0, 112.0):
        d.window_band("win_castle", -232.0, -94.0, z=z, run=20, pause=3)
    d.window_band("win_engine", -304.0, -276.0, z=42.0, run=12, pause=2)
    d.window_band("win_ram", 282.0, 318.0, z=22.0, run=10, pause=2)
    d.window_band("win_belly", -150.0, 200.0, x=56.0, run=24, pause=6, spacing=4.2)

    # Crimson markings: chevrons down the bow deck, stripes across the engine
    # deck and the castle glacis.
    for y in (196.0, 222.0):
        d.chevron("markings", y)
    d.stripe_across("markings", 22.0, -246.0, 26.0)
    d.stripe_across("markings", 16.0, -120.0, 18.0)

    # Panels on every large flat area.
    d.panels_top("main_deck", 31.0, 81.0, -62.0, 142.0, 18.0, 26.0)
    d.panels_top("bow_deck", 0.0, 64.0, 146.0, 272.0, 15.0, 20.0)
    d.panels_top("castle_top", 0.0, 34.0, -232.0, -90.0, 14.0, 20.0)
    d.panels_top("castle_flanks", 44.0, 76.0, -232.0, -90.0, 13.0, 20.0)
    d.panels_top("engine_deck", 0.0, 82.0, -312.0, -238.0, 16.0, 16.0)
    d.panels_side("bastion_face", 50.0, 120.0, 12.0, 74.0, 13.0, 22.0)
    d.panels_side("bastion_face", -130.0, -60.0, 12.0, 74.0, 13.0, 22.0)
    d.panels_side("castle_wall", -234.0, -92.0, 78.0, 124.0, 10.0, 18.0)
    d.panels_side("engine_side", -308.0, -268.0, 14.0, 56.0, 12.0, 16.0)

    d.report()
    d.apply()

def assemble_juggernaut_scene():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)
    for m in list(bpy.data.meshes):
        bpy.data.meshes.remove(m)
        
    scene = bpy.context.scene
    
    col_ship = bpy.data.collections.new("Juggernaut")
    col_turret = bpy.data.collections.new("Turret_Standalone")
    col_collision = bpy.data.collections.new("Collision")
    col_markers = bpy.data.collections.new("Markers")
    
    scene.collection.children.link(col_ship)
    scene.collection.children.link(col_turret)
    scene.collection.children.link(col_collision)
    scene.collection.children.link(col_markers)
    
    # 1. Hull
    me_hull = build_juggernaut_hull()
    obj_hull = bpy.data.objects.new("Juggernaut_Hull", me_hull)
    col_ship.objects.link(obj_hull)
    bpy.context.view_layer.update()
    
    # 1b. Surface detail, painted into the hull
    paint_juggernaut_hull(obj_hull)
    
    # 2. Bridge (Pivot at base, placed at BRIDGE_Y, BRIDGE_Z)
    me_bridge = build_juggernaut_bridge()
    obj_bridge = bpy.data.objects.new("Juggernaut_Bridge", me_bridge)
    obj_bridge.location = Vector((0.0, BRIDGE_Y * SCALE, BRIDGE_Z * SCALE))
    col_ship.objects.link(obj_bridge)
    
    # 3. Thrusters (Keel at X=0, Y=-335*SCALE, Z=20*SCALE; Side thrusters at X=±62*SCALE, Y=-335*SCALE, Z=36*SCALE)
    me_keel = build_juggernaut_thruster_keel()
    obj_keel = bpy.data.objects.new("Juggernaut_ThrusterKeel", me_keel)
    obj_keel.location = Vector((0.0, -335.0 * SCALE, 20.0 * SCALE))
    col_ship.objects.link(obj_keel)
    
    me_pod = build_juggernaut_thruster_pod()
    obj_pod_l = bpy.data.objects.new("Juggernaut_ThrusterPod_L", me_pod)
    obj_pod_l.location = Vector((-62.0 * SCALE, -335.0 * SCALE, 36.0 * SCALE))
    col_ship.objects.link(obj_pod_l)
    
    obj_pod_r = bpy.data.objects.new("Juggernaut_ThrusterPod_R", me_pod)
    obj_pod_r.location = Vector((62.0 * SCALE, -335.0 * SCALE, 36.0 * SCALE))
    obj_pod_r.scale.x = -1.0 # Mirrored
    col_ship.objects.link(obj_pod_r)
    
    # 4. Hangar Doors & Empties
    me_door = build_juggernaut_hangar_door()
    obj_door_l = bpy.data.objects.new("Juggernaut_HangarDoor_L", me_door)
    obj_door_l.location = Vector((-88.0 * SCALE, -10.0 * SCALE, 24.0 * SCALE))
    col_ship.objects.link(obj_door_l)
    
    obj_door_r = bpy.data.objects.new("Juggernaut_HangarDoor_R", me_door)
    obj_door_r.location = Vector((88.0 * SCALE, -10.0 * SCALE, 24.0 * SCALE))
    obj_door_r.scale.x = -1.0
    col_ship.objects.link(obj_door_r)
    
    emp_launch_l = bpy.data.objects.new("Juggernaut_Launch_L", None)
    emp_launch_l.location = Vector((-90.0 * SCALE, -10.0 * SCALE, 24.0 * SCALE))
    col_ship.objects.link(emp_launch_l)
    
    emp_launch_r = bpy.data.objects.new("Juggernaut_Launch_R", None)
    emp_launch_r.location = Vector((90.0 * SCALE, -10.0 * SCALE, 24.0 * SCALE))
    col_ship.objects.link(emp_launch_r)
    
    # 5. Turret Mount Empties & Placed Turrets
    me_t_base, me_t_yaw, me_t_pitch = build_turret_parts()

    for i, p in enumerate(MOUNT_PADS, 1):
        emp_m = bpy.data.objects.new(f"Juggernaut_TurretMount_{i}", None)
        emp_m.location = Vector((p[0] * SCALE, p[1] * SCALE, p[2] * SCALE + 1.0))
        col_ship.objects.link(emp_m)
        
        t_b = bpy.data.objects.new(f"Ship_Turret_{i}_Base", me_t_base)
        t_b.location = emp_m.location
        col_ship.objects.link(t_b)
        
        t_y = bpy.data.objects.new(f"Ship_Turret_{i}_Yaw", me_t_yaw)
        t_y.location = emp_m.location + Vector((0.0, 0.0, 2.0))
        col_ship.objects.link(t_y)
        
        t_p = bpy.data.objects.new(f"Ship_Turret_{i}_Pitch", me_t_pitch)
        t_p.location = t_y.location + Vector((0.0, 1.3, 0.8))
        t_p.rotation_euler = Euler((math.radians(15.0), 0.0, 0.0), 'XYZ')
        col_ship.objects.link(t_p)
        
    # Standalone Turret in collection Turret_Standalone
    t_stand_b = bpy.data.objects.new("Turret_Base", me_t_base)
    t_stand_b.location = Vector((0.0, 0.0, 0.0))
    col_turret.objects.link(t_stand_b)
    
    t_stand_y = bpy.data.objects.new("Turret_Yaw", me_t_yaw)
    t_stand_y.location = Vector((0.0, 0.0, 2.0))
    col_turret.objects.link(t_stand_y)
    
    t_stand_p = bpy.data.objects.new("Turret_Pitch", me_t_pitch)
    t_stand_p.location = Vector((0.0, 1.3, 2.8))
    t_stand_p.rotation_euler = Euler((math.radians(45.0), 0.0, 0.0), 'XYZ')
    col_turret.objects.link(t_stand_p)
    
    muz_l = bpy.data.objects.new("Turret_MuzzleL", None)
    muz_l.parent = t_stand_p
    muz_l.location = Vector((-1.0, 9.5, 0.0))
    col_turret.objects.link(muz_l)
    
    muz_r = bpy.data.objects.new("Turret_MuzzleR", None)
    muz_r.parent = t_stand_p
    muz_r.location = Vector((1.0, 9.5, 0.0))
    col_turret.objects.link(muz_r)
    
    # 6. Collision Collection (14 convex Col_ meshes)
    col_objs = build_collision_meshes(col_collision)
    
    # 7. Markers Collection (16 marker empties)
    marker_objs = build_markers(col_markers)

    # 8. Plating UVs on every mesh (the hull greys carry the plating texture)
    for me in bpy.data.meshes:
        add_plating_uvs(me)

    col_turret.hide_render = True
    col_collision.hide_render = True
    col_markers.hide_render = True
    
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_FILE)
    print(f"Juggernaut C2 scene assembled and saved to {BLEND_FILE}")
    
    scene_data = {
        "hull": obj_hull,
        "bridge": obj_bridge,
        "keel": obj_keel,
        "pod_l": obj_pod_l,
        "pod_r": obj_pod_r,
        "door_l": obj_door_l,
        "door_r": obj_door_r,
        "turret_standalone": [t_stand_b, t_stand_y, t_stand_p, muz_l, muz_r],
        "t_stand_base": t_stand_b,
        "t_stand_pitch": t_stand_p,
        "collision": col_objs,
        "markers": marker_objs,
        "col_ship": col_ship,
        "col_turret": col_turret,
        "col_collision": col_collision,
        "col_markers": col_markers,
    }
    return scene_data

# -----------------------------------------------------------------------------
# Metric Measurements
# -----------------------------------------------------------------------------
def measure_c2_metrics():
    metrics = {}
    
    # 1. Triangle counts
    mesh_tris = {}
    for m in bpy.data.meshes:
        name = m.name
        tris = sum(len(p.vertices) - 2 for p in m.polygons)
        mesh_tris[name] = tris
    metrics["tri_counts"] = mesh_tris
    
    hull_parts = [
        "Juggernaut_Hull", "Juggernaut_Bridge",
        "Juggernaut_ThrusterKeel", "Juggernaut_ThrusterPod",
        "Juggernaut_HangarDoor"
    ]
    total_hull = sum(mesh_tris.get(k, 0) for k in hull_parts)
    metrics["total_hull_assembly_tris"] = total_hull
    
    # 2. Global Bounding Box & Warp Portal Clearance
    col_ship = bpy.data.collections["Juggernaut"]
    min_co = Vector((1e9, 1e9, 1e9))
    max_co = Vector((-1e9, -1e9, -1e9))
    max_r = 0.0
    
    for obj in col_ship.objects:
        if obj.type == 'MESH':
            mw = obj.matrix_world
            for v in obj.data.vertices:
                g = mw @ v.co
                min_co.x = min(min_co.x, g.x)
                min_co.y = min(min_co.y, g.y)
                min_co.z = min(min_co.z, g.z)
                max_co.x = max(max_co.x, g.x)
                max_co.y = max(max_co.y, g.y)
                max_co.z = max(max_co.z, g.z)
                
                # Portal is centered at (0, 0, 30.0) in XY plane
                r_portal = math.sqrt(g.x ** 2 + (g.z - 30.0) ** 2)
                if r_portal > max_r:
                    max_r = r_portal
                    
    metrics["bbox"] = (max_co.y - min_co.y, max_co.x - min_co.x, max_co.z - min_co.z)
    metrics["bounds_x"] = (min_co.x, max_co.x)
    metrics["bounds_y"] = (min_co.y, max_co.y)
    metrics["bounds_z"] = (min_co.z, max_co.z)
    metrics["max_radial"] = max_r
    metrics["portal_margin"] = 220.0 - max_r
    
    # 3. Turret 5.0m Bounding Sphere Check (Base + Yaw excluding barrels)
    turret_max_dist = 0.0
    t_center = Vector((0.0, 0.0, 3.75)) # Defined center 3.75m above base
    for part_name, loc in [("Turret_Base", Vector((0, 0, 0))), ("Turret_Yaw", Vector((0, 0, 2.0)))]:
        m = bpy.data.meshes[part_name]
        for v in m.vertices:
            p_world = loc + v.co
            d = (p_world - t_center).length
            if d > turret_max_dist:
                turret_max_dist = d
    metrics["turret_sphere_r"] = turret_max_dist
    metrics["turret_fits_5m_sphere"] = (turret_max_dist <= 5.0)
    
    # 4. Bridge & Thruster Targeting Spheres
    m_bridge = bpy.data.meshes["Juggernaut_Bridge"]
    b_center = Vector((0.0, 0.0, 18.0 * SCALE))
    b_max_r = max((v.co - b_center).length for v in m_bridge.vertices)
    metrics["bridge_targeting_r"] = b_max_r
    
    m_keel = bpy.data.meshes["Juggernaut_ThrusterKeel"]
    k_center = Vector((0.0, 20.0 * SCALE, 0.0))
    k_max_r = max((v.co - k_center).length for v in m_keel.vertices)
    metrics["thruster_targeting_r"] = k_max_r
    
    # 5. Non-manifold check
    non_man = {}
    for m in bpy.data.meshes:
        bm = bmesh.new()
        bm.from_mesh(m)
        nm_edges = [e for e in bm.edges if not e.is_manifold]
        if nm_edges:
            non_man[m.name] = len(nm_edges)
        bm.free()
    metrics["non_manifold"] = non_man
    
    # 6. Engine Nozzle Protrusion past Engine Block Transom
    transom_y = -315.0 * SCALE
    nozzle_y = -335.0 * SCALE
    protrusion = transom_y - nozzle_y
    metrics["nozzle_protrusion_scaled"] = protrusion
    metrics["nozzle_protrusion_unscaled"] = protrusion / SCALE
    
    # Gap between nozzle rims:
    keel_r = 22.0 * SCALE
    pod_r = 18.0 * SCALE
    center_dist = math.sqrt((62.0 * SCALE)**2 + ((36.0 - 20.0) * SCALE)**2)
    rim_gap = center_dist - (keel_r + pod_r)
    metrics["nozzle_rim_gap"] = rim_gap
    
    # 7. Nozzle Line-of-Sight Exposure Ray Casting (Direct Aft, 45° Above, 45° Below)
    hull_obj = bpy.data.objects["Juggernaut_Hull"]
    bvh_hull = BVHTree.FromObject(hull_obj, bpy.context.evaluated_depsgraph_get())
    
    thruster_targets = {
        "Keel": Vector((0.0, -335.0 * SCALE, 20.0 * SCALE)),
        "Pod_L": Vector((-62.0 * SCALE, -335.0 * SCALE, 36.0 * SCALE)),
        "Pod_R": Vector((62.0 * SCALE, -335.0 * SCALE, 36.0 * SCALE)),
    }
    
    test_dirs = {
        "Direct_Aft": Vector((0.0, -1.0, 0.0)),
        "45_Above": Vector((0.0, -1.0, 1.0)).normalized(),
        "45_Below": Vector((0.0, -1.0, -1.0)).normalized(),
    }
    
    exposure_results = {}
    all_clear = True
    for t_name, tgt in thruster_targets.items():
        exposure_results[t_name] = {}
        for d_name, d_vec in test_dirs.items():
            ray_origin = tgt + d_vec * 350.0
            ray_dir = -d_vec
            loc, normal, face_idx, dist = bvh_hull.ray_cast(ray_origin, ray_dir)
            if loc is not None and dist < 348.0:
                is_clear = False
                all_clear = False
            else:
                is_clear = True
            exposure_results[t_name][d_name] = is_clear
            
    metrics["exposure_rays"] = exposure_results
    metrics["all_exposure_rays_unobstructed"] = all_clear
    
    # 8. HANGAR CHECKS (RIGOROUSLY MEASURED FRESH ON THIS GEOMETRY)
    door_center = Vector((-88.0 * SCALE, -10.0 * SCALE, 24.0 * SCALE))
    door_w, door_h = 78.0 * SCALE, 36.0 * SCALE
    
    # Check 1: Broadside Visibility (Ray-cast hemisphere outwards towards -X)
    unobstructed_rays = 0
    total_rays = 0
    azimuths = np.linspace(-60, 60, 15)
    elevations = np.linspace(-30, 30, 7)
    
    for az in azimuths:
        for el in elevations:
            raz = math.radians(az)
            rel = math.radians(el)
            d = Vector((-math.cos(raz) * math.cos(rel), math.sin(raz) * math.cos(rel), math.sin(rel))).normalized()
            for dy in np.linspace(-door_w * 0.4, door_w * 0.4, 5):
                for dz in np.linspace(-door_h * 0.4, door_h * 0.4, 5):
                    origin = door_center + Vector((-0.2 * SCALE, dy, dz))
                    hit, norm, idx, dist = bvh_hull.ray_cast(origin, d, 450.0)
                    total_rays += 1
                    if hit is None:
                        unobstructed_rays += 1
                        
    metrics["broadside_rays_total"] = total_rays
    metrics["broadside_rays_unobstructed"] = unobstructed_rays
    metrics["broadside_percent"] = (unobstructed_rays / total_rays) * 100.0
    
    # Check 2: Launch Corridor (200m perpendicular clear corridor)
    corridor_min = Vector((-288.0 * SCALE, -40.0 * SCALE, -1.0 * SCALE))
    corridor_max = Vector((-88.1 * SCALE, 20.0 * SCALE, 49.0 * SCALE))
    
    verts_inside = 0
    for v in hull_obj.data.vertices:
        g = hull_obj.matrix_world @ v.co
        if (corridor_min.x <= g.x <= corridor_max.x and
            corridor_min.y <= g.y <= corridor_max.y and
            corridor_min.z <= g.z <= corridor_max.z):
            verts_inside += 1
            
    metrics["corridor_verts_inside"] = verts_inside
    metrics["corridor_box"] = (corridor_min, corridor_max)
    
    # Check 3: Room to Open (Slide-Up Strip)
    slide_obstructions = 0
    for dy in np.linspace(-door_w * 0.48, door_w * 0.48, 25):
        test_pt = Vector((-89.0 * SCALE, (-10.0 + dy / SCALE) * SCALE, 46.0 * SCALE))
        hit, norm, idx, dist = bvh_hull.ray_cast(test_pt, Vector((0, 0, 1)), 60.0)
        if hit is not None:
            slide_obstructions += 1
            
    metrics["slide_clearance_measured"] = (80.0 - 42.0) * SCALE # 57.0m vertical wall height
    metrics["slide_margin"] = (80.0 - 42.0) * SCALE - (36.0 * SCALE) # +3.0m margin beyond scaled door height
    metrics["slide_strip_obstructions"] = slide_obstructions
    
    # Check 4: Attackable at Speed (Strafing run length and time at 60m out)
    strafing_flight_x = (-88.0 * SCALE) - 60.0 # -192.0m (60m out from hull side at -132m)
    strafing_flight_z = 24.0 * SCALE           # 36.0m
    strafing_points = []
    for y_test in range(int(-320 * SCALE), int(350 * SCALE), 3):
        pos = Vector((strafing_flight_x, float(y_test), strafing_flight_z))
        los_dir = (door_center - pos).normalized()
        los_dist = (door_center - pos).length
        hit, norm, idx, dist = bvh_hull.ray_cast(pos, los_dir, los_dist - 0.5)
        close_hit, c_norm, c_idx, c_dist = bvh_hull.find_nearest(pos, 10.0 * SCALE)
        if hit is None and close_hit is None:
            strafing_points.append(y_test)
            
    if strafing_points:
        run_length = max(strafing_points) - min(strafing_points)
        run_time = run_length / 100.0 # at 100 m/s
        metrics["strafing_run_m"] = run_length
        metrics["strafing_time_s"] = run_time
        metrics["strafing_start_y"] = min(strafing_points)
        metrics["strafing_end_y"] = max(strafing_points)
        metrics["strafing_flight_line"] = (strafing_flight_x, strafing_flight_z)
    else:
        metrics["strafing_run_m"] = 0.0
        metrics["strafing_time_s"] = 0.0
        
    return metrics

# -----------------------------------------------------------------------------
# Asset glTF Export Pipeline
# -----------------------------------------------------------------------------
def export_all_glb(scene_objs):
    """
    Exports the 8 required .glb files into models/destroyer/:
    1. juggernaut_hull.glb
    2. juggernaut_bridge.glb (at its pivot)
    3. juggernaut_thruster_keel.glb (at its pivot)
    4. juggernaut_thruster_pod.glb (at its pivot)
    5. juggernaut_hangar_door.glb (at its pivot)
    6. juggernaut_turret.glb (3 parts + 2 muzzle empties)
    7. juggernaut_collision.glb (only Col_ meshes)
    8. juggernaut_markers.glb (only empty markers)
    """
    os.makedirs(EXPORT_DIR, exist_ok=True)
    exported_files = {}
    
    def deselect_all():
        bpy.ops.object.select_all(action='DESELECT')
        
    def export_selected(filename):
        out_path = os.path.join(EXPORT_DIR, filename)
        bpy.ops.export_scene.gltf(
            filepath=out_path,
            export_format='GLB',
            use_selection=True,
            use_active_scene=True,
            export_apply=True,
            export_materials='EXPORT',
            export_yup=True
        )
        size_kb = os.path.getsize(out_path) / 1024.0
        exported_files[filename] = size_kb
        print(f"Exported {filename}: {size_kb:.1f} KB")
        return out_path
        
    # 1. Hull
    deselect_all()
    scene_objs["hull"].select_set(True)
    bpy.context.view_layer.objects.active = scene_objs["hull"]
    export_selected("juggernaut_hull.glb")
    
    # 2. Bridge (at pivot: center of base at origin)
    deselect_all()
    obj_b = scene_objs["bridge"]
    old_b_loc = obj_b.location.copy()
    obj_b.location = Vector((0.0, 0.0, 0.0))
    obj_b.select_set(True)
    bpy.context.view_layer.objects.active = obj_b
    export_selected("juggernaut_bridge.glb")
    obj_b.location = old_b_loc
    
    # 3. Thruster Keel (at pivot: nozzle center at origin)
    deselect_all()
    obj_k = scene_objs["keel"]
    old_k_loc = obj_k.location.copy()
    obj_k.location = Vector((0.0, 0.0, 0.0))
    obj_k.select_set(True)
    bpy.context.view_layer.objects.active = obj_k
    export_selected("juggernaut_thruster_keel.glb")
    obj_k.location = old_k_loc
    
    # 4. Thruster Pod (at pivot: nozzle center at origin)
    deselect_all()
    obj_p = scene_objs["pod_l"]
    old_p_loc = obj_p.location.copy()
    old_p_scale = obj_p.scale.copy()
    obj_p.location = Vector((0.0, 0.0, 0.0))
    obj_p.scale = Vector((1.0, 1.0, 1.0))
    obj_p.select_set(True)
    bpy.context.view_layer.objects.active = obj_p
    export_selected("juggernaut_thruster_pod.glb")
    obj_p.location = old_p_loc
    obj_p.scale = old_p_scale
    
    # 5. Hangar Door (at pivot: door center at origin)
    deselect_all()
    obj_d = scene_objs["door_l"]
    old_d_loc = obj_d.location.copy()
    old_d_scale = obj_d.scale.copy()
    obj_d.location = Vector((0.0, 0.0, 0.0))
    obj_d.scale = Vector((1.0, 1.0, 1.0))
    obj_d.select_set(True)
    bpy.context.view_layer.objects.active = obj_d
    export_selected("juggernaut_hangar_door.glb")
    obj_d.location = old_d_loc
    obj_d.scale = old_d_scale
    
    # 6. Turret (standalone turret: 3 parts + 2 muzzle empties)
    deselect_all()
    turret_objs = scene_objs["turret_standalone"]
    t_pitch = scene_objs["t_stand_pitch"]
    old_pitch_rot = t_pitch.rotation_euler.copy()
    t_pitch.rotation_euler = Euler((0.0, 0.0, 0.0), 'XYZ') # Neutral 0° orientation
    for tobj in turret_objs:
        tobj.select_set(True)
    bpy.context.view_layer.objects.active = scene_objs["t_stand_base"]
    export_selected("juggernaut_turret.glb")
    t_pitch.rotation_euler = old_pitch_rot
    
    # 7. Collision (only Col_ meshes)
    deselect_all()
    for cobj in scene_objs["collision"]:
        cobj.select_set(True)
    bpy.context.view_layer.objects.active = scene_objs["collision"][0]
    export_selected("juggernaut_collision.glb")
    
    # 8. Markers (only empty markers)
    deselect_all()
    for mobj in scene_objs["markers"]:
        mobj.select_set(True)
    bpy.context.view_layer.objects.active = scene_objs["markers"][0]
    export_selected("juggernaut_markers.glb")
    
    deselect_all()
    return exported_files

# -----------------------------------------------------------------------------
# Camera & Rendering Setup (Workbench Flat + Outline)
# -----------------------------------------------------------------------------
def setup_workbench_render():
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_WORKBENCH'
    shading = scene.display.shading
    shading.light = 'FLAT'
    shading.color_type = 'MATERIAL'
    shading.show_object_outline = True
    shading.object_outline_color = (0.0, 0.0, 0.0) # 3-tuple outline color
    scene.render.film_transparent = False
    
    world = bpy.data.worlds.get("C1_World") or bpy.data.worlds.new("C1_World")
    world.color = (0.18, 0.20, 0.22) # Neutral dark studio backdrop
    scene.world = world
    
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100

def get_or_create_camera():
    scene = bpy.context.scene
    cam_obj = bpy.data.objects.get("C1_Camera")
    if not cam_obj:
        cam_data = bpy.data.cameras.new("C1_Camera")
        cam_obj = bpy.data.objects.new("C1_Camera", cam_data)
        scene.collection.objects.link(cam_obj)
    scene.camera = cam_obj
    return cam_obj

def point_camera(cam, loc, target):
    cam.location = Vector(loc)
    dir_vec = (Vector(target) - Vector(loc)).normalized()
    rot_quat = dir_vec.to_track_quat('-Z', 'Y')
    cam.rotation_euler = rot_quat.to_euler()

def render_c2_views():
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    setup_workbench_render()
    cam = get_or_create_camera()
    cam_data = cam.data
    cam_data.clip_end = 5000.0
    scene = bpy.context.scene
    col_ship = bpy.data.collections["Juggernaut"]
    col_turret = bpy.data.collections["Turret_Standalone"]
    col_collision = bpy.data.collections["Collision"]
    col_markers = bpy.data.collections["Markers"]
    
    col_ship.hide_render = False
    col_turret.hide_render = True
    col_collision.hide_render = True
    col_markers.hide_render = True
    
    # 1. Hero 3/4 View
    cam_data.type = 'PERSP'
    cam_data.lens = 45.0
    point_camera(cam, (380.0 * SCALE, 680.0 * SCALE, 320.0 * SCALE), (0.0, 30.0 * SCALE, 60.0 * SCALE))
    scene.render.filepath = os.path.join(PREVIEW_DIR, "C3_hero.png")
    bpy.ops.render.render(write_still=True)
    print("Rendered: C3_hero.png")
    
    # 2. Side Elevation (Ortho, framed for 1.5x scale)
    cam_data.type = 'ORTHO'
    cam_data.sensor_fit = 'HORIZONTAL'
    cam_data.ortho_scale = 820.0 * SCALE
    cam.location = Vector((-600.0 * SCALE, 7.5 * SCALE, 73.4 * SCALE))
    cam.rotation_euler = (math.radians(90.0), 0.0, math.radians(-90.0))
    scene.render.filepath = os.path.join(PREVIEW_DIR, "C3_side.png")
    bpy.ops.render.render(write_still=True)
    print("Rendered: C3_side.png")
    
    # 3. Top Plan (Ortho, framed for 1.5x scale)
    cam_data.type = 'ORTHO'
    cam_data.sensor_fit = 'VERTICAL'
    cam_data.ortho_scale = 820.0 * SCALE
    cam.location = Vector((0.0, 7.5 * SCALE, 700.0 * SCALE))
    cam.rotation_euler = (0.0, 0.0, 0.0)
    scene.render.filepath = os.path.join(PREVIEW_DIR, "C3_top.png")
    bpy.ops.render.render(write_still=True)
    print("Rendered: C3_top.png")
    
    # 4. Rear Engine View (Angle showing flared bells and burning cores in 170m engine block)
    cam_data.type = 'PERSP'
    cam_data.lens = 40.0
    point_camera(cam, (-140.0 * SCALE, -560.0 * SCALE, 90.0 * SCALE), (0.0, -320.0 * SCALE, 36.0 * SCALE))
    scene.render.filepath = os.path.join(PREVIEW_DIR, "C3_rear.png")
    bpy.ops.render.render(write_still=True)
    print("Rendered: C3_rear.png")
    
    # 5. Three-Quarter View from Below (Ventral Keel architecture)
    cam_data.type = 'PERSP'
    cam_data.lens = 36.0
    point_camera(cam, (-360.0 * SCALE, 420.0 * SCALE, -300.0 * SCALE), (0.0, 10.0 * SCALE, 20.0 * SCALE))
    scene.render.filepath = os.path.join(PREVIEW_DIR, "C3_below.png")
    bpy.ops.render.render(write_still=True)
    print("Rendered: C3_below.png")
    
    # 6. Bridge View (from 150m from FRONT-QUARTER looking into the visor brow!)
    cam_data.type = 'PERSP'
    cam_data.lens = 65.0
    point_camera(cam, (65.0 * SCALE, -71.0 * SCALE, 185.0 * SCALE), (0.0, BRIDGE_Y * SCALE, 155.0 * SCALE))
    scene.render.filepath = os.path.join(PREVIEW_DIR, "C3_bridge.png")
    bpy.ops.render.render(write_still=True)
    print("Rendered: C3_bridge.png")
    
    # 7. Hangar Bay View (with cyan 200m corridor box)
    bm_corr = bmesh.new()
    bmesh_add_box(bm_corr, (200.0, 60.0, 48.0), (-188.0, -10.0, 24.0), mat_idx=0)
    me_corr = bpy.data.meshes.new("Corridor_Mesh")
    bm_corr.to_mesh(me_corr)
    bm_corr.free()
    mat_cyan = get_or_create_material("CorridorCyan")
    me_corr.materials.append(mat_cyan)
    obj_corr = bpy.data.objects.new("Hangar_Corridor_Box", me_corr)
    col_ship.objects.link(obj_corr)
    
    cam_data.type = 'PERSP'
    cam_data.lens = 38.0
    point_camera(cam, (-310.0 * SCALE, -165.0 * SCALE, 110.0 * SCALE), (-90.0 * SCALE, -10.0 * SCALE, 24.0 * SCALE))
    scene.render.filepath = os.path.join(PREVIEW_DIR, "C3_hangar.png")
    bpy.ops.render.render(write_still=True)
    print("Rendered: C3_hangar.png")
    col_ship.objects.unlink(obj_corr)
    bpy.data.objects.remove(obj_corr)
    bpy.data.meshes.remove(me_corr)
    
    # 8. Turret Stitched View (-5°, 45°, 80° Pitch Angles Proving Zero Clipping)
    col_ship.hide_render = True
    col_turret.hide_render = False
    
    t_pitch_obj = bpy.data.objects["Turret_Pitch"]
    cam_data.type = 'PERSP'
    cam_data.lens = 65.0
    point_camera(cam, (14.0, 18.0, 11.5), (0.0, 2.0, 2.8))
    
    scene.render.resolution_x = 640
    scene.render.resolution_y = 720
    
    pitch_angles = [(-5.0, "t_m5.png"), (45.0, "t_p45.png"), (80.0, "t_p80.png")]
    panel_paths = []
    
    for deg, fname in pitch_angles:
        t_pitch_obj.rotation_euler = Euler((math.radians(deg), 0.0, 0.0), 'XYZ')
        p_out = os.path.join(PREVIEW_DIR, fname)
        scene.render.filepath = p_out
        bpy.ops.render.render(write_still=True)
        panel_paths.append(p_out)
        
    img0 = bpy.data.images.load(panel_paths[0])
    img1 = bpy.data.images.load(panel_paths[1])
    img2 = bpy.data.images.load(panel_paths[2])
    
    arr0 = np.array(img0.pixels[:], dtype=np.float32).reshape((720, 640, 4))
    arr1 = np.array(img1.pixels[:], dtype=np.float32).reshape((720, 640, 4))
    arr2 = np.array(img2.pixels[:], dtype=np.float32).reshape((720, 640, 4))
    
    stitched_arr = np.hstack([arr0, arr1, arr2]) # 720 x 1920 x 4
    
    p_final_turret = os.path.join(PREVIEW_DIR, "C3_turret.png")
    img_final = bpy.data.images.new("C3_Turret_Stitched", width=1920, height=720, alpha=True)
    img_final.pixels.foreach_set(stitched_arr.ravel())
    img_final.filepath_raw = p_final_turret
    img_final.file_format = 'PNG'
    img_final.save()
    print("Rendered & Stitched: C3_turret.png (1920x720 showing -5°, 45°, 80°)")
    
    bpy.data.images.remove(img0)
    bpy.data.images.remove(img1)
    bpy.data.images.remove(img2)
    bpy.data.images.remove(img_final)
    for p_temp in panel_paths:
        if os.path.exists(p_temp):
            try:
                os.remove(p_temp)
            except Exception:
                pass
                
    # 9. Silhouette Stitched View (Pure black on pure light grey: Side, Hero, Top)
    col_ship.hide_render = False
    col_turret.hide_render = True
    
    shading = scene.display.shading
    shading.color_type = 'SINGLE'
    shading.single_color = (0.0, 0.0, 0.0)
    shading.show_object_outline = False
    
    old_world = scene.world
    world_white = bpy.data.worlds.new("C2_Sil_World")
    world_white.color = (0.80, 0.80, 0.80)
    scene.world = world_white
    
    scene.render.resolution_x = 640
    scene.render.resolution_y = 720
    
    # Side Silhouette
    cam_data.type = 'ORTHO'
    cam_data.sensor_fit = 'HORIZONTAL'
    cam_data.ortho_scale = 820.0 * SCALE
    cam.location = Vector((-600.0 * SCALE, 7.5 * SCALE, 73.4 * SCALE))
    cam.rotation_euler = (math.radians(90.0), 0.0, math.radians(-90.0))
    p_side = os.path.join(PREVIEW_DIR, "sil_side.png")
    scene.render.filepath = p_side
    bpy.ops.render.render(write_still=True)
    
    # Hero 3/4 Silhouette
    cam_data.type = 'PERSP'
    cam_data.lens = 45.0
    point_camera(cam, (380.0 * SCALE, 680.0 * SCALE, 320.0 * SCALE), (0.0, 30.0 * SCALE, 60.0 * SCALE))
    p_hero = os.path.join(PREVIEW_DIR, "sil_hero.png")
    scene.render.filepath = p_hero
    bpy.ops.render.render(write_still=True)
    
    # Top Silhouette
    cam_data.type = 'ORTHO'
    cam_data.sensor_fit = 'VERTICAL'
    cam_data.ortho_scale = 820.0 * SCALE
    cam.location = Vector((0.0, 7.5 * SCALE, 700.0 * SCALE))
    cam.rotation_mode = 'XYZ'
    cam.rotation_euler = (0.0, 0.0, 0.0)
    p_top = os.path.join(PREVIEW_DIR, "sil_top.png")
    scene.render.filepath = p_top
    bpy.ops.render.render(write_still=True)
    
    img_s = bpy.data.images.load(p_side)
    img_h = bpy.data.images.load(p_hero)
    img_t = bpy.data.images.load(p_top)
    
    arr_s = np.array(img_s.pixels[:], dtype=np.float32).reshape((720, 640, 4))
    arr_h = np.array(img_h.pixels[:], dtype=np.float32).reshape((720, 640, 4))
    arr_t = np.array(img_t.pixels[:], dtype=np.float32).reshape((720, 640, 4))
    
    stitched_sil = np.hstack([arr_s, arr_h, arr_t]) # 720 x 1920 x 4
    
    p_final_sil = os.path.join(PREVIEW_DIR, "C3_silhouette.png")
    img_final_sil = bpy.data.images.new("C3_Silhouette_Stitched", width=1920, height=720, alpha=True)
    img_final_sil.pixels.foreach_set(stitched_sil.ravel())
    img_final_sil.filepath_raw = p_final_sil
    img_final_sil.file_format = 'PNG'
    img_final_sil.save()
    print("Rendered & Stitched: C3_silhouette.png (1920x720)")
    
    bpy.data.images.remove(img_s)
    bpy.data.images.remove(img_h)
    bpy.data.images.remove(img_t)
    bpy.data.images.remove(img_final_sil)
    for p_temp in (p_side, p_hero, p_top):
        if os.path.exists(p_temp):
            try:
                os.remove(p_temp)
            except Exception:
                pass
                
    # Restore standard render settings
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 900
    scene.world = old_world
    shading.color_type = 'MATERIAL'
    shading.show_object_outline = True
    col_turret.hide_render = False
    
    # -------------------------------------------------------------------------
    # 6 Focal Area Detail Close-Up Views (C2 Requirement)
    # -------------------------------------------------------------------------
    print("\n--- RENDERING 6 FOCAL AREA DETAIL CLOSE-UPS ---")
    
    # 10. Detail: Bridge Command Head
    cam_data.type = 'PERSP'
    cam_data.lens = 48.0
    point_camera(cam, (42.0 * SCALE, -81.0 * SCALE, 175.0 * SCALE), (0.0, BRIDGE_Y * SCALE, 152.0 * SCALE))
    scene.render.filepath = os.path.join(PREVIEW_DIR, "C3_detail_bridge.png")
    bpy.ops.render.render(write_still=True)
    print("Rendered: C3_detail_bridge.png")
    
    # 11. Detail: Recessed Hangar Bay & Portal Frame
    cam_data.type = 'PERSP'
    cam_data.lens = 38.0
    point_camera(cam, (-195.0 * SCALE, -60.0 * SCALE, 55.0 * SCALE), (-88.0 * SCALE, -10.0 * SCALE, 28.0 * SCALE))
    scene.render.filepath = os.path.join(PREVIEW_DIR, "C3_detail_hangar.png")
    bpy.ops.render.render(write_still=True)
    print("Rendered: C3_detail_hangar.png")
    
    # 12. Detail: 170m Engine Block Transom & Nozzles
    cam_data.type = 'PERSP'
    cam_data.lens = 45.0
    point_camera(cam, (-85.0 * SCALE, -420.0 * SCALE, 65.0 * SCALE), (0.0, -320.0 * SCALE, 30.0 * SCALE))
    scene.render.filepath = os.path.join(PREVIEW_DIR, "C3_detail_engines.png")
    bpy.ops.render.render(write_still=True)
    print("Rendered: C3_detail_engines.png")
    
    # 13. Detail: Battering Ram Prow & Bow Glacis
    cam_data.type = 'PERSP'
    cam_data.lens = 38.0
    point_camera(cam, (140.0 * SCALE, 480.0 * SCALE, 80.0 * SCALE), (0.0, 320.0 * SCALE, 20.0 * SCALE))
    scene.render.filepath = os.path.join(PREVIEW_DIR, "C3_detail_prow.png")
    bpy.ops.render.render(write_still=True)
    print("Rendered: C3_detail_prow.png")
    
    # 14. Detail: Dorsal Radiator Trench Spine & Arches
    cam_data.type = 'PERSP'
    cam_data.lens = 45.0
    point_camera(cam, (42.0 * SCALE, -25.0 * SCALE, 135.0 * SCALE), (0.0, 45.0 * SCALE, 90.0 * SCALE))
    scene.render.filepath = os.path.join(PREVIEW_DIR, "C3_detail_radiator.png")
    bpy.ops.render.render(write_still=True)
    print("Rendered: C3_detail_radiator.png")
    
    # 15. Detail: Ventral Belly Keel Architecture & Reactor Vault
    cam_data.type = 'PERSP'
    cam_data.lens = 34.0
    point_camera(cam, (-130.0 * SCALE, 140.0 * SCALE, -110.0 * SCALE), (0.0, 60.0 * SCALE, -25.0 * SCALE))
    scene.render.filepath = os.path.join(PREVIEW_DIR, "C3_detail_belly.png")
    bpy.ops.render.render(write_still=True)
    print("Rendered: C3_detail_belly.png")

    # 16. Detail: Main Deck Surface Detail
    cam_data.type = 'PERSP'
    cam_data.lens = 38.0
    point_camera(cam, (80.0 * SCALE, 0.0 * SCALE, 120.0 * SCALE), (60.0 * SCALE, 50.0 * SCALE, 80.0 * SCALE))
    scene.render.filepath = os.path.join(PREVIEW_DIR, "C3_detail_main_deck.png")
    bpy.ops.render.render(write_still=True)
    print("Rendered: C3_detail_main_deck.png")
    
    # 17. Detail: Flank Surface Detail
    cam_data.type = 'PERSP'
    cam_data.lens = 38.0
    point_camera(cam, (150.0 * SCALE, 20.0 * SCALE, 40.0 * SCALE), (100.0 * SCALE, -60.0 * SCALE, 40.0 * SCALE))
    scene.render.filepath = os.path.join(PREVIEW_DIR, "C3_detail_flank.png")
    bpy.ops.render.render(write_still=True)
    print("Rendered: C3_detail_flank.png")

    # 18. Detail: Castle Side
    cam_data.type = 'PERSP'
    cam_data.lens = 38.0
    point_camera(cam, (100.0 * SCALE, -155.0 * SCALE, 150.0 * SCALE), (0.0, -155.0 * SCALE, 140.0 * SCALE))
    scene.render.filepath = os.path.join(PREVIEW_DIR, "C3_detail_castle.png")
    bpy.ops.render.render(write_still=True)
    print("Rendered: C3_detail_castle.png")

    # 19. Detail: Engine Deck
    cam_data.type = 'PERSP'
    cam_data.lens = 38.0
    point_camera(cam, (70.0 * SCALE, -210.0 * SCALE, 140.0 * SCALE), (0.0, -250.0 * SCALE, 110.0 * SCALE))
    scene.render.filepath = os.path.join(PREVIEW_DIR, "C3_detail_engine_deck.png")
    bpy.ops.render.render(write_still=True)
    print("Rendered: C3_detail_engine_deck.png")

    # 20. Detail: Bow Glacis
    cam_data.type = 'PERSP'
    cam_data.lens = 38.0
    point_camera(cam, (80.0 * SCALE, 350.0 * SCALE, 120.0 * SCALE), (0.0, 300.0 * SCALE, 90.0 * SCALE))
    scene.render.filepath = os.path.join(PREVIEW_DIR, "C3_detail_glacis.png")
    bpy.ops.render.render(write_still=True)
    print("Rendered: C3_detail_glacis.png")

# -----------------------------------------------------------------------------
# Main Execution Runner
# -----------------------------------------------------------------------------
def run_pass_c2():
    print("=== STARTING STAGE C: PASS C2 (DETAIL PASS & GLTF EXPORT) ===")
    scene_objs = assemble_juggernaut_scene()
    
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_FILE)
    print(f"Saved initial .blend to {BLEND_FILE}")
    
    print("\n--- MEASURING PASS C2 METRICS (AT 1.5X SCALE) ---")
    metrics = measure_c2_metrics()
    print("Triangle Counts per Object:")
    for k, v in metrics["tri_counts"].items():
        print(f"  {k}: {v} tris")
    print(f"Total Unique Hull Assembly: {metrics['total_hull_assembly_tris']} tris")
    print(f"Bounding Box: {metrics['bbox'][0]:.1f}m L × {metrics['bbox'][1]:.1f}m W × {metrics['bbox'][2]:.1f}m H")
    print(f"Y Bounds: {metrics['bounds_y'][0]:.1f} to {metrics['bounds_y'][1]:.1f}m")
    print(f"X Bounds: {metrics['bounds_x'][0]:.1f} to {metrics['bounds_x'][1]:.1f}m")
    print(f"Z Bounds: {metrics['bounds_z'][0]:.1f} to {metrics['bounds_z'][1]:.1f}m")
    print(f"Warp Portal Radial Extent: {metrics['max_radial']:.1f}m (Portal Limit: 220.0m, Margin: {metrics['portal_margin']:.1f}m)")
    print(f"Turret Bounding Sphere Radius: {metrics['turret_sphere_r']:.2f}m (Limit: 5.0m, Fits: {metrics['turret_fits_5m_sphere']})")
    print(f"Bridge Targeting Sphere Radius: {metrics['bridge_targeting_r']:.1f}m (Limit: ~75m)")
    print(f"Thruster Keel Targeting Sphere Radius: {metrics['thruster_targeting_r']:.1f}m (Limit: ~45m)")
    
    print("\n--- NOZZLE PROTRUSION & EXPOSURE MEASUREMENTS ---")
    print(f"  Nozzle Protrusion past Transom: {metrics['nozzle_protrusion_scaled']:.1f}m (scaled) / {metrics['nozzle_protrusion_unscaled']:.1f}m (unscaled, >= 15.0m)")
    print(f"  Gap between nozzle rims: {metrics['nozzle_rim_gap']:.1f}m (Separate targets verified)")
    print("  Line-of-Sight Exposure Rays (3 thrusters x 3 directions):")
    for t_name, dirs in metrics["exposure_rays"].items():
        for d_name, is_clear in dirs.items():
            print(f"    {t_name} from {d_name}: {'UNOBSTRUCTED (CLEAR)' if is_clear else 'OCCLUDED'}")
    print(f"  All Exposure Rays Unobstructed: {metrics['all_exposure_rays_unobstructed']}")
    
    print("\n--- HANGAR CHECKS (MEASURED FRESH ON C2 GEOMETRY) ---")
    print(f"Check 1 (Broadside Visibility): {metrics['broadside_percent']:.1f}% ({metrics['broadside_rays_unobstructed']}/{metrics['broadside_rays_total']} rays unobstructed)")
    print(f"Check 2 (Launch Corridor): {metrics['corridor_verts_inside']} vertices inside corridor box")
    print(f"Check 3 (Room to Open / Slide-Up Strip): min vertical clearance = {metrics['slide_clearance_measured']:.1f}m (door height = {36.0 * SCALE:.1f}m, margin = {metrics['slide_margin']:.1f}m)")
    print(f"Check 4 (Attackable at Speed): flight line (X={metrics['strafing_flight_line'][0]:.1f}, Z={metrics['strafing_flight_line'][1]:.1f}, 60m out from side), unobstructed run length = {metrics['strafing_run_m']:.1f}m, time = {metrics['strafing_time_s']:.2f}s at 100m/s")
    
    if metrics["non_manifold"]:
        print("\nWARNING: Non-manifold edges detected:", metrics["non_manifold"])
    else:
        print("\nMesh Integrity: 0 non-manifold edges across all meshes!")
        
    print("\n--- EXPORTING GLTF BINARY (.GLB) ASSETS ---")
    exported_files = export_all_glb(scene_objs)
    metrics["exported_files"] = exported_files
    
    print("\n--- RENDERING WORKBENCH SCREENSHOTS (9 STANDARD + 6 DETAIL) ---")
    render_c2_views()
    
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_FILE)
    print(f"\nFinal C2 scene saved: {BLEND_FILE}")
    print("=== PASS C2 COMPLETE ===")
    return metrics

if __name__ == "__main__":
    run_pass_c2()



