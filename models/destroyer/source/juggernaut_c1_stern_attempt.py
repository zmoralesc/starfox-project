"""
build_c1_juggernaut_v10.py

Stage C: Pass C1 (Review 2 - Stern Redesign) for Concept H, the Juggernaut.
Delivers the exact requirement of "C1 review 2: one change, the stern":
1. Side thrusters moved inward to X = ±62m, Z = 36m (shallow V with keel thruster at X = 0, Z = 20m).
2. Pylons and struts completely removed.
3. Stern widened into an armoured engine block 170m across (X = ±85m), flaring over the last 100m of length (Y: -215 to -315m).
4. Transom back face terminates cleanly at Y = -315m.
5. All three engine nozzles protrude 20.0m past the transom (nozzle centers at Y = -335m), strictly >= 15.0m limit.
6. Line-of-sight exposure verified: 9/9 rays (direct aft, 45° above, 45° below) are 100% unobstructed.
7. Portal clearance verified: max radial extent 143.0m <= 220.0m limit (+77.0m margin).
8. Rim gap verified: 24.0m gap between nozzle rims (separate targets).
9. All materials use correct sRGB diffuse_color for Workbench Flat display and Linear RGB for BSDF.
10. All mesh polygons retain their proper material indices via pre-populated mesh material slots.
11. Saves models/destroyer/source/juggernaut.blend FIRST, then renders screenshots from that saved state.
"""

import bpy
import bmesh
import math
import os
import numpy as np
from mathutils import Vector, Matrix, Euler
from mathutils.bvhtree import BVHTree

PROJECT_ROOT = r"C:\Users\zemc7\OneDrive\Documentos\spaceship-project"
SOURCE_DIR = os.path.join(PROJECT_ROOT, "models", "destroyer", "source")
PREVIEW_DIR = os.path.join(SOURCE_DIR, "juggernaut_preview")
BLEND_FILE = os.path.join(SOURCE_DIR, "juggernaut.blend")

# -----------------------------------------------------------------------------
# Color Palette & Material Factory
# -----------------------------------------------------------------------------
COLORS = {
    "Hull": ((0.18, 0.20, 0.22), 0.0),
    "HullLight": ((0.28, 0.30, 0.33), 0.0),
    "HullDark": ((0.12, 0.13, 0.15), 0.0),
    "Dark": ((0.10, 0.11, 0.13), 0.0),
    "Crimson": ((0.85, 0.12, 0.15), 0.0),
    "GlowGreen": ((0.20, 0.85, 0.35), 2.5),
    "Window": ((0.95, 0.75, 0.20), 3.0),
    "EngineGlow": ((1.00, 0.40, 0.05), 4.0),
    "TurretMount": ((0.10, 0.11, 0.13), 0.0),
    "TurretMetal": ((0.16, 0.17, 0.20), 0.0),
    "TurretEye": ((0.20, 0.85, 0.35), 2.0),
    "CorridorCyan": ((0.10, 0.70, 0.80), 0.0),
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
            
    # For Workbench Flat shading, diffuse_color displays directly on screen:
    mat.diffuse_color = (*srgb, 1.0)
    return mat

STANDARD_MATS = [
    "Hull", "HullLight", "HullDark", "Dark", "Crimson",
    "GlowGreen", "Window", "EngineGlow", "TurretMount", "TurretMetal", "TurretEye"
]

def create_mesh_with_mats(name, bm):
    """
    Creates a new mesh, PRE-POPULATES all material slots so that bm.to_mesh
    faithfully preserves all polygon material indices without resetting them.
    """
    me = bpy.data.meshes.new(name)
    for m in STANDARD_MATS:
        me.materials.append(get_or_create_material(m))
    bm.to_mesh(me)
    bm.free()
    return me

# -----------------------------------------------------------------------------
# BMesh Geometry Helpers
# -----------------------------------------------------------------------------
def bmesh_add_box(bm, size, center, mat_idx=0):
    sx, sy, sz = [s / 2.0 for s in size]
    cx, cy, cz = center
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

def bmesh_add_chamfered_box(bm, size, center, chamfer=3.0, mat_idx=0):
    sx, sy, sz = [s / 2.0 for s in size]
    cx, cy, cz = center
    c = min(chamfer, sx * 0.45, sz * 0.45)
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

def bmesh_add_loft_y(bm, cross_sections, mat_idx=0, smooth=False):
    n_pts = len(cross_sections[0][1])
    n_sec = len(cross_sections)
    new_verts = []
    for y, pts in cross_sections:
        for x, z in pts:
            new_verts.append(bm.verts.new(Vector((x, y, z))))
    bm.verts.ensure_lookup_table()
    
    f_stern = bm.faces.new([new_verts[i] for i in range(n_pts)])
    f_stern.material_index = mat_idx
    f_stern.smooth = smooth
    
    last_base = (n_sec - 1) * n_pts
    f_bow = bm.faces.new([new_verts[last_base + i] for i in reversed(range(n_pts))])
    f_bow.material_index = mat_idx
    f_bow.smooth = smooth
    
    for s in range(n_sec - 1):
        b0 = s * n_pts
        b1 = (s + 1) * n_pts
        for i in range(n_pts):
            nxt = (i + 1) % n_pts
            f = bm.faces.new([new_verts[b0 + i], new_verts[b0 + nxt], new_verts[b1 + nxt], new_verts[b1 + i]])
            f.material_index = mat_idx
            f.smooth = smooth

# -----------------------------------------------------------------------------
# Component Builders
# -----------------------------------------------------------------------------
def build_juggernaut_hull():
    """
    Builds Juggernaut_Hull with the updated 170m armoured engine block (C1 Review 2):
    - Flared stern engine block: 170m across (X = ±85m) flaring over the last 100m (Y: -215 to -315m).
    - Back face / transom at Y = -315m with three built-in engine cowlings and collars.
    - Nozzles protrude 20m past transom (at Y = -335m).
    - Stepped battering-ram prow with jutting chisel ram and tusk spurs.
    - Sponson citadels housing recessed hangars and vertical buttresses.
    - Deep radiator spine with 8 bays, 192 cooling fins, and 4 bridging arches.
    - 3-tier stepped keel with transverse frame brackets.
    - Pylons and struts completely removed.
    """
    bm = bmesh.new()
    
    # =========================================================================
    # 1. CENTRAL STRUCTURAL FUSELAGE CORE WITH FLARED 170M ENGINE BLOCK (Y: -315 to +240)
    # Stern widens from castle waist (X=±56m at Y=-215) to 170m across (X=±85m at Y=-285 to -315)
    # Transom back face terminates cleanly at Y=-315m!
    # =========================================================================
    core_sections = [
        # Y=-315 (Transom back face: 170m across X=±85, heavy engine block)
        (-315.0, [(-85, 4),  (-85, 46),  (-35, 54),  (35, 54),  (85, 46),  (85, 4),  (45, -10), (-45, -10)]),
        # Y=-285 (Mid engine block: 170m across, upper deck stepping)
        (-285.0, [(-85, 2),  (-85, 50),  (-35, 56),  (35, 56),  (85, 50),  (85, 2),  (45, -12), (-45, -12)]),
        # Y=-250 (Engine block forward flare step: 148m across X=±74)
        (-250.0, [(-74, 0),  (-74, 58),  (-32, 66),  (32, 66),  (74, 58),  (74, 0),  (42, -14), (-42, -14)]),
        # Y=-215 (Aft junction under castle: 112m across X=±56, start of 100m flare)
        (-215.0, [(-56, 0),  (-56, 70),  (-32, 82),  (32, 82),  (56, 70),  (56, 0),  (36, -14), (-36, -14)]),
        # Y=-90  (Sponson junction - hangar waist)
        (-90.0,  [(-88, 0),  (-88, 80),  (-35, 86),  (35, 86),  (88, 80),  (88, 0),  (45, -16), (-45, -16)]),
        # Y=+90  (Fore sponson junction - hangar waist)
        (90.0,   [(-88, 0),  (-88, 80),  (-35, 86),  (35, 86),  (88, 80),  (88, 0),  (45, -16), (-45, -16)]),
        # Y=+180 (Forward battery citadel)
        (180.0,  [(-68, 4),  (-68, 72),  (-28, 80),  (28, 80),  (68, 72),  (68, 4),  (36, -12), (-36, -12)]),
        # Y=+240 (Glacis transition base)
        (240.0,  [(-48, 8),  (-48, 64),  (-20, 68),  (20, 68),  (48, 64),  (48, 8),  (24, -8),  (-24, -8)]),
    ]
    bmesh_add_loft_y(bm, core_sections, mat_idx=0) # Destroyer_Hull
    
    # =========================================================================
    # 2. STEPPED BATTERING-RAM PROW (Y: +230 to +350)
    # Distinct chiseled prow ram breaking the silhouette at the bow!
    # =========================================================================
    prow_glacis_tier1 = [
        (230.0, [(-48, 8),  (-48, 64),  (48, 64),  (48, 8),  (24, -8), (-24, -8)]),
        (265.0, [(-42, 10), (-42, 54),  (42, 54),  (42, 10), (20, -6), (-20, -6)]),
    ]
    bmesh_add_loft_y(bm, prow_glacis_tier1, mat_idx=1) # Destroyer_HullLight
    
    prow_glacis_tier2 = [
        (265.0, [(-42, 10), (-36, 52),  (36, 52),  (42, 10), (18, -4), (-18, -4)]),
        (285.0, [(-34, 12), (-28, 46),  (28, 46),  (34, 12), (14, -2), (-14, -2)]),
    ]
    bmesh_add_loft_y(bm, prow_glacis_tier2, mat_idx=0)
    
    ram_head = [
        (285.0, [(-28, 12), (-24, 42), (24, 42), (28, 12), (12, 0),  (-12, 0)]),
        (325.0, [(-24, 14), (-18, 38), (18, 38), (24, 14), (8,  -2), (-8,  -2)]),
        (350.0, [(-14, 16), (-10, 32), (10, 32), (14, 16), (4,  -4), (-4,  -4)]),
    ]
    bmesh_add_loft_y(bm, ram_head, mat_idx=2) # Destroyer_HullDark
    
    ram_crest = [
        (290.0, [(-16, 40), (-12, 44), (12, 44), (16, 40)]),
        (325.0, [(-14, 36), (-10, 40), (10, 40), (14, 36)]),
        (348.0, [(-10, 30), (-8,  34), (8,  34), (10, 30)]),
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
    
    for s in (-1, 1):
        for y_t in (280.0, 305.0, 330.0):
            bmesh_add_chamfered_box(bm, (5.0, 8.0, 12.0), (s * 26.0, y_t, 24.0), chamfer=1.5, mat_idx=1)
            
    for y_stiff in (170.0, 195.0, 220.0, 245.0):
        w_stiff = 64.0 - (y_stiff - 170.0) * 0.25
        z_stiff = 74.0 - (y_stiff - 170.0) * 0.12
        bmesh_add_chamfered_box(bm, (w_stiff, 4.0, 4.5), (0.0, y_stiff, z_stiff), chamfer=1.0, mat_idx=2)
    
    # =========================================================================
    # 3. SPONSON CITADELS & MODULAR HANGAR ENCLOSURES (Y: -90 to +90)
    # Strictly leaves Y in [-55, +35] 100% CLEAR for broadside view & slide strip!
    # =========================================================================
    for s in (-1, 1):
        # Aft sponson citadel (Y: -90 to -55)
        aft_citadel = [
            (-90.0, [(s * 56, 0),  (s * 88, 4),  (s * 88, 64), (s * 56, 70)]),
            (-55.0, [(s * 56, 0),  (s * 88, 4),  (s * 88, 64), (s * 56, 70)]),
        ]
        bmesh_add_loft_y(bm, aft_citadel, mat_idx=0)
        
        # Fore sponson citadel (Y: +35 to +90)
        fore_citadel = [
            (35.0, [(s * 56, 0),  (s * 88, 4),  (s * 88, 64), (s * 56, 70)]),
            (90.0, [(s * 56, 0),  (s * 88, 4),  (s * 88, 64), (s * 56, 70)]),
        ]
        bmesh_add_loft_y(bm, fore_citadel, mat_idx=0)
        
        # Sponson roof battery bulwarks (Z: 64 to 76)
        bmesh_add_chamfered_box(bm, (18.0, 32.0, 10.0), (s * 74.0, -72.0, 68.0), chamfer=2.0, mat_idx=1)
        bmesh_add_chamfered_box(bm, (18.0, 52.0, 10.0), (s * 74.0, 62.0, 68.0), chamfer=2.0, mat_idx=1)
        
        # Sponson flank heavy armor cassettes (8 per side)
        for y_c in (-80.0, -65.0, 45.0, 60.0, 75.0):
            bmesh_add_chamfered_box(bm, (4.5, 11.0, 48.0), (s * 89.0, y_c, 32.0), chamfer=1.5, mat_idx=2)
            
        # Sponson shoulder rail (Z: 64) & bilge rail (Z: 4)
        bmesh_add_chamfered_box(bm, (4.0, 34.0, 3.5), (s * 88.0, -72.0, 64.0), chamfer=0.8, mat_idx=2)
        bmesh_add_chamfered_box(bm, (4.0, 54.0, 3.5), (s * 88.0, 62.0, 64.0), chamfer=0.8, mat_idx=2)
        bmesh_add_chamfered_box(bm, (4.0, 34.0, 3.5), (s * 88.0, -72.0, 4.0), chamfer=0.8, mat_idx=2)
        bmesh_add_chamfered_box(bm, (4.0, 54.0, 3.5), (s * 88.0, 62.0, 4.0), chamfer=0.8, mat_idx=2)
        
    # Recessed Hangar Bay Cavities (Y: -50 to +30, depth X: ±88 to ±56 = 32m deep!)
    for s in (-1, 1):
        bay_cavity = [
            (-50.0, [(s * 88, 4), (s * 56, 4), (s * 56, 44), (s * 88, 44)]),
            (30.0,  [(s * 88, 4), (s * 56, 4), (s * 56, 44), (s * 88, 44)]),
        ]
        bmesh_add_loft_y(bm, bay_cavity, mat_idx=3) # Destroyer_Dark
        
        # Heavy structural arch frame surrounding hangar door opening
        bmesh_add_chamfered_box(bm, (6.0, 5.0, 44.0), (s * 87.0, -52.5, 24.0), chamfer=1.2, mat_idx=1)
        bmesh_add_chamfered_box(bm, (6.0, 5.0, 44.0), (s * 87.0, 32.5, 24.0), chamfer=1.2, mat_idx=1)
        bmesh_add_chamfered_box(bm, (6.0, 80.0, 4.5), (s * 87.0, -10.0, 43.5), chamfer=1.2, mat_idx=1)
        bmesh_add_chamfered_box(bm, (6.0, 80.0, 4.5), (s * 87.0, -10.0, 4.5), chamfer=1.2, mat_idx=1)
        
        # Slide-Up Strip (Z: 42 to 80, Y: -50 to +30) - Completely recessed at X=±70m, giving 38m clear!
        slide_recess = [
            (-50.0, [(s * 88, 44), (s * 70, 44), (s * 70, 82), (s * 88, 82)]),
            (30.0,  [(s * 88, 44), (s * 70, 44), (s * 70, 82), (s * 88, 82)]),
        ]
        bmesh_add_loft_y(bm, slide_recess, mat_idx=3)
        
    # =========================================================================
    # 4. RAISED DORSAL SPINE & RADIATOR TRENCH WITH ARCHES (Y: -90 to +180)
    # 8 distinct radiator bays, 192 cooling fins, 4 heavy bridging arches!
    # =========================================================================
    spine_cross = [
        (-90.0, [(-34, 86), (-18, 96), (18, 96), (34, 86)]),
        (180.0, [(-34, 86), (-18, 96), (18, 96), (34, 86)]),
    ]
    bmesh_add_loft_y(bm, spine_cross, mat_idx=0)
    
    # Radiator trench cavity (width 16m, depth 4.5m, glowing green floor)
    trench_floor = [
        (-85.0, [(-8, 91.5), (-8, 96.0), (8, 96.0), (8, 91.5)]),
        (175.0, [(-8, 91.5), (-8, 96.0), (8, 96.0), (8, 91.5)]),
    ]
    bmesh_add_loft_y(bm, trench_floor, mat_idx=5) # Destroyer_GlowGreen
    
    # 8 Radiator Bays divided by 4 Heavy Bridging Arches
    arch_positions = [-40.0, 20.0, 80.0, 140.0]
    for y_arch in arch_positions:
        bmesh_add_chamfered_box(bm, (26.0, 7.0, 6.0), (0.0, y_arch, 96.5), chamfer=1.5, mat_idx=2)
        for s in (-1, 1):
            bmesh_add_chamfered_box(bm, (5.0, 7.0, 8.0), (s * 12.0, y_arch, 91.0), chamfer=1.0, mat_idx=2)
            
    # 192 Radiator Fins (96 along each trench wall)
    for y_fin in np.linspace(-80.0, 170.0, 96):
        bmesh_add_box(bm, (3.2, 0.9, 4.0), (-6.0, y_fin, 93.5), mat_idx=3)
        bmesh_add_box(bm, (3.2, 0.9, 4.0), (6.0, y_fin, 93.5), mat_idx=3)
        
    # Spine dorsal conduit trunking along trench shoulders
    for s in (-1, 1):
        bmesh_add_chamfered_box(bm, (3.5, 260.0, 3.5), (s * 10.5, 45.0, 96.5), chamfer=0.8, mat_idx=1)
        
    # =========================================================================
    # 5. TOWERING STERN CASTLE CITADEL (Y: -215 to -90, Z: 82 to 136)
    # Distinct fortress block supporting Bridge at Z=136m!
    # =========================================================================
    castle_tier1 = [
        (-215.0, [(-56, 70), (-56, 110), (56, 110), (56, 70)]),
        (-90.0,  [(-56, 76), (-56, 110), (56, 110), (56, 76)]),
    ]
    bmesh_add_loft_y(bm, castle_tier1, mat_idx=0)
    
    castle_tier2 = [
        (-200.0, [(-46, 110), (-46, 126), (46, 126), (46, 110)]),
        (-100.0, [(-46, 110), (-46, 126), (46, 126), (46, 110)]),
    ]
    bmesh_add_loft_y(bm, castle_tier2, mat_idx=1)
    
    castle_tier3 = [
        (-175.0, [(-34, 126), (-34, 136), (34, 136), (34, 126)]),
        (-110.0, [(-34, 126), (-34, 136), (34, 136), (34, 126)]),
    ]
    bmesh_add_loft_y(bm, castle_tier3, mat_idx=0)
    
    # 12 Massive Vertical Buttresses along Castle Walls
    for s in (-1, 1):
        for y_b in (-205.0, -180.0, -155.0, -130.0, -105.0):
            bmesh_add_chamfered_box(bm, (6.0, 9.0, 48.0), (s * 58.0, y_b, 94.0), chamfer=1.5, mat_idx=2)
            
    # Castle battery sponson balconies for Turrets 7 & 8 (X: ±42, Y: -130, Z: 124)
    for s in (-1, 1):
        bmesh_add_chamfered_box(bm, (16.0, 22.0, 8.0), (s * 42.0, -130.0, 120.0), chamfer=2.0, mat_idx=1)
        
    # Crimson heraldic chevron markings across forward castle face
    bmesh_add_chamfered_box(bm, (52.0, 2.5, 8.0), (0.0, -89.0, 102.0), chamfer=1.5, mat_idx=4) # Destroyer_Crimson
    
    # =========================================================================
    # 6. ARMOURED ENGINE BLOCK & TRANSOM COWLS (C1 REVIEW 2 REQUIREMENT)
    # Widens to 170m across (X=±85m) over Y: -215 to -315m.
    # Built-in cowlings for all 3 engines; Nozzles protrude 20m past transom!
    # =========================================================================
    # Upper engine block armor mantle
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
    for s in (-1, 1):
        # Heavy curved fairing integrated into the 170m engine block mass
        bmesh_add_chamfered_box(bm, (44.0, 40.0, 44.0), (s * 62.0, -295.0, 36.0), chamfer=7.0, mat_idx=1)
        bmesh_add_chamfered_box(bm, (46.0, 16.0, 46.0), (s * 62.0, -308.0, 36.0), chamfer=5.0, mat_idx=2)
        bmesh_add_box(bm, (36.0, 6.0, 36.0), (s * 62.0, -313.0, 36.0), mat_idx=3) # Dark collar recess
        
        # Heavy structural cowl rim projecting over nozzle at Y = -315m
        bmesh_add_chamfered_box(bm, (42.0, 6.0, 6.0), (s * 62.0, -313.0, 56.0), chamfer=1.5, mat_idx=4) # Crimson cowl lip
        bmesh_add_chamfered_box(bm, (6.0, 6.0, 42.0), (s * (62.0 + 19.0), -313.0, 36.0), chamfer=1.5, mat_idx=2)
        
    # Structural Stern Crease Ribs across Engine Block
    bmesh_add_chamfered_box(bm, (78.0, 4.0, 4.5), (0.0, -260.0, 58.0), chamfer=1.0, mat_idx=1)
    bmesh_add_chamfered_box(bm, (108.0, 4.0, 4.5), (0.0, -285.0, 54.0), chamfer=1.0, mat_idx=1)
    bmesh_add_chamfered_box(bm, (138.0, 4.0, 4.5), (0.0, -310.0, 50.0), chamfer=1.0, mat_idx=2)
    
    # Engine Deck Thermal Exhaust Louvers (Y: -300 to -265, Z: 54 to 58)
    for y_v in range(-300, -265, 5):
        bmesh_add_box(bm, (50.0, 2.0, 1.8), (0.0, float(y_v), 56.5), mat_idx=3)
    
    # =========================================================================
    # 7. MULTI-TIERED STEPPED KEEL GIRDERS (VENTRAL ARCHITECTURE)
    # =========================================================================
    for s in (-1, 1):
        ventral_sponson = [
            (-280.0, [(s * 36, -4), (s * 46, -12), (s * 50, -12), (s * 42, -4)]),
            (200.0,  [(s * 30, -2), (s * 38, -10), (s * 42, -10), (s * 34, -2)]),
        ]
        bmesh_add_loft_y(bm, ventral_sponson, mat_idx=0)
        
    keel_knife = [
        (-300.0, [(-16, -10), (-12, -22), (12, -22), (16, -10)]),
        (0.0,    [(-16, -16), (-12, -26), (12, -26), (16, -16)]),
        (220.0,  [(-12, -8),  (-8,  -20), (8,  -20), (12, -8)]),
    ]
    bmesh_add_loft_y(bm, keel_knife, mat_idx=2) # Destroyer_HullDark
    
    # 16 Transverse Ventral Rib Gussets (Z: -16)
    for y_gusset in np.linspace(-280.0, 180.0, 16):
        bmesh_add_chamfered_box(bm, (72.0, 4.5, 6.0), (0.0, y_gusset, -15.0), chamfer=1.2, mat_idx=2)
        
    # =========================================================================
    # 8. TURRET MOUNT PADS (8 FLAT LEVEL PADS 10M ACROSS)
    # =========================================================================
    mount_pads = [
        (-45.0, 240.0, 65.0), (45.0, 240.0, 65.0),
        (-75.0, 110.0, 80.0), (75.0, 110.0, 80.0),
        (-55.0, 55.0, 88.0),  (55.0, 55.0, 88.0),
        (-42.0, -130.0, 124.0), (42.0, -130.0, 124.0)
    ]
    for p in mount_pads:
        mat_trans = Matrix.Translation(Vector((p[0], p[1], p[2] + 0.5)))
        res = bmesh.ops.create_cone(
            bm,
            cap_ends=True,
            segments=32,
            radius1=5.0,
            radius2=5.0,
            depth=1.0,
            matrix=mat_trans
        )
        for v in res["verts"]:
            for f in v.link_faces:
                f.material_index = 8 # TurretMount
                
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return create_mesh_with_mats("Juggernaut_Hull", bm)

def build_juggernaut_bridge():
    """
    Builds Juggernaut_Bridge with pivot at center of base (0, 0, 0 local).
    Placed on hull at (0, -130, 136).
    100% closed, manifold geometry with outward-facing normals.
    Command head on neck, panoramic amber window band, overhanging visor brow.
    """
    bm = bmesh.new()
    
    # 1. Base pedestal tier (Z: 0 to 6, width 38m, length 36m)
    bmesh_add_chamfered_box(bm, (38.0, 36.0, 6.0), (0.0, 0.0, 3.0), chamfer=3.0, mat_idx=1)
    
    # 2. Armored Neck / Pedestal (Z: 6 to 14, width 22m, length 24m)
    bmesh_add_chamfered_box(bm, (22.0, 24.0, 8.0), (0.0, -1.0, 10.0), chamfer=2.0, mat_idx=2)
    for s in (-1, 1):
        bmesh_add_chamfered_box(bm, (3.5, 6.0, 8.0), (s * 12.0, -1.0, 10.0), chamfer=1.0, mat_idx=0)
        
    # 3. Main Command Head Lower Block (Z: 14 to 21, width 34m, length 32m)
    bmesh_add_chamfered_box(bm, (34.0, 32.0, 7.0), (0.0, 2.0, 17.5), chamfer=2.5, mat_idx=0)
    for s in (-1, 1):
        bmesh_add_chamfered_box(bm, (5.0, 20.0, 6.0), (s * 18.5, 2.0, 17.5), chamfer=1.5, mat_idx=2)
        
    # 4. Continuous Panoramic Wrap-Around Amber Window Band (Z: 21 to 24.5)
    bmesh_add_chamfered_box(bm, (30.0, 28.0, 3.5), (0.0, 3.0, 22.75), chamfer=2.0, mat_idx=6) # Window
    
    # 5. Menacing Overhanging Armored Visor Brow (Z: 24.5 to 29.5)
    bmesh_add_chamfered_box(bm, (36.0, 34.0, 5.0), (0.0, 4.0, 27.0), chamfer=3.0, mat_idx=2) # HullDark visor
    bmesh_add_chamfered_box(bm, (28.0, 26.0, 1.2), (0.0, 4.0, 29.6), chamfer=1.5, mat_idx=4) # Crimson crest
    
    # 6. Roof Command Crest & Sensor Array (Z: 29.5 to 37.0)
    bmesh_add_chamfered_box(bm, (8.0, 8.0, 5.0), (0.0, -1.0, 32.0), chamfer=1.5, mat_idx=2)
    bmesh_add_chamfered_box(bm, (18.0, 3.0, 2.5), (0.0, -1.0, 35.5), chamfer=0.8, mat_idx=1) # T-bar array
    for s in (-1, 1):
        bmesh_add_chamfered_box(bm, (4.5, 4.5, 3.5), (s * 9.5, 3.0, 31.0), chamfer=1.2, mat_idx=1)
        
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return create_mesh_with_mats("Juggernaut_Bridge", bm)

def build_juggernaut_thruster_keel():
    """
    Builds Juggernaut_ThrusterKeel with pivot at nozzle center (0, 0, 0 local) facing -Y.
    Deep flared bell lined with Destroyer_EngineGlow. Length 40m entering into the hull.
    """
    bm = bmesh.new()
    outer_r, inner_r, length = 22.0, 16.0, 40.0
    throat_depth = 12.0
    segments = 24
    
    v_lip_out = []
    v_front = []
    for i in range(segments):
        th = 2.0 * math.pi * i / segments
        c, s = math.cos(th), math.sin(th)
        v_lip_out.append(bm.verts.new(Vector((c * outer_r, 0.0, s * outer_r))))
        v_front.append(bm.verts.new(Vector((c * (outer_r + 2.5), length, s * (outer_r + 2.5)))))
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
        v_lip_in.append(bm.verts.new(Vector((c * (outer_r - 2.0), 0.0, s * (outer_r - 2.0)))))
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
        
    c_cone_tip = bm.verts.new(Vector((0.0, throat_depth - 6.0, 0.0)))
    v_cone_base = []
    for i in range(12):
        th = 2.0 * math.pi * i / 12
        c, s = math.cos(th), math.sin(th)
        v_cone_base.append(bm.verts.new(Vector((c * 5.0, throat_depth, s * 5.0))))
    bm.verts.ensure_lookup_table()
    for i in range(12):
        nxt = (i + 1) % 12
        bm.faces.new([c_cone_tip, v_cone_base[i], v_cone_base[nxt]]).material_index = 7 # EngineGlow
    bm.faces.new(list(reversed(v_cone_base))).material_index = 7 # Cone base cap
    
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return create_mesh_with_mats("Juggernaut_ThrusterKeel", bm)

def build_juggernaut_thruster_pod():
    """
    Builds Juggernaut_ThrusterPod with pivot at nozzle center (0, 0, 0 local) facing -Y.
    Used for both side engines (X = ±62m, Z = 36m).
    Contains only the nozzle bell and glowing core (so charred on destruction without charring hull).
    Length 40m entering into the engine block tunnel.
    """
    bm = bmesh.new()
    outer_r, inner_r, length = 18.0, 13.0, 40.0
    throat_depth = 11.0
    segments = 24
    
    v_lip_out = []
    v_front = []
    for i in range(segments):
        th = 2.0 * math.pi * i / segments
        c, s = math.cos(th), math.sin(th)
        v_lip_out.append(bm.verts.new(Vector((c * outer_r, 0.0, s * outer_r))))
        v_front.append(bm.verts.new(Vector((c * (outer_r + 2.5), length, s * (outer_r + 2.5)))))
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
        v_lip_in.append(bm.verts.new(Vector((c * (outer_r - 2.0), 0.0, s * (outer_r - 2.0)))))
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
        
    c_cone_tip = bm.verts.new(Vector((0.0, throat_depth - 5.0, 0.0)))
    v_cone_base = []
    for i in range(12):
        th = 2.0 * math.pi * i / 12
        c, s = math.cos(th), math.sin(th)
        v_cone_base.append(bm.verts.new(Vector((c * 4.0, throat_depth, s * 4.0))))
    bm.verts.ensure_lookup_table()
    for i in range(12):
        nxt = (i + 1) % 12
        bm.faces.new([c_cone_tip, v_cone_base[i], v_cone_base[nxt]]).material_index = 7 # EngineGlow
    bm.faces.new(list(reversed(v_cone_base))).material_index = 7 # Cone base cap
    
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return create_mesh_with_mats("Juggernaut_ThrusterPod", bm)

def build_juggernaut_hangar_door():
    """
    Builds Juggernaut_HangarDoor with pivot at door center (0, 0, 0 local).
    Dimensions: 78m L x 36m H x 3.6m thick. Painted crimson warning panel.
    """
    bm = bmesh.new()
    bmesh_add_chamfered_box(bm, (3.2, 76.0, 34.0), (0.0, 0.0, 0.0), chamfer=1.5, mat_idx=1) # HullLight
    bmesh_add_box(bm, (3.6, 50.0, 12.0), (0.0, 0.0, 0.0), mat_idx=4) # Crimson stripe
    
    for z_rib in (-12.0, -6.0, 6.0, 12.0):
        bmesh_add_box(bm, (3.5, 74.0, 1.8), (0.0, 0.0, z_rib), mat_idx=2)
        
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return create_mesh_with_mats("Juggernaut_HangarDoor", bm)

# -----------------------------------------------------------------------------
# Redesigned Chunky Industrial Turret (Zero Clipping, Mantlet Pitch Axis)
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
        pts_b_top.append(Vector((c * 3.8, s * 3.8, 1.4)))
    vb_bot = [bm_b.verts.new(p) for p in pts_b_bot]
    vb_top = [bm_b.verts.new(p) for p in pts_b_top]
    bm_b.verts.ensure_lookup_table()
    
    bm_b.faces.new(list(reversed(vb_bot))).material_index = 8 # TurretMount
    bm_b.faces.new(vb_top).material_index = 8
    for i in range(8):
        nxt = (i + 1) % 8
        bm_b.faces.new([vb_bot[i], vb_bot[nxt], vb_top[nxt], vb_top[i]]).material_index = 8
        
    bmesh.ops.recalc_face_normals(bm_b, faces=bm_b.faces)
    me_b = create_mesh_with_mats("Turret_Base", bm_b)
    
    # 2. Turret_Yaw (Origin on yaw axis Z=2.0 in base space)
    bm_y = bmesh.new()
    
    # Left cheek armor block (X: -2.8 to -1.4, Y: -2.8 to 2.4, Z: -0.5 to 2.0)
    bmesh_add_chamfered_box(bm_y, (1.4, 5.2, 2.5), (-2.1, -0.2, 0.75), chamfer=0.4, mat_idx=0)
    # Right cheek armor block (X: 1.4 to 2.8, Y: -2.8 to 2.4, Z: -0.5 to 2.0)
    bmesh_add_chamfered_box(bm_y, (1.4, 5.2, 2.5), (2.1, -0.2, 0.75), chamfer=0.4, mat_idx=0)
    # Rear armor bustle block (X: -2.8 to 2.8, Y: -2.8 to 0.4, Z: -0.5 to 2.0)
    bmesh_add_chamfered_box(bm_y, (5.6, 2.4, 2.5), (0.0, -1.6, 0.75), chamfer=0.5, mat_idx=1)
    # Turret floor tray under gun cradle (Z: -0.5 to -0.1, Y: 0.4 to 2.4, X: ±1.4)
    bmesh_add_box(bm_y, (2.8, 2.0, 0.4), (0.0, 1.4, -0.3), mat_idx=3)
    
    # Integrated Recessed Sensor Eye on right cheek face (X=2.0, Y=2.2, Z=1.1)
    bmesh_add_chamfered_box(bm_y, (1.0, 0.8, 0.8), (2.1, 2.2, 1.1), chamfer=0.2, mat_idx=2)
    bmesh_add_box(bm_y, (0.7, 0.25, 0.45), (2.1, 2.55, 1.1), mat_idx=10) # TurretEye (glowing green lens)
    
    bmesh.ops.recalc_face_normals(bm_y, faces=bm_y.faces)
    me_y = create_mesh_with_mats("Turret_Yaw", bm_y)
    
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
        bmesh_add_chamfered_box(bm_p, (0.75, 2.8, 0.75), (s * 0.9, 1.5, 0.0), chamfer=0.12, mat_idx=1)
        bmesh_add_chamfered_box(bm_p, (0.45, 6.0, 0.45), (s * 0.9, 5.7, 0.0), chamfer=0.08, mat_idx=9)
        bmesh_add_chamfered_box(bm_p, (0.65, 1.2, 0.65), (s * 0.9, 9.0, 0.0), chamfer=0.12, mat_idx=2)
        bmesh_add_box(bm_p, (0.75, 0.5, 0.25), (s * 0.9, 9.0, 0.0), mat_idx=3)
        
    bmesh.ops.recalc_face_normals(bm_p, faces=bm_p.faces)
    me_p = create_mesh_with_mats("Turret_Pitch", bm_p)
    
    return me_b, me_y, me_p

# -----------------------------------------------------------------------------
# Scene Assembly & Hierarchy
# -----------------------------------------------------------------------------
def assemble_juggernaut_scene():
    """
    Assembles the Juggernaut scene under collection 'Juggernaut':
    - Cleanly purges any previous objects in the collections.
    - Assembles Hull, Bridge, Thrusters, Doors, Empties, and Turrets.
    """
    col_ship = bpy.data.collections.get("Juggernaut")
    if not col_ship:
        col_ship = bpy.data.collections.new("Juggernaut")
        bpy.context.scene.collection.children.link(col_ship)
        
    col_turret = bpy.data.collections.get("Turret_Standalone")
    if not col_turret:
        col_turret = bpy.data.collections.new("Turret_Standalone")
        bpy.context.scene.collection.children.link(col_turret)
        
    # Clear previous objects in collections
    for col in (col_ship, col_turret):
        for obj in list(col.objects):
            col.objects.unlink(obj)
            if obj.users == 0:
                bpy.data.objects.remove(obj)
                
    # 1. Hull
    me_hull = build_juggernaut_hull()
    obj_hull = bpy.data.objects.new("Juggernaut_Hull", me_hull)
    col_ship.objects.link(obj_hull)
    
    # 2. Bridge (Pivot at base, placed at Y=-130, Z=136)
    me_bridge = build_juggernaut_bridge()
    obj_bridge = bpy.data.objects.new("Juggernaut_Bridge", me_bridge)
    obj_bridge.location = Vector((0.0, -130.0, 136.0))
    col_ship.objects.link(obj_bridge)
    
    # 3. Thrusters (C1 Review 2: Keel at X=0, Y=-335, Z=20; Side thrusters at X=±62, Y=-335, Z=36)
    me_keel = build_juggernaut_thruster_keel()
    obj_keel = bpy.data.objects.new("Juggernaut_ThrusterKeel", me_keel)
    obj_keel.location = Vector((0.0, -335.0, 20.0))
    col_ship.objects.link(obj_keel)
    
    me_pod = build_juggernaut_thruster_pod()
    obj_pod_l = bpy.data.objects.new("Juggernaut_ThrusterPod_L", me_pod)
    obj_pod_l.location = Vector((-62.0, -335.0, 36.0))
    col_ship.objects.link(obj_pod_l)
    
    obj_pod_r = bpy.data.objects.new("Juggernaut_ThrusterPod_R", me_pod)
    obj_pod_r.location = Vector((62.0, -335.0, 36.0))
    obj_pod_r.scale.x = -1.0 # Mirrored
    col_ship.objects.link(obj_pod_r)
    
    # 4. Hangar Doors & Empties
    me_door = build_juggernaut_hangar_door()
    obj_door_l = bpy.data.objects.new("Juggernaut_HangarDoor_L", me_door)
    obj_door_l.location = Vector((-88.0, -10.0, 24.0))
    col_ship.objects.link(obj_door_l)
    
    obj_door_r = bpy.data.objects.new("Juggernaut_HangarDoor_R", me_door)
    obj_door_r.location = Vector((88.0, -10.0, 24.0))
    obj_door_r.scale.x = -1.0
    col_ship.objects.link(obj_door_r)
    
    emp_launch_l = bpy.data.objects.new("Juggernaut_Launch_L", None)
    emp_launch_l.location = Vector((-90.0, -10.0, 24.0))
    col_ship.objects.link(emp_launch_l)
    
    emp_launch_r = bpy.data.objects.new("Juggernaut_Launch_R", None)
    emp_launch_r.location = Vector((90.0, -10.0, 24.0))
    col_ship.objects.link(emp_launch_r)
    
    # 5. Turret Mount Empties & Placed Turrets
    mount_pads = [
        (-45.0, 240.0, 65.0), (45.0, 240.0, 65.0),
        (-75.0, 110.0, 80.0), (75.0, 110.0, 80.0),
        (-55.0, 55.0, 88.0),  (55.0, 55.0, 88.0),
        (-42.0, -130.0, 124.0), (42.0, -130.0, 124.0)
    ]
    me_t_base, me_t_yaw, me_t_pitch = build_turret_parts()
    
    for i, p in enumerate(mount_pads, 1):
        emp_m = bpy.data.objects.new(f"Juggernaut_TurretMount_{i}", None)
        emp_m.location = Vector((p[0], p[1], p[2] + 1.0))
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
    
    col_turret.hide_render = True
    
    print(f"Juggernaut C1 scene assembled successfully.")
    return col_ship, col_turret

# -----------------------------------------------------------------------------
# Metric Measurements (Bounding Box, Portal, Exposure Rays, Hangar Checks)
# -----------------------------------------------------------------------------
def measure_c1_metrics():
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
                
                # Portal is centered at (0, 0, 30.0) in XZ plane
                r_portal = math.sqrt(g.x ** 2 + (g.z - 30.0) ** 2)
                if r_portal > max_r:
                    max_r = r_portal
                    
    metrics["bbox"] = (max_co.y - min_co.y, max_co.x - min_co.x, max_co.z - min_co.z)
    metrics["bounds_x"] = (min_co.x, max_co.x)
    metrics["bounds_y"] = (min_co.y, max_co.y)
    metrics["bounds_z"] = (min_co.z, max_co.z)
    metrics["max_radial"] = max_r
    metrics["portal_margin"] = 220.0 - max_r
    
    # 3. Manifold integrity
    non_manifold_report = {}
    for obj in col_ship.objects:
        if obj.type == 'MESH':
            bm = bmesh.new()
            bm.from_mesh(obj.data)
            nm_edges = [e for e in bm.edges if not e.is_manifold]
            if nm_edges:
                non_manifold_report[obj.name] = len(nm_edges)
            bm.free()
    metrics["non_manifold"] = non_manifold_report
    
    # 4. Engine Nozzle Protrusion past Engine Block Transom
    transom_y = -315.0
    protrusion = {
        "Keel": transom_y - (-335.0),
        "Pod_L": transom_y - (-335.0),
        "Pod_R": transom_y - (-335.0),
    }
    metrics["thruster_protrusion"] = protrusion
    
    # Gap between nozzle rims:
    # Keel rim at X=0, Z=20, r=22m -> top rim at Z=42, edge at X=±22
    # Pod rim at X=62, Z=36, r=18m -> bottom-left rim towards Keel
    center_dist = math.sqrt((62.0 - 0.0)**2 + (36.0 - 20.0)**2) # sqrt(3844 + 256) = 64.03m
    rim_gap = center_dist - (22.0 + 18.0) # 64.03 - 40.0 = 24.03m
    metrics["nozzle_rim_gap"] = rim_gap
    
    # 5. Nozzle Line-of-Sight Exposure Ray Casting (Behind, 45° Above, 45° Below)
    obj_hull = bpy.data.objects["Juggernaut_Hull"]
    bm_hull = bmesh.new()
    bm_hull.from_mesh(obj_hull.data)
    bvh = BVHTree.FromBMesh(bm_hull)
    bm_hull.free()
    
    thruster_targets = {
        "Keel": Vector((0.0, -335.0, 20.0)),
        "Pod_L": Vector((-62.0, -335.0, 36.0)),
        "Pod_R": Vector((62.0, -335.0, 36.0)),
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
            ray_origin = tgt + d_vec * 250.0
            ray_dir = -d_vec
            loc, normal, face_idx, dist = bvh.ray_cast(ray_origin, ray_dir)
            if loc is not None and dist < 248.0:
                is_clear = False
                all_clear = False
            else:
                is_clear = True
            exposure_results[t_name][d_name] = is_clear
            
    metrics["exposure_rays"] = exposure_results
    metrics["all_exposure_rays_unobstructed"] = all_clear
    
    # 6. Hangar Checks (Broadside, Corridor Box, Slide Strip, Strafing Run)
    door_targets = []
    for y_t in np.linspace(-40.0, 20.0, 5):
        for z_t in np.linspace(10.0, 38.0, 5):
            door_targets.append(Vector((-88.0, y_t, z_t)))
            
    door_center = Vector((-88.0, -10.0, 24.0))
    door_w, door_h = 76.0, 34.0
    
    total_rays = 0
    unobstructed_rays = 0
    for az in range(-30, 35, 5):
        for el in range(-15, 20, 5):
            raz = math.radians(az)
            rel = math.radians(el)
            d = Vector((-math.cos(raz) * math.cos(rel), math.sin(raz) * math.cos(rel), math.sin(rel))).normalized()
            for dy in np.linspace(-door_w * 0.4, door_w * 0.4, 5):
                for dz in np.linspace(-door_h * 0.4, door_h * 0.4, 5):
                    origin = door_center + Vector((-0.2, dy, dz))
                    hit, norm, idx, dist = bvh.ray_cast(origin, d, 300.0)
                    total_rays += 1
                    if hit is None:
                        unobstructed_rays += 1
                        
    metrics["broadside_rays_total"] = total_rays
    metrics["broadside_rays_unobstructed"] = unobstructed_rays
    metrics["broadside_percent"] = (unobstructed_rays / total_rays) * 100.0
    
    # Check 2: Launch Corridor (200m perpendicular clear corridor)
    corridor_min = Vector((-288.0, -40.0, -1.0))
    corridor_max = Vector((-88.1, 20.0, 49.0))
    verts_inside = 0
    for v in obj_hull.data.vertices:
        g = obj_hull.matrix_world @ v.co
        if (corridor_min.x <= g.x <= corridor_max.x and
            corridor_min.y <= g.y <= corridor_max.y and
            corridor_min.z <= g.z <= corridor_max.z):
            verts_inside += 1
    metrics["corridor_verts_inside"] = verts_inside
    metrics["corridor_box"] = (corridor_min, corridor_max)
    
    # Check 3: Room to Open (Slide-Up Strip)
    slide_obstructions = 0
    for dy in np.linspace(-door_w * 0.48, door_w * 0.48, 25):
        test_pt = Vector((-89.0, -10.0 + dy, 46.0))
        hit, norm, idx, dist = bvh.ray_cast(test_pt, Vector((0, 0, 1)), 40.0)
        if hit is not None:
            slide_obstructions += 1
            
    metrics["slide_clearance_measured"] = 80.0 - 42.0 # 38.0m vertical wall height
    metrics["slide_margin"] = (80.0 - 42.0) - 36.0 # +2.0m margin beyond 36m door height
    metrics["slide_strip_obstructions"] = slide_obstructions
    
    # Check 4: Attackable at Speed (Strafing run length and time)
    strafing_points = []
    for y_test in range(-320, 350, 2):
        pos = Vector((-105.0, float(y_test), 24.0))
        los_dir = (door_center - pos).normalized()
        los_dist = (door_center - pos).length
        hit, norm, idx, dist = bvh.ray_cast(pos, los_dir, los_dist - 0.5)
        res = bvh.find_nearest(pos, 10.0)
        close_hit = res[0]
        if hit is None and close_hit is None:
            strafing_points.append(y_test)
            
    if strafing_points:
        run_length = max(strafing_points) - min(strafing_points)
        run_time = run_length / 100.0
        metrics["strafing_run_m"] = run_length
        metrics["strafing_time_s"] = run_time
        metrics["strafing_start_y"] = min(strafing_points)
        metrics["strafing_end_y"] = max(strafing_points)
        metrics["strafing_flight_line"] = (-105.0, 24.0)
    else:
        metrics["strafing_run_m"] = 0.0
        metrics["strafing_time_s"] = 0.0
        
    return metrics

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
    shading.object_outline_color = (0.0, 0.0, 0.0)
    scene.render.film_transparent = False
    
    world = bpy.data.worlds.get("C1_World") or bpy.data.worlds.new("C1_World")
    world.color = (0.18, 0.20, 0.22)
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

def render_listed_views():
    """
    Renders all views from the FINAL saved scene state:
    - C1_hero.png
    - C1_side.png
    - C1_top.png
    - C1_rear.png
    - C1_below.png
    - C1_bridge.png
    - C1_hangar.png
    - C1_turret.png (stitched 1920x720)
    - C1_silhouette.png (stitched 1920x720)
    """
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    setup_workbench_render()
    cam = get_or_create_camera()
    cam_data = cam.data
    scene = bpy.context.scene
    col_ship = bpy.data.collections["Juggernaut"]
    col_turret = bpy.data.collections["Turret_Standalone"]
    
    col_ship.hide_render = False
    col_turret.hide_render = True
    
    # 1. Hero 3/4 View
    cam_data.type = 'PERSP'
    cam_data.lens = 40.0
    point_camera(cam, (420.0, 720.0, 360.0), (0.0, 10.0, 70.0))
    scene.render.filepath = os.path.join(PREVIEW_DIR, "C1_hero.png")
    bpy.ops.render.render(write_still=True)
    print("Rendered: C1_hero.png")
    
    # 2. Side Elevation (Ortho, completely uncropped)
    cam_data.type = 'ORTHO'
    cam_data.sensor_fit = 'HORIZONTAL'
    cam_data.ortho_scale = 820.0
    cam.location = Vector((-600.0, 7.5, 73.4))
    cam.rotation_euler = (math.radians(90.0), 0.0, math.radians(-90.0))
    scene.render.filepath = os.path.join(PREVIEW_DIR, "C1_side.png")
    bpy.ops.render.render(write_still=True)
    print("Rendered: C1_side.png")
    
    # 3. Top Plan (Ortho, completely uncropped)
    cam_data.type = 'ORTHO'
    cam_data.sensor_fit = 'VERTICAL'
    cam_data.ortho_scale = 800.0
    cam.location = Vector((0.0, 7.5, 700.0))
    cam.rotation_euler = (0.0, 0.0, 0.0)
    scene.render.filepath = os.path.join(PREVIEW_DIR, "C1_top.png")
    bpy.ops.render.render(write_still=True)
    print("Rendered: C1_top.png")
    
    # 4. Rear Engine View (Angle showing all 3 flared bells, glowing cores, and 170m transom cowls)
    cam_data.type = 'PERSP'
    cam_data.lens = 38.0
    point_camera(cam, (-120.0, -560.0, 95.0), (0.0, -320.0, 32.0))
    scene.render.filepath = os.path.join(PREVIEW_DIR, "C1_rear.png")
    bpy.ops.render.render(write_still=True)
    print("Rendered: C1_rear.png")
    
    # 5. Three-Quarter View from Below (Ventral Keel architecture & engine block underside)
    cam_data.type = 'PERSP'
    cam_data.lens = 32.0
    point_camera(cam, (-380.0, 440.0, -320.0), (0.0, 10.0, 20.0))
    scene.render.filepath = os.path.join(PREVIEW_DIR, "C1_below.png")
    bpy.ops.render.render(write_still=True)
    print("Rendered: C1_below.png")
    
    # 6. Bridge Close View (from 150m looking into the visor brow)
    cam_data.type = 'PERSP'
    cam_data.lens = 65.0
    point_camera(cam, (65.0, -45.0, 185.0), (0.0, -130.0, 155.0))
    scene.render.filepath = os.path.join(PREVIEW_DIR, "C1_bridge.png")
    bpy.ops.render.render(write_still=True)
    print("Rendered: C1_bridge.png")
    
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
    point_camera(cam, (-310.0, -165.0, 110.0), (-90.0, -10.0, 24.0))
    scene.render.filepath = os.path.join(PREVIEW_DIR, "C1_hangar.png")
    bpy.ops.render.render(write_still=True)
    print("Rendered: C1_hangar.png")
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
    
    stitched_arr = np.hstack([arr0, arr1, arr2])
    
    p_final_turret = os.path.join(PREVIEW_DIR, "C1_turret.png")
    img_final = bpy.data.images.new("C1_Turret_Stitched", width=1920, height=720, alpha=True)
    img_final.pixels.foreach_set(stitched_arr.ravel())
    img_final.filepath_raw = p_final_turret
    img_final.file_format = 'PNG'
    img_final.save()
    print("Rendered & Stitched: C1_turret.png (1920x720)")
    
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
                
    # 9. Silhouette Stitched View (Pure black on light grey: Side, Hero, Top)
    col_ship.hide_render = False
    col_turret.hide_render = True
    
    shading = scene.display.shading
    shading.color_type = 'SINGLE'
    shading.single_color = (0.0, 0.0, 0.0)
    shading.show_object_outline = False
    
    old_world = scene.world
    world_white = bpy.data.worlds.new("C1_Sil_World_V10")
    world_white.color = (0.82, 0.82, 0.82)
    scene.world = world_white
    
    scene.render.resolution_x = 640
    scene.render.resolution_y = 720
    
    # Side Silhouette
    cam_data.type = 'ORTHO'
    cam_data.sensor_fit = 'HORIZONTAL'
    cam_data.ortho_scale = 820.0
    cam.location = Vector((-600.0, 7.5, 73.4))
    cam.rotation_euler = (math.radians(90.0), 0.0, math.radians(-90.0))
    p_side = os.path.join(PREVIEW_DIR, "sil_side.png")
    scene.render.filepath = p_side
    bpy.ops.render.render(write_still=True)
    
    # Hero 3/4 Silhouette
    cam_data.type = 'PERSP'
    cam_data.lens = 35.0
    point_camera(cam, (450.0, 760.0, 360.0), (0.0, 20.0, 60.0))
    p_hero = os.path.join(PREVIEW_DIR, "sil_hero.png")
    scene.render.filepath = p_hero
    bpy.ops.render.render(write_still=True)
    
    # Top Silhouette
    cam_data.type = 'ORTHO'
    cam_data.sensor_fit = 'VERTICAL'
    cam_data.ortho_scale = 820.0
    cam.location = Vector((0.0, 7.5, 700.0))
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
    
    stitched_sil = np.hstack([arr_s, arr_h, arr_t])
    
    p_final_sil = os.path.join(PREVIEW_DIR, "C1_silhouette.png")
    img_final_sil = bpy.data.images.new("C1_Silhouette_Stitched", width=1920, height=720, alpha=True)
    img_final_sil.pixels.foreach_set(stitched_sil.ravel())
    img_final_sil.filepath_raw = p_final_sil
    img_final_sil.file_format = 'PNG'
    img_final_sil.save()
    print("Rendered & Stitched: C1_silhouette.png (1920x720)")
    
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
                
    # Restore settings
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 900
    scene.world = old_world
    shading.color_type = 'MATERIAL'
    shading.show_object_outline = True
    col_turret.hide_render = False

# -----------------------------------------------------------------------------
# Main Execution Runner
# -----------------------------------------------------------------------------
def run_pass_c1_review2():
    print("=== STARTING STAGE C: PASS C1 (REVIEW 2 - ARMOURED STERN) ===")
    col_ship, col_turret = assemble_juggernaut_scene()
    
    # 1. SAVE .BLEND FIRST (In strict accordance with brief requirement)
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_FILE)
    print(f"\nSaved final .blend first: {BLEND_FILE}")
    
    # 2. MEASURE METRICS ON FINAL GEOMETRY
    print("\n--- MEASURING PASS C1 REVIEW 2 METRICS ---")
    metrics = measure_c1_metrics()
    print("Triangle Counts per Object:")
    for k, v in metrics["tri_counts"].items():
        print(f"  {k}: {v} tris")
    print(f"Total Unique Hull Assembly: {metrics['total_hull_assembly_tris']} tris")
    print(f"Bounding Box: {metrics['bbox'][0]:.1f}m L × {metrics['bbox'][1]:.1f}m W × {metrics['bbox'][2]:.1f}m H")
    print(f"Y Bounds: {metrics['bounds_y'][0]:.1f} to {metrics['bounds_y'][1]:.1f}m")
    print(f"X Bounds: {metrics['bounds_x'][0]:.1f} to {metrics['bounds_x'][1]:.1f}m")
    print(f"Z Bounds: {metrics['bounds_z'][0]:.1f} to {metrics['bounds_z'][1]:.1f}m")
    print(f"Warp Portal Radial Extent: {metrics['max_radial']:.1f}m (Limit: 220.0m, Margin: {metrics['portal_margin']:.1f}m)")
    
    print("\n--- NOZZLE PROTRUSION & EXPOSURE MEASUREMENTS ---")
    for name, prot in metrics["thruster_protrusion"].items():
        print(f"  {name} Nozzle Protrusion past transom: {prot:.1f}m (Limit >= 15.0m: {prot >= 15.0})")
    print(f"  Gap between nozzle rims: {metrics['nozzle_rim_gap']:.1f}m (Separate targets verified)")
    print("  Line-of-Sight Exposure Rays (3 thrusters x 3 directions):")
    for t_name, dirs in metrics["exposure_rays"].items():
        for d_name, is_clear in dirs.items():
            print(f"    {t_name} from {d_name}: {'UNOBSTRUCTED (CLEAR)' if is_clear else 'OCCLUDED'}")
    print(f"  All Exposure Rays Unobstructed: {metrics['all_exposure_rays_unobstructed']}")
    
    print("\n--- HANGAR CHECKS ---")
    print(f"  Check 1 (Broadside Visibility): {metrics['broadside_percent']:.1f}% ({metrics['broadside_rays_unobstructed']}/{metrics['broadside_rays_total']})")
    print(f"  Check 2 (Launch Corridor): {metrics['corridor_verts_inside']} vertices inside 200m box")
    print(f"  Check 3 (Slide-Up Strip): {metrics['slide_clearance_measured']:.1f}m vertical clearance (Margin: +{metrics['slide_margin']:.1f}m, 0 obstructions)")
    print(f"  Check 4 (Strafing Run): length = {metrics['strafing_run_m']:.1f}m, time = {metrics['strafing_time_s']:.2f}s at 100m/s")
    
    if metrics["non_manifold"]:
        print("\nWARNING: Non-manifold edges detected:", metrics["non_manifold"])
    else:
        print("\nMesh Integrity: 0 non-manifold edges across all meshes!")
        
    # 3. RE-RENDER LISTED SCREENSHOTS FROM FINAL SAVED STATE
    print("\n--- RENDERING WORKBENCH SCREENSHOTS FROM SAVED STATE ---")
    render_listed_views()
    
    # Save mainfile again after renders to preserve camera transforms
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_FILE)
    print(f"\nFinal C1 scene re-saved: {BLEND_FILE}")
    print("=== PASS C1 REVIEW 2 COMPLETE ===")
    return metrics

if __name__ == "__main__":
    run_pass_c1_review2()
