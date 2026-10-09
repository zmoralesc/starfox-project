"""The landmarks' kit pieces (models/corneria/ASSETS.md, "Landmarks"): the
bay's monumental stone arches (Kit_Landmark_Arch) and the natural sea arch on
the big island's shore (Kit_Rock_Arch).

    KIT_OUT=<copy.blend> KIT_PREVIEW=<dir> blender --background --python kit_landmarks.py
    KIT_BAY_PREVIEW=<dir>  also renders three bay arches standing in the sea
                           as gen_landmarks.py stands them (scaled, one
                           stretched taller in deep water), seen from the
                           approach and from the air

Both pieces are gateways the player flies through along y, their span along
x, their origin at the centre of the footprint on the ground (the generator
sinks the feet 2 m into the sea bed). The bay arch is fitted to a size and
stretched up to 1.25x in height in deep water, so its round shapes are kept
to the arch's curve: the piers, plinths and beacon are plain boxes that
stretch cleanly. The gameplay opening is checked by casting rays through the
built geometry (opening_report()): the clear width at the base, the clear
height at the centre, and a flight through the whole required profile.

Bay arch: the opening is a wide, slightly flattened arch (a half ellipse,
rising 44 m over a 123 m span) on tall piers, so the gateway reads as mass
on legs rather than a hoop, and a 1.25x stretch only makes it rounder. One
closed shell is the two piers (open-topped prisms) and the ring between
them, cut into radial segments from springing to springing, so the piers'
top edges are the ring's first and last edges and nothing overlaps. The
plinth steps and the keystone block are separate shells sunk SINK into what
they stand on. The keystone is the beacon: a Cream block standing proud of
the ring's faces and above its crown, a LightStrip band round its top.
Everything else is paint: Cream base and impost bands on the piers, a Cream
cornice on the plinths, and two LightStrip bands running the length of the
extrados from shoulder to shoulder.

Rock arch: a faceted tube (kit_nature's lump(): jittered rings joined by
triangle bands) bent along a spine of hand-placed stations: up the left leg,
over an uneven hump-shouldered arc, down the right leg. Each ring lies
across the spine's tangent, so the tube's bands are collars round the arch;
the jitter only ever moves the inside of the bend inwards into the rock, so
the opening is as the stations say. The legs carry a Stone stratum at the
same height on both sides and the faces that look up over the crown are
TreeLight grass.
"""

import math
import os
import random
import sys

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit_tools as kt  # noqa: E402
from kit_tools import Builder  # noqa: E402

SINK = 0.2                        # a part sinks this far into the one it stands on

# --- Kit_Landmark_Arch: the bay's gateways (170 x 120 x 26, 3,000 tris) -----------------------
ARCH_W, ARCH_H = 170.0, 120.0     # nominal size (ASSETS.md); the opening must be 0.70 w x 0.72 h
PLINTH_IN = 59.8                  # the plinths' inner edge: the clear width at the base is twice this
PLINTH_OUT = 85.0                 # ...and their outer edge: half the width
PLINTH_HD = 13.0                  # half the lower step's depth: half the piece's
STEP_Z = (10.0, 20.0)             # the plinth's two steps' tops
CORNICE = 1.5                     # the Cream band at the top of the upper step
PIER_IN, PIER_OUT = 61.5, 83.0    # the piers' inner and outer faces: the opening above the plinths is 123 m
PIER_HD = 11.0                    # half the piers' and ring's depth
SPRING_Z = 44.0                   # the springing: the opening's curve starts here
RISE = 44.0                       # ...and rises this far to the crown (the opening's top is a half ellipse)
BASE_BAND, IMPOST = 3.0, 4.5      # the Cream bands at the foot and top of each pier are this tall
THICK = 26.0                      # the ring's thickness at the crown (the extrados is the opening's ellipse grown by it)
SEGMENTS = 36                     # radial segments from springing to springing (5 degrees each)
KEYSTONE = (85.0, 95.0)           # the angles between which the ring is painted Cream (the keystone, under its block)
LIGHT_W = 3.0                     # the LightStrip bands along the extrados' edges are this wide
KEY_BLOCK = ((8.0, 92.0), (10.8, 118.0), (11.0, ARCH_H))   # the keystone block's profile: (half width, z), bottom to top
KEY_HD = 12.5                     # ...half its depth: proud of the ring's faces

# --- Kit_Rock_Arch: the natural arch (110 x 70 x 22, 1,500 tris) ------------------------------
ROCK_SIDES = 10                   # points round each ring of the tube
ROCK_JITTER = 0.16                # kit_nature's rock jitter (inwards only on the inside of the bend)
ROCK_WOBBLE = 0.15                # ring points slide along the spine by up to this share of the radius
# The spine: (x, z, radius across the spine in the x-z plane, radius along y)
# from the left foot up and over to the right foot. The left leg is the bulky
# one and springs higher, the hump on its shoulder breaks the symmetry; the
# legs bulge at the stratum and narrow under the springings.
ROCK_SPINE = [
    (-48.5, 0.0, 9.6, 11.0), (-48.5, 8.0, 10.2, 11.0), (-48.0, 14.5, 10.0, 10.8), (-47.0, 24.0, 8.8, 10.4),
    (-45.0, 34.0, 8.8, 10.0),                                                   # the left springing
    (-39.5, 47.0, 9.6, 10.6), (-27.0, 57.5, 8.4, 9.8), (-10.0, 62.0, 7.4, 9.2),   # the hump, the crown
    (8.0, 61.0, 7.0, 9.0), (24.0, 54.5, 7.2, 9.4), (37.0, 43.0, 7.6, 9.8), (44.0, 31.0, 7.8, 10.2),
    (46.5, 23.0, 8.2, 10.4),                                                    # the right springing
    (46.8, 14.5, 9.2, 10.8), (47.0, 8.0, 9.4, 11.0), (47.0, 0.0, 8.8, 11.0),    # (the last two in line: a flat foot)
]
ROCK_STRATA = (1, 13)             # bands painted Stone: between the 8.5 and 14.5 m stations of each leg
ROCK_GRASS = range(5, 10)         # bands over the top that carry grass...
ROCK_TOP_K = (1, 2, 3)            # ...on the faces that look up (the ring's points 36 degrees apart: 36-144)


# --- Builder helpers ------------------------------------------------------------------------
def mirrored(side):
    """The transform for a pier: as built for side 1 (right, +x) or 1-in-x
    mirrored for side -1 (left)."""
    return Matrix.Diagonal((side, 1.0, 1.0, 1.0))


def tube_ring(p, t, rv, ry, n, seed, jitter=0.0, wobble=0.0):
    """n points round spine point `p` in the plane across the tangent `t`:
    `ry` along y, `rv` across it in the x-z plane (its +side is t x y: the
    outside of a bend, up over the crown). Jittered like kit_nature.ring(),
    except that points on the inside of the bend only ever move inwards
    (the opening is gameplay); `wobble` slides each point along the tangent
    by up to that share of rv."""
    rng = random.Random(seed)
    u = Vector((0.0, 1.0, 0.0))
    v = t.cross(u).normalized()
    pts = []
    for k in range(n):
        a = 2.0 * math.pi * (k + rng.uniform(-0.35, 0.35) * jitter) / n
        s = 1.0 + rng.uniform(-1.0, 1.0) * jitter
        if math.sin(a) < 0.0:
            s = min(s, 1.0)
        q = p + u * (ry * s * math.cos(a)) + v * (rv * s * math.sin(a)) + t * (rng.uniform(-1.0, 1.0) * wobble * rv)
        pts.append(tuple(q))
    return pts


def lump(b, rings, mat, paint=None, tri=True):
    """A closed faceted body through `rings` (kit_nature.lump(), flat caps):
    a band of two triangles per quad between each pair of rings, closed by a
    flat cap at each end. paint(band, k) -> a band's k-th face's material."""
    n = len(rings[0])
    for i in range(len(rings) - 1):
        lo, hi = rings[i], rings[i + 1]
        for k in range(n):
            k1 = (k + 1) % n
            m = (paint(i, k) if paint else None) or mat
            quad = [lo[k], lo[k1], hi[k1], hi[k]]
            if not tri:
                b.face(quad, m)
            elif (i + k) % 2 == 0:
                b.face(quad[:3], m)
                b.face([quad[0], quad[2], quad[3]], m)
            else:
                b.face([quad[0], quad[1], quad[3]], m)
                b.face(quad[1:], m)
    b.face(rings[0][::-1], mat)
    b.face(rings[-1], mat)


# --- Kit_Landmark_Arch ----------------------------------------------------------------------
def shoulder_angle():
    """The parametric angle at which the extrados ellipse crosses the piers'
    outer faces: the shoulders, where the ring leaves the piers."""
    return math.acos(PIER_OUT / (PIER_IN + THICK))


def ring_stations():
    """The ring's stations, parametric angles from 0 (the right springing)
    to pi (the left): SEGMENTS even steps plus the two shoulders, so the
    silhouette has its corner there."""
    angles = {round(math.pi * i / SEGMENTS, 6) for i in range(SEGMENTS + 1)}
    for a in (shoulder_angle(), math.pi - shoulder_angle()):
        if all(abs(a - other) > math.radians(0.5) for other in angles):
            angles.add(round(a, 6))
    return sorted(angles)


def ring_point(a):
    """The ring's intrados and extrados points (x, z) at parametric angle
    `a`. The intrados is the opening's half ellipse (PIER_IN by RISE about
    the springing centre); the extrados the same grown by THICK, clipped to
    the piers' outer faces: below the shoulders it runs straight down them
    (stations spread evenly down the face)."""
    inner = (PIER_IN * math.cos(a), SPRING_Z + RISE * math.sin(a))
    ao, bo = PIER_IN + THICK, RISE + THICK
    shoulder = shoulder_angle()
    if abs(ao * math.cos(a)) > PIER_OUT:
        rise = (RISE + THICK) * math.sin(shoulder) * min(a, math.pi - a) / shoulder
        outer = (math.copysign(PIER_OUT, math.cos(a)), SPRING_Z + rise)
    else:
        outer = (ao * math.cos(a), SPRING_Z + bo * math.sin(a))
    return inner, outer


def pier(b, side):
    """A pier (side 1 right, -1 left): an open-topped prism from inside the
    plinth's upper step to the springing, its outer face cut at the light
    bands' lines (the extrados strips above share those edges), a Cream
    band painted at its foot and IMPOST metres of Cream at its top."""
    outline = [(PIER_IN, -PIER_HD), (PIER_OUT, -PIER_HD), (PIER_OUT, PIER_HD), (PIER_IN, PIER_HD)]
    cut = LIGHT_W / (2 * PIER_HD)
    with b.at(mirrored(side)):
        b.prism(outline, STEP_Z[1] - SINK, SPRING_Z, "Stone", levels=[STEP_Z[1] + BASE_BAND, SPRING_Z - IMPOST],
                top=False, columns=lambda s, length: [cut, 1.0 - cut] if s == 1 else [],
                cell=lambda s, c, r, u, z: "Cream" if r != 1 else None)


def plinth(b, side):
    """A pier's stepped plinth: a Concrete lower step, a Stone upper step
    with a Cream cornice band, each proud of what stands on it all round."""
    with b.at(mirrored(side)):
        b.box(PLINTH_IN, -PLINTH_HD, 0.0, PLINTH_OUT, PLINTH_HD, STEP_Z[0], "Concrete")
        b.box(PLINTH_IN + 1.0, -PLINTH_HD + 1.0, STEP_Z[0] - SINK, PLINTH_OUT - 1.0, PLINTH_HD - 1.0, STEP_Z[1],
              "Stone", levels=[STEP_Z[1] - CORNICE], cell=lambda s, c, r, u, z: "Cream" if r == 1 else None)


def ring(b):
    """The arch between the springings: a radial segment between each pair
    of stations, each a front and back face, an intrados face and three
    extrados strips (the outer two LightStrip from the shoulders over the
    crown). The keystone's segments are Cream on every face. The curved
    faces are smooth-shaded."""
    ys = [-PIER_HD, -PIER_HD + LIGHT_W, PIER_HD - LIGHT_W, PIER_HD]
    stations = ring_stations()
    shoulder = shoulder_angle()
    for a0, a1 in zip(stations, stations[1:]):
        in0, out0 = ring_point(a0)
        in1, out1 = ring_point(a1)
        mid = math.degrees((a0 + a1) / 2)
        stone = "Cream" if KEYSTONE[0] <= mid <= KEYSTONE[1] else "Stone"
        lit = shoulder - 1e-6 <= a0 and a1 <= math.pi - shoulder + 1e-6
        for y, flip in ((-PIER_HD, False), (PIER_HD, True)):
            quad = [(in0[0], y, in0[1]), (in1[0], y, in1[1]), (out1[0], y, out1[1]), (out0[0], y, out0[1])]
            b.face(quad[::-1] if flip else quad, stone)
        b.face([(in0[0], -PIER_HD, in0[1]), (in0[0], PIER_HD, in0[1]), (in1[0], PIER_HD, in1[1]),
                (in1[0], -PIER_HD, in1[1])], stone, True)
        for j in range(3):
            m = "LightStrip" if lit and j != 1 else stone
            b.face([(out0[0], ys[j], out0[1]), (out1[0], ys[j], out1[1]), (out1[0], ys[j + 1], out1[1]),
                    (out0[0], ys[j + 1], out0[1])], m, True)


def keystone(b):
    """The keystone block, the arch's beacon: a Cream wedge (KEY_BLOCK's
    profile, widening upwards) through the crown, its bottom sunk in the
    ring and its faces proud of the ring's, with a LightStrip band round
    its top and a lit top face: seen head-on down the whole approach."""
    (w0, z0), (w1, z1), (w2, z2) = KEY_BLOCK
    for y, flip in ((-KEY_HD, False), (KEY_HD, True)):   # front and back: the wedge, then the lit band
        body = [(-w0, y, z0), (w0, y, z0), (w1, y, z1), (-w1, y, z1)]
        band = [(-w1, y, z1), (w1, y, z1), (w2, y, z2), (-w2, y, z2)]
        b.face(body[::-1] if flip else body, "Cream")
        b.face(band[::-1] if flip else band, "LightStrip")
    for side in (1, -1):                                   # the sloping sides, in two bands
        b.face([(side * w0, -KEY_HD, z0), (side * w0, KEY_HD, z0), (side * w1, KEY_HD, z1), (side * w1, -KEY_HD, z1)],
               "Cream")
        b.face([(side * w1, -KEY_HD, z1), (side * w1, KEY_HD, z1), (side * w2, KEY_HD, z2), (side * w2, -KEY_HD, z2)],
               "LightStrip")
    b.face([(-w2, -KEY_HD, z2), (w2, -KEY_HD, z2), (w2, KEY_HD, z2), (-w2, KEY_HD, z2)], "LightStrip")
    b.face([(-w0, KEY_HD, z0), (w0, KEY_HD, z0), (w0, -KEY_HD, z0), (-w0, -KEY_HD, z0)], "Cream")


def landmark_arch():
    """The bay's gateway: piers and ring as one shell, the plinths and the
    keystone block as their own."""
    b = Builder()
    for side in (1, -1):
        plinth(b, side)
        pier(b, side)
    ring(b)
    keystone(b)
    return [("", b)]


# --- Kit_Rock_Arch --------------------------------------------------------------------------
def rock_arch():
    """The natural arch: one faceted tube along ROCK_SPINE, its rings across
    the spine's tangent (central differences; the feet vertical, so their
    caps lie flat on the ground), strata on the legs, grass over the top."""
    b = Builder()
    pts = [Vector((x, 0.0, z)) for x, z, _, _ in ROCK_SPINE]
    rings = []
    for i, (x, z, rv, ry) in enumerate(ROCK_SPINE):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        foot = i in (0, len(pts) - 1)
        rings.append(tube_ring(pts[i], t, rv, ry, ROCK_SIDES, seed=100 + i, jitter=ROCK_JITTER,
                               wobble=0.0 if foot else ROCK_WOBBLE))

    def paint(band, k):
        if band in ROCK_STRATA:
            return "Stone"
        if band in ROCK_GRASS and k in ROCK_TOP_K:
            return "TreeLight"
        return None
    lump(b, rings, "Rock", paint=paint)
    return [("", b)]


# --- The opening check ----------------------------------------------------------------------
def opening_report(name, builders, profile, flight_hd):
    """Casts rays through the piece's geometry: the clear width at the
    base (1 m up, from the centre out to each side), the clear height at the
    centre (up from the ground), and a flight along y through every point
    of a 2 m grid inside `profile`(x, z) -> bool, the opening the game needs.
    Prints them as fractions of the piece's width and height."""
    verts, tris = [], []
    for _, b in builders:
        base = len(verts)
        verts += [tuple(v) for v in b.verts]
        for idx, _, _ in b.faces:                 # every face here is convex: a fan triangulates it
            for i in range(1, len(idx) - 1):
                tris.append((base + idx[0], base + idx[i], base + idx[i + 1]))
    bvh = BVHTree.FromPolygons(verts, tris, all_triangles=True)
    width = max(v[0] for v in verts) - min(v[0] for v in verts)
    height = max(v[2] for v in verts) - min(v[2] for v in verts)

    def reach(origin, direction):
        hit = bvh.ray_cast(Vector(origin), Vector(direction), 1000.0)
        return hit[3] if hit[0] is not None else math.inf
    clear_w = reach((0.0, 0.0, 1.0), (1.0, 0.0, 0.0)) + reach((0.0, 0.0, 1.0), (-1.0, 0.0, 0.0))
    clear_h = reach((0.0, 0.0, 0.0), (0.0, 0.0, 1.0))
    samples, blocked = 0, []
    for ix in range(-int(width / 4), int(width / 4) + 1):
        for iz in range(0, int(height / 2) + 1):
            x, z = ix * 2.0, iz * 2.0 + 0.5
            if not profile(x, z):
                continue
            samples += 1
            if reach((x, -flight_hd - 50.0, z), (0.0, 1.0, 0.0)) < 2 * flight_hd + 100.0:
                blocked.append((x, z))
    print("  %s opening: clear width at the base %.1f m (%.3f x width), clear height at the centre %.1f m "
          "(%.3f x height), %d of %d flight samples blocked%s" % (
              name, clear_w, clear_w / width, clear_h, clear_h / height, len(blocked), samples,
              " at " + ", ".join("(%.0f, %.0f)" % p for p in blocked[:8]) if blocked else ""))


def arch_profile(x, z):
    """The gateway the game needs (gen_landmarks.py): 0.70 w wide and 0.72 h
    high with a round top (a semicircle of 0.35 w)."""
    r = 0.35 * ARCH_W
    zs = 0.72 * ARCH_H - r
    return abs(x) <= r and (z <= zs or x * x + (z - zs) ** 2 <= r * r)


def rock_profile(x, z):
    """The natural arch's: 75 wide, 50 high at the centre, with a round top
    (a half ellipse from 20 m up)."""
    return abs(x) <= 37.5 and (z <= 20.0 or (x / 37.5) ** 2 + ((z - 20.0) / 30.0) ** 2 <= 1.0)


# --- Previews from the bay --------------------------------------------------------------------
def stand(scene, name, at, turn, scale):
    """An instance of kit piece `name` in `scene` at `at`, turned `turn`
    radians about Z and scaled (x, y, z)."""
    col = bpy.data.collections[name]
    inst = bpy.data.objects.new(name, None)
    inst.instance_type = "COLLECTION"
    inst.instance_collection = col
    inst.matrix_world = (Matrix.Translation(at) @ Matrix.Rotation(turn, 4, "Z")
                         @ Matrix.Diagonal((scale[0], scale[1], scale[2], 1.0)))
    scene.collection.objects.link(inst)
    return inst


def sea(scene, half):
    """A square of sea `half` out from the origin at z = 0."""
    b = Builder()
    b.face([(-half, -half, 0.0), (half, -half, 0.0), (half, half, 0.0), (-half, half, 0.0)], "Water")
    scene.collection.objects.link(b.object("Sea"))


def render(scene, eye, target, path, size=(1280, 720), lens=35):
    """Renders `scene` (Workbench, palette colours, outlines, shadows) from `eye` towards `target`."""
    cam_data = bpy.data.cameras.new("BayCam")
    cam_data.lens = lens
    cam_data.clip_end = 8000.0
    cam = bpy.data.objects.new("BayCam", cam_data)
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
    shading.show_shadows = True
    shading.shadow_intensity = 0.6
    shading.show_cavity = False
    scene.render.resolution_x, scene.render.resolution_y = size
    world = bpy.data.worlds.new("BayWorld")
    world.color = (0.55, 0.65, 0.8)
    scene.world = world
    cam.location = Vector(eye)
    cam.rotation_euler = (Vector(target) - Vector(eye)).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True, scene=scene.name)
    bpy.data.objects.remove(cam)
    bpy.data.cameras.remove(cam_data)
    bpy.data.worlds.remove(world)


def bay_previews(out):
    """Three bay arches 550 m apart along the approach, each scaled and
    turned a little as gen_landmarks.py does, their feet on beds 10, 30 and
    14 m down (the middle one in deep water: stretched 1.25x in height), and
    the rock arch off to one side; seen low from 600 m back on the approach,
    from 300 m up, and close from a pilot's seat."""
    os.makedirs(out, exist_ok=True)
    scene = bpy.data.scenes.new("Bay")
    sea(scene, 4000.0)
    for y, bed, s, tall, turn in ((0.0, -10.0, 1.0, 1.0, 0.1), (550.0, -30.0, 0.95, 1.25, -0.08),
                                  (1100.0, -14.0, 1.07, 1.0, 0.05)):
        stand(scene, "Kit_Landmark_Arch", (0.0, y, bed - 2.0), turn, (s, s, s * tall))
    stand(scene, "Kit_Rock_Arch", (-420.0, 700.0, -4.0), math.pi / 2 + 0.3, (1.0, 1.0, 1.0))
    render(scene, (40.0, -600.0, 45.0), (0.0, 300.0, 70.0), os.path.join(out, "bay_approach.png"))
    render(scene, (260.0, -500.0, 300.0), (-40.0, 500.0, 0.0), os.path.join(out, "bay_high.png"))
    render(scene, (-60.0, -180.0, 60.0), (10.0, 0.0, 70.0), os.path.join(out, "bay_close.png"))
    render(scene, (-420.0, 420.0, 40.0), (-420.0, 700.0, 35.0), os.path.join(out, "bay_rock_arch.png"))
    bpy.data.scenes.remove(scene)
    print("bay previews in " + out)


# --- The batch --------------------------------------------------------------------------------
PIECES = [("Kit_Landmark_Arch", landmark_arch, arch_profile, PIER_HD),
          ("Kit_Rock_Arch", rock_arch, rock_profile, 11.0)]


def main():
    kt.begin("kit_landmarks", 6)
    for name, build, profile, hd in PIECES:
        builders = build()
        if kt.piece(name, builders) is not None:
            opening_report(name, builders, profile, hd)
    kt.finish()
    if os.environ.get("KIT_BAY_PREVIEW"):
        bay_previews(os.environ["KIT_BAY_PREVIEW"])


if __name__ == "__main__":
    main()
